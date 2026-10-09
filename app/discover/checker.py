"""V4 eligibility checks behind one interface: in-process call or the Analyze A2A service (M2 spec §3.9)."""

import asyncio
import concurrent.futures
import json
import logging
import re
import uuid
from collections.abc import Callable
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from db.models import EligibilityVerdictRow

log = logging.getLogger(__name__)
_VERDICT = re.compile(r'"?verdict"?\s*[:=]\s*"?(ELIGIBLE|INELIGIBLE|NEEDS_REVIEW)\b')


def parse_verdict(text: str) -> str:
    m = _VERDICT.search(text or "")
    return m.group(1) if m else "unchecked"


class EligibilityChecker(Protocol):
    cost_usd: float

    def check(self, opportunity_id: uuid.UUID) -> str: ...


class DirectChecker:
    def __init__(self, analyze: Callable[..., dict] | None = None) -> None:
        self.analyze, self.cost_usd = analyze, 0.0

    def check(self, opportunity_id: uuid.UUID) -> str:
        fn = self.analyze
        if fn is None:
            from app.analyze.service import analyze_opportunity

            fn = analyze_opportunity
        try:
            out = fn(str(opportunity_id))
        except Exception as exc:
            log.warning("direct eligibility check failed: %s", exc)
            return "unchecked"
        self.cost_usd += float(out.get("cost_usd") or 0.0)
        return parse_verdict(json.dumps(out))


async def _send_a2a(url: str, text: str, timeout: float) -> str:
    from google.adk.agents.remote_a2a_agent import (
        AGENT_CARD_WELL_KNOWN_PATH,
        RemoteA2aAgent,
    )
    from google.adk.runners import InMemoryRunner
    from google.genai import types

    agent = RemoteA2aAgent(
        name="analyze_remote",
        agent_card=url.rstrip("/") + AGENT_CARD_WELL_KNOWN_PATH,
        timeout=timeout,
    )
    runner = InMemoryRunner(agent=agent, app_name="discover_v4")
    session = await runner.session_service.create_session(
        app_name="discover_v4", user_id="discover"
    )
    parts: list[str] = []
    message = types.Content(role="user", parts=[types.Part.from_text(text=text)])
    async for event in runner.run_async(
        user_id="discover", session_id=session.id, new_message=message
    ):
        for p in event.content.parts if event.content and event.content.parts else []:
            if p.text:
                parts.append(p.text)
            if p.function_response:
                parts.append(json.dumps(p.function_response.response, default=str))
    return "\n".join(parts)


def _send_blocking(url: str, text: str, timeout: float) -> str:
    # Own thread and event loop: callers may already be inside ADK's running loop.
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, _send_a2a(url, text, timeout)).result(
            timeout=timeout + 10
        )


class A2AChecker:
    def __init__(
        self,
        url: str,
        timeout: float = 120.0,
        send: Callable[[str, str, float], str] | None = None,
    ) -> None:
        self.url, self.timeout = url, timeout
        self.send = send or _send_blocking
        self.cost_usd = 0.0  # billed by the Analyze service, not visible here

    def check(self, opportunity_id: uuid.UUID) -> str:
        try:
            reply = self.send(
                self.url, f"Analyze opportunity {opportunity_id}.", self.timeout
            )
        except Exception as exc:  # service down or slow: keep the candidate, unchecked
            log.warning("A2A eligibility check failed: %s", exc)
            return "unchecked"
        return parse_verdict(reply)


def make_checker(settings: Settings) -> EligibilityChecker:
    if settings.discover_v4_transport == "a2a":
        return A2AChecker(settings.analyze_a2a_url)
    return DirectChecker()


def cached_verdicts(
    session: Session, company_id: uuid.UUID, ids: list[uuid.UUID]
) -> dict[uuid.UUID, str]:
    rows = session.execute(
        select(
            EligibilityVerdictRow.opportunity_id, EligibilityVerdictRow.verdict
        ).where(
            EligibilityVerdictRow.company_id == company_id,
            EligibilityVerdictRow.opportunity_id.in_(ids),
        )
    )
    return {r.opportunity_id: r.verdict for r in rows}
