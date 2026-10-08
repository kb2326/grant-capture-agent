from google.adk.agents import LlmAgent

from my_agent.sub_agents.executor.prompt import EXECUTOR_INSTRUCTION
from my_agent.tools.apis import grants_toolset, sbir_toolset

executor_agent = LlmAgent(
    model="gemini-2.5-flash",
    name="search_executor",
    description="Executes planned searches using Simpler Grants API and SBIR.gov API",
    tools=[grants_toolset, sbir_toolset],
    instruction=EXECUTOR_INSTRUCTION,
)
