"""The Analyze agent as a local A2A service (M2 spec §3.9). Deploying it on Agent Runtime is M4.

Run: uv run uvicorn app.analyze.a2a_app:a2a_app --port 8001
"""

import os

from google.adk.a2a.utils.agent_to_a2a import to_a2a
from google.adk.agents import Agent
from google.adk.models import Gemini
from google.genai import types

from app.analyze.service import analyze_opportunity
from app.config import get_settings

A2A_PORT = 8001

# Run standalone (outside the playground), so point ADK's Gemini client at Vertex AI explicitly.
_settings = get_settings()
os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "TRUE")
os.environ.setdefault("GOOGLE_CLOUD_PROJECT", _settings.google_cloud_project)
os.environ.setdefault("GOOGLE_CLOUD_LOCATION", _settings.google_cloud_location)

analyze_agent = Agent(
    name="analyze_agent",
    description=(
        "Decides whether Lumen Grid Labs may apply to a funding opportunity and extracts its "
        "requirements, with page citations. Send: 'Analyze opportunity <uuid>.'"
    ),
    model=Gemini(
        model=_settings.model_agent,
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    instruction=(
        "Call analyze_opportunity with the opportunity ID from the request. Reply with only this JSON: "
        '{"opportunity_id": "<id>", "verdict": "<verdict exactly as returned>"}. '
        'If the tool returns no verdict, reply {"opportunity_id": "<id>", "verdict": "unchecked"}.'
    ),
    tools=[analyze_opportunity],
)

# 127.0.0.1, not localhost: clients require the card URL and the fetch origin to match,
# and "localhost" can resolve to IPv6 where uvicorn is not listening.
a2a_app = to_a2a(analyze_agent, host="127.0.0.1", port=A2A_PORT)
