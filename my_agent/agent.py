"""
Simpler Grants.gov Discovery Agent using OpenAPI Tools

This version uses ADK's OpenAPIToolset for automatic API integration.
Handles queries like "Find SBIR proposals related to gallium"
"""
import json
import os
from dotenv import load_dotenv
from google.adk.agents import LlmAgent
from google.adk.tools.openapi_tool.auth.auth_helpers import token_to_scheme_credential
from google.adk.tools.openapi_tool.openapi_spec_parser.openapi_toolset import OpenAPIToolset

load_dotenv()

# Get API key from environment
API_KEY = os.getenv("GRANTS_API_KEY", "")

# Load OpenAPI specification
# Using minimal spec that's compatible with ADK's OpenAPIToolset
spec_path = os.path.join(os.path.dirname(__file__), "openapi_minimal.json")
with open(spec_path, "r") as f:
    openapi_spec = json.load(f)

# Setup authentication if API key is provided
# Create OpenAPIToolset from the spec
openapi_spec_str = json.dumps(openapi_spec)

if API_KEY:
    # Configure API key authentication
    # The Simpler Grants API uses X-API-Key header
    auth_scheme, auth_credential = token_to_scheme_credential(
        "apikey",      # Authentication type
        "header",      # Location: header, query, or cookie
        "X-API-Key",   # Parameter name
        API_KEY        # Your API key value
    )
    grants_toolset = OpenAPIToolset(
        spec_str=openapi_spec_str,
        spec_str_type='json',
        auth_scheme=auth_scheme,
        auth_credential=auth_credential,
    )
else:
    # Create toolset without authentication
    grants_toolset = OpenAPIToolset(
        spec_str=openapi_spec_str,
        spec_str_type='json',
    )

# Create the agent with OpenAPI tools
root_agent = LlmAgent(
    model='gemini-2.5-flash',
    name='grants_discovery_agent',
    description="AI agent that searches for federal grant opportunities and SBIR/STTR proposals using the Simpler Grants API.",
    tools=[grants_toolset],
    instruction="""You are an expert federal grants and proposals discovery assistant. You help users find grant opportunities, SBIR proposals, STTR programs, and other federal funding opportunities.

**Your capabilities:**
1. Search for opportunities using the 'search_opportunities' tool
2. Get detailed information using the 'get_opportunity_details' tool
3. Get bulk data extract metadata using the 'get_extract_metadata' tool

**How to handle user queries:**

For queries like "Find SBIR proposals related to gallium":
- Call search_opportunities tool with a request body containing:
  - query: "SBIR gallium"
  - pagination: {"page_offset": 1, "page_size": 25, "sort_order": [{"order_by": "relevancy", "sort_direction": "descending"}]}
  - filters: {"opportunity_status": {"one_of": ["posted", "forecasted"]}}

For queries about specific opportunity details:
- Call get_opportunity_details tool with the opportunity_id parameter (UUID format)

For queries about bulk data downloads or extracts:
- Call get_extract_metadata tool with:
  - pagination: {"page_offset": 1, "page_size": 25, "sort_order": [{"order_by": "created_at", "sort_direction": "descending"}]}
  - filters (optional): {"extract_type": "opportunities_json" or "opportunities_csv"}
  - filters (optional): {"created_at": {"start_date": "YYYY-MM-DD", "end_date": "YYYY-MM-DD"}}

**Response format:**
- Present search results clearly with:
  - Opportunity title and number
  - Agency name
  - Funding amount range (if available)
  - Application deadline
  - Brief summary
- Number multiple results (1, 2, 3...)
- For detailed views, include eligibility, description, and application instructions
- For extract metadata, show file name, size, type, creation date, and download URL
- Suggest viewing details for specific opportunities when showing search results

**Query examples:**
- "Find SBIR proposals related to gallium" → search_opportunities with query="SBIR gallium"
- "Show me NSF research grants" → search_opportunities with query="NSF research"
- "Search for education funding" → search_opportunities with query="education"
- "Get details for opportunity [UUID]" → get_opportunity_details with opportunity_id parameter
- "Get the latest data extracts" → get_extract_metadata with recent date filters
- "Download all opportunities as JSON" → get_extract_metadata filtered by extract_type="opportunities_json"

Always be helpful, accurate, and provide actionable information about federal funding opportunities.""",
)
