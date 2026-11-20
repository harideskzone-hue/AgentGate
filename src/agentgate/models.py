from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


class ScenarioType(str, Enum):
    BENIGN = "benign"
    ATTACK = "attack"


class Scenario(BaseModel):
    id: str
    type: ScenarioType
    goal: str = Field(min_length=10)
    tags: list[str] = Field(default_factory=list)
    max_steps: int = Field(default=10, ge=1, le=50)


class Step(BaseModel):
    run_id: int
    index: int = Field(ge=0)
    kind: Literal[
        "model",
        "tool_call",
        "tool_result",
        "policy_decision",
    ]
    payload: dict[str, Any]
