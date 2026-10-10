"""M2 Discover evaluation stages (M2 spec §4-5).

python -m evals.discover queries            draft the query set once (Flash); the user reviews it
python -m evals.discover retrieval          4 retrieval arms, no LLM -> reports/m2/runs-<arm>.json
python -m evals.discover label              silver-label every unlabeled pooled result (Flash-Lite)
python -m evals.discover workflow [--yes]   B0 and B1 with the winning retrieval settings
python -m evals.discover report             reports/m2/ablation.md
"""

import argparse
import json
import random
import uuid
from pathlib import Path

from app.config import Settings, get_settings
from app.contracts import SearchPlan, SearchQuery
from evals.suites.discover import (
    keep_richer,
    load_jsonl,
    load_qrels,
    pool_missing,
    run_arm,
    summarize,
    tune_tau,
)

GOLDEN, DEV, OUT = Path("evals/data/golden"), Path("evals/data/dev"), Path("reports/m2")
QUERIES = (GOLDEN / "discover_queries.jsonl", DEV / "discover_queries.jsonl")
QRELS = GOLDEN / "discover_qrels.jsonl"
RETRIEVAL_ARMS = ("gemini", "local", "gemini+rerank", "local+rerank")
WORKFLOW_ARMS = ("B0", "B1")
CONFIRM_USD = 0.50


def parse_arm(name: str) -> tuple[str, bool]:
    emb, _, rr = name.partition("+")
    return emb, rr == "rerank"


def estimate_workflow_usd(n_queries: int, settings: Settings) -> float:
    """Worst case: B0 = 1 plan call; B1 = 1 plan + 2 refine calls; ~2.5k tokens in, ~800 out per call."""
    calls = n_queries * (1 + 3)
    per_call = (
        2_500 * settings.price_agent_input_per_m / 1e6
        + 800 * settings.price_agent_output_per_m / 1e6
    )
    rank_calls = n_queries * 2 * 6  # B0 + B1, up to 5 queries per plan + a refined plan
    return calls * per_call + rank_calls * settings.price_rank_per_1k / 1000


def _queries() -> dict[str, dict]:
    return {q["id"]: q for path in QUERIES for q in load_jsonl(path)}


def _runs(arm: str) -> list[dict]:
    path = OUT / f"runs-{arm}.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else []


def _save_runs(arm: str, runs: list[dict]) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"runs-{arm}.json").write_text(
        json.dumps(runs, indent=1, default=str), encoding="utf-8"
    )


def _golden(runs: list[dict], queries: dict[str, dict]) -> list[dict]:
    return [r for r in runs if queries[r["query_id"]]["split"] == "golden"]


def decide_retrieval(
    runs: dict[str, list[dict]], qrels, queries
) -> tuple[str, bool, list[str]]:
    s = {arm: summarize(_golden(r, queries), qrels, queries) for arm, r in runs.items()}
    # The free local model is the baseline; the paid Gemini embedding must earn its place.
    emb = "gemini" if keep_richer(s["local"], s["gemini"]) else "local"
    rerank = keep_richer(s[emb], s[f"{emb}+rerank"])

    def ndcg_of(arm: str) -> str:
        v = s[arm]["all"]["ndcg@10"]
        return "n/a" if v is None else f"{v:.3f}"

    notes = [
        f"Embeddings: {emb} (nDCG@10 gemini {ndcg_of('gemini')} vs local {ndcg_of('local')}).",
        f"Rerank: {'on' if rerank else 'off'} (nDCG@10 {ndcg_of(emb)} without vs "
        f"{ndcg_of(emb + '+rerank')} with).",
    ]
    return emb, rerank, notes


def _session(settings: Settings):
    from db.session import make_engine, make_session_factory

    return make_session_factory(make_engine(settings.database_url))()


def cmd_queries(force: bool) -> None:
    from app.discover.llm import GeminiJson
    from app.discover.tools import load_company
    from evals.discover_queries import draft_queries, split_queries

    if QUERIES[0].exists() and not force:
        raise SystemExit(
            f"{QUERIES[0]} exists; queries are frozen once reviewed (--force only before labeling)"
        )
    settings = get_settings()
    with _session(settings) as s:
        _, profile = load_company(s)
    golden, dev = split_queries(draft_queries(GeminiJson(settings), profile).items)
    for path, rows in zip(QUERIES, (golden, dev), strict=True):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
        print(f"wrote {len(rows)} queries to {path}")


