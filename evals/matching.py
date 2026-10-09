"""Text matching for clause and requirement metrics (M1 spec §7)."""

import re


def tokens(s: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", (s or "").lower()))


def jaccard(a: str, b: str) -> float:
    ta, tb = tokens(a), tokens(b)
    if not ta and not tb:
        return 1.0
    return len(ta & tb) / len(ta | tb)


def match_count(gold: list[dict], pred: list[dict], *, threshold: float = 0.6) -> int:
    used: set[int] = set()
    matched = 0
    for g in gold:
        best, best_score = None, threshold
        for i, p in enumerate(pred):
            if (
                i in used
                or str(p["document_id"]) != str(g["document_id"])
                or abs(p["page"] - g["page"]) > 1
            ):
                continue
            score = jaccard(g["text"], p["text"])
            if score >= best_score:
                best, best_score = i, score
        if best is not None:
            used.add(best)
            matched += 1
    return matched
