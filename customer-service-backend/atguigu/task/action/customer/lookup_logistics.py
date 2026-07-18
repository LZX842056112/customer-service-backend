from typing import Any

from atguigu.domain.state import DialogueState
from atguigu.task.action.base import Action, ActionResult


class LookupOrderStatusAction(Action):
    name = "action_lookup_order_status"

    async def run(self, state: DialogueState, action_args: dict[str, Any]) -> ActionResult:
        """
        从中台服务中查询订单状态接口
        :param state:
        :param action_args:
        :return:
        """
        return ActionResult(slot_updates={})
