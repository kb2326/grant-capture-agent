import json
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass
class MetricResult:
    suite: str
    metric: str
    value: float | None
    target: float | None
    higher_is_better: bool = True

    @property
    def passed(self) -> bool | None:
        if self.value is None or self.target is None:
            return None
        return (
            self.value >= self.target
            if self.higher_is_better
            else self.value <= self.target
        )


def _fmt(v: float | None) -> str:
    return "n/a" if v is None else f"{v:.3f}"


def write_report(
    results: list[MetricResult], out_dir: Path, run_id: str
) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    js = out_dir / f"eval-{run_id}.json"
    md = out_dir / f"eval-{run_id}.md"
    js.write_text(
        json.dumps(
            {
                "run_id": run_id,
                "results": [{**asdict(r), "passed": r.passed} for r in results],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    lines = [
        f"# Eval report `{run_id}`",
        "",
        "| suite | metric | value | target | result |",
        "|---|---|---|---|---|",
    ]
    status = {True: "pass", False: "FAIL", None: "pending"}
    lines += [
        f"| {r.suite} | {r.metric} | {_fmt(r.value)} | {_fmt(r.target)} | {status[r.passed]} |"
        for r in results
    ]
    if not results:
        lines.append("| (no suites registered yet) | | | | |")
    md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return js, md
