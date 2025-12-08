from google.adk.agents import LlmAgent
from my_agent.sub_agents.verifier.prompt import VERIFIER_INSTRUCTION
from my_agent.tools.verification import exit_verification_loop
from my_agent.tools.advanced_search import check_eligibility_semantic, get_competitor_intelligence

verifier_agent = LlmAgent(
    model='gemini-2.5-flash',
    name='result_verifier',
    description="Verifies search results meet quality criteria and match user intent",
    tools=[exit_verification_loop, check_eligibility_semantic, get_competitor_intelligence],
    instruction=VERIFIER_INSTRUCTION
)
