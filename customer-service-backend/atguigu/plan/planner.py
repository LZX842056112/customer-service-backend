import json
from typing import Any
from dataclasses import asdict

from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import JsonOutputParser

from atguigu.plan.turn_plan import TurnPlan
from atguigu.domain.messages import UserMessage
from atguigu.domain.state import DialogueState
from atguigu.prompts.loader import load_prompt_template
from atguigu.infrastructure.llm_client import llm_client
from atguigu.history.builder import ChatHistoryBuilder
from atguigu.task.flow.flows import FlowsList
from atguigu.knowledge.intents import KnowledgeIntent


class TurnPlanner:
    """
    对话轮次规划器
    """

    async def predict(self,
                      user_message: UserMessage,
                      *,
                      state: DialogueState,
                      flow_list: FlowsList,
                      intents: dict[str, KnowledgeIntent]
                      ) -> TurnPlan:
        # 1. 构建提示词模版要的内容（不需要构建提示词模版）

        prompt_inputs: dict[str, Any] = self._prepare_prompt_inputs(user_message, state=state, flow_list=flow_list,
                                                                    intents=intents)

        # 2. 调用大语言模型
        turn_plan = await self.predict_from_prompt_inputs(prompt_inputs)

        return turn_plan

    def _prepare_prompt_inputs(self,
                               user_message: UserMessage,
                               state: DialogueState,
                               flow_list: FlowsList,
                               intents: dict[str, KnowledgeIntent]
                               ) -> dict[str, Any]:
        user_message = ChatHistoryBuilder.process_user_message(user_message)
        current_conversation = ChatHistoryBuilder.build(state.current_session().turns[-10:])

        focused_object_json = json.dumps(state.focused_object.to_dict(),
                                         ensure_ascii=False) if state.focused_object else "null"

        interrupted_tasks_json = json.dumps([paused_task.to_dict() for paused_task in state.interrupted_active_tasks],
                                            ensure_ascii=False)

        active_task_json = json.dumps(state.active_task.to_dict(),
                                      ensure_ascii=False) if state.active_task else "null"

        # 业务流程(只用提供业务流程给LLM :需要业务流程信息 不需要系统流程信息，且业务流程也不需要steps)
        available_flows_json = json.dumps({
            "flows": [
                {
                    k: v for k, v in asdict(flow).items() if k != "steps"
                } for flow in flow_list.flows if not flow.flow_id.startswith("system_")
            ]
        }, ensure_ascii=False)

        # 知识意图的清单
        knowledge_intents_json = json.dumps(
            [{"id": intent.id, "description": intent.description} for intent in intents.values()],
            ensure_ascii=False
        )

        return {
            "user_message": user_message,
            "current_conversation": current_conversation,

            "focused_object_json": focused_object_json,

            "interrupted_tasks_json": interrupted_tasks_json,
            "active_task_json": active_task_json,

            "available_flows_json": available_flows_json,
            "knowledge_intents_json": knowledge_intents_json

        }

    async def predict_from_prompt_inputs(self, prompt_inputs: dict[str, Any]) -> TurnPlan:
        # 1. 加载提示词模版
        task_prompt_template = load_prompt_template("turn_plan")

        # 2. 解析
        prompt_template = PromptTemplate.from_template(template=task_prompt_template, template_format="jinja2")

        # 3. 构建链执行(提示词模版对象 | 模型实现对象 | json输出解析器对象)
        chain = prompt_template | llm_client | JsonOutputParser()

        turn_plan_dict = await chain.ainvoke(
            prompt_inputs)  # 原始输入---> prompt_template.invoke(原始输入) 格式化提示词模版---> llm_client.invoke(格式化后提示词) 调用大语言模型,得到结果---> JsonOutputParser.invoke(LLM输出结果)---> dict(应用使用)

        # 4. 返回
        return TurnPlan.from_dict(turn_plan_dict)
