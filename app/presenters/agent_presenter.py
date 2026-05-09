from typing import Any, Dict

from ..agent_loop import AgentLoop


class AgentPresenter:
    def __init__(self, agent: AgentLoop):
        self._agent = agent

    def status(self) -> Dict[str, Any]:
        state = self._agent._state
        return {
            "running": self._agent._running,
            "last_run": state.get("last_run"),
            "strategy": state.get("strategy"),
            "decision": state.get("decision"),
            "status": state.get("status", "stopped"),
            "last_error": state.get("last_error"),
            "symbol": self._agent.symbol,
            "bar_interval": self._agent.bar_interval,
        }

    def market_summary(self) -> Dict[str, Any]:
        return self._agent._market_store.market_summary()

    def signals_summary(self) -> Dict[str, Any]:
        summary = self._agent._signal_store.summary()
        summary["inputs"] = self._agent.indicator_inputs()
        return summary

    def features_summary(self) -> Dict[str, Any]:
        return self._agent._feature_store.summary()

    def live(self) -> Dict[str, Any]:
        raw_status = self.status()
        market_summary = self.market_summary()
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
            "signals_summary": self.signals_summary(),
            "features_summary": self.features_summary(),
        }
