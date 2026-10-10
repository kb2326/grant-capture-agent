# ruff: noqa
# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from google.adk.agents import Agent
from google.adk.apps import App
from google.adk.models import Gemini
from google.genai import types
import logging
from google.adk.plugins.bigquery_agent_analytics_plugin import (
    BigQueryAgentAnalyticsPlugin,
    BigQueryLoggerConfig,
)
from google.cloud import bigquery

from app.analyze.qa import ask_solicitation
from app.analyze.service import analyze_opportunity
from app.config import get_settings
from app.discover.tools import find_opportunities, remembered_preferences
from app.draft.tools import draft_section


MODEL = get_settings().model_agent


root_agent = Agent(
    # Keep in sync with agents-cli-manifest.yaml: agents-cli derives this name
    # from the project `name:` recorded there, and telemetry reports it as
    # gen_ai.agent.name. Renaming the agent only here makes the two disagree,
    # and anything selecting traces by name stops finding this agent's.
    name="grant_capture_agent",
    model=Gemini(
        model=MODEL,
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    instruction=(
        "You are the grant-capture assistant for a small R&D company (Lumen Grid Labs). "
        "To find opportunities, call find_opportunities with the user's request; show each result's title, agency, "
        "close date, eligibility and why, and mention the search plan it used. "
        "To decide whether the company may apply and what a solicitation requires, call analyze_opportunity "
        "with the opportunity ID. For follow-up questions about a solicitation, call ask_solicitation. "
        "To see what the company asked you to remember, call remembered_preferences. "
        "Report verdicts exactly as returned, quote deciding clauses with their pages, and never invent "
        "eligibility rules. To draft a proposal section for an analyzed opportunity, call draft_section; "
        "always show its notice, its AI-use warnings and its gaps."
    ),
    tools=[
        find_opportunities,
        analyze_opportunity,
        ask_solicitation,
        draft_section,
        remembered_preferences,
    ],
)
import os

# Initialize BigQuery Analytics
_plugins = []
_project_id = os.environ.get("GOOGLE_CLOUD_PROJECT")
_dataset_id = os.environ.get("BQ_ANALYTICS_DATASET_ID", "adk_agent_analytics")
_location = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")

if _project_id:
    try:
        bq = bigquery.Client(project=_project_id)
        bq.create_dataset(f"{_project_id}.{_dataset_id}", exists_ok=True)

        _plugins.append(
            BigQueryAgentAnalyticsPlugin(
                project_id=_project_id,
                dataset_id=_dataset_id,
                location=_location,
                config=BigQueryLoggerConfig(
                    gcs_bucket_name=os.environ.get("BQ_ANALYTICS_GCS_BUCKET"),
                    connection_id=os.environ.get("BQ_ANALYTICS_CONNECTION_ID"),
                ),
            )
        )
    except Exception as e:
        logging.warning(f"Failed to initialize BigQuery Analytics: {e}")

app = App(
    root_agent=root_agent,
    name="app",
    plugins=_plugins,
)
