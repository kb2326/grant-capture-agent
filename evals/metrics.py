"""Plain metric functions. No model calls, so they are deterministic and unit-tested."""

import math
from collections import Counter
from collections.abc import Hashable, Sequence


def precision_recall(predicted: set, actual: set) -> tuple[float, float]:
    tp = len(predicted & actual)
    precision = (1.0 if not actual else 0.0) if not predicted else tp / len(predicted)
    recall = 1.0 if not actual else tp / len(actual)
    return precision, recall


def precision_at_k(ranked: Sequence[str], relevant: set[str], k: int) -> float:
    return sum(1 for item in ranked[:k] if item in relevant) / k


def ndcg_at_k(ranked: Sequence[str], gains: dict[str, int], k: int) -> float:
    def dcg(values: Sequence[int]) -> float:
        return sum((2**g - 1) / math.log2(i + 2) for i, g in enumerate(values))

    actual = dcg([gains.get(item, 0) for item in ranked[:k]])
    ideal = dcg(sorted(gains.values(), reverse=True)[:k])
    return 0.0 if ideal == 0 else actual / ideal


def cohen_kappa(a: Sequence[Hashable], b: Sequence[Hashable]) -> float:
    if len(a) != len(b) or not a:
        raise ValueError("label lists must be non-empty and the same length")
    n = len(a)
    observed = sum(x == y for x, y in zip(a, b, strict=True)) / n
    ca, cb = Counter(a), Counter(b)
    expected = sum(ca[label] * cb[label] for label in ca.keys() | cb.keys()) / (n * n)
    return 1.0 if expected == 1 else (observed - expected) / (1 - expected)
