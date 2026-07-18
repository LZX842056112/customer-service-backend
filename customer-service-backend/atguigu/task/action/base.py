from abc import ABC, abstractmethod
from typing import Any
from dataclasses import dataclass, field
from atguigu.domain.messages import BotMessage
from atguigu.domain.state import DialogueState


@dataclass
class ActionResult:
    messages: list[BotMessage] = field(default_factory=list)
    slot_updates: dict[str, Any] = field(default_factory=dict)

@dataclass
class ActionCall:
    action_name: str
    action_kwargs: dict[str, Any] = field(default_factory=dict)



class Action(ABC):
    """
    基类Action
    """
    name: str  # 抽象action的名字属性

    @abstractmethod
    async  def run(self,
            state: DialogueState,
            action_args: dict[str, Any]
            ) -> ActionResult:
        pass
