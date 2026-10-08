"""python -m ingest {run,seed-company,stats}"""

import json
import logging
from pathlib import Path

import typer
from sqlalchemy import func, select

from app.config import get_settings
from db.models import DocumentRow, IngestRunRow, OpportunityRow
from db.session import make_engine, make_session_factory
from ingest.company import seed_company
from ingest.http import build_client, download
from ingest.pipeline import run_ingest
from ingest.sources.grants_gov import GrantsGovAdapter
from ingest.sources.sam_gov import SamGovAdapter
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
    logging.basicConfig(level=logging.INFO)
    s = get_settings()
    with build_client() as client, _session() as session:
        if source == "grants_gov":
            if s.simpler_grants_api_key is None:
                raise typer.BadParameter("SIMPLER_GRANTS_API_KEY is not set")
            adapter = GrantsGovAdapter(
                client, s.simpler_grants_api_key.get_secret_value()
            )
        elif source == "sam_gov":
            adapter = SamBulkAdapter(client, cache_path=Path("data/cache/sam_full.csv"))
        elif source == "sam_gov_api":
            if s.sam_api_key is None:
                raise typer.BadParameter("SAM_API_KEY is not set")
            adapter = SamGovAdapter(
                client,
                s.sam_api_key.get_secret_value(),
                request_budget=s.sam_daily_request_budget,
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
            blob_store_from_root(s.blob_root),
            fetch,
            limit=limit,
            download_attachments=attachments,
        )
    typer.echo(
        json.dumps({k: v for k, v in stats.__dict__.items() if k != "errors"}, indent=2)
    )
    for e in stats.errors[:20]:
        typer.echo(f"error: {e}", err=True)


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


if __name__ == "__main__":
    cli()
