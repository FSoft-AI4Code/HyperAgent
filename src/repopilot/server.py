from fastapi import FastAPI
from typing import Dict
from repopilot.agents.plan_seeking import PlanSeeking
from fastapi.responses import JSONResponse
import uvicorn
from pydantic import BaseModel
import threading

class Query(BaseModel):
    query: str

app = FastAPI()

def serve(system: PlanSeeking, port: int):
    global SYSTEM
    SYSTEM = system
    # we need to run the server in a separate thread, otherwise it will block the main thread which contains the query function
    thread = threading.Thread(target=uvicorn.run, args=(app,), kwargs={"host": "0.0.0.0", "port": port})
    thread.start()

@app.post("/query")
async def query_system(query: Query):
    if not SYSTEM:
        return JSONResponse(status_code=404, content={"message": "System not found"})
    if not query.query:
        return JSONResponse(status_code=400, content={"message": "Query not provided"})
    result = SYSTEM.run(query.query)
    return {"result": result}