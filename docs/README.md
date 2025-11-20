# Grant Discovery Agent Documentation

An AI-powered agent for discovering federal grants and SBIR/STTR opportunities using Google's Agent Development Kit (ADK).

## 📚 Documentation Index

- **[Getting Started](../README.md)** - Installation and quick start guide
- **[PEV Architecture](PEV_ARCHITECTURE.md)** - Detailed architecture documentation
- **[SBIR Integration](SBIR_INTEGRATION.md)** - SBIR.gov API integration details
- **[API Reference](API_REFERENCE.md)** - API endpoints and usage

## 🏗️ Architecture Overview

The agent uses a **Plan-Execute-Verify (PEV)** architecture with three specialized agents:

1. **Planner** - Analyzes queries and creates search strategies
2. **Executor** - Executes searches across multiple APIs
3. **Verifier** - Validates results and triggers retries if needed

## 🔧 Key Features

- ✅ Dual API integration (Simpler Grants + SBIR.gov)
- ✅ Self-correcting with up to 3 retry iterations
- ✅ Built-in quality assurance
- ✅ Natural language query processing
- ✅ Web interface with real-time progress tracking

## 📖 Quick Links

### For Users
- [Installation Guide](../README.md#setup)
- [Usage Examples](../README.md#usage)
- [Troubleshooting](../README.md#troubleshooting)

### For Developers
- [Architecture Details](PEV_ARCHITECTURE.md)
- [API Integration](SBIR_INTEGRATION.md)
- [Contributing Guidelines](CONTRIBUTING.md)

## 🚀 Getting Started

```bash
# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your API keys

# Run the agent
adk run my_agent

# Or run the web server
python server.py
```

## 📝 Example Queries

**Simple Searches:**
- "Find SBIR grants for artificial intelligence"
- "Show me NASA research opportunities"
- "Search for clean energy funding"

**Complex Searches:**
- "Find NASA and NSF grants for AI and robotics for small businesses"
- "Show me open SBIR Phase I opportunities in quantum computing"
- "Find grants for universities in clean energy from DOE"

## 🤝 Support

For issues, questions, or contributions, please refer to the main README.
