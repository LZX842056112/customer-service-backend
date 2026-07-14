from dataclasses import dataclass, field, asdict
from atguigu.task.flow.steps import FlowStep


@dataclass(slots=True)
class FlowSlot:
    name: str  # 槽位名字
    type: str  # 槽位的类型
    label: str
    description: str


@dataclass(slots=True)
class Flow:
    """
    流程
    """
    flow_id: str  # (不分业务、系统)流程ID
    flow_name: str  # (不分业务、系统)流程名字
    description: str  # (不分业务、系统)流程描述（非常重要，给大语言模型【工具信息以及工具描述给LLM,目的让大语言模型根据任务选择处理任务的工具】，未来把所有的业务流程给LLM,然后让LLM根据任务 来选择到底要开启哪个业务流程）
    steps: list[FlowStep] = field(default_factory=list)
    slots: dict[str, FlowSlot] = field(default_factory=dict)  # 将业务流程用到的槽位封装到Flow


@dataclass(slots=True)
class FlowsList:
    """
    一个结构表示两份yaml文件
    """
    flows: list[Flow] = field(default_factory=list)  # 两份yaml的flows内容
    slots: dict[str, FlowSlot] = field(default_factory=dict)  # 两份yaml的slots内容



    def  get_flow_by_id(self,flow_id:str)->Flow | None:

        for flow in self.flows:
            if flow.flow_id==flow_id:
                return  flow
        return  None
