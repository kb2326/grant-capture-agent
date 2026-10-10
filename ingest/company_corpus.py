"""Company corpus for M3 Draft: plan, ground-truth checks, generation and loading (M3 spec §3.1-3.2)."""

import json
from pathlib import Path

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
