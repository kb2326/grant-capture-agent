"""The Analyze agent as a local A2A service (M2 spec §3.9). Deploying it on Agent Runtime is M4.

Run: uv run uvicorn app.analyze.a2a_app:a2a_app --port 8001
"""

from google.adk.a2a.utils.agent_to_a2a import to_a2a
from google.adk.agents import Agent
from google.adk.models import Gemini
from google.genai import types

from app.analyze.service import analyze_opportunity
from app.config import get_settings

A2A_PORT = 8001

analyze_agent = Agent(
    name="analyze_agent",
    description=(
        "Decides whether Lumen Grid Labs may apply to a funding opportunity and extracts its "
        "requirements, with page citations. Send: 'Analyze opportunity <uuid>.'"
    ),
    model=Gemini(
        model=get_settings().model_agent,
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    instruction=(
        "Call analyze_opportunity with the opportunity ID from the request. Reply with only this JSON: "
        '{"opportunity_id": "<id>", "verdict": "<verdict exactly as returned>"}. '
        'If the tool returns no verdict, reply {"opportunity_id": "<id>", "verdict": "unchecked"}.'
    ),
    tools=[analyze_opportunity],
)

a2a_app = to_a2a(analyze_agent, port=A2A_PORT)
