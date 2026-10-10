"""Company corpus for M3 Draft: plan, ground-truth checks, generation and loading (M3 spec §3.1-3.2)."""

import argparse
import hashlib
import json
import re
from pathlib import Path

from pydantic import BaseModel
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from db.models import ChunkRow, DocumentRow
from ingest.storage import BlobStore, safe_key

BANNER = "> Synthetic document for grant-capture-agent evaluation. All people, numbers and results are fictional."
GAP_TERMS = [
    "hydrogen",
    "cyber",
    "offshore",
    "phase iii",
    "cmmc",
    "800-171",
    "salt fog",
    "electrolyzer",
    "fuel cell",
]
# superseded values: allowed only in outdated docs
DENY_ON_TOPIC = [
    "18 employees",
    "12 employees",
    "LGL-BMS2",
    "LGL-BMS1",
    "900 sq ft",
    "plus or minus 5 mV",
    "HelioLink 100",
    "96.5%",
    "NFPA 70E-2018",
    "Boulder Valley Energy",
]


def load_plan(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def kinds(plan: dict) -> dict[str, str]:
    out = dict.fromkeys(plan["originals"], "on_topic")
    out.update({e["file"]: e["kind"] for e in plan["new"]})
    return out


def check_doc(text: str, entry: dict) -> list[str]:
    problems = []
    if not text.startswith(BANNER):
        problems.append(f"{entry['file']}: missing synthetic-data banner")
    problems += [
        f"{entry['file']}: missing phrase {p!r}"
        for p in entry.get("phrases", [])
        if p not in text
    ]
    low = text.lower()
    problems += [
        f"{entry['file']}: mentions gap term {t!r}" for t in GAP_TERMS if t in low
    ]
    if entry["kind"] == "on_topic":
        problems += [
            f"{entry['file']}: outdated value {d!r}" for d in DENY_ON_TOPIC if d in text
        ]
    return problems


def check_corpus(docs_dir: Path, plan: dict) -> list[str]:
    entries = [
        {"file": f, "kind": "on_topic", "phrases": []} for f in plan["originals"]
    ] + plan["new"]
    problems: list[str] = []
    for e in entries:
        path = docs_dir / e["file"]
        if path.exists():  # not yet generated files are skipped
            problems += check_doc(path.read_text(encoding="utf-8"), e)
    return problems


def load_tasks(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def check_tasks(tasks: list[dict], plan: dict, docs_dir: Path) -> list[str]:
    """Evidence phrases must be promised by the plan or present in an original; gap terms must be banned."""
    k = kinds(plan)
    promised = [p for e in plan["new"] if e["kind"] == "on_topic" for p in e["phrases"]]
    originals = "\n".join(
        (docs_dir / f).read_text(encoding="utf-8") for f in plan["originals"]
    )
    problems = []
    for t in tasks:
        for r in t["requirements"]:
            if "evidence" in r:
                if not any(p in promised or p in originals for p in r["evidence"]):
                    problems.append(
                        f"{t['id']}/{r['id']}: no on-topic source for {r['evidence']}"
                    )
            elif not r.get("gap_terms") or not all(
                g.lower() in GAP_TERMS for g in r["gap_terms"]
            ):
                problems.append(
                    f"{t['id']}/{r['id']}: gap terms must all be in GAP_TERMS"
                )
    if len(k) != len(plan["originals"]) + len(plan["new"]):
        problems.append("duplicate file names in the corpus plan")
    return problems


class DocText(BaseModel):
    markdown: str


KIND_GUIDE = {
    "on_topic": "It is current (2024-2025) and must agree with every fact in the facts table.",
    "outdated": "It is an OLD document from the year in its title. State that year near the top. Its numbers are the old ones it was written with.",
    "off_topic": "It is an ordinary internal company document that has nothing to do with proposals or technology.",
}


def doc_prompt(entry: dict, facts_table: str) -> str:
    phrases = "\n".join(f"- {p}" for p in entry["phrases"]) or "- (none)"
    return (
        "You write one internal document for Lumen Grid Labs, a fictional small R&D company. Plain English, "
        "concrete numbers, Markdown with a # title and ## headings, 300-700 words.\n"
        f"The first line must be exactly:\n{BANNER}\n\n"
        f"Company facts table (authoritative for current documents):\n{facts_table}\n\n"
        f"Document: {entry['title']}\nWhat it covers: {entry['brief']}\n{KIND_GUIDE[entry['kind']]}\n"
        f"It must contain each of these phrases exactly as written:\n{phrases}\n"
        "Never mention hydrogen, fuel cells, electrolyzers, cybersecurity or anything cyber, offshore wind, "
        "salt fog, CMMC, NIST 800-171 or Phase III. Contact details may only use @example.com emails and "
        "555-01xx phone numbers. Return the document as `markdown`."
    )


def generate_missing(
    plan: dict,
    docs_dir: Path,
    llm,
    facts_table: str,
    *,
    price_in_per_m: float,
    price_out_per_m: float,
    max_usd: float,
) -> dict:
    stats: dict = {
        "written": 0,
        "skipped": 0,
        "failed": 0,
        "cost_usd": 0.0,
        "stopped": None,
    }
    in0, out0 = llm.total_tokens_in, llm.total_tokens_out

    def spent() -> float:
        return (
            (llm.total_tokens_in - in0) * price_in_per_m
            + (llm.total_tokens_out - out0) * price_out_per_m
        ) / 1e6

    for entry in plan["new"]:
        path = docs_dir / entry["file"]
        if path.exists():  # never overwrite
            stats["skipped"] += 1
            continue
        if spent() >= max_usd:
            stats["stopped"] = "budget"
            break
        prompt, problems = doc_prompt(entry, facts_table), ["not generated"]
        for _ in range(2):  # one retry, told what was wrong
            text = llm.generate(
                DocText,
                prompt,
                "Write the document."
                if problems == ["not generated"]
                else "Fix these problems: " + "; ".join(problems),
            ).markdown.strip()
            problems = check_doc(text, entry)
            if not problems:
                path.write_text(text + "\n", encoding="utf-8", newline="\n")
                stats["written"] += 1
                break
        else:
            stats["failed"] += 1
        stats["cost_usd"] = spent()
    return stats


_HEADING = re.compile(r"^(#{1,3})\s+(.*)$", re.M)


def chunk_markdown(
    text: str, title: str, max_chars: int = 3200, min_chars: int = 320
) -> list[tuple[str, str]]:
    """Split on ## / ### headings; merge sections under min_chars into the next; split long ones on paragraphs."""
    body = "\n".join(
        line for line in text.splitlines() if not line.startswith(BANNER[:20])
    )
    parts: list[tuple[str, str]] = []
    marks = list(_HEADING.finditer(body))
    for i, m in enumerate(marks):
        if len(m.group(1)) == 1:  # the document title
            continue
        end = marks[i + 1].start() if i + 1 < len(marks) else len(body)
        parts.append((f"{title} > {m.group(2).strip()}", body[m.end() : end].strip()))
    if not parts:
        parts = [(title, body.strip())]
    merged: list[tuple[str, str]] = []
    carry = ""
    for path, txt in parts:
        txt = (carry + "\n\n" + txt).strip() if carry else txt
        if len(txt) < min_chars and path is not parts[-1][0]:
            carry = txt
            continue
        carry = ""
        merged.append((path, txt))
    if carry:
        merged.append((parts[-1][0], carry))
    out: list[tuple[str, str]] = []
    for path, txt in merged:
        buf = ""
        for para in [p for p in txt.split("\n\n") if p.strip()]:
            if buf and len(buf) + len(para) > max_chars:
                out.append((path, buf.strip()))
                buf = ""
            buf += para + "\n\n"
        if buf.strip():
            out.append((path, buf.strip()))
    return out


def load_company_docs(
    session: Session, store: BlobStore, docs_dir: Path, plan: dict
) -> dict:
    stats = {"stored": 0, "unchanged": 0, "chunks": 0}
    for file in kinds(plan):
        path = docs_dir / file
        if not path.exists():
            continue
        data = path.read_bytes()
        sha = hashlib.sha256(data).hexdigest()
        row = session.scalar(
            select(DocumentRow).where(
                DocumentRow.corpus == "company", DocumentRow.title == file
            )
        )
        if row is not None and row.sha256 == sha:
            stats["unchanged"] += 1
            continue
        uri = store.put(safe_key("company", "lumen-grid-labs", file), data)
        if row is None:
            row = DocumentRow(
                corpus="company",
                gcs_uri=uri,
                mime="text/markdown",
                title=file,
                sha256=sha,
            )
            session.add(row)
            session.flush()
        else:
            row.gcs_uri, row.sha256 = uri, sha
            session.execute(delete(ChunkRow).where(ChunkRow.document_id == row.id))
        chunks = chunk_markdown(data.decode("utf-8"), file)
        for i, (section_path, txt) in enumerate(chunks):
            session.add(
                ChunkRow(
                    document_id=row.id,
                    ord=i,
                    section_path=section_path,
                    text=txt,
                    n_tokens=len(txt) // 4,
                )
            )
        row.page_count, row.parse_status = 1, "parsed"
        session.commit()
        stats["stored"] += 1
        stats["chunks"] += len(chunks)
    return stats


def embed_company_chunks(
    session: Session, embedder, *, price_per_m: float, max_usd: float, batch: int = 50
) -> dict:
    ids = list(
        session.scalars(
            select(ChunkRow.id)
            .join(DocumentRow, DocumentRow.id == ChunkRow.document_id)
            .where(DocumentRow.corpus == "company", ChunkRow.embedding.is_(None))
        )
    )
    start, stats = embedder.tokens, {"embedded": 0, "cost_usd": 0.0, "stopped": None}
    for i in range(0, len(ids), batch):
        if stats["cost_usd"] >= max_usd:
            stats["stopped"] = "budget"
            break
        rows = session.scalars(
            select(ChunkRow).where(ChunkRow.id.in_(ids[i : i + batch]))
        ).all()
        vecs = embedder.embed_documents([f"{r.section_path}\n{r.text}" for r in rows])
        for r, v in zip(rows, vecs, strict=True):
            r.embedding = v
        session.commit()
        stats["embedded"] += len(rows)
        stats["cost_usd"] = (embedder.tokens - start) * price_per_m / 1e6
    return stats


def main(argv: list[str] | None = None) -> int:
    from app.config import get_settings
    from app.discover.llm import GeminiJson
    from db.session import make_engine, make_session_factory
    from ingest.storage import LocalBlobStore
    from rag.embed import GeminiEmbedder

    parser = argparse.ArgumentParser(prog="python -m ingest.company_corpus")
    parser.add_argument("cmd", choices=["check", "generate", "load"])
    parser.add_argument("--yes", action="store_true")
    args = parser.parse_args(argv)
    root = Path("data/company")
    plan = load_plan(root / "corpus_plan.json")
    settings = get_settings()
    if args.cmd == "check":
        problems = check_corpus(root / "docs", plan)
        print("\n".join(problems) or "corpus OK")
        return 1 if problems else 0
    if args.cmd == "generate":
        missing = [e for e in plan["new"] if not (root / "docs" / e["file"]).exists()]
        est = (
            len(missing)
            * (
                2500 * settings.price_agent_input_per_m
                + 2500 * settings.price_agent_output_per_m
            )
            / 1e6
        )
        print(f"{len(missing)} docs to write, estimated <= ${est:.2f}")
        if est > 0.5 and not args.yes:
            raise SystemExit("estimate above $0.50: re-run with --yes")
        facts = _facts_table()
        out = generate_missing(
            plan,
            root / "docs",
            GeminiJson(settings),
            facts,
            price_in_per_m=settings.price_agent_input_per_m,
            price_out_per_m=settings.price_agent_output_per_m,
            max_usd=1.0,
        )
        print(json.dumps(out, indent=2))
        return 0
    with make_session_factory(make_engine(settings.database_url))() as s:
        print(
            json.dumps(
                load_company_docs(
                    s, LocalBlobStore(Path(settings.blob_root)), root / "docs", plan
                )
            )
        )
        print(
            json.dumps(
                embed_company_chunks(
                    s,
                    GeminiEmbedder(settings),
                    price_per_m=settings.price_embedding_per_m,
                    max_usd=0.2,
                )
            )
        )
    return 0


def _facts_table() -> str:
    """The authoritative facts table from the M0 plan (Task 9)."""
    text = Path("docs/plans/2026-10-07-m0-foundation.md").read_text(encoding="utf-8")
    start = text.index("**Facts every document must agree with**")
    return text[start : text.index("**Documents to write**", start)].strip()


if __name__ == "__main__":
    raise SystemExit(main())
