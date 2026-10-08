from google.adk.agents import LoopAgent
from my_agent.sub_agents.planner.agent import planner_agent
from my_agent.sub_agents.executor.agent import executor_agent
from my_agent.sub_agents.verifier.agent import verifier_agent

# Create the PEV loop: Planner -> Executor -> Verifier (with retry capability)
pev_loop = LoopAgent(
    name="PEV_Loop",
    sub_agents=[planner_agent, executor_agent, verifier_agent],
    max_iterations=3,  # Allow up to 3 attempts to get satisfactory results
    description="Plan-Execute-Verify loop for grant search with quality assurance"
)

# Main PEV agent sequence
# Root is now just the loop, as Verifier handles formatting
root_agent = pev_loop
