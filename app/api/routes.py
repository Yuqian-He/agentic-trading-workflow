from fastapi import APIRouter, BackgroundTasks
from fastapi.responses import JSONResponse

from ..agent_loop import agent_loop
from ..models.schemas import AgentStatus

router = APIRouter()


@router.get("/status", response_model=AgentStatus)
async def get_status():
    return agent_loop.status()


@router.post("/control/start")
async def start_loop():
    await agent_loop.start()
    return JSONResponse({"detail": "Agent loop started"})


@router.post("/control/stop")
async def stop_loop():
    await agent_loop.stop()
    return JSONResponse({"detail": "Agent loop stopped"})


@router.get("/summary")
async def get_summary():
    return {
        "market_summary": agent_loop.market_summary(),
        "signals_summary": agent_loop.signals_summary(),
    }
