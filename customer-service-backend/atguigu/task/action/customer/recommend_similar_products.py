from typing import Any

from atguigu.domain.state import DialogueState
from atguigu.task.action.base import Action, ActionResult


class RecommendSimilarProductsAction(Action):
    name = "action_recommend_similar_products"

    def run(self, state: DialogueState, action_args: dict[str, Any]) -> ActionResult:
        """
        从中台服务中查询商品推荐的接口
        :param state:
        :param action_args:
        :return:
        """
        pass




