import asyncio
import json
from typing import Any
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser

from atguigu.infrastructure.llm_client import llm_client
from atguigu.plan.turn_plan import ClarifyReason
from atguigu.domain.state import DialogueState
from atguigu.domain.messages import BotMessage
from atguigu.prompts.loader import load_prompt_template
from atguigu.history.builder import ChatHistoryBuilder


class ClarifyResponser:
    """
    意图澄清响应器(把响应内容给用户展示)
    """

    async def respond(self,
                      reason: ClarifyReason,
                      state: DialogueState
                      ) -> list[BotMessage]:
        # 1. 构建意图澄清提示词模版要的内容
        prompt_inputs: dict[str, Any] = self._build_clarify_prompt_inputs(reason, state)

        # 2. 调用LLM生成澄清的文本
        return await self._invoke_respond(prompt_inputs)

    async def _invoke_respond(self, prompt_inputs: dict[str, Any]) -> list[BotMessage]:
        clarify_prompt_template = load_prompt_template("clarify_respond")

        prompt_template = PromptTemplate.from_template(template=clarify_prompt_template, template_format="jinja2")

        chain = prompt_template | llm_client | StrOutputParser()

        rewritten_result = await chain.ainvoke(prompt_inputs)

        return [BotMessage(text=rewritten_result)]

    def _build_clarify_prompt_inputs(self,
                                     reason: ClarifyReason,
                                     state: DialogueState) -> dict[str, Any]:
        user_message_str = ChatHistoryBuilder.process_user_message(state.pending_turn.user_message)
        history_str = ChatHistoryBuilder.build(state.current_session().turns[-10:])
        focused_object_str = json.dumps(state.focused_object.to_dict(),
                                        ensure_ascii=False) if state.focused_object else "null"
        clarify_message = self._build_base_script(reason, state)
        return {
            "reason": reason.value,  # 枚举的字符串内容
            "clarify_message": clarify_message,
            "focused_object": focused_object_str,
            "history": history_str,
            "user_message": user_message_str

        }

    def _build_base_script(self, reason: ClarifyReason, state: DialogueState) -> str:
        if reason is ClarifyReason.MULTIPLE_TRACKS:
            return "你这次同时提到了多个方向。我们先处理一个，你想先办业务还是先咨询信息呢？"

        if reason is ClarifyReason.MISSING_FOCUSED_OBJECT:
            return "请先发送你想咨询的对象，我再继续帮你看。"

        if reason is ClarifyReason.MISSING_KNOWLEDGE_INTENT:
            return "你是想了解商品信息、订单信息，还是售后配送规则呢？"

        if reason is ClarifyReason.MISSING_TRACK:
            return "你是想先处理业务问题，还是先咨询信息呢？"

        if reason is ClarifyReason.MISSING_TASK_COMMANDS:
            return "你这次是想办理什么业务呢？比如查订单、查物流，或者申请退款。"

        if reason is ClarifyReason.OBJECT_REQUIRES_INTENT:
            focused_object = state.focused_object
            if focused_object is not None and focused_object.type == "order":
                return "我已经收到这个订单了。你想查订单状态、查物流，还是申请退款呢？"
            if focused_object is not None and focused_object.type == "product":
                return "我已经收到这个商品了。你想了解它的商品信息、发货情况，还是售后相关问题呢？"

        return "我还需要再确认一下你的意思，你可以换个更具体的说法告诉我。"
