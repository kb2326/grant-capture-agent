"""python -m ingest {run,seed-company,stats}"""

import json
from datetime import date
from pathlib import Path
from typing import Annotated

import typer
from sqlalchemy import func, select

from app.config import get_settings
from db.models import DocumentRow, IngestRunRow, OpportunityRow
from db.session import make_engine, make_session_factory
from ingest.company import seed_company
from ingest.http import build_client, download
from ingest.logging_setup import configure_logging
from ingest.pipeline import run_ingest
from ingest.raw import RawArchive, ReplayAdapter, replay_grants_gov, replay_sam_bulk
from ingest.sources.grants_gov import GrantsGovAdapter
from ingest.sources.sam_gov import SamGovAdapter, SamQuota
from ingest.sources.sam_gov_bulk import SamBulkAdapter
from ingest.storage import blob_store_from_root

cli = typer.Typer(no_args_is_help=True)


def _session():
    return make_session_factory(make_engine(get_settings().database_url))()


@cli.command()
def run(
    source: str = typer.Option(
        ..., help="grants_gov, sam_gov (daily bulk extract) or sam_gov_api"
    ),
    limit: int | None = typer.Option(None),
    attachments: bool = typer.Option(True),
) -> None:
    configure_logging()
    s = get_settings()
    store = blob_store_from_root(s.blob_root)
    archive = RawArchive(store, source, date.today())
    with build_client() as client, _session() as session:
        if source == "grants_gov":
            if s.simpler_grants_api_key is None:
                raise typer.BadParameter("SIMPLER_GRANTS_API_KEY is not set")
            adapter = GrantsGovAdapter(
                client, s.simpler_grants_api_key.get_secret_value(), archive=archive
            )
        elif source == "sam_gov":
            adapter = SamBulkAdapter(
                client, cache_path=Path("data/cache/sam_full.csv"), archive=archive
            )
        elif source == "sam_gov_api":
            if s.sam_api_key is None:
                raise typer.BadParameter("SAM_API_KEY is not set")
            adapter = SamGovAdapter(
                client,
                s.sam_api_key.get_secret_value(),
                request_budget=s.sam_daily_request_budget,
                quota=SamQuota(store, date.today()),
                archive=archive,
            )
        else:
            raise typer.BadParameter(f"unknown source {source!r}")

        def fetch(url: str) -> bytes | None:
            return download(client, url, max_bytes=s.max_attachment_bytes)

        if source == "sam_gov_api" and attachments:
            # SAM attachment downloads may count against the ~10 requests/day key quota.
            # Links are kept in raw/customFields; M1's Analyze agent fetches them on demand.
            typer.echo(
                "sam_gov: attachment download deferred to on-demand (quota)", err=True
            )
            attachments = False
        stats = run_ingest(
            adapter,
            session,
            store,
            fetch,
            limit=limit,
            download_attachments=attachments,
        )
    typer.echo(
        json.dumps({k: v for k, v in stats.__dict__.items() if k != "errors"}, indent=2)
    )
    for e in stats.errors[:20]:
        typer.echo(f"error: {e}", err=True)
    for issue in stats.quality_issues:
        typer.echo(
            f"quality {issue['severity']}: {issue['check']} - {issue['message']}",
            err=True,
        )
    if any(i["severity"] == "error" for i in stats.quality_issues):
        raise typer.Exit(code=1)


@cli.command()
def replay(
    source: str = typer.Option(..., help="grants_gov or sam_gov"),
    day: str = typer.Option(..., "--date", help="YYYY-MM-DD of the archived run"),
) -> None:
    """Rebuild opportunities from the raw zone without calling any API."""
    s = get_settings()
    store = blob_store_from_root(s.blob_root)
    archive = RawArchive(store, source, date.fromisoformat(day))
    factories = {
        "grants_gov": ("grants_gov/1", lambda: replay_grants_gov(archive)),
        "sam_gov": ("sam_gov/1", lambda: replay_sam_bulk(archive)),
    }
    if source not in factories:
        raise typer.BadParameter(f"unknown source {source!r}")
    version, factory = factories[source]
    with _session() as session:
        stats = run_ingest(
            ReplayAdapter(source, version, factory),
            session,
            store,
            fetch=lambda url: None,
            download_attachments=False,
        )
    typer.echo(
        json.dumps({k: v for k, v in stats.__dict__.items() if k != "errors"}, indent=2)
    )
    for issue in stats.quality_issues:
        typer.echo(
            f"quality {issue['severity']}: {issue['check']} - {issue['message']}",
            err=True,
        )
    if any(i["severity"] == "error" for i in stats.quality_issues):
        raise typer.Exit(code=1)


@cli.command("seed-company")
def seed(profile: Path = Path("data/company/profile.json")) -> None:
    with _session() as session:
        typer.echo(f"company id: {seed_company(session, profile)}")


@cli.command()
def stats() -> None:
    with _session() as session:
        by_source = session.execute(
            select(OpportunityRow.source, OpportunityRow.status, func.count()).group_by(
                OpportunityRow.source, OpportunityRow.status
            )
        ).all()
        docs = session.scalar(select(func.count()).select_from(DocumentRow))
        opps_with_docs = session.scalar(
            select(func.count(func.distinct(DocumentRow.opportunity_id)))
        )
        last = session.scalar(
            select(IngestRunRow).order_by(IngestRunRow.started_at.desc()).limit(1)
        )
    for src, status, n in by_source:
        typer.echo(f"{src:12} {status:11} {n}")
    typer.echo(f"documents: {docs}  opportunities with documents: {opps_with_docs}")
    if last:
        typer.echo(
            f"last run: {last.started_at:%Y-%m-%d %H:%M} {last.stats.get('source')}"
        )


@cli.command()
def parse(
    limit: int | None = typer.Option(None), opportunity: str | None = typer.Option(None)
) -> None:
    """Build the page-tagged text layer for pending documents."""
    import uuid as _uuid

    from ingest.parsing import parse_documents
    from ingest.storage import read_uri

    with _session() as session:
        stats = parse_documents(
            session,
            read_uri,
            limit=limit,
            opportunity_id=_uuid.UUID(opportunity) if opportunity else None,
        )
    typer.echo(json.dumps(stats, indent=2))


@cli.command("sam-attachments")
def sam_attachments(
    notice: Annotated[list[str], typer.Option(help="SAM notice IDs (repeatable)")],
) -> None:
    """Fetch attachments for specific SAM.gov notices (uses the daily API quota)."""
    configure_logging()
    s = get_settings()
    if s.sam_api_key is None:
        raise typer.BadParameter("SAM_API_KEY is not set")
    store = blob_store_from_root(s.blob_root)
    from ingest.sam_attachments import attach_sam_documents

    with build_client() as client, _session() as session:
        adapter = SamGovAdapter(
            client,
            s.sam_api_key.get_secret_value(),
            request_budget=s.sam_daily_request_budget,
            quota=SamQuota(store, date.today()),
            archive=RawArchive(store, "sam_gov_api", date.today()),
        )
        stats = attach_sam_documents(
            session, adapter, client, store, notice, max_bytes=s.max_attachment_bytes
        )
    typer.echo(json.dumps(stats, indent=2))


if __name__ == "__main__":
    cli()
