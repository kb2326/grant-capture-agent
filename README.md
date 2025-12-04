# Simpler Grants Discovery Agent

An AI agent built with Google's Agent Development Kit (ADK) to search for federal grant opportunities and SBIR/STTR proposals.

## Features

- 🔍 Search for federal grants and SBIR/STTR proposals by keyword
- 📊 Get detailed information about specific opportunities
- 💰 View funding ranges, deadlines, and eligibility requirements
- 🎯 Natural language queries like "Find SBIR proposals related to gallium"
- ✅ **NEW:** PEV Architecture with quality assurance and self-correction

## Two Architecture Options

### 1. Simple Tool Use (`agent.py`) - Default
- Single LLM agent with direct tool access
- Fast and efficient for straightforward queries
- Best for: Simple searches, single topics, quick results

### 2. PEV Architecture (`agent_pev.py`) - Advanced ⭐
- Three-agent system: Planner → Executor → Verifier
- Built-in quality assurance and retry logic
- Self-correcting with up to 3 iterations
- Best for: Complex queries, multi-criteria searches, high-quality results

See [PEV_ARCHITECTURE.md](PEV_ARCHITECTURE.md) for detailed documentation.

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

### Run the Simple Agent (default):
```bash
adk run my_agent
```

### Run the PEV Agent (recommended for complex queries):
```bash
adk run my_agent.agent_pev
```

### Test and Compare Both:
```bash
python my_agent/test_pev.py
```

### Example queries:

**Simple queries (both agents work well):**
- "Find SBIR proposals related to gallium"
- "Show me NSF research grants"
- "Search for education funding opportunities"

**Complex queries (PEV excels):**
- "Find NASA and NSF grants for AI and robotics for small businesses"
- "Show me open SBIR Phase I opportunities in quantum computing and materials science"
- "Find grants for universities in clean energy from DOE and DOC"

## Architecture Comparison

| Feature | Simple Tool Use | PEV Architecture |
|---------|----------------|------------------|
| **Agents** | 1 agent | 3 specialized agents |
| **Planning** | Implicit | Explicit planning phase |
| **Verification** | None | Built-in quality checks |
| **Retry Logic** | None | Up to 3 iterations |
| **Self-Correction** | ❌ | ✅ |
| **Complex Queries** | May miss aspects | Systematic handling |
| **Speed** | Faster | Slightly slower |
| **Quality Assurance** | Manual | Automatic |
| **Best For** | Simple queries | Complex, multi-criteria |

### When to Use Each:

**Use Simple Agent (`agent.py`) when:**
- Single topic or agency
- Quick results needed
- Straightforward search criteria
- Testing or development

**Use PEV Agent (`agent_pev.py`) when:**
- Multiple topics or agencies
- Complex eligibility requirements
- High-quality results critical
- Multi-criteria filtering needed
- Production use with end users

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
