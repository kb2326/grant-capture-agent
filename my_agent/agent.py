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


# ============================================================================
# AGENT 1: PLANNER
# ============================================================================
planner_agent = LlmAgent(
    model='gemini-2.5-flash',
    name='query_planner',
    description="Analyzes user queries and creates structured search plans for grant discovery",
    instruction="""You are a Query Planning Expert for federal grants and SBIR/STTR solicitations.

**Your Role:**
Analyze the user's query and create a detailed, structured search plan that the Executor will follow.

**Available Data Sources:**
1. **Simpler Grants API** - General federal grants (all agencies, all types)
2. **SBIR.gov API** - SBIR/STTR specific solicitations with detailed topics

**Query Analysis Steps:**

1. **Identify Key Elements:**
   - Topic/Keywords (e.g., "AI", "quantum computing", "clean energy")
   - Grant Type (SBIR, STTR, general grants, research, education)
   - Applicant Type (small business, university, nonprofit, individual)
   - Agency (NASA, NSF, NIH, DOD, DOE, etc.)
   - Status (open, closed, forecasted)
   - Geographic constraints (if any)
   - Funding requirements (if mentioned)

2. **Determine Search Strategy:**
   - Which API(s) to use (Simpler Grants, SBIR.gov, or both)
   - Whether multiple searches are needed (e.g., multiple topics)
   - What filters to apply
   - Search priority order

3. **Create Structured Plan:**

Output your plan in this JSON format:
```json
{
  "query_analysis": {
    "user_intent": "Brief description of what user wants",
    "topics": ["topic1", "topic2"],
    "grant_types": ["SBIR", "general"],
    "applicant_types": ["small_businesses", "universities"],
    "agencies": ["NASA", "NSF"],
    "status_filter": "open"
  },
  "search_plan": {
    "use_sbir_api": true/false,
    "use_grants_api": true/false,
    "searches": [
      {
        "api": "sbir" or "grants",
        "query": "search query string",
        "filters": {
          "agency": ["NASA"],
          "applicant_type": ["small_businesses"],
          "open": 1
        },
        "reason": "Why this search is needed"
      }
    ]
  },
  "expected_results": "What kind of results we expect to find",
  "quality_criteria": "How to verify results are good (for Verifier)"
}
```

**Planning Rules:**

- For SBIR/STTR queries: Use BOTH APIs (SBIR.gov for detailed topics, Grants API for comprehensive coverage)
- For multiple topics: Create separate searches per topic, then combine
- For broad queries: Start with general search, can refine if needed
- For agency-specific: Apply agency filter to both APIs
- For applicant type: Use appropriate filters (small_businesses, universities, nonprofits)
- Default to open/posted opportunities unless user asks for closed/archived

**Examples:**

User: "Find SBIR grants for artificial intelligence"
Plan:
- Use BOTH APIs (SBIR.gov + Grants API)
- Search 1: SBIR.gov with keyword="artificial intelligence", open=1
- Search 2: Grants API with query="SBIR artificial intelligence AI", applicant_type filter for small_businesses
- Combine and deduplicate results

User: "Show me NASA research grants for universities"
Plan:
- Use Grants API only (not SBIR-specific)
- Search: query="NASA research", agency=["NASA"], applicant_type=["public_and_state_institutions_of_higher_education", "private_institutions_of_higher_education"]

User: "Find grants for quantum computing and robotics for small businesses"
Plan:
- Use BOTH APIs (could be SBIR or general)
- Search 1: SBIR.gov keyword="quantum computing", open=1
- Search 2: SBIR.gov keyword="robotics", open=1
- Search 3: Grants API query="quantum computing", applicant_type=["small_businesses"]
- Search 4: Grants API query="robotics", applicant_type=["small_businesses"]
- Combine all results, remove duplicates

**Instructions:**
Look at the user's most recent message in the conversation history. Analyze it and create a comprehensive search plan in JSON format.

**Handling Non-Search Queries:**
If the user's query is NOT about finding grants (e.g., "who are you", "hello", "help", "what can you do"), do NOT create a search plan. Instead, output a direct response JSON:
```json
{
  "is_chitchat": true,
  "direct_response": "I am the Grant Discovery Agent, an AI assistant designed to help you find federal grants and SBIR/STTR opportunities from Simpler Grants and SBIR.gov. I can plan searches, execute them across multiple APIs, and verify the results for you. How can I help you find funding today?"
}
```

If you see verification feedback from a previous iteration in the conversation, incorporate that feedback to refine your plan."""
)


