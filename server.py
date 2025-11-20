import os
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from google.adk import Runner
from google.adk.runners import InMemorySessionService
from my_agent.agent import root_agent

# Initialize FastAPI app
app = FastAPI(title="Grant Discovery Agent API")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request model
class ChatRequest(BaseModel):
    message: str

# Chat endpoint
@app.post("/chat")
async def chat(request: ChatRequest):
    try:
        # Initialize the runner with the root agent and session service
        session_service = InMemorySessionService()
        runner = Runner(agent=root_agent, app_name="grant_discovery_agent", session_service=session_service)
        
        final_response = ""
        
        # Run the agent asynchronously
        # We iterate through events to find the final response from the formatter
        async for event in runner.run_async(user_id="user", session_id="session", new_message=request.message):
            # Log events for debugging (optional)
            # print(f"[{event.agent_name}] {event.content}")
            
            # Capture the output from the response_formatter agent
            if event.agent_name == "response_formatter":
                final_response = event.content
        
        if not final_response:
            # Fallback if no formatter response found (shouldn't happen in happy path)
            return {"response": "I processed your request but couldn't generate a final response. Please check the logs."}
            
        return {"response": final_response}
        
    except Exception as e:
        print(f"Error processing request: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Mount the web directory to serve static files
# This must be after API routes to avoid conflicts
app.mount("/", StaticFiles(directory="web", html=True), name="static")

if __name__ == "__main__":
    import socket
    
    def find_available_port(start_port):
        port = start_port
        while True:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                if s.connect_ex(('localhost', port)) != 0:
                    return port
                print(f"Port {port} is in use, trying {port + 1}...")
                port += 1

    port = find_available_port(8000)
    
    print("Starting Grant Discovery Agent Server...")
    print(f"Open http://127.0.0.1:{port} in your browser")
    uvicorn.run(app, host="127.0.0.1", port=port)
