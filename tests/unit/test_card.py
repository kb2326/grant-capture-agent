from datetime import date
from types import SimpleNamespace

from rag.card import MAX_CARD_CHARS, card_hash, card_text


def _opp(**over):
    base = dict(
        title="Grid-forming inverter controls",
        agency="DOE",
        kind="sbir",
        status="open",
        close_at=date(2026, 12, 1),
        assistance_listings=["81.049"],
        naics=["541715"],
        summary="<p>Develop <b>SiC</b> converters.</p>\n\n  More.",
    )
    base.update(over)
    return SimpleNamespace(**base)


def test_card_text_has_header_and_plain_summary():
    t = card_text(_opp())
    assert t.startswith(
        "Grid-forming inverter controls | DOE | sbir | open | closes 2026-12-01 | AL 81.049 | NAICS 541715\n"
    )
    assert "Develop SiC converters. More." in t and "<" not in t


def test_card_text_truncates_and_handles_missing_fields():
    t = card_text(
        _opp(summary="x " * 10_000, close_at=None, assistance_listings=[], naics=[])
    )
    assert "closes none" in t and len(t) <= MAX_CARD_CHARS
    assert "AL " not in t and "NAICS" not in t


def test_card_hash_is_stable():
    assert card_hash("a") == card_hash("a") != card_hash("b")
