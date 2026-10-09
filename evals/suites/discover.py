"""Discover retrieval metrics, the arm runner and the ablation decision rule (M2 spec §5). No model calls."""

import json
import math
import time
from collections.abc import Callable, Sequence
from pathlib import Path

from evals.metrics import ndcg_at_k, precision_at_k
from evals.report import MetricResult

SLICES = ("all", "specific", "vague")
MIN_GAIN = 0.03
FREE_COST_USD, FREE_LATENCY_S = 0.005, 2.0


def recall_at_k(ranked: Sequence[str], relevant: set[str], k: int) -> float | None:
    return None if not relevant else len(set(ranked[:k]) & relevant) / len(relevant)


def query_metrics(ranked: Sequence[str], grades: dict[str, int]) -> dict:
    return {
        "p@10": precision_at_k(ranked, {i for i, g in grades.items() if g >= 1}, 10),
        "ndcg@10": ndcg_at_k(ranked, grades, 10),
        "recall@20": recall_at_k(ranked, {i for i, g in grades.items() if g == 2}, 20),
    }


def percentile(values: Sequence[float], q: float) -> float | None:
    if not values:
        return None
    s = sorted(values)
    return s[max(0, math.ceil(q * len(s)) - 1)]  # nearest rank


def _mean(values: list) -> float | None:
    vals = [v for v in values if v is not None]
    return sum(vals) / len(vals) if vals else None


def summarize(
    runs: list[dict], qrels: dict[str, dict[str, int]], queries: dict[str, dict]
) -> dict[str, dict]:
    out = {}
    for sl in SLICES:
        rows = [r for r in runs if sl == "all" or queries[r["query_id"]]["slice"] == sl]
        ok = [r for r in rows if not r.get("error")]
        per = [query_metrics(r["ranked"], qrels.get(r["query_id"], {})) for r in ok]
        lat = [r["latency_s"] for r in ok]
        out[sl] = {
            "n": len(ok),
            "errors": len(rows) - len(ok),
            **{m: _mean([p[m] for p in per]) for m in ("p@10", "ndcg@10", "recall@20")},
            "p50_s": percentile(lat, 0.5),
            "p95_s": percentile(lat, 0.95),
            "cost_usd": _mean([r.get("cost_usd", 0.0) for r in ok]),
        }
    return out


def _within(simple: float | None, rich: float | None, free: float) -> bool:
    if simple is None or rich is None:
        return True
    return rich <= 2 * simple or rich - simple < free


def keep_richer(simple: dict[str, dict], rich: dict[str, dict]) -> bool:
    """Keep the richer arm only if nDCG@10 gains >= 0.03 overall or on the vague slice, without
    more than doubling cost or p95 latency (small absolute increases always allowed)."""
    gain = any(
        simple[sl]["ndcg@10"] is not None
        and rich[sl]["ndcg@10"] is not None
        and rich[sl]["ndcg@10"] - simple[sl]["ndcg@10"] >= MIN_GAIN
        for sl in ("all", "vague")
    )
    return (
        gain
        and _within(simple["all"]["cost_usd"], rich["all"]["cost_usd"], FREE_COST_USD)
        and _within(simple["all"]["p95_s"], rich["all"]["p95_s"], FREE_LATENCY_S)
    )


def tune_tau(pairs: list[tuple[float, int]], keep: float = 0.9) -> float | None:
    """Highest rerank-score threshold that keeps >= `keep` of relevant (grade >= 1) dev candidates."""
    scores = sorted((s for s, g in pairs if g >= 1), reverse=True)
    return scores[math.ceil(keep * len(scores)) - 1] if scores else None


def pool_missing(
    runs_by_arm: dict[str, list[dict]],
    qrels: dict[str, dict[str, int]],
    depth: int = 10,
) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for runs in runs_by_arm.values():
        for r in runs:
            if r.get("error"):
                continue
            todo = out.setdefault(r["query_id"], [])
            for oid in r["ranked"][:depth]:
                if oid not in qrels.get(r["query_id"], {}) and oid not in todo:
                    todo.append(oid)
    return {q: ids for q, ids in out.items() if ids}


def run_arm(
    queries: list[dict], search_one: Callable[[dict], dict], *, max_usd: float
) -> list[dict]:
    """Run queries in order; stop before one more (as costly as the costliest so far) could exceed max_usd."""
    out: list[dict] = []
    spent: float = 0.0
    worst: float = 0.0
    for q in queries:
        if spent + worst > max_usd:
            out.append({"query_id": q["id"], "error": "skipped: eval budget reached"})
            continue
        start = time.monotonic()
        try:
            r = {"query_id": q["id"], **search_one(q)}
        except Exception as exc:  # reported, never hidden; its spend still counts
            r = {
                "query_id": q["id"],
                "error": f"{type(exc).__name__}: {exc}",
                "cost_usd": getattr(exc, "cost_usd", 0.0),
            }
        r["latency_s"] = time.monotonic() - start
        cost = float(r.get("cost_usd") or 0.0)
        spent, worst = spent + cost, max(worst, cost)
        out.append(r)
    return out


def load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    return [r for r in rows if "_meta" not in r]


def load_qrels(path: Path) -> dict[str, dict[str, int]]:
    out: dict[str, dict[str, int]] = {}
    for r in load_jsonl(path):
        out.setdefault(r["query_id"], {})[r["opportunity_id"]] = int(r["grade"])
    return out


FIXTURES = Path("evals/fixtures/discover_smoke")


def run_smoke() -> list[MetricResult]:
    """Scores saved runs against saved labels: checks the metric pipeline end to end at no cost."""
    queries = {q["id"]: q for q in load_jsonl(FIXTURES / "queries.jsonl")}
    runs = json.loads((FIXTURES / "runs.json").read_text(encoding="utf-8"))
    s = summarize(runs, load_qrels(FIXTURES / "qrels.jsonl"), queries)["all"]
    return [
        MetricResult("discover_smoke", "p@10", s["p@10"], 0.1),
        MetricResult("discover_smoke", "ndcg@10", s["ndcg@10"], 0.5),
    ]
