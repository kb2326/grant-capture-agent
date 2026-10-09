"""B0 vs B1 side-by-side report (M1 spec §7)."""

import json
from pathlib import Path

from evals.suites.analyze import evaluate_cases, load_golden

LONG_PAGES = 50


def _table(rows: list[tuple[str, list]]) -> list[str]:
    out = ["| metric | B0 | B1 |", "|---|---|---|"]
    names = [m.metric for m in rows[0][1]]
    for i, name in enumerate(names):
        vals = [
            f"{r[1][i].value:.3f}" if r[1][i].value is not None else "n/a" for r in rows
        ]
        out.append(f"| {name} | {vals[0]} | {vals[1]} |")
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
    b0, b1 = (
        json.loads(b0_cases.read_text(encoding="utf-8")),
        json.loads(b1_cases.read_text(encoding="utf-8")),
    )
    lines = [
        "# M1 ablation: B0 (whole document) vs B1 (page windows)",
        "",
        "## All solicitations",
        "",
    ]
    lines += _table(
        [
            ("B0", evaluate_cases("B0", b0, gk, gr)),
            ("B1", evaluate_cases("B1", b1, gk, gr)),
        ]
    )
    long0 = [c for c in b0 if (c.get("pages") or 0) > LONG_PAGES]
    long1 = [c for c in b1 if (c.get("pages") or 0) > LONG_PAGES]
    lines += [
        "",
        f"## Long documents (> {LONG_PAGES} pages): {len(long0)} solicitations",
        "",
    ]
    lines += _table(
        [
            ("B0", evaluate_cases("B0", long0, gk, gr)),
            ("B1", evaluate_cases("B1", long1, gk, gr)),
        ]
    )
    for name, cases in (("B0", b0), ("B1", b1)):
        misses = [
            c
            for c in cases
            if c["opportunity_id"] in gk
            and not c.get("error")
            and c["verdict"] != gk[c["opportunity_id"]]["verdict"]
        ][:5]
        lines += ["", f"## {name}: verdict misses (first 5)", ""]
        lines += [
            f"- `{c['opportunity_id']}`: predicted {c['verdict']}, labeled "
            f"{gk[c['opportunity_id']]['verdict']}"
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
