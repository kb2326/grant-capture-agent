# Proposal ADK Search Agent

An advanced AI agent built with Google's Agent Development Kit (ADK) designed to automate the discovery and analysis of federal grant opportunities and SBIR/STTR proposals.

This agent utilizes a **Plan-Execute-Verify (PEV)** architecture to ensure high-quality search results, automated eligibility verification, and competitive intelligence gathering.

## 🚀 Key Features

- **🧠 Intelligent Search Planning**: The **Planner** agent breaks down complex user queries (e.g., "Find renewable energy grants for a small business in Ohio") into targeted search strategies.
- **🕵️ Semantic Eraser (Eligibility Check)**: Automatically scans full solicitation documents to identify "knockout" criteria (e.g., "non-profit only" restrictions) and filters out irrelevant opportunities.
- **📊 Competitor Intelligence**: Integrates with the **USAspending API** to analyze past award data, identifying top competitors and funding trends for specific grant categories.
- **🛡️ Quality Assurance (Verifier)**: A dedicated **Verifier** agent reviews search results against the user's original request, triggering self-correction loops if the results are unsatisfactory.
- **🏛️ Federal Data Integration**: Accesses real-time data from **Grants.gov** and **SBIR.gov** (via Simpler Grants API).

## 🏗️ Architecture

This project employs a robust **PEV (Plan-Execute-Verify)** pattern:

1.  **Planner**: Analyzes the user's intent and creates a step-by-step search plan.
2.  **Executor**: Executes the plan using available tools (Keyword Search, Semantic Check, Competitor Intel).
3.  **Verifier**: Evaluates the output. If the result is poor, it provides feedback to the Planner for a retry (up to 3 iterations).

See [docs/PEV_ARCHITECTURE.md](docs/PEV_ARCHITECTURE.md) for a deep dive into the system design.

## 🛠️ Setup & Installation

This project uses `uv` for modern, fast Python dependency management.

### Prerequisites
- Python 3.13+
- `uv` (Recommended) or `pip`
- Google Cloud Project with Vertex AI API enabled (if using Vertex) or Google AI Studio Key.

### Installation

1.  **Clone the repository:**
    ```bash
    git clone <repository-url>
    cd "Proposal ADK search Agent"
    ```

2.  **Install dependencies:**
    Using `uv` (Recommended):
    ```bash
    uv sync
    ```
    Or using standard `pip`:
    ```bash
    pip install .
    ```

3.  **Configure Environment:**
    Create a `.env` file in the root directory:
    ```env
    GOOGLE_GENAI_USE_VERTEXAI=0  # Set to 1 for Vertex AI, 0 for AI Studio
    GOOGLE_API_KEY=your_google_api_key_here
    GRANTS_API_KEY=your_grants_api_key_here  # Optional, for Simpler Grants API
    ```

4.  **Developer Mode (Windows Users):**
    To avoid symlink privilege errors during execution:
    - Go to **Settings** → **Privacy & Security** → **For developers**.
    - Enable **Developer Mode**.

## 🏃 Usage

Run the agent using the ADK CLI:

```bash
adk run my_agent
```

### Example Queries

- **Discovery**: "Find open SBIR Phase I opportunities related to underwater robotics."
- **Specifics**: "Search for NSF grants for AI education and tell me if a for-profit company is eligible."
- **Intelligence**: "Who are the past winners of Dept of Energy grants for solar panel recycling?"
- **Complex**: "Find NASA grants for materials science, check my eligibility as a startup, and show me the competition."

## 📂 Project Structure

- `my_agent/`
    - `agent.py`: Main entry point defining the PEV Loop Agent.
    - `sub_agents/`: Contains the `planner`, `executor`, and `verifier` agent definitions.
    - `tools/`
        - `advanced_search.py`: Implementation of Semantic Eraser and Competitor Intel.
        - `apis.py`: API setup for Grants and SBIR data.
- `docs/`: Detailed documentation.

## ⚠️ Troubleshooting

**429 Rate Limit Error**
- If using the free tier of Google AI API, wait a minute between complex requests due to the multiple agent calls involved in the PEV loop.

**Windows Symlink Error**
- Ensure "Developer Mode" is enabled in Windows settings.

## License

Copyright 2025 - Built with Google Agent Development Kit
