from typing import Optional

from pydantic import BaseModel


class AgentStatus(BaseModel):
    running: bool
    last_run: Optional[str]
    strategy: Optional[str]
    decision: Optional[str]
    status: str
