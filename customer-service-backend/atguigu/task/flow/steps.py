from typing import Any, Self
from enum import Enum
from dataclasses import dataclass, field
from atguigu.task.flow.links import FlowStepLink, FlowStepStaticLink, FlowStepConditionLink, FlowStepFallbackLink


class FlowStepType(Enum):
    """
    start/end(通用类型)  非通用的(collect/action)
    """

    START = "start"
    COLLECT = "collect"  # 业务流程需要补充槽位---填写槽位(collect的类型一定出现在业务流程中，因为只有业务流程才知道自己要什么信息)
    ACTION = "action"  # action_listen 1. 让执行引擎停下来 action_response 2. 告诉用户要填写什么信息 action_xxx 3. 找外部要数据  # 系统流程的step类型有action的，且action的名字有且只有两种情况：  action_response(作用：告诉用户一些信息【开场白、槽位填写什么】) action_listen(作用：把控制权从应用层面交给用户层面，让用户填写槽位) action_xxx永远不会出现在系统流程中（因为找外部要数据是业务方决定的）业务流程一定会有step类型是action的，且还会有名字action_xxx(业务找外部要数据)、以及action_response(填写的槽位以及外部数据给用户看) 但是一定没有action_listen(能让流程停下来，不继续推进的只有系统流程，且这个系统流程名字system_collect_information)
    END = "end"


@dataclass(slots=True)
class ResponseDefinition:
    text: str  # 响应的内容  如果mode是static或者没有，直接将text内容渲染出去  如果mode是rephrase，text内容利用LLM根据prompt提示词改写之后的内容
    mode: str = "static"
    prompt: str | None = None


@dataclass(slots=True)
class SlotValidation:
    """
    只用对槽位做校验
     """
    condition: str
    failure_response: ResponseDefinition | None = None


@dataclass(slots=True)
class FlowStep:
    """
    步骤基类：提供四种步骤类型的通用字段
    """
    id: str  # 步骤ID
    type: FlowStepType
    next: list[FlowStepLink] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        step_type = data['type']

        clz = FLOW_STEP_TYPE_TO_CLASS[step_type]

        return clz.from_dict(data)

    @staticmethod
    def load_base_fields(step_data: dict[str, Any]) -> dict[str, Any]:
        return {
            'id': step_data['id'],
            'type': FlowStepType(step_data['type']),
            'next': FlowStep.build_links(step_data['next'])
        }

    @classmethod
    def build_links(cls, link: str | list[dict[str, Any]]) -> list[FlowStepLink]:

        links: list[FlowStepLink] = []
        if isinstance(link, str):
            links.append(FlowStepStaticLink(target=link))  # 非条件边
        else:
            for condition_link in link:
                if "if" in condition_link:
                    links.append(FlowStepConditionLink(condition=condition_link['if'], target=condition_link['then']))
                else:
                    links.append(FlowStepFallbackLink(target=condition_link['else']))

        return links


@dataclass(slots=True)
class StartFlowStep(FlowStep):

    @classmethod
    def from_dict(cls, start_step_data: dict[str, Any]):
        return cls(**FlowStep.load_base_fields(start_step_data))


@dataclass(slots=True)
class EndFlowStep(FlowStep):

    @classmethod
    def from_dict(cls, end_step_data: dict[str, Any]):
        return cls(**FlowStep.load_base_fields(end_step_data))


@dataclass(slots=True)
class ActionFlowStep(FlowStep):
    """
    定义属于自己步骤类型的字段
    """
    action: str = ""  # 行动的名字(三种action的名字:action_listen  action_response action_xxx)  必填字段
    args: dict[str, Any] = field(default_factory=dict)  # 参数指的是给外部【第三方接口【数据、{order_id}】、前端【渲染内容】】提供的数据

    @classmethod
    def from_dict(cls, action_step_data: dict[str, Any]):
        return cls(
            **FlowStep.load_base_fields(action_step_data),
            action=action_step_data['action'],
            args=action_step_data.get('args')
        )


@dataclass(slots=True)
class CollectFlowStep(FlowStep):
    slot_name: str = ""  # 收集的槽位名字
    response: ResponseDefinition = field(default_factory=ResponseDefinition)
    validate: SlotValidation | None = None  # 扩展校验机制

    @classmethod
    def from_dict(cls, collect_step_data: dict[str, Any]):
        return cls(
            **FlowStep.load_base_fields(collect_step_data),
            slot_name=collect_step_data.get('slot_name'),
            response=ResponseDefinition(
                text=collect_step_data['response']['text'],
                mode=collect_step_data['response'].get('mode'),
                prompt=collect_step_data['response'].get('prompt')
            ),
            validate=SlotValidation(
                condition=collect_step_data['validate']['condition'],
                failure_response=ResponseDefinition(
                    text=collect_step_data['validate']['failure_response']['text'],
                    mode=collect_step_data['validate'].get('failure_response').get('mode'),
                    prompt=collect_step_data['validate'].get('failure_response').get('prompt')
                ) if collect_step_data['validate'].get('failure_response') else None
            ) if collect_step_data.get('validate') else None
        )


FLOW_STEP_TYPE_TO_CLASS: dict[str, type[FlowStep]] = {
    "start": StartFlowStep,
    "end": EndFlowStep,
    "collect": CollectFlowStep,
    "action": ActionFlowStep
}
