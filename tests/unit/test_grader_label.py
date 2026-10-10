from fastapi.testclient import TestClient

from evals.grader_label import kappas, make_app, sample_pairs

TASKS = {"T": {"id": "T", "requirements": [{"id": "R1", "text": "lab"}]}}
SECTIONS = [
    {
        "task_id": "T",
        "retrieval_trace": [
            {
                "requirement_id": "R1",
                "query": "q",
                "chunk_ids": [f"c{i}" for i in range(9)],
                "grades": ["relevant"] * 3 + ["partly"] * 3 + ["not"] * 3,
            }
        ],
    }
]
TEXT = {f"c{i}": f"text {i}" for i in range(9)}


def test_sample_is_stratified_and_hides_nothing_needed():
    pairs = sample_pairs(SECTIONS, TEXT, TASKS, n=6)
    assert sorted(p["grader"] for p in pairs) == [
        "not",
        "not",
        "partly",
        "partly",
        "relevant",
        "relevant",
    ]
    assert pairs[0]["requirement"] == "lab" and pairs[0]["text"].startswith("text")


def test_kappas_3class_and_binary():
    pairs = [
        {"pair_id": i, "grader": g}
        for i, g in enumerate(["relevant", "partly", "not", "not"])
    ]
    k = kappas(pairs, {0: "relevant", 1: "partly", 2: "not", 3: "partly"})
    assert k["n"] == 4 and 0 < k["kappa_3"] < 1 and k["kappa_binary"] == 1.0


def test_label_page_hides_grader_label_and_saves(tmp_path):
    import json

    pp, lp = tmp_path / "pairs.json", tmp_path / "labels.jsonl"
    pp.write_text(
        json.dumps(sample_pairs(SECTIONS, TEXT, TASKS, n=3)), encoding="utf-8"
    )
    c = TestClient(make_app(pp, lp))
    shown = c.get("/api/pairs").json()
    assert "grader" not in shown[0] and c.get("/").status_code == 200
    assert (
        c.post(
            "/api/label", json={"pair_id": shown[0]["pair_id"], "label": "partly"}
        ).status_code
        == 200
    )
    assert (
        c.post(
            "/api/label", json={"pair_id": shown[0]["pair_id"], "label": "maybe"}
        ).status_code
        == 422
    )
    assert (
        json.loads(lp.read_text(encoding="utf-8").splitlines()[0])["label"] == "partly"
    )
