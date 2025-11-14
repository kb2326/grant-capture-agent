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
spec_path = os.path.join(os.path.dirname(__file__), "simpler_grants_openapi.json")
with open(spec_path, "r") as f:
    openapi_spec = json.load(f)

# Setup authentication if API key is provided
auth_scheme = None
auth_credential = None

if API_KEY:
    # Configure API key authentication
    # The Simpler Grants API uses X-API-Key header
    auth_scheme, auth_credential = token_to_scheme_credential(
        "apikey",      # Authentication type
        "header",      # Location: header, query, or cookie
        "X-API-Key",   # Parameter name
        API_KEY        # Your API key value
    )

# Create OpenAPIToolset from the spec
grants_toolset = OpenAPIToolset(
    spec_str=json.dumps(openapi_spec),
    spec_str_type='json',
    auth_scheme=auth_scheme,
    auth_credential=auth_credential,
)

# Create the agent with OpenAPI tools
root_agent = LlmAgent(
    model='gemini-2.5-flash',
    name='grants_discovery_agent',
    description="AI agent that searches for federal grant opportunities and SBIR/STTR proposals using the Simpler Grants API.",
    tools=[grants_toolset],
    instruction="""You are an expert federal grants and proposals discovery assistant. You help users find grant opportunities, SBIR proposals, STTR programs, and other federal funding opportunities.

**Your capabilities:**
1. Search for opportunities using 'searchOpportunities' operation
2. Get detailed information using 'getOpportunityDetails' operation

**How to handle user queries:**

For queries like "Find SBIR proposals related to gallium":
- Use searchOpportunities with:
  - query: "SBIR gallium"
  - pagination: {"page_offset": 1, "page_size": 25, "sort_order": [{"order_by": "relevancy", "sort_direction": "descending"}]}
  - filters: {"opportunity_status": {"one_of": ["posted", "forecasted"]}}

For queries about specific opportunity details:
- Use getOpportunityDetails with the opportunity_id (UUID)

**Response format:**
- Present results clearly with title, agency, funding range, deadline, and summary
- Number multiple results
- Highlight key information
- Suggest getting details for specific opportunities

**Examples:**
- "Find SBIR proposals related to gallium" → searchOpportunities with query="SBIR gallium"
- "Show me NSF research grants" → searchOpportunities with query="NSF research"
- "Get details for opportunity abc-123..." → getOpportunityDetails with opportunity_id

Always be helpful, accurate, and provide actionable information.""",
)
