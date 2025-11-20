# PEV Architecture for Grants Discovery Agent

## Overview

The **Plan-Execute-Verify (PEV)** architecture is a robust, self-correcting agent system that dramatically improves result quality through a three-stage process with built-in verification and retry logic.

## Architecture Diagram

```
User Query
    ↓
┌─────────────────────────────────────────────────┐
│         PEV Loop (max 3 iterations)             │
│                                                 │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐ │
│  │ PLANNER  │ -> │ EXECUTOR │ -> │ VERIFIER │ │
│  └──────────┘    └──────────┘    └──────────┘ │
│       ↑                                  │      │
│       │         Verification FAIL        │      │
│       └──────────────────────────────────┘      │
│                                                 │
│              Verification PASS                  │
│                     ↓                           │
└─────────────────────────────────────────────────┘
    ↓
Verified Results to User
```

## Three Agents

### 1. Planner Agent (`query_planner`)

**Role:** Strategic query analysis and search plan creation

**Responsibilities:**
- Analyze user intent and extract key elements (topics, agencies, applicant types)
- Determine which APIs to use (Simpler Grants, SBIR.gov, or both)
- Create structured search plan with specific queries and filters
- Define quality criteria for verification
- Refine plan based on verification feedback (if retry)

**Input:**
- User query
- Verification feedback (on retry iterations)

**Output:**
```json
{
  "query_analysis": {
    "user_intent": "Find SBIR grants for AI research",
    "topics": ["artificial intelligence", "machine learning"],
    "grant_types": ["SBIR"],
    "applicant_types": ["small_businesses"],
    "agencies": ["NASA", "NSF"],
    "status_filter": "open"
  },
  "search_plan": {
    "use_sbir_api": true,
    "use_grants_api": true,
    "searches": [
      {
        "api": "sbir",
        "query": "artificial intelligence",
        "filters": {"open": 1, "agency": "NASA"},
        "reason": "SBIR-specific AI opportunities from NASA"
      },
      {
        "api": "grants",
        "query": "SBIR artificial intelligence",
        "filters": {"applicant_type": ["small_businesses"]},
        "reason": "Comprehensive coverage from Grants API"
      }
    ]
  },
  "expected_results": "10-30 SBIR opportunities related to AI",
  "quality_criteria": "Results must include AI/ML keywords, be from NASA/NSF, status open"
}
```

**Model:** `gemini-2.5-flash`

---

### 2. Executor Agent (`search_executor`)

**Role:** Execute planned searches using API tools

**Responsibilities:**
- Parse the search plan JSON
- Call appropriate API tools (searchOpportunities, searchSBIRSolicitations)
- Handle multiple searches and combine results
- Track which API each result came from
- Handle errors gracefully and continue execution
- Format results in structured format

**Input:**
- Search plan from Planner
- Verification feedback (on retry iterations)

**Tools Available:**
- `searchOpportunities` - Simpler Grants API
- `getOpportunityDetails` - Detailed grant info
- `getExtractMetadata` - Bulk downloads
- `searchSBIRSolicitations` - SBIR.gov API

**Output:**
```json
{
  "execution_summary": {
    "searches_executed": 2,
    "total_results_found": 23,
    "results_returned": 23,
    "apis_used": ["sbir", "grants"]
  },
  "combined_results": [
    {
      "title": "Advanced AI for Space Systems",
      "number": "NASA-SBIR-2024-A1.01",
      "agency": "NASA",
      "source": "sbir",
      "opportunity_id": "uuid-here",
      "summary": "Develop AI systems for autonomous spacecraft",
      "deadline": "2024-12-15",
      "funding_range": "$150K - $250K"
    }
  ],
  "execution_notes": "All searches completed successfully"
}
```

**Model:** `gemini-2.5-flash`

---

### 3. Verifier Agent (`result_verifier`)

**Role:** Quality assurance and result validation

**Responsibilities:**
- Verify results match user intent and query criteria
- Check completeness (all searches executed, sufficient results)
- Validate data quality (no duplicates, valid dates, proper attribution)
- Check relevance (correct topics, agencies, applicant types)
- Make PASS/FAIL decision
- Provide actionable feedback for retry if FAIL

