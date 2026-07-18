from typing import Any

from atguigu.domain.messages import BotMessage
from atguigu.domain.state import DialogueState
from atguigu.task.action.base import Action, ActionResult


class ActionResponse(Action):
    name = "action_response"

    async def run(self,
                  state: DialogueState,
                  action_args: dict[str, Any]) -> ActionResult:
        """
        生成回复：回复的模版内容 （action_args：{"text":"{{name}}...."}）
        :param state:
        :param action_args:
        :return:
        """
        text = action_args.get('text')
        return ActionResult(messages=[BotMessage(text=text)])
