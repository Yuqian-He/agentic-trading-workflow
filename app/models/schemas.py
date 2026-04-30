from typing import Any, Optional

from pydantic import BaseModel


class AgentStatus(BaseModel):
    running: bool
    last_run: Optional[str]
    strategy: Optional[Any]
    decision: Optional[Any]
    status: str
    symbol: str
    bar_interval: str
