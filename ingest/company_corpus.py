"""Company corpus for M3 Draft: plan, ground-truth checks, generation and loading (M3 spec §3.1-3.2)."""

import json
from pathlib import Path

from pydantic import BaseModel

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
