from typing import Any, Dict


def present_status(raw_status: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "running": raw_status.get("running", False),
        "last_run": raw_status.get("last_run"),
        "strategy": raw_status.get("strategy"),
        "decision": raw_status.get("decision"),
        "status": raw_status.get("status", "stopped"),
        "symbol": raw_status.get("symbol"),
        "bar_interval": raw_status.get("bar_interval"),
    }


def present_live(raw_status: Dict[str, Any], market_summary: Dict[str, Any], signals_summary: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "running": raw_status.get("running", False),
        "status": raw_status.get("status", "stopped"),
        "last_error": raw_status.get("last_error"),
        "last_run": raw_status.get("last_run"),
        "user_input": {
            "ticker": raw_status.get("symbol"),
            "interval": raw_status.get("bar_interval"),
        },
        "latest_price": market_summary.get("latest_price"),
        "tick": market_summary.get("tick"),
        "bar": market_summary.get("bar"),
        "signals_summary": signals_summary or {},
    }
