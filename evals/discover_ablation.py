"""reports/m2/ablation.md: one table per ablation, with the silver-set and pooling caveats (M2 spec §5)."""

from pathlib import Path

COLS = ("p@10", "ndcg@10", "recall@20", "p50_s", "p95_s", "cost_usd", "n")


def _fmt(v) -> str:
    if v is None:
        return "n/a"
    if isinstance(v, int):
        return str(v)
    return f"{v:.4f}" if v and abs(v) < 0.01 else f"{v:.3f}"


def write_ablation(
    out: Path,
    sections: list[tuple[str, dict[str, dict]]],
    decisions: list[str],
    meta: dict,
) -> Path:
    lines = [
        "# M2 Discover ablation",
        "",
        f"Labels: **silver set** from `{meta.get('labeler', '?')}` (an AI reviewer, not a person). "
        "Read every number as agreement with that reviewer.",
        "Pooling: only results that some arm ranked in its top 10 were labeled; unlabeled results "
        "count as not relevant, which can understate an arm that finds things the others miss.",
        "",
    ]
    for title, arms in sections:
        lines += [
            f"## {title}",
            "",
            "| arm | slice | " + " | ".join(COLS) + " |",
            "|---|---|" + "---|" * len(COLS),
        ]
        for arm, summary in arms.items():
            for sl in ("all", "specific", "vague"):
                cells = " | ".join(_fmt(summary[sl].get(c)) for c in COLS)
                lines.append(f"| {arm} | {sl} | {cells} |")
        lines.append("")
    lines += ["## Decisions", "", *[f"- {d}" for d in decisions], ""]
    out.mkdir(parents=True, exist_ok=True)
    path = out / "ablation.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path
