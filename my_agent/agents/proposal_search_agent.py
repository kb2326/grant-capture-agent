"""
PEV (Plan-Execute-Verify) Architecture for Grants Discovery Agent

This implementation uses a three-agent system:
1. Planner: Analyzes user query and creates structured search plan
2. Executor: Executes the planned searches using API tools
3. Verifier: Validates results and determines if retry is needed

The agents work in a loop until verification passes or max iterations reached.
"""
import json
import os
from dotenv import load_dotenv
from google.adk.agents import LlmAgent, SequentialAgent, LoopAgent
from google.adk.tools.openapi_tool.auth.auth_helpers import token_to_scheme_credential
from google.adk.tools.openapi_tool.openapi_spec_parser.openapi_toolset import OpenAPIToolset
from google.adk.tools import ToolContext
import datetime
from pathlib import Path
import docx


load_dotenv()

# Get API key from environment
API_KEY = os.getenv("GRANTS_API_KEY", "")

# Load Simpler Grants API OpenAPI specification
grants_spec_path = os.path.join(os.path.dirname(__file__), "data", "openapi_minimal.json")
with open(grants_spec_path, "r") as f:
    grants_spec = json.load(f)

# Load SBIR.gov API OpenAPI specification
sbir_spec_path = os.path.join(os.path.dirname(__file__), "data", "sbir_openapi.json")
with open(sbir_spec_path, "r") as f:
    sbir_spec = json.load(f)

# Create Simpler Grants toolset with authentication
grants_spec_str = json.dumps(grants_spec)

if API_KEY:
    auth_scheme, auth_credential = token_to_scheme_credential(
        "apikey", "header", "X-API-Key", API_KEY
    )
    grants_toolset = OpenAPIToolset(
        spec_str=grants_spec_str,
        spec_str_type='json',
        auth_scheme=auth_scheme,
        auth_credential=auth_credential,
    )
else:
    grants_toolset = OpenAPIToolset(
        spec_str=grants_spec_str,
        spec_str_type='json',
    )

# Create SBIR.gov toolset (no authentication required)
sbir_spec_str = json.dumps(sbir_spec)
sbir_toolset = OpenAPIToolset(
    spec_str=sbir_spec_str,
    spec_str_type='json',
)

# Define exit loop tool for verification
from typing import Optional
def exit_verification_loop(tool_context: ToolContext, output_data: Optional[dict] = None):
    """Call this to exit the verification loop.
    
    Args:
        output_data: Optional dictionary containing results or response to pass forward.
    """
    print(f"[Verification] Exiting loop")
    tool_context.actions.escalate = True
    return {"status": "loop_exited", "output_data": output_data}

def load_capabilities(file_path: str) -> str:
    """Loads company capabilities from a file (supports .txt and .docx)."""
    try:
        path = Path(file_path)
        if not path.exists():
            return "Error: File not found."
            
        if path.suffix.lower() == '.docx':
            doc = docx.Document(file_path)
            return "\n".join([para.text for para in doc.paragraphs])
        else:
            # Default to text
            return path.read_text(encoding='utf-8')
    except Exception as e:
        return f"Error loading capabilities: {str(e)}"

# Define tool for the agent to use directly
def read_capabilities_doc(file_path: str) -> str:
    """Reads a company capabilities document (txt or docx) and returns the content.
    
    Args:
        file_path: Absolute path to the capabilities document.
    """
    return load_capabilities(file_path)


#This agent is the main agent that will be used to search for grants
# ============================================================================
# AGENT 1: PLANNER
# ============================================================================
planner_agent = LlmAgent(
    model='gemini-2.5-flash',
    name='query_planner',
    description="Analyzes user queries and creates structured search plans for grant discovery",
    tools=[read_capabilities_doc],
    instruction="""You are a Strategic Grant Proposal Planner for a specific company.

**Context:**
- **Company Capabilities:** You need to understand the company's expertise. 
  - If the user provides a file path to a capabilities document (txt or docx), USE the `read_capabilities_doc` tool to read it immediately.
  - If the capabilities are already in the conversation history, use them.
  - You MUST align all search plans with these capabilities.
- **Current Date:** Use the current date to identify "new" or "daily" opportunities.

**Your Role:**
Analyze the User's Query AND the Company Capabilities to create a highly targeted search plan.

**Query Analysis & Strategy:**

1.  **Analyze Capabilities:**
    - Extract key technologies, methodologies, and domain expertise from the Company Capabilities.
    - Identify the company's "sweet spot" (e.g., "AI for healthcare," "Drone swarms for defense").

2.  **Analyze Request:**
    - If "Daily" or "New": Focus on opportunities posted in the last 24-48 hours.
    - If "General Search": Focus on overall alignment.

3.  **Determine Search Strategy:**
    - **Keywords:** Generate specific, technical keywords derived from the capabilities (not just generic terms).
    - **Filters:**
        - **Grants API:** Use `sort_order` = `post_date` (descending) for daily checks. Use `applicant_type` matching the company (e.g., small_business).
        - **SBIR API:** Filter by relevant agencies and `open=1`.

**Output Plan (JSON):**

```json
{
  "analysis": {
    "company_focus": "Brief summary of what the company does",
    "search_intent": "daily_update" or "deep_dive",
    "key_terms": ["term1", "term2"]
  },
  "search_plan": {
    "searches": [
      {
        "api": "grants",
        "query": "technical keyword",
        "filters": {
          "opportunity_status": {"one_of": ["posted"]},
          "applicant_type": {"one_of": ["small_businesses"]},
           "sort_order": [{"order_by": "post_date", "sort_direction": "descending"}]
        },
        "reason": "Matches company capability X"
      },
      {
        "api": "sbir",
        "keyword": "technical keyword",
        "open": 1,
        "reason": "Matches company capability Y"
      }
    ]
  },
  "verification_criteria": "Strictly match results to: [Insert Key Capabilities Summary]"
}
```

**Handling Non-Search Queries:**
If the user's query is NOT about finding grants (e.g., "who are you", "hello", "help", "what can you do"), do NOT create a search plan. Instead, output a direct response JSON:
```json
{
  "is_chitchat": true,
  "direct_response": "I am the Grant Discovery Agent. I have analyzed your company's capabilities and am ready to find aligned funding opportunities. How can I help?"
}
```
"""
)


