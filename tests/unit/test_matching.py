from evals.matching import jaccard, match_count


def test_jaccard_basic():
    assert (
        jaccard(
            "Proposals shall not exceed 15 pages", "proposals shall not exceed 15 pages"
        )
        == 1.0
    )
    assert jaccard("a b", "c d") == 0.0


def test_match_requires_same_document_and_near_page():
    gold = [
        {
            "document_id": "d1",
            "page": 3,
            "text": "Proposals shall not exceed fifteen pages",
        }
    ]
    assert (
        match_count(
            gold,
            [
                {
                    "document_id": "d1",
                    "page": 4,
                    "text": "proposals shall not exceed fifteen pages",
                }
            ],
        )
        == 1
    )
    assert (
        match_count(
            gold,
            [
                {
                    "document_id": "d2",
                    "page": 3,
                    "text": "Proposals shall not exceed fifteen pages",
                }
            ],
        )
        == 0
    )
    assert (
        match_count(
            gold,
            [
                {
                    "document_id": "d1",
                    "page": 9,
                    "text": "Proposals shall not exceed fifteen pages",
                }
            ],
        )
        == 0
    )


def test_match_is_one_to_one():
    gold = [{"document_id": "d", "page": 1, "text": "submit a budget"}]
    pred = [{"document_id": "d", "page": 1, "text": "submit a budget"}] * 2
    assert match_count(gold, pred) == 1
