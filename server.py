
import uvicorn
from fastapi import FastAPI
from google.adk.server import AgentServer
from my_agent.agent import root_agent

# Initialize the Agent Server
# logic might vary based on exact library version, but this is the standard pattern
server = AgentServer(agent=root_agent)
app = server.app

if __name__ == "__main__":
    print("Starting ADK Agent Server on port 8001...")
    uvicorn.run(app, host="0.0.0.0", port=8001)
