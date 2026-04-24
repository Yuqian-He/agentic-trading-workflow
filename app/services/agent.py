from typing import Dict, Any


class StrategySelectionAgent:
    def select_strategy(self, market_summary: Dict[str, Any], signals: Dict[str, Any], context: Dict[str, Any]) -> str:
        # TODO: 使用 LLM 或策略规则选择最佳策略
        return "SMA"


class ExecutionDecisionAgent:
    def decide(self, strategy_name: str, signals: Dict[str, Any], context: Dict[str, Any]) -> str:
        # TODO: 使用 Agent 决策是否执行
        return "execute" if signals else "skip"