**Input:**
- Original user query
- Search plan
- Search results from Executor

**Tools Available:**
- `exit_verification_loop` - Call when verification passes

**Verification Checklist:**
1. ✅ **Relevance** - Results match topics, agencies, applicant types
2. ✅ **Completeness** - All searches executed, sufficient quantity
3. ✅ **Quality** - Diverse results, valid data, no major errors
4. ✅ **Data Integrity** - IDs present, dates valid, proper attribution

**Output (PASS):**
```json
{
  "verification_status": "PASS",
  "quality_score": 9,
  "results_approved": 23,
  "verification_notes": "Results are relevant, comprehensive, and high quality",
  "user_ready_summary": "Found 23 SBIR opportunities for AI research from NASA and NSF"
}
```

**Output (FAIL):**
```json
{
  "verification_status": "FAIL",
  "issues_found": [
    "Only 3 results returned, expected at least 10",
    "No results from NSF despite being in query"
  ],
  "feedback_for_planner": "Add broader search terms, include 'machine learning' synonym",
  "feedback_for_executor": "Retry with NSF agency filter explicitly set",
  "suggested_modifications": {
    "add_searches": [
      {"api": "grants", "query": "NSF machine learning", "reason": "Cover NSF explicitly"}
    ]
  }
}
```

**Model:** `gemini-2.5-flash`

---

## Loop Orchestration

### LoopAgent Configuration

```python
pev_loop = LoopAgent(
    name="PEV_Loop",
    sub_agents=[planner_agent, executor_agent, verifier_agent],
    max_iterations=3,  # Up to 3 attempts
    description="Plan-Execute-Verify loop with quality assurance"
)
```

### Iteration Flow

**Iteration 1:**
1. Planner creates initial search plan
2. Executor runs searches
3. Verifier checks results
   - **PASS** → Exit loop, return results ✅
   - **FAIL** → Provide feedback, continue to iteration 2

**Iteration 2:**
1. Planner refines plan based on verification feedback
2. Executor runs modified searches
3. Verifier checks results again
   - **PASS** → Exit loop, return results ✅
   - **FAIL** → Provide feedback, continue to iteration 3

**Iteration 3 (Final):**
1. Planner makes final refinements
2. Executor runs final searches
3. Verifier checks results (more lenient on final iteration)
   - **PASS** → Exit loop, return results ✅
   - **FAIL** → Return best available results with notes

---

## Key Advantages Over Simple Tool Use

### 1. **Self-Correcting**
- Automatically retries with refined queries if initial results are poor
- Learns from verification feedback
- Adapts search strategy based on what worked/didn't work

### 2. **Quality Assurance**
- Built-in verification ensures results meet criteria
- Catches common issues (wrong agency, irrelevant results, too few results)
- Validates data integrity before presenting to user

### 3. **Better Complex Query Handling**
- Breaks down complex queries into structured plans
- Handles multi-topic, multi-agency searches systematically
- Ensures comprehensive coverage across both APIs

### 4. **Transparency**
- Clear separation of planning, execution, and verification
- Traceable decision-making process
- Detailed feedback on why results passed/failed

### 5. **Robustness**
- Handles API errors gracefully
- Continues execution even if one search fails
- Provides best available results even if verification fails

---

## Usage

### Running the PEV Agent

```bash
# Use the PEV agent instead of the simple agent
adk run my_agent.agent_pev
```

### Example Queries

**Simple Query:**
```
User: "Find SBIR grants for quantum computing"

Iteration 1:
- Planner: Create plan for SBIR + Grants API searches
- Executor: Run 2 searches, return 18 results
- Verifier: PASS ✅ (relevant, sufficient quantity)
Result: 18 verified opportunities delivered
```

**Complex Query with Retry:**
```
User: "Find NASA and NSF grants for AI and robotics for small businesses"

Iteration 1:
- Planner: Create plan with 4 searches (2 topics × 2 agencies)
- Executor: Run searches, return 5 results (only NASA results)
- Verifier: FAIL ❌ (missing NSF results, low quantity)

Iteration 2:
- Planner: Refine plan, add explicit NSF searches, broaden terms
- Executor: Run 6 searches with modifications
- Verifier: PASS ✅ (23 results, both agencies covered)
Result: 23 verified opportunities delivered
```

