import json
import os

from dotenv import load_dotenv
from google.adk.tools.openapi_tool.auth.auth_helpers import token_to_scheme_credential
from google.adk.tools.openapi_tool.openapi_spec_parser.openapi_toolset import (
    OpenAPIToolset,
)

load_dotenv()

# Get API key from environment
API_KEY = os.getenv("GRANTS_API_KEY", "")

# Load Simpler Grants API OpenAPI specification
# Path logic needs to be robust
current_dir = os.path.dirname(os.path.abspath(__file__))
base_dir = os.path.dirname(os.path.dirname(current_dir))  # my_agent/
data_dir = os.path.join(base_dir, "my_agent", "data")

grants_spec_path = os.path.join(data_dir, "openapi_minimal.json")
with open(grants_spec_path) as f:
    grants_spec = json.load(f)

# Load SBIR.gov API OpenAPI specification
sbir_spec_path = os.path.join(data_dir, "sbir_openapi.json")
with open(sbir_spec_path) as f:
    sbir_spec = json.load(f)

# Create Simpler Grants toolset with authentication
grants_spec_str = json.dumps(grants_spec)

if API_KEY:
    auth_scheme, auth_credential = token_to_scheme_credential(
        "apikey", "header", "X-API-Key", API_KEY
    )
    grants_toolset = OpenAPIToolset(
        spec_str=grants_spec_str,
        spec_str_type="json",
        auth_scheme=auth_scheme,
        auth_credential=auth_credential,
    )
else:
    grants_toolset = OpenAPIToolset(
        spec_str=grants_spec_str,
        spec_str_type="json",
    )

# Create SBIR.gov toolset (no authentication required)
sbir_spec_str = json.dumps(sbir_spec)
sbir_toolset = OpenAPIToolset(
    spec_str=sbir_spec_str,
    spec_str_type="json",
)
