from typing import Any
from dataclasses import field, dataclass, asdict

"""

定义两个数据模型
业务流程
系统流程
上下文概念：
把动态(变化)的东西，装进去
承载动态可变的内容(上下文)

TaskContext/SystemContext各个子类未来给引擎使用(运行流程以及执行流程的步骤)
引擎未来执行流程【不固定】哪一步（信息数据）----TaskContext(flow_id step_id) 是抽象
"""


@dataclass(slots=True)
class TaskContext:
    """
    业务流程的上下文（运行期间【流程在变换】某一个业务流程的信息）
    """

    flow_id: str  # 业务流程的流程ID
    step_id: str  # 某一个业务流程对应的步骤ID
    slots: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "flow_id": self.flow_id,
            "step_id": self.step_id,
            "slots": dict(self.slots)
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TaskContext":
        return cls(
            flow_id=data['flow_id'],
            step_id=data['step_id'],
            slots=data.get('slots')
        )


@dataclass(slots=True)
class SystemContext:
    """
    系统流程的模版
    """
    flow_id: str  # 开启的系统流程ID(不同的阶段)
    step_id: str  # 开启系统流程的步骤ID(某一个流程下的不同的步骤)

    def to_dict(self) -> dict[str, Any]:
        """将具体的子类对象转成字典 asdict()"""
        return asdict(self)  # type:ignore

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SystemContext":
        """
        将字典转成对应的子类对象
        :param data:
        :return:
        """
        clz = SYSTEM_CONTEXT_TO_CLASS[data['flow_id']]
        return clz(**data)


@dataclass(slots=True)
class StartedSystemContext(SystemContext):
    """
    触发时机 开启业务流程的时候(先触发)
    """
    started_flow_id: str  # 具体开启的业务流程(变化)
    started_flow_name: str  # 具体开启的业务流程的名字


@dataclass(slots=True)
class InterruptedSystemContext(SystemContext):
    """
    触发时机 中断某一个业务流程的时候(场景：之前正在进行A业务流程 接着开启B的业务流程 底层：先把之前的业务流程存储起来，然后在开启新的业务流程：中断的开场白)
    """
    interrupted_flow_id: str  # 中断的业务流程ID
    interrupted_flow_name: str  # 中断的业务流程名字
    started_flow_id: str  # 开启新的业务流程ID
    started_flow_name: str  # 开启新的业务流程名字


@dataclass(slots=True)
class ResumedSystemContext(SystemContext):
    """
    触发时机 恢复某一个业务流程的时候( 场景: 之前正在进行A业务流程，开启了B的业务流程，接着B的业务流程做完了，继续执行A的业务流程)
    """

    resumed_flow_id: str  # 中断的业务流程ID
    resumed_flow_name: str  # 中断的业务流程名字


@dataclass(slots=True)
class CanceledSystemContext(SystemContext):
    """
    触发时机  取消某一个已经开启的业务流程(场景： 之前开启了一个业务流程，接着你说取消掉，不做了)
    """
    canceled_flow_id: str  # 取消的业务流程ID
    canceled_flow_name: str  # 取消的业务流程名字


@dataclass(slots=True)
class CollectedSystemContext(SystemContext):
    """
    触发时机 当某一个业务流程要补充槽位信息的时候，会触发。1. 告诉用户槽位填写什么 2.收集用户填写这个槽位的名字order_number----下游如果有逻辑继续使用用户填写的槽位信息就可以使用
    """

    response: dict[str, Any]  # {"text": "请告诉我你的订单号。"}
    slot_name: str  # 槽位名字 "order_number"


SYSTEM_CONTEXT_TO_CLASS: dict[str, Any] = {

    "system_task_started": StartedSystemContext,
    "system_task_resumed": ResumedSystemContext,
    "system_collect_information": CollectedSystemContext,
    "system_task_interrupted": InterruptedSystemContext,
    "system_task_canceled": CanceledSystemContext
}
