from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from ..agent_loop import agent_loop
from ..models.schemas import AgentStatus

router = APIRouter()


class BarIntervalRequest(BaseModel):
    interval: str


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


@router.get("/settings")
async def get_settings():
    return {
        "bar_interval": agent_loop.bar_interval,
        "options": agent_loop.bar_interval_options(),
    }


@router.post("/settings/bar-interval")
async def set_bar_interval(request: BarIntervalRequest):
    try:
        await agent_loop.set_bar_interval(request.interval)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return JSONResponse({"detail": "Bar interval updated", "bar_interval": agent_loop.bar_interval})
