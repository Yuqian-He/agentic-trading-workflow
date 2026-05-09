from typing import Any, Dict

from ..agent_loop import AgentLoop


class AgentController:
    def __init__(self, agent: AgentLoop):
        self._agent = agent

    async def start(self) -> None:
        await self._agent.start()

    async def stop(self) -> None:
        await self._agent.stop()

    async def set_ticker(self, symbol: str) -> None:
        await self._agent.set_ticker(symbol)

    async def set_interval(self, interval: str) -> None:
        await self._agent.set_bar_interval(interval)

    async def set_indicator_inputs(self, payload: Dict[str, Any]) -> None:
        await self._agent.set_indicator_inputs(payload)
