import os
import json
from dotenv import load_dotenv
from google.adk.tools.openapi_tool.auth.auth_helpers import token_to_scheme_credential
from google.adk.tools.openapi_tool.openapi_spec_parser.openapi_toolset import OpenAPIToolset

load_dotenv()

# Get API key from environment
API_KEY = os.getenv("GRANTS_API_KEY", "")
SAM_API_KEY = os.getenv("SAM_API_KEY", "")

# Load Simpler Grants API OpenAPI specification
# Path logic needs to be robust
current_dir = os.path.dirname(os.path.abspath(__file__))
base_dir = os.path.dirname(os.path.dirname(current_dir)) # my_agent/
data_dir = os.path.join(base_dir, "my_agent", "data")

grants_spec_path = os.path.join(data_dir, "openapi_minimal.json")
with open(grants_spec_path, "r") as f:
    grants_spec = json.load(f)

# Load SBIR.gov API OpenAPI specification
sbir_spec_path = os.path.join(data_dir, "sbir_openapi.json")
with open(sbir_spec_path, "r") as f:
    sbir_spec = json.load(f)

# Load SAM.gov API OpenAPI specification
sam_spec_path = os.path.join(data_dir, "sam_openapi.json")
with open(sam_spec_path, "r") as f:
    sam_spec = json.load(f)

# Load USAspending API OpenAPI specification
usa_spending_spec_path = os.path.join(data_dir, "usa_spending_openapi.json")
with open(usa_spending_spec_path, "r") as f:
    usa_spending_spec = json.load(f)

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

# Create SAM.gov toolset
sam_spec_str = json.dumps(sam_spec)

if SAM_API_KEY:
    # SAM.gov uses query parameter auth: ?api_key=VALUE
    auth_scheme, auth_credential = token_to_scheme_credential(
        "apikey", "query", "api_key", SAM_API_KEY
    )
    sam_toolset = OpenAPIToolset(
        spec_str=sam_spec_str,
        spec_str_type='json',
        auth_scheme=auth_scheme,
        auth_credential=auth_credential,
    )
else:
    sam_toolset = OpenAPIToolset(
        spec_str=sam_spec_str,
        spec_str_type='json',
    )

# Create USAspending toolset (no authentication required)
usa_spending_spec_str = json.dumps(usa_spending_spec)
usa_spending_toolset = OpenAPIToolset(
    spec_str=usa_spending_spec_str,
    spec_str_type='json',
)