def _retrieval_one(deps, q: dict) -> dict:
    from app.discover.service import execute

    emb0, rank0 = deps.embedder.tokens, deps.reranker.calls
    plan = SearchPlan(
        intent=q["text"], queries=[SearchQuery(text=q["text"], min_days_to_close=0)]
    )
    cands = execute(deps, plan)
    s = deps.settings
    emb_cost = (
        (deps.embedder.tokens - emb0) * s.price_embedding_per_m / 1e6
        if deps.embedder.name == "gemini"
        else 0.0
    )
    return {
        "ranked": [str(c.opportunity_id) for c in cands[:20]],
        "scores": [[str(c.opportunity_id), c.score, c.reranked] for c in cands[:30]],
        "cost_usd": emb_cost
        + (deps.reranker.calls - rank0) * s.price_rank_per_1k / 1000,
    }


def warm_up(deps) -> None:
    """One untimed call per component, so client setup and sign-in are not billed to the first query's latency."""
    from rag.rerank import RerankDoc

    deps.embedder.embed_query("warm up")
    deps.reranker.rerank("warm up", [RerankDoc("w", "warm up", "warm up")])
    if (
        deps.llm is not None
    ):  # count_tokens is free and opens the same client connection
        deps.llm.client.models.count_tokens(model=deps.llm.model_id, contents="warm up")


def cmd_retrieval() -> None:
    from app.discover.service import DiscoverDeps
    from rag.embed import COLUMNS, make_embedder
    from rag.rerank import make_reranker

    settings, queries = get_settings(), list(_queries().values())
    with _session(settings) as s:
        embedders = {name: make_embedder(name, settings) for name in COLUMNS}
        for arm in RETRIEVAL_ARMS:
            emb, rr = parse_arm(arm)
            deps = DiscoverDeps(
                session=s,
                settings=settings,
                embedder=embedders[emb],
                column=COLUMNS[emb],
                reranker=make_reranker(rr, settings),
            )
            warm_up(deps)
            runs = run_arm(
                queries,
                lambda q, d=deps: _retrieval_one(d, q),
                max_usd=settings.discover_eval_budget_usd,
            )
            _save_runs(arm, runs)
            print(f"{arm}: {sum(not r.get('error') for r in runs)}/{len(runs)} queries")


def cmd_label() -> None:
    from app.discover.llm import GeminiJson
    from app.discover.service import load_rows
    from app.discover.tools import load_company
    from evals.ai_label import write_labels
    from evals.discover_label import LABEL_PROMPT_VERSION, label_query

    settings, queries = get_settings(), _queries()
    llm = GeminiJson(settings, model_id=settings.model_grader)
    arms = {a: _runs(a) for a in (*RETRIEVAL_ARMS, *WORKFLOW_ARMS) if _runs(a)}
    todo = pool_missing(arms, load_qrels(QRELS))
    meta = {
        "labeler": f"ai:{settings.model_grader}",
        "silver": True,
        "prompt_version": LABEL_PROMPT_VERSION,
    }
    with _session(settings) as s:
        _, profile = load_company(s)
        for qid, ids in todo.items():
            spent = (
                llm.total_tokens_in * settings.price_grader_input_per_m
                + llm.total_tokens_out * settings.price_grader_output_per_m
            ) / 1e6
            if spent > settings.discover_eval_budget_usd:
                print("label budget reached; re-run to continue")
                break
            rows = load_rows(s, [uuid.UUID(i) for i in ids])
            cards = [(i, rows[uuid.UUID(i)][1]) for i in ids if uuid.UUID(i) in rows]
            for start in range(0, len(cards), 10):
                labels = label_query(
                    llm, qid, queries[qid]["text"], cards[start : start + 10], profile
                )
                write_labels(QRELS, labels, meta)
    print(
        f"pooled {sum(len(v) for v in todo.values())} unlabeled results; "
        f"tokens in {llm.total_tokens_in}, out {llm.total_tokens_out}"
    )


