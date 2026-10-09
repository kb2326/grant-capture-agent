"""B0 vs B1 report (M1 spec §7). B0 is scored on every case it measured; the head-to-head uses shared cases only."""

import json
from collections import Counter
from pathlib import Path

from evals.suites.analyze import evaluate_cases, load_golden

VERDICTS = ("ELIGIBLE", "INELIGIBLE", "NEEDS_REVIEW")


def shared_cases(b0: list[dict], b1: list[dict]) -> tuple[list[dict], list[dict]]:
    """Cases both variants completed, in the same order, so the comparison is like for like."""
    ok1 = {c["opportunity_id"]: c for c in b1 if not c.get("error")}
    s0 = [c for c in b0 if not c.get("error") and c["opportunity_id"] in ok1]
    return s0, [ok1[c["opportunity_id"]] for c in s0]


def _fmt(v: float | None) -> str:
    return "n/a" if v is None else f"{v:.3f}"


def _table(columns: list[tuple[str, list]]) -> list[str]:
    out = [
        "| metric | " + " | ".join(n for n, _ in columns) + " | target |",
        "|---|" + "---|" * (len(columns) + 1),
    ]
    for i, m in enumerate(columns[0][1]):
        vals = " | ".join(_fmt(col[i].value) for _, col in columns)
        out.append(
            f"| {m.metric} | {vals} | {_fmt(m.target) if m.target is not None else ''} |"
        )
    return out


def _confusion(cases: list[dict], gk: dict) -> list[str]:
    pairs = Counter(
        (gk[c["opportunity_id"]]["verdict"], c["verdict"])
        for c in cases
        if not c.get("error") and c["opportunity_id"] in gk
    )
    out = [
        "| labeled \\ predicted | " + " | ".join(VERDICTS) + " |",
        "|---|---|---|---|",
    ]
    out += [
        f"| {g} | " + " | ".join(str(pairs.get((g, p), 0)) for p in VERDICTS) + " |"
        for g in VERDICTS
    ]
    return out


def write_ablation(
    b0_cases: Path,
    b1_cases: Path,
    out: Path,
    golden_dir: Path = Path("evals/data/golden"),
) -> Path:
    gk, gr = (
        load_golden(golden_dir / "knockout.jsonl"),
        load_golden(golden_dir / "requirements.jsonl"),
    )
    b0 = json.loads(b0_cases.read_text(encoding="utf-8"))
    b1 = json.loads(b1_cases.read_text(encoding="utf-8"))
    s0, s1 = shared_cases(b0, b1)
    lines = [
        "# M1 ablation: B0 (whole document) vs B1 (page windows)",
        "",
        "Labels are a **silver set**: written by an independent AI labeler (see `evals/LABELING.md`), not by a person.",
        "Read every number as agreement with that labeler. Cases skipped by the eval budget cap are not errors.",
        "",
        "## B0 on the full sample",
        "",
        *_table([("B0", evaluate_cases("B0", b0, gk, gr))]),
        "",
        "### B0 verdicts vs labels",
        "",
        *_confusion(b0, gk),
        "",
        f"## Head to head on the {len(s0)} cases both variants completed",
        "",
        *_table(
            [
                ("B0", evaluate_cases("B0", s0, gk, gr)),
                ("B1", evaluate_cases("B1", s1, gk, gr)),
            ]
        ),
    ]
    for name, cases in (("B0", b0), ("B1", s1)):
        misses = [
            c
            for c in cases
            if c["opportunity_id"] in gk
            and not c.get("error")
            and c["verdict"] != gk[c["opportunity_id"]]["verdict"]
        ]
        lines += ["", f"## {name}: verdict disagreements ({len(misses)})", ""]
        lines += [
            f"- `{c['opportunity_id']}`: predicted {c['verdict']}, labeled {gk[c['opportunity_id']]['verdict']}"
            for c in misses
        ] or ["- none"]
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out


if __name__ == "__main__":
    print(
        write_ablation(
            Path("reports/m1/B0-cases.json"),
            Path("reports/m1/B1-cases.json"),
            Path("reports/m1/ablation.md"),
        )
    )
