"""M3 Draft evaluation stages (M3 spec §4-5).

python -m evals.draft run --variant B1 [--yes]   draft the 12 tasks (saves retrieval traces)
python -m evals.draft run --variant B0 [--yes]
python -m evals.draft pairs                      sample 40 grader pairs from B1 traces for the labeling page
python -m evals.draft kappa                      kappa between the user's labels and the grader
python -m evals.draft report                     reports/m3/ablation.md
"""

import argparse
import json
import time
from pathlib import Path

from app.config import Settings, get_settings
from app.contracts import DraftTask, TaskRequirement
from evals.suites.draft import keep_b1, score_section, summarize_draft
from ingest.company_corpus import kinds, load_plan, load_tasks

OUT = Path("reports/m3")
TASKS = Path("evals/data/golden/draft_tasks.jsonl")
PLAN = Path("data/company/corpus_plan.json")
COLS = (
    "gap_recall",
    "gap_precision",
    "evidence_recall",
    "citation_validity",
    "distractor_rate",
    "faithfulness",
    "context_precision",
    "p50_s",
    "p95_s",
    "cost_usd",
    "n",
)


def to_task(d: dict) -> DraftTask:
    return DraftTask(
        id=d["id"],
        section_title=d["section_title"],
        instructions=d["instructions"],
        criteria=d.get("criteria", []),
        requirements=[
            TaskRequirement(id=r["id"], text=r["text"]) for r in d["requirements"]
        ],
    )


def estimate_run_usd(
    variant: str, n_tasks: int, corpus_tokens: int, settings: Settings
) -> float:
    inp, out = (
        settings.price_agent_input_per_m / 1e6,
        settings.price_agent_output_per_m / 1e6,
    )
    if (
        variant == "B0"
    ):  # corpus cached once (billed in full here as the worst case), drafts + judge per task
        return corpus_tokens * inp + n_tasks * (
            corpus_tokens * inp * 0.25 + 2 * (3_000 * inp + 1_500 * out)
        )
    grade = (
        8 * 600 * settings.price_grader_input_per_m
        + 400 * settings.price_grader_output_per_m
    ) / 1e6
    return n_tasks * (4 * 3 * grade + 3 * (6_000 * inp + 1_500 * out))


def _runs(variant: str) -> list[dict]:
    p = OUT / f"runs-{variant}.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else []


def _chunk_maps(session) -> tuple[dict[str, str], dict[str, str], dict[str, str]]:
    from app.draft.corpus import load_company_chunks

    k = kinds(load_plan(PLAN))
    chunks = load_company_chunks(session)
    return (
        {str(c.chunk_id): c.text for c in chunks},
        {str(c.chunk_id): k.get(c.document_title, "on_topic") for c in chunks},
        {str(c.chunk_id): c.document_title for c in chunks},
    )


def cmd_run(variant: str, yes: bool) -> None:
    from app.discover.tools import open_session
    from app.draft.service import draft
    from app.draft.tools import default_draft_deps

    settings, tasks = get_settings(), load_tasks(TASKS)
    with open_session(settings) as s:
        deps = default_draft_deps(s, settings)
        corpus_tokens = sum(len(c.text) for c in deps.chunks) // 4
        est = estimate_run_usd(variant, len(tasks), corpus_tokens, settings)
        print(
            f"{variant}: {len(tasks)} tasks, corpus ~{corpus_tokens:,} tokens, estimated <= ${est:.2f}"
        )
        if est > 0.5 and not yes:
            raise SystemExit("estimate above $0.50: re-run with --yes")
        done = {r["task_id"]: r for r in _runs(variant) if not r.get("error")}
        rows, spent = [], 0.0
        for t in tasks:
            if t["id"] in done:
                rows.append(done[t["id"]])
                continue
            if spent >= settings.draft_eval_budget_usd:
                rows.append(
                    {"task_id": t["id"], "error": "skipped: eval budget reached"}
                )
                continue
            start = time.monotonic()
            try:
                section, stats = draft(deps, to_task(t), variant)
                given = (
                    sorted(
                        {
                            str(c)
                            for tr in section.retrieval_trace
                            for c, g in zip(tr.chunk_ids, tr.grades, strict=True)
                            if g == "relevant"
                        }
                    )
                    if variant == "B1"
                    else []
                )
                rows.append(
                    {
                        **section.model_dump(mode="json"),
                        "given": given,
                        "stats": {
                            **stats,
                            "latency_s": section.latency_s,
                            "cost_usd": section.cost_usd,
                        },
                    }
                )
                spent += section.cost_usd
            except Exception as exc:  # recorded, never hidden
                rows.append(
                    {
                        "task_id": t["id"],
                        "error": f"{type(exc).__name__}: {exc}",
                        "stats": {"latency_s": time.monotonic() - start},
                    }
                )
            OUT.mkdir(
                parents=True, exist_ok=True
            )  # save after every task, so a stopped run can resume
            (OUT / f"runs-{variant}.json").write_text(
                json.dumps(rows, indent=1), encoding="utf-8"
            )
        if deps.cache:
            deps.cache.delete()
    print(
        f"{variant}: {sum(not r.get('error') for r in rows)}/{len(rows)} drafted, ${spent:.3f}"
    )


