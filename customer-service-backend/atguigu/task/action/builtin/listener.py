from typing import Any

from atguigu.domain.state import DialogueState
from atguigu.task.action.base import Action, ActionResult


class ActionListener(Action):

    name = "action_listen"

    def run(self,
            state: DialogueState,
            action_args: dict[str, Any]) -> ActionResult:
        pass

