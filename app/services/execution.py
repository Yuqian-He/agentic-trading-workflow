from typing import Any, Dict


class ExecutionService:
    def execute_order(self, decision: Dict[str, Any]) -> None:
        # TODO: Implement simulated or IB order execution.
        print(f"Executing order: {decision}")
