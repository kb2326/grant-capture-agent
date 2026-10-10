"""Opportunity cards: the one piece of text per opportunity that Discover searches (M2 spec §3.1)."""

import hashlib
import re

from bs4 import BeautifulSoup
from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models import OpportunityCardRow, OpportunityRow

MAX_CARD_CHARS = 8_000  # ≈ 2,000 tokens at 4 characters per token


def _plain(html: str) -> str:
    text = BeautifulSoup(html or "", "html.parser").get_text(" ")
    return re.sub(r"\s+", " ", text).strip()


def card_text(opp) -> str:
    parts = [
        opp.title,
        opp.agency,
        opp.kind,
        opp.status,
        f"closes {opp.close_at.isoformat() if opp.close_at else 'none'}",
    ]
    if opp.assistance_listings:
        parts.append("AL " + ", ".join(opp.assistance_listings))
    if opp.naics:
        parts.append("NAICS " + ", ".join(opp.naics))
    return (" | ".join(parts) + "\n" + _plain(opp.summary))[:MAX_CARD_CHARS]


def card_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def build_cards(session: Session) -> dict[str, int]:
    """Create or refresh every card. A changed card loses its embeddings so it is re-embedded."""
    stats = {"created": 0, "updated": 0, "unchanged": 0}
    existing = {
        r.opportunity_id: r for r in session.scalars(select(OpportunityCardRow))
    }
    for opp in session.scalars(select(OpportunityRow)):
        text = card_text(opp)
        h = card_hash(text)
        row = existing.get(opp.id)
        if row is None:
            session.add(
                OpportunityCardRow(opportunity_id=opp.id, text=text, text_hash=h)
            )
            stats["created"] += 1
        elif row.text_hash != h:
            row.text, row.text_hash, row.emb_gemini, row.emb_local = text, h, None, None
            stats["updated"] += 1
        else:
            stats["unchanged"] += 1
    session.commit()
    return stats