def cmd_pairs() -> None:
    from app.discover.tools import open_session
    from evals.grader_label import PAIRS, sample_pairs

    with open_session(get_settings()) as s:
        text, _, _ = _chunk_maps(s)
    tasks = {t["id"]: t for t in load_tasks(TASKS)}
    pairs = sample_pairs([r for r in _runs("B1") if not r.get("error")], text, tasks)
    PAIRS.parent.mkdir(parents=True, exist_ok=True)
    PAIRS.write_text(json.dumps(pairs, indent=1), encoding="utf-8")
    print(
        f"wrote {len(pairs)} pairs; label them: uv run python -m evals.grader_label  (http://127.0.0.1:8766)"
    )


def _kappa() -> dict:
    from evals.grader_label import LABELS, PAIRS, kappas

    labels = {}
    if LABELS.exists():
        for line in LABELS.read_text(encoding="utf-8").splitlines():
            if line.strip():
                d = json.loads(line)
                labels[d["pair_id"]] = d["label"]
    return (
        kappas(json.loads(PAIRS.read_text(encoding="utf-8")), labels)
        if PAIRS.exists()
        else {"n": 0}
    )


def write_draft_report(
    out: Path, summaries: dict[str, dict], decision_lines: list[str], meta: dict
) -> Path:
    def fmt(v):
        return (
            "n/a"
            if v is None
            else str(v)
            if isinstance(v, int)
            else f"{v:.3f}"
            if abs(v) >= 0.01 or not v
            else f"{v:.4f}"
        )

    lines = [
        "# M3 Draft ablation",
        "",
        "Ground truth: gap, evidence, citation and distractor metrics are scored by code from the checked-in "
        "corpus plan (exact phrases). Faithfulness is a **silver** score from a Flash judge.",
        f"Grader calibration against the user's own labels: {meta}",
        "",
        "| variant | " + " | ".join(COLS) + " |",
        "|---|" + "---|" * len(COLS),
    ]
    lines += [
        f"| {v} | " + " | ".join(fmt(s.get(c)) for c in COLS) + " |"
        for v, s in summaries.items()
    ]
    lines += ["", "## Decision", "", *[f"- {d}" for d in decision_lines], ""]
    out.mkdir(parents=True, exist_ok=True)
    path = out / "ablation.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def cmd_report() -> None:
    from app.discover.tools import open_session

    with open_session(get_settings()) as s:
        text, kind, _ = _chunk_maps(s)
    tasks = {t["id"]: t for t in load_tasks(TASKS)}
    summaries = {}
    for v in ("B0", "B1"):
        rows = [
            {**score_section(tasks[r["task_id"]], r, text, kind), **r["stats"]}
            for r in _runs(v)
            if not r.get("error")
        ]
        summaries[v] = summarize_draft(rows)
    b1 = keep_b1(summaries["B0"], summaries["B1"])
    lines = [
        f"ADR-0018: {'B1 (corrective RAG)' if b1 else 'B0 (long context)'} - B1 is kept only with a >= 0.05 "
        "gain in gap recall, evidence recall or faithfulness without doubling cost or p95."
    ]
    print(
        write_draft_report(OUT, summaries, lines, _kappa()).read_text(encoding="utf-8")
    )


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m evals.draft")
    p.add_argument("stage", choices=["run", "pairs", "kappa", "report"])
    p.add_argument("--variant", choices=["B0", "B1"], default="B0")
    p.add_argument("--yes", action="store_true")
    a = p.parse_args(argv)
    if a.stage == "run":
        cmd_run(a.variant, a.yes)
    elif a.stage == "pairs":
        cmd_pairs()
    elif a.stage == "kappa":
        print(json.dumps(_kappa(), indent=2))
    else:
        cmd_report()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