---

## Configuration

### Adjusting Iteration Limit

```python
pev_loop = LoopAgent(
    sub_agents=[planner_agent, executor_agent, verifier_agent],
    max_iterations=5,  # Increase for more retry attempts
)
```

### Adjusting Verification Strictness

Modify the verifier agent's instruction to be more/less strict:

```python
# More lenient
"If 5+ relevant results found, consider PASS"

# More strict
"Require 20+ results, must include both APIs, no errors"
```

### Customizing Models

```python
# Use different models for different agents
planner_agent = LlmAgent(model='gemini-2.0-flash-thinking-exp', ...)  # Better planning
executor_agent = LlmAgent(model='gemini-2.5-flash', ...)  # Fast execution
verifier_agent = LlmAgent(model='gemini-2.5-pro', ...)  # Thorough verification
```

---

## Comparison: Simple vs PEV

| Aspect | Simple Tool Use (agent.py) | PEV Architecture (agent_pev.py) |
|--------|---------------------------|--------------------------------|
| **Agents** | 1 agent | 3 specialized agents |
| **Planning** | Implicit in instructions | Explicit planning phase |
| **Verification** | None | Built-in quality checks |
| **Retry Logic** | None | Up to 3 iterations |
| **Complex Queries** | May miss aspects | Systematic decomposition |
| **Quality Assurance** | User must verify | Automatic verification |
| **Error Recovery** | Fails immediately | Self-correcting |
| **Transparency** | Black box | Clear stages |
| **Best For** | Simple, single-topic queries | Complex, multi-criteria queries |

---

## Monitoring and Debugging

### Session State Tracking

The PEV loop stores intermediate results in session state:

```python
session.state = {
    "search_plan": {...},           # From Planner
    "search_results": {...},        # From Executor
    "verification_result": {...},   # From Verifier
    "final_results": {...}          # Final output
}
```

### Event Streaming

Monitor the PEV process in real-time:

```python
events = runner.run_async(user_id="user", session_id="session", new_message=content)

async for event in events:
    if event.agent_name == "query_planner":
        print(f"[PLAN] {event.content}")
    elif event.agent_name == "search_executor":
        print(f"[EXECUTE] {event.content}")
    elif event.agent_name == "result_verifier":
        print(f"[VERIFY] {event.content}")
```

---

## Future Enhancements

### Potential Improvements

1. **Adaptive Iteration Limits**
   - Increase iterations for complex queries
   - Decrease for simple queries

2. **Learning from History**
   - Track which search strategies work best
   - Build query pattern library

3. **Parallel Execution**
   - Run multiple searches concurrently in Executor
   - Faster results for multi-topic queries

4. **Semantic Verification**
   - Use embeddings to verify semantic relevance
   - More sophisticated quality scoring

5. **User Feedback Loop**
   - Allow users to rate results
   - Improve verification criteria based on ratings

---

## Troubleshooting

### Issue: Too Many Iterations

**Symptom:** Loop hits max_iterations without passing verification

**Solutions:**
- Increase max_iterations
- Make verifier more lenient
- Check if query is too narrow/specific
- Review verification feedback for patterns

### Issue: Poor Quality Results

**Symptom:** Verifier passes but results aren't relevant

**Solutions:**
- Tighten verification criteria
- Improve quality checklist
- Add more specific relevance checks
- Review planner's query analysis

### Issue: Slow Performance

**Symptom:** Takes too long to get results

**Solutions:**
- Reduce max_iterations
- Optimize search plan (fewer searches)
- Use faster models
- Implement parallel execution

---

## Conclusion

The PEV architecture transforms the grants discovery agent from a simple tool-using agent into a robust, self-correcting system with built-in quality assurance. It's particularly valuable for:

- ✅ Complex, multi-criteria queries
- ✅ High-stakes searches where quality matters
- ✅ Users who need comprehensive coverage
- ✅ Scenarios where initial results may be insufficient

The three-agent system with verification and retry logic ensures users receive high-quality, relevant results that truly match their needs.
