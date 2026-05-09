from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from ..agent_loop import agent_loop
from ..models.schemas import AgentStatus
from ..presenters.agent_presenter import AgentPresenter
from ..services.agent_controller import AgentController
from ..services.ui_settings import UISettingsService

router = APIRouter()
presenter = AgentPresenter(agent_loop)
controller = AgentController(agent_loop)


class BarIntervalRequest(BaseModel):
    interval: str


class TickerRequest(BaseModel):
    symbol: str


class IndicatorInputsRequest(BaseModel):
    sma: dict = {}
    rsi: dict = {}


@router.get("/status", response_model=AgentStatus)
async def get_status():
    return presenter.status()


@router.post("/control/start")
async def start_loop():
    try:
        await controller.start()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to start loop: {exc}")
    return JSONResponse({"detail": "Agent loop started"})


@router.post("/control/stop")
async def stop_loop():
    await controller.stop()
    return JSONResponse({"detail": "Agent loop stopped"})


@router.get("/summary")
async def get_summary():
    return {
        "market_summary": presenter.market_summary(),
        "signals_summary": presenter.signals_summary(),
        "features_summary": presenter.features_summary(),
    }

@router.get("/live")
async def get_live():
    return presenter.live()


@router.get("/settings")
async def get_settings():
    return {
        "symbol": agent_loop.symbol,
        "ticker_options": UISettingsService.ticker_options(),
        "bar_interval": agent_loop.bar_interval,
        "options": UISettingsService.bar_interval_options(),
        "indicator_inputs": agent_loop.indicator_inputs(),
    }


@router.post("/settings/bar-interval")
async def set_bar_interval(request: BarIntervalRequest):
    try:
        await controller.set_interval(request.interval)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to update bar interval: {exc}")
    return JSONResponse({"detail": "Bar interval updated", "bar_interval": agent_loop.bar_interval})


@router.post("/settings/ticker")
async def set_ticker(request: TickerRequest):
    try:
        await controller.set_ticker(request.symbol)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to update ticker: {exc}")
    return JSONResponse({"detail": "Ticker updated", "symbol": agent_loop.symbol})


@router.post("/settings/indicator-inputs")
async def set_indicator_inputs(request: IndicatorInputsRequest):
    try:
        payload = request.model_dump() if hasattr(request, "model_dump") else request.dict()
        await controller.set_indicator_inputs(payload)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to update indicator inputs: {exc}")
    return JSONResponse({"detail": "Indicator inputs updated", "indicator_inputs": agent_loop.indicator_inputs()})