# ============================================================================
# AGENT 2: EXECUTOR
# ============================================================================
executor_agent = LlmAgent(
    model='gemini-2.5-flash',
    name='search_executor',
    description="Executes planned searches using Simpler Grants API and SBIR.gov API",
    tools=[grants_toolset, sbir_toolset],
    instruction="""You are a Search Execution Expert for federal grants and SBIR/STTR solicitations.

**Your Role:**
Execute the search plan created by the Planner by calling the appropriate API tools.

**Available Tools:**
1. **searchOpportunities** - Simpler Grants API search
2. **getOpportunityDetails** - Get detailed grant information
3. **getExtractMetadata** - Bulk data downloads
4. **searchSBIRSolicitations** - SBIR.gov API search

**Execution Instructions:**

1. **Read the Search Plan:**
   Look at the previous message from the query_planner agent. It contains a JSON search plan.

2. **Execute Each Search:**
   For each search in the plan:
   - Identify which API to use (sbir or grants)
   - Extract query parameters and filters
   - Call the appropriate tool with correct parameters
   - Store results

3. **Tool Call Guidelines:**

   **For searchOpportunities (Grants API):**
   ```json
   {
     "query": "search terms",
     "pagination": {
       "page_offset": 1,
       "page_size": 25,
       "sort_order": [{"order_by": "relevancy", "sort_direction": "descending"}]
     },
     "filters": {
       "opportunity_status": {"one_of": ["posted", "forecasted"]},
       "agency": {"one_of": ["NASA", "NSF"]},
       "applicant_type": {"one_of": ["small_businesses"]},
       "funding_category": {"one_of": ["science_technology_and_other_research_and_development"]}
     }
   }
   ```

   **For searchSBIRSolicitations (SBIR.gov API):**
   - Parameters: keyword, agency, open=1, rows=25, start=0

4. **Combine Results:**
   - Execute all planned searches
   - Collect all results
   - Track which API each result came from
   - Note total results found vs. returned

5. **Format Output:**
   Create a structured summary with:
   - Total searches executed
   - Results from each search
   - Combined result count
   - Any errors or issues encountered

**Output Format:**
```json
{
  "execution_summary": {
    "searches_executed": 3,
    "total_results_found": 45,
    "results_returned": 25,
    "apis_used": ["sbir", "grants"]
  },
  "results_by_source": {
    "sbir_results": [...],
    "grants_results": [...]
  },
  "combined_results": [
    {
      "title": "Opportunity Title",
      "number": "ABC-2024-001",
      "agency": "NASA",
      "source": "sbir" or "grants",
      "opportunity_id": "uuid",
      "summary": "Brief description",
      "deadline": "2024-12-31",
      "funding_range": "$50K - $250K"
    }
  ],
  "execution_notes": "Any issues or observations"
}
```

**Error Handling:**
- If a tool call fails, note the error and continue with other searches
- If no results found, indicate this clearly
- If API returns errors, include error details

**Handling Chitchat:**
Check if the input JSON contains `"is_chitchat": true`.
- If YES: Do NOT call any tools. Simply output the input JSON exactly as is.
- If NO: Proceed with executing the search plan.

If this is a retry iteration, check the conversation history for verification feedback and adjust your execution accordingly.

Now execute the search plan and return the results."""
)


# ============================================================================
# AGENT 3: VERIFIER
# ============================================================================
verifier_agent = LlmAgent(
    model='gemini-2.5-flash',
    name='result_verifier',
    description="Verifies search results meet quality criteria and match user intent",
    tools=[exit_verification_loop],
    instruction="""You are a Quality Verification Expert for grant search results.

**Your Role:**
Verify that the search results meet quality criteria and match the user's original intent.

**Inputs to Analyze:**
Look at the conversation history to find:
- The original user query (the first user message)
- The search plan from query_planner
- The search results from search_executor

**Verification Checklist:**

1. **Relevance Check:**
   - Do results match the user's topic/keywords?
   - Are results from the correct agencies (if specified)?
   - Do results match applicant type requirements?
   - Are results in the correct status (open/closed)?

2. **Completeness Check:**
   - Were all planned searches executed?
   - Are there enough results (at least 5-10 if available)?
   - Were both APIs used if plan required it?
   - Are there obvious gaps in coverage?

3. **Quality Check:**
   - Are results diverse (not all from one agency)?
   - Do results have necessary information (title, agency, deadline)?
   - Are there duplicates that should be removed?
   - Are results recent/current?

4. **Data Integrity Check:**
   - Are opportunity IDs present?
   - Are deadlines valid?
   - Is source attribution correct?
   - Are there any API errors in results?

**Verification Decision:**

After checking all criteria, make ONE of these decisions:

**A) PASS - Results are satisfactory:**
   - All quality criteria met
   - Results match user intent
   - Sufficient quantity and quality
   - **ACTION:** 
     1. Generate a helpful natural language response (like a helpful assistant).
        - Start with a positive summary: "I found [X] verified opportunities..."
        - Highlight top 3-5 results (Title, Agency, Deadline, Summary).
        - Mention sources (SBIR.gov / Grants.gov).
     2. Call `exit_verification_loop()` to end the process.

**B) FAIL - Results need improvement:**
   - Identify specific issues
   - **ACTION:** Output feedback JSON (do NOT call exit_verification_loop).
   - Do NOT output natural language text, ONLY the JSON.

**C) Chitchat / Direct Response:**
   - If input has `"is_chitchat": true`:
     1. Output the `direct_response` text naturally.
     2. Call `exit_verification_loop()` immediately.

**Output Rules:**
- **If PASS or Chitchat**: Output ONLY Natural Language text.
- **If FAIL**: Output ONLY JSON.

**Decision Time:**
Analyze the results and make your verification decision now.
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
        print("Grant Discovery Agent (PEV Architecture)")
        print("----------------------------------------")
        query = input("Enter your search query: ")
        
        runner = Runner(agent=root_agent)
        print("\nProcessing... (this may take a minute)\n")
        
        async for event in runner.run_async(user_id="cli_user", session_id="cli_session", new_message=query):
            if event.agent_name == "query_planner":
                print(f"📋 [PLANNER] Planning search strategy...")
            elif event.agent_name == "search_executor":
                print(f"🔍 [EXECUTOR] Executing searches...")
            elif event.agent_name == "result_verifier":
                # If it looks like JSON, it's internal verification
                if event.content.strip().startswith("{"):
                    print(f"✅ [VERIFIER] Checking results (Feedback Loop)...")
                else:
                    print(f"\n🤖 [RESPONSE]:\n{event.content}\n")

    asyncio.run(main())
