# Simpler Grants Discovery Agent

An AI agent built with Google's Agent Development Kit (ADK) to search for federal grant opportunities and SBIR/STTR proposals.

## Features

- 🔍 Search for federal grants and SBIR/STTR proposals by keyword
- 📊 Get detailed information about specific opportunities
- 💰 View funding ranges, deadlines, and eligibility requirements
- 🎯 Natural language queries like "Find SBIR proposals related to gallium"

## Setup

1. **Install dependencies:**
```bash
pip install google-adk python-dotenv requests
```

2. **Configure environment variables:**
Create a `.env` file:
```env
GOOGLE_GENAI_USE_VERTEXAI=0
GOOGLE_API_KEY=your_google_api_key_here
GRANTS_API_KEY=your_grants_api_key_here  # Optional
```

3. **Enable Developer Mode (Windows):**
To avoid symlink privilege errors:
- Settings → Privacy & Security → For developers
- Enable "Developer Mode"

## Usage

### Run the agent:
```bash
adk run my_agent
```

### Example queries:
- "Find SBIR proposals related to gallium"
- "Show me NSF research grants"
- "Search for education funding opportunities"
- "Get details for opportunity [UUID]"

## Implementation Approaches

### 1. Custom Functions (agent.py) - Current
Uses manually defined Python functions for API calls.
- ✅ Full control over request/response handling
- ✅ Custom error handling and formatting
- ✅ Works with current ADK version

### 2. OpenAPI Tools (agent_openapi.py) - Alternative
Uses ADK's OpenAPIToolset for automatic API integration.
- ✅ Automatic tool generation from OpenAPI spec
- ✅ Less code to maintain
- ✅ Standardized API integration pattern

## API Documentation

The agent uses the [Simpler Grants API](https://api.simpler.grants.gov):
- **Search**: `POST /v1/opportunities/search`
- **Details**: `GET /v1/opportunities/{opportunity_id}`

See `initial.MD` for complete API documentation.

## Troubleshooting

### 429 Rate Limit Error
- Wait 1-2 minutes between requests
- Using free tier of Google AI API
- Consider upgrading to paid tier for higher limits

### Windows Symlink Error
- Enable Developer Mode in Windows Settings
- Or run terminal as Administrator

### Model Not Found
- Ensure using valid model: `gemini-1.5-flash` or `gemini-2.0-flash`
- Check Google API key is valid

## Files

- `agent.py` - Main agent implementation (custom functions)
- `agent_openapi.py` - Alternative using OpenAPIToolset
- `simpler_grants_openapi.json` - OpenAPI specification
- `.env` - Environment variables (create this)
- `initial.MD` - ADK documentation and API reference

## License

Copyright 2025 - Built with Google Agent Development Kit
