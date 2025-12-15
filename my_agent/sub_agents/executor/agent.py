from google.adk.agents import LlmAgent
from my_agent.sub_agents.executor.prompt import EXECUTOR_INSTRUCTION
from my_agent.tools.apis import grants_toolset, sbir_toolset, sam_toolset, usa_spending_toolset

executor_agent = LlmAgent(
    model='gemini-2.5-flash',
    name='search_executor',
    description="Executes planned searches using Simpler Grants API and SBIR.gov API",
    tools=[
        grants_toolset,
        sbir_toolset,
        sam_toolset,
        usa_spending_toolset
    ],
    instruction=EXECUTOR_INSTRUCTION + """
    
    **CRITICAL API USAGE RULES:**
    
    1. **Grants.gov (searchOpportunities):**
       - `query` MUST be less than 100 characters. TRUNCATE if necessary.
       - `pagination` is REQUIRED. You MUST send `{"pagination": {"page_offset": 1, "page_size": 25}, "query": "..."}`
    
    2. **USAspending.gov (searchSpendingByAward):**
       - `keywords` MUST be a list of strings, NOT a single string. Example: `["energy", "solar"]`.
       - `award_type_codes` is REQUIRED. Always send `["A", "B", "C", "D"]` unless specified otherwise.
       
    3. **SAM.gov:**
       - Ensure `postedFrom` and `postedTo` are always included and formatted MM/dd/yyyy.
    """
)
