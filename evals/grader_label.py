"""Calibrate the Flash-Lite grader against the user's own labels (M3 spec §4.2). Never shows the grader's label.

uv run python -m evals.grader_label   ->  http://127.0.0.1:8766
"""

import json
import random
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from evals.metrics import cohen_kappa

PAIRS = Path("reports/m3/grader_pairs.json")
LABELS = Path("evals/data/golden/grader_labels.jsonl")


def sample_pairs(
    sections: list[dict],
    chunk_text: dict[str, str],
    tasks: dict[str, dict],
    n: int = 40,
    seed: int = 20261010,
) -> list[dict]:
    seen, by_grade = set(), {"relevant": [], "partly": [], "not": []}
    for s in sections:
        reqs = {r["id"]: r["text"] for r in tasks[s["task_id"]]["requirements"]}
        for t in s["retrieval_trace"]:
            for cid, grade in zip(t["chunk_ids"], t["grades"], strict=True):
                key = (s["task_id"], t["requirement_id"], cid)
                if grade in by_grade and key not in seen and cid in chunk_text:
                    seen.add(key)
                    by_grade[grade].append(
                        {
                            "task_id": s["task_id"],
                            "requirement_id": t["requirement_id"],
                            "requirement": reqs[t["requirement_id"]],
                            "chunk_id": cid,
                            "text": chunk_text[cid],
                            "grader": grade,
                        }
                    )
    rng, out = random.Random(seed), []
    per = {g: n // 3 + (1 if i < n % 3 else 0) for i, g in enumerate(by_grade)}
    for g, items in by_grade.items():
        out += rng.sample(items, min(per[g], len(items)))
    rng.shuffle(out)
    return [{**p, "pair_id": i} for i, p in enumerate(out)]


def kappas(pairs: list[dict], labels: dict[int, str]) -> dict:
    both = [
        (p["grader"], labels[p["pair_id"]]) for p in pairs if p["pair_id"] in labels
    ]
    if not both:
        return {"kappa_3": None, "kappa_binary": None, "n": 0}
    g, h = zip(*both, strict=True)

    def binary(xs):
        return [x == "relevant" for x in xs]

    return {
        "kappa_3": cohen_kappa(g, h),
        "kappa_binary": cohen_kappa(binary(g), binary(h)),
        "n": len(both),
    }


class Label(BaseModel):
    pair_id: int
    label: Literal["relevant", "partly", "not"]


def make_app(pairs_path: Path = PAIRS, labels_path: Path = LABELS) -> FastAPI:
    app = FastAPI()
    ui = (Path(__file__).parent / "grader_label_ui.html").read_text(encoding="utf-8")

    def pairs():
        return json.loads(pairs_path.read_text(encoding="utf-8"))

    @app.get("/", response_class=HTMLResponse)
    def page():
        return ui

    @app.get("/api/pairs")
    def get_pairs():
        return [{k: v for k, v in p.items() if k != "grader"} for p in pairs()]

    @app.post("/api/label")
    def post_label(item: Label):
        if item.pair_id not in {p["pair_id"] for p in pairs()}:
            raise HTTPException(404, "unknown pair")
        labels_path.parent.mkdir(parents=True, exist_ok=True)
        with labels_path.open("a", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(item.model_dump()) + "\n")
        return {"ok": True}

    return app


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(make_app(), host="127.0.0.1", port=8766)