def cmd_workflow(yes: bool) -> None:
    from app.discover.llm import GeminiJson
    from app.discover.service import DiscoverDeps, discover
    from app.discover.tools import load_company
    from app.memory import load_preferences
    from rag.embed import COLUMNS, make_embedder
    from rag.rerank import make_reranker

    settings, queries = get_settings(), _queries()
    qrels = load_qrels(QRELS)
    emb, rerank, notes = decide_retrieval(
        {a: _runs(a) for a in RETRIEVAL_ARMS}, qrels, queries
    )
    tau = None
    if rerank:  # V3 threshold from the dev queries' reranked candidates
        dev = [
            r
            for r in _runs(f"{emb}+rerank")
            if queries[r["query_id"]]["split"] == "dev" and not r.get("error")
        ]
        tau = tune_tau(
            [
                (sc, qrels.get(r["query_id"], {}).get(i, 0))
                for r in dev
                for i, sc, rr in r["scores"]
                if rr
            ]
        )
    est = estimate_workflow_usd(len(queries), settings)
    print(*notes, f"tau={tau}", f"estimated cost <= ${est:.2f}", sep="\n")
    if est > CONFIRM_USD and not yes:
        raise SystemExit("estimate above $0.50: re-run with --yes to proceed")
    with _session(settings) as s:
        company_id, profile = load_company(s)
        prefs = load_preferences(s, company_id)
        for variant in WORKFLOW_ARMS:
            deps = DiscoverDeps(
                session=s,
                settings=settings,
                embedder=make_embedder(emb, settings),
                column=COLUMNS[emb],
                reranker=make_reranker(rerank, settings),
                llm=GeminiJson(settings),
                checker=None,  # V4 off in evals: it would measure Analyze, not Discover
                company_id=company_id,
                tau=tau,
            )
            warm_up(deps)

            def one(q: dict, d=deps, v=variant) -> dict:
                r = discover(
                    d,
                    q["text"],
                    variant=v,
                    profile=profile,
                    prefs=prefs,
                    explain_top=False,
                )
                return {
                    "ranked": [str(c.opportunity_id) for c in r.candidates],
                    "iterations": r.iterations,
                    "plans": [p.model_dump(mode="json") for p in r.plans],
                    "cost_usd": r.cost_usd,
                }

            runs = run_arm(
                list(queries.values()), one, max_usd=settings.discover_eval_budget_usd
            )
            _save_runs(variant, runs)
            print(
                f"{variant}: {sum(not r.get('error') for r in runs)}/{len(runs)} queries"
            )
    (OUT / "decisions.json").write_text(
        json.dumps({"embedding": emb, "rerank": rerank, "tau": tau}), encoding="utf-8"
    )


def cmd_report() -> None:
    from evals.discover_ablation import write_ablation

    settings, queries, qrels = get_settings(), _queries(), load_qrels(QRELS)
    emb, _, notes = decide_retrieval(
        {a: _runs(a) for a in RETRIEVAL_ARMS}, qrels, queries
    )
    summ = {
        a: summarize(_golden(_runs(a), queries), qrels, queries)
        for a in (*RETRIEVAL_ARMS, *WORKFLOW_ARMS)
    }
    b1 = keep_richer(summ["B0"], summ["B1"])

    def ndcg_of(arm: str, sl: str) -> str:
        v = summ[arm][sl]["ndcg@10"]
        return "n/a" if v is None else f"{v:.3f}"

    notes.append(
        f"Workflow (ADR-0017): {'B1 (Plan-Execute-Verify)' if b1 else 'B0 (single pass)'} "
        f"(nDCG@10 B0 {ndcg_of('B0', 'all')} vs B1 {ndcg_of('B1', 'all')}; "
        f"vague {ndcg_of('B0', 'vague')} vs {ndcg_of('B1', 'vague')})."
    )
    path = write_ablation(
        OUT,
        [
            (
                "Embeddings (no LLM, no rerank)",
                {a: summ[a] for a in ("gemini", "local")},
            ),
            ("Rerank (no LLM)", {a: summ[a] for a in (emb, f"{emb}+rerank")}),
            (
                "Workflow: single pass (B0) vs Plan-Execute-Verify (B1)",
                {a: summ[a] for a in WORKFLOW_ARMS},
            ),
        ],
        notes,
        {"labeler": f"ai:{settings.model_grader}"},
    )
    labels = load_jsonl(QRELS)
    sample = random.Random(20261009).sample(labels, k=min(20, len(labels)))
    (OUT / "label_spotcheck.md").write_text(
        "# Label spot check (mark each agree / disagree)\n\n"
        + "\n".join(
            f"- [ ] {queries[r['query_id']]['text']} -> `{r['opportunity_id']}` "
            f"grade {r['grade']}: {r['reason']}"
            for r in sample
        )
        + "\n",
        encoding="utf-8",
    )
    print(path.read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m evals.discover")
    parser.add_argument(
        "stage", choices=["queries", "retrieval", "label", "workflow", "report"]
    )
    parser.add_argument("--yes", action="store_true")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)
    stages = {
        "queries": lambda: cmd_queries(args.force),
        "retrieval": cmd_retrieval,
        "label": cmd_label,
        "workflow": lambda: cmd_workflow(args.yes),
        "report": cmd_report,
    }
    stages[args.stage]()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
