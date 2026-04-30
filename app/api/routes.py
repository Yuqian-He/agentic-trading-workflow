from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from ..agent_loop import agent_loop
from ..models.schemas import AgentStatus

router = APIRouter()


class BarIntervalRequest(BaseModel):
    interval: str


class TickerRequest(BaseModel):
    symbol: str


@router.get("/status", response_model=AgentStatus)
async def get_status():
    return agent_loop.status()


@router.post("/control/start")
async def start_loop():
    try:
        await agent_loop.start()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to start loop: {exc}")
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

@router.get("/live")
async def get_live():
    return agent_loop.live_view()


@router.get("/settings")
async def get_settings():
    return {
        "symbol": agent_loop.symbol,
        "ticker_options": agent_loop.ticker_options(),
        "bar_interval": agent_loop.bar_interval,
        "options": agent_loop.bar_interval_options(),
    }


@router.post("/settings/bar-interval")
async def set_bar_interval(request: BarIntervalRequest):
    try:
        await agent_loop.set_bar_interval(request.interval)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to update bar interval: {exc}")
    return JSONResponse({"detail": "Bar interval updated", "bar_interval": agent_loop.bar_interval})


@router.post("/settings/ticker")
async def set_ticker(request: TickerRequest):
    try:
        await agent_loop.set_ticker(request.symbol)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to update ticker: {exc}")
    return JSONResponse({"detail": "Ticker updated", "symbol": agent_loop.symbol})
