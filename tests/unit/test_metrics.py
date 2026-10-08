import pytest

from evals.metrics import cohen_kappa, ndcg_at_k, precision_at_k, precision_recall


def test_precision_recall_including_empty_edges():
    assert precision_recall({"a", "b"}, {"b", "c"}) == (0.5, 0.5)
    assert precision_recall(set(), set()) == (1.0, 1.0)
    assert precision_recall(set(), {"a"}) == (0.0, 0.0)
    assert precision_recall({"a"}, set()) == (0.0, 1.0)


def test_precision_at_k_divides_by_k():
    assert precision_at_k(["a", "x", "b"], {"a", "b"}, k=3) == pytest.approx(2 / 3)
    assert precision_at_k(["a"], {"a"}, k=10) == pytest.approx(0.1)


def test_ndcg_hand_computed():
    # dcg = 0 + 3/log2(3) + 1/2 = 2.3928 ; idcg = 3 + 1/log2(3) = 3.6309
    assert ndcg_at_k(["a", "b", "c"], {"a": 0, "b": 2, "c": 1}, k=3) == pytest.approx(
        0.6590, abs=1e-3
    )
    assert ndcg_at_k(["a"], {"a": 0}, k=5) == 0.0


def test_cohen_kappa_hand_computed():
    assert cohen_kappa([1, 1, 0, 0], [1, 0, 0, 0]) == pytest.approx(0.5)
    assert cohen_kappa(["x", "x"], ["x", "x"]) == 1.0
    with pytest.raises(ValueError):
        cohen_kappa([1], [1, 0])
