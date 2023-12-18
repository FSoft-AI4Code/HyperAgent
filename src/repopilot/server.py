from fastapi import FastAPI
from typing import Dict
from repopilot.agents.plan_seeking import PlanSeeking
from fastapi.responses import JSONResponse
import uvicorn

app = FastAPI()

global systems 

@app.post("/{server_id}/query")
async def query_system(server_id: str, body: Dict[str, str]):
    system = systems.get(server_id)
    if not system:
        return JSONResponse(status_code=404, content={"message": "System not found"})
    query = body.get('query')
    if not query:
        return JSONResponse(status_code=400, content={"message": "Query not provided"})
    result = system.query_codebase(query)
    return {"result": result}

def serve(system: PlanSeeking, server_id: str):
    systems[server_id] = system
    uvicorn.run(app, host="0.0.0.0", port=8000)