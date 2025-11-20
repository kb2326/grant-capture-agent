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
def exit_verification_loop(tool_context: ToolContext):
    """Call this when verification passes and results are satisfactory."""
    print(f"[Verification] Results verified successfully - exiting loop")
    tool_context.actions.escalate = True
    return {"status": "verification_passed", "message": "Results meet quality criteria"}


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

If you see verification feedback from a previous iteration in the conversation, incorporate that feedback to refine your plan.""",
    output_key="search_plan"
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

If this is a retry iteration, check the conversation history for verification feedback and adjust your execution accordingly.

Now execute the search plan and return the results.""",
    output_key="search_results"
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
   - **ACTION:** Call the `exit_verification_loop` tool to approve results

**B) FAIL - Results need improvement:**
   - Identify specific issues
   - Provide actionable feedback for retry
   - Suggest plan modifications
   - **ACTION:** Output feedback JSON (do NOT call exit_verification_loop)

**Output Format for PASS:**
Call `exit_verification_loop()` and output:
```json
{
  "verification_status": "PASS",
  "quality_score": 9,
  "results_approved": 25,
  "verification_notes": "Results are relevant, comprehensive, and meet all criteria.",
  "user_ready_summary": "Found 25 relevant opportunities from NASA and NSF for AI research..."
}
```

**Output Format for FAIL:**
```json
{
  "verification_status": "FAIL",
  "issues_found": [
    "Only 2 results returned, expected at least 10",
    "No SBIR.gov results included despite plan requiring it",
    "Results don't match 'quantum computing' keyword"
  ],
  "feedback_for_planner": "Broaden search terms, add synonyms like 'quantum information science'",
  "feedback_for_executor": "Retry SBIR.gov search with corrected parameters",
  "suggested_modifications": {
    "add_searches": [
      {"api": "sbir", "keyword": "quantum information", "reason": "Broader term coverage"}
    ],
    "adjust_filters": "Remove overly restrictive agency filter"
  }
}
```

**Verification Rules:**

- Be strict but reasonable - don't fail for minor issues
- If 0 results found, check if query is too narrow
- If 100+ results, that's okay (pagination handles it)
- Duplicates across APIs are expected and acceptable
- Missing optional fields (funding amount) is acceptable
- If this is retry iteration 2+, be more lenient

**Decision Time:**
Analyze the results and make your verification decision now.

If PASS: Call exit_verification_loop() immediately.
If FAIL: Output detailed feedback JSON.""",
    output_key="verification_result"
)


# ============================================================================
# AGENT 4: FORMATTER
# ============================================================================
formatter_agent = LlmAgent(
    model='gemini-2.5-flash',
    name='response_formatter',
    description="Formats the final output from the PEV loop into a helpful natural language response",
    instruction="""You are a helpful assistant explaining grant search results to a user.
    
**Input:**
You will receive the final output from a Plan-Execute-Verify (PEV) search process. This might be:
1. A successful result (PASS) with a list of verified opportunities.
2. A failed result (FAIL) with feedback on why it failed (e.g., API errors, no results found).

**Your Goal:**
Translate this structured JSON output into a clear, helpful, and professional natural language response.

**Scenarios:**

**Scenario A: Success (PASS)**
- Start with a positive summary: "I found [X] verified opportunities matching your request."
- Highlight the top 3-5 most relevant results with their Titles, Agencies, Deadlines, and a brief summary.
- Mention if results came from SBIR.gov, Grants.gov, or both.
- Ask if the user would like more details on any specific opportunity.

**Scenario B: Failure (FAIL)**
- Be honest but helpful. "I wasn't able to find specific grants matching your exact criteria right now."
- Explain *why* in simple terms (e.g., "The SBIR API is currently down," or "No grants matched the specific keywords").
- Use the `feedback_for_planner` or `suggested_modifications` from the input to suggest next steps.
- Example: "However, I suggest we try broadening the search to [Topic] or checking back later."

**Tone:**
- Professional, encouraging, and concise.
- Do NOT output raw JSON.
- Do NOT mention "JSON", "Planner", "Executor", or "Verifier" internal names unless necessary for debugging (keep it user-focused).
""",
    output_key="final_response"
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
# 1. Run the loop to get results
# 2. Run the formatter to explain results to user
root_agent = SequentialAgent(
    name='grants_discovery_pev_agent',
    description="AI agent for federal grant discovery using Plan-Execute-Verify architecture",
    sub_agents=[pev_loop, formatter_agent]
)

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
                print(f"✅ [VERIFIER] Verifying results...")
            elif event.agent_name == "response_formatter":
                print(f"\n🤖 [RESPONSE]:\n{event.content}\n")

    asyncio.run(main())
