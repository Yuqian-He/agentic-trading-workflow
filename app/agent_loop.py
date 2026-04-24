import asyncio
from datetime import datetime
from typing import Dict, Any

from .services.data_store import MarketDataStore, NewsStore, HistoricalStore
from .services.agent import StrategySelectionAgent, ExecutionDecisionAgent
from .services.rag import RAGService
from .services.signals import SignalsEngine


class AgentLoop:
    def __init__(self):
        self._task = None
        self._running = False
        self._last_bar_ts = None
        self._market_store = MarketDataStore()
        self._news_store = NewsStore()
        self._history_store = HistoricalStore()
        self._signals_engine = SignalsEngine()
        self._rag_service = RAGService(self._history_store)
        self._strategy_agent = StrategySelectionAgent()
        self._execution_agent = ExecutionDecisionAgent()
        self._state: Dict[str, Any] = {
            "last_run": None,
            "strategy": None,
            "decision": None,
            "status": "stopped",
        }

    async def start(self):
        if self._running:
            return
        self._running = True
        self._state["status"] = "running"
        self._task = asyncio.create_task(self._loop())

    async def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._state["status"] = "stopped"


    async def _loop(self):
        while self._running:
            # update market data
            self._market_store.update_tick()
            # strategy only runs when new bar arrives
            if self._market_store.is_new_bar():
                bar_ts = self._market_store.current_bar_timestamp()

                if bar_ts != self._last_bar_ts:
                    self._last_bar_ts = bar_ts
                    asyncio.create_task(self._strategy_cycle())

            await asyncio.sleep(1)

    async def _strategy_cycle(self):

        indicators = self._market_store.get_indicators()
        signals = self._signals_engine.generate(indicators)
        self._market_store.signals = signals 

        market_summary = self._market_store.market_summary()
        rag_context = self._rag_service.build_context(
            market_summary=market_summary,
            signals=signals
        )

        strategy = self._strategy_agent.select_strategy(
            market_summary,
            signals,
            rag_context
        )

        decision = self._execution_agent.decide(
            strategy,
            signals,
            rag_context
        )

        if decision["action"] != "hold":
            self._market_store.execute_order(decision)

        self._state["strategy"] = strategy
        self._state["decision"] = decision

    def status(self):
        return {
            "running": self._running,
            "last_run": self._state["last_run"],
            "strategy": self._state["strategy"],
            "decision": self._state["decision"],
            "status": self._state["status"],
        }

    def market_summary(self):
        return self._market_store.market_summary()

    def signals_summary(self):
        return self._market_store.signals_summary()


agent_loop = AgentLoop()
