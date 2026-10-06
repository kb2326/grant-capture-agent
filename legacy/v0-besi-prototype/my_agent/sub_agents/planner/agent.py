from google.adk.agents import LlmAgent
from my_agent.tools.capabilities import read_capabilities_doc
from my_agent.tools.verification import exit_verification_loop, ask_user_approval
from my_agent.sub_agents.planner.prompt import PLANNER_INSTRUCTION

planner_agent = LlmAgent(
    model='gemini-2.5-flash',
    name='query_planner',
    description="Analyzes user queries and creates structured search plans for grant discovery",
    tools=[read_capabilities_doc, exit_verification_loop, ask_user_approval],
    instruction=PLANNER_INSTRUCTION
)