# ============================================================================
# AGENT 2: EXECUTOR
# ============================================================================
executor_agent = LlmAgent(
    model='gemini-2.5-flash',
    name='search_executor',
    description="Executes planned searches using Simpler Grants API and SBIR.gov API",
    tools=[grants_toolset, sbir_toolset],
    instruction="""You are a High-Performance Search Executor.

**Your Role:**
Execute the search plan with maximum efficiency.

**Execution Rules:**
1.  **Follow the Plan:** Execute every search defined in the `search_plan`.
2.  **Optimize for Daily/New:** If the plan includes `sort_order` for `post_date`, ensure you pass that correctly to the `searchOpportunities` tool.
3.  **Parallel Execution:** If multiple searches are independent, you can execute them in parallel (by generating multiple tool calls in one turn if supported, or sequentially if not).
4.  **Error Resilience:** If one API fails, log the error but continue with the others. Do not stop.

**Tool Call Guidelines:**
- **Grants API (`searchOpportunities`):**
  - Ensure `pagination` is set (e.g., page_size=25).
  - If `sort_order` is provided in the plan, USE IT. This is critical for finding "new" grants.
- **SBIR API (`searchSBIRSolicitations`):**
  - Use `open=1` to find active solicitations.

**Output:**
Return a JSON summary of all results, grouped by source.
"""
)


# ============================================================================
# AGENT 3: VERIFIER
# ============================================================================
verifier_agent = LlmAgent(
    model='gemini-2.5-flash',
    name='result_verifier',
    description="Verifies search results meet quality criteria and match user intent",
    tools=[exit_verification_loop],
    instruction="""You are a Strict Quality Verifier for Company Alignment.

**Your Role:**
Filter and verify search results against the Company Capabilities.

**Verification Process:**
1.  **Read Context:**
    - User Query
    - Company Capabilities (from conversation history)
    - Search Results

2.  **Evaluate Each Result:**
    - **Alignment Score (0-100):** How well does this grant match the company's specific expertise?
    - **Freshness Check:** If the user asked for "daily" or "new", is the `post_date` recent (e.g., last 7 days)?

3.  **Decision:**
    - **PASS:** Found at least 1 high-quality match (>80 score).
    - **FAIL:** No high-quality matches found. Need to refine search terms.

**Output:**
- **If PASS:**
  - Generate a "Daily Briefing" style response.
  - "Found [X] new opportunities aligned with [Company Capability Y]:"
  - List top results with Title, Agency, Deadline, and *Why it matches*.
  - Call `exit_verification_loop()`.
- **If FAIL:**
  - Return JSON feedback explaining *why* (e.g., "Results were too generic," "No results matched 'Drone Swarm' capability").
  - Do NOT call exit.

**Chitchat:**
- If input has `"is_chitchat": true`, output response and call `exit_verification_loop()`.
"""
)


# ============================================================================
# PEV ORCHESTRATION
# ============================================================================

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

if __name__ == "__main__":
    import asyncio
    from google.adk import Runner
    
    async def main():
        print("Grant Discovery Agent (Company-Aware & Daily Optimized)")
        print("-------------------------------------------------------")
        
        # 1. Load Capabilities
        caps_path = input("Enter path to Company Capabilities doc (or press Enter to skip): ").strip()
        company_caps = "No specific company capabilities provided."
        if caps_path:
            company_caps = load_capabilities(caps_path)
            print(f"✅ Loaded capabilities from {caps_path}")
        
        # 2. Get Query
        query = input("Enter your search query (e.g., 'Find daily new grants'): ")
        
        # 3. Inject Context
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        context_message = (
            f"Current Date: {today}\n"
            f"User Query: {query}\n"
            f"Company Capabilities Document:\n{company_caps}\n"
        )

        runner = Runner(agent=root_agent)
        print("\nProcessing... (this may take a minute)\n")
        
        async for event in runner.run_async(user_id="cli_user", session_id="cli_session", new_message=context_message):
            if event.agent_name == "query_planner":
                print(f"📋 [PLANNER] Analyzing capabilities and planning...")
            elif event.agent_name == "search_executor":
                print(f"🔍 [EXECUTOR] Executing optimized searches...")
            elif event.agent_name == "result_verifier":
                if event.content.strip().startswith("{"):
                    print(f"✅ [VERIFIER] Checking alignment (Feedback Loop)...")
                else:
                    print(f"\n🤖 [RESPONSE]:\n{event.content}\n")

    asyncio.run(main())
