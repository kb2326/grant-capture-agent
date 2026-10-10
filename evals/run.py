"""python -m evals.run --suite smoke|full --out reports/<dir>"""

import argparse
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from evals.report import MetricResult, write_report


# Suites register here as milestones add them (M1: knockout, requirements; M2: discover; M3: draft).
def _analyze_smoke():
    from evals.suites.analyze_smoke import run

    return run()


def _discover_smoke():
    from evals.suites.discover import run_smoke

    return run_smoke()


def _analyze(variant: str):
    def _run():
        from evals.suites.analyze import run_variant

        return run_variant(variant)

    return _run


SUITES: dict[str, Callable[[], list[MetricResult]]] = {
    "analyze_smoke": _analyze_smoke,
    "discover_smoke": _discover_smoke,
    "analyze_b0": _analyze("B0"),
    "analyze_b1": _analyze("B1"),
}
SMOKE: tuple[str, ...] = ("analyze_smoke", "discover_smoke")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--suite", choices=["smoke", "full"], default="smoke")
    parser.add_argument("--out", default="reports/local")
    args = parser.parse_args(argv)
    names = SMOKE if args.suite == "smoke" else tuple(SUITES)
    results = [r for name in names for r in SUITES[name]()]
    run_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    _, md = write_report(results, Path(args.out), run_id)
    print(md.read_text(encoding="utf-8"))
    return 1 if any(r.passed is False for r in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
