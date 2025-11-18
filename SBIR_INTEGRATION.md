# SBIR.gov API Integration

## What Was Added

Successfully integrated the SBIR.gov public API to provide comprehensive SBIR/STTR solicitation search capabilities alongside the existing Simpler Grants API.

## New Capabilities

### 4 Total Tools Available:

**From Simpler Grants API:**
1. `search_opportunities` - General federal grants search
2. `get_opportunity_details` - Detailed opportunity information
3. `get_extract_metadata` - Bulk data downloads

**From SBIR.gov API:**
4. `search_sbir_solicitations` - SBIR/STTR specific solicitations

## SBIR.gov API Features

### Search Parameters:
- `keyword` - Search in solicitation titles
- `agency` - Filter by agency (DOD, HHS, NASA, NSF, DOE, USDA, EPA, DOC, ED, DOT, DHS)
- `open` - Set to 1 for open solicitations only
- `closed` - Set to 1 for closed solicitations only
- `rows` - Results per page (max 50, default 25)
- `start` - Pagination offset (0-based)
- `format` - Response format (json or xml)

### Data Returned:
- Solicitation title, number, program (SBIR/STTR)
- Phase (Phase I, Phase II)
- Agency, branch, year
- Release date, open date, close date
- Application due dates
- Current status
- **Solicitation topics** with:
  - Topic title, number, description
  - SBIR topic link
  - **Subtopics** with detailed descriptions

## Agent Intelligence

The agent now automatically:

### 1. Dual-Source Search for SBIR/STTR Queries
When user asks: "Find SBIR grants for AI"

Agent executes:
- `search_sbir_solicitations(keyword="AI", open=1)`
- `search_opportunities(query="SBIR AI")`
- Combines results from both sources
- Labels each result with its source

### 2. Agency-Specific Searches
When user asks: "Show me NASA SBIR opportunities"

Agent executes:
- `search_sbir_solicitations(agency="NASA", open=1)`
- `search_opportunities(query="NASA SBIR", agency filter)`
- Presents comprehensive results

### 3. Phase-Specific Searches
When user asks: "Find Phase II SBIR grants"

Agent recognizes Phase II is SBIR-specific and uses SBIR.gov API

### 4. Multi-Topic Searches
When user asks: "Find SBIR grants for quantum computing and materials science"

Agent executes:
- Multiple searches across both APIs
- Combines and deduplicates results
- Presents unified view

## Example Queries

### SBIR/STTR Specific:
- "Find open SBIR solicitations for artificial intelligence"
- "Show me NASA SBIR Phase I opportunities"
- "What STTR grants are available for robotics?"
- "Find DOD SBIR solicitations closing soon"

### Combined Searches:
- "Find all small business grants for clean energy" (uses both APIs)
- "Show me SBIR and general grants for biotechnology" (dual search)
- "What funding is available for small businesses in aerospace?" (comprehensive)

### Agency Focused:
- "Find all NSF SBIR opportunities"
- "Show me HHS SBIR solicitations"
- "What SBIR grants does DOE have open?"

## Technical Implementation

### No Authentication Required
SBIR.gov API is public and doesn't require API keys, making it immediately accessible.

### OpenAPI 3.0 Spec
Created `sbir_openapi.json` with complete endpoint definition including:
- All query parameters
- Response schema with nested topics and subtopics
- Enum values for agencies and formats

### Dual Toolset Architecture
```python
# Simpler Grants toolset (with auth)
grants_toolset = OpenAPIToolset(spec_str=grants_spec_str, auth_scheme=..., auth_credential=...)

# SBIR.gov toolset (no auth)
sbir_toolset = OpenAPIToolset(spec_str=sbir_spec_str)

# Agent with both
root_agent = LlmAgent(tools=[grants_toolset, sbir_toolset], ...)
```

## Benefits

1. **Comprehensive Coverage** - Now searches both general grants AND SBIR/STTR specific solicitations
2. **Topic-Level Details** - SBIR.gov provides detailed topic and subtopic information
3. **Better SBIR Discovery** - Dedicated SBIR database often has more detailed SBIR/STTR info
4. **Redundancy** - If one API is down, the other can still provide results
5. **Richer Results** - Combines data from two authoritative sources

## Response Format

Agent now clearly labels results:

```
SBIR/STTR Solicitations (from SBIR.gov):
1. Advanced Materials for Space Applications (NASA-SBIR-2024-1)
   Agency: NASA | Program: SBIR | Phase: Phase I
   Deadline: 2024-06-30 | Status: Open
   Topics: 5 topics available
   Source: SBIR.gov API

General Grant Opportunities (from Simpler Grants):
2. Small Business Innovation Research Program (NASA-2024-SBIR-001)
   Agency: NASA | Funding: $50,000 - $250,000
   Deadline: 2024-06-30
   Source: Simpler Grants API
```

## Next Steps

The agent is now production-ready for comprehensive federal funding discovery, covering:
- ✅ General federal grants (all agencies, all types)
- ✅ SBIR/STTR solicitations (dedicated database)
- ✅ Bulk data downloads
- ✅ Detailed opportunity information
- ✅ Multi-source search and deduplication
