import json
from pathlib import Path

from evals.report import MetricResult, write_report
from evals.run import main


def test_report_files_and_pass_logic(tmp_path: Path):
    results = [
        MetricResult("knockout", "recall", 0.96, 0.95),
        MetricResult("system", "p95_latency_s", 120.0, 90.0, higher_is_better=False),
        MetricResult("draft", "faithfulness", None, 0.90),
    ]
    assert [r.passed for r in results] == [True, False, None]
    js, md = write_report(results, tmp_path, run_id="t1")
    data = json.loads(js.read_text(encoding="utf-8"))
    assert data["run_id"] == "t1" and len(data["results"]) == 3
    assert "| knockout | recall | 0.960 | 0.950 | pass |" in md.read_text(
        encoding="utf-8"
    )


def test_smoke_run_exits_zero_and_writes_report(tmp_path: Path):
    assert main(["--suite", "smoke", "--out", str(tmp_path)]) == 0
    assert list(tmp_path.glob("*.json")) and list(tmp_path.glob("*.md"))


def test_smoke_runs_the_offline_analyze_suite(tmp_path):
    from evals.run import SMOKE

    assert "analyze_smoke" in SMOKE
    assert main(["--suite", "smoke", "--out", str(tmp_path)]) == 0
    assert "analyze_smoke" in next(tmp_path.glob("*.md")).read_text(encoding="utf-8")
