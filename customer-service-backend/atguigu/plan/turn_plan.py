from dataclasses import dataclass, field
from typing import Any
from enum import  Enum

from atguigu.task.command.commands import Command


@dataclass
class TaskTurnPlan:
    commands: list[Command] = field(default_factory=list)

    @classmethod
    def from_dict(cls, task_data: dict[str, Any]) -> "TaskTurnPlan":
        return cls(
            commands=[Command.from_dict(task_dict) for task_dict in task_data.get('commands', [])]
        )


@dataclass
class KnowledgeTurnPlan:
    intents: list[str]

    @classmethod
    def from_dict(cls, knowledge_data: dict[str, Any]) -> "KnowledgeTurnPlan":
        return cls(intents=knowledge_data.get('intents', []))


class ChitChatTurnPlan:
    pass


@dataclass
class TurnPlan:
    task: TaskTurnPlan | None = None
    knowledge: KnowledgeTurnPlan | None = None
    chitchat: ChitChatTurnPlan | None = None

    @classmethod
    def from_dict(cls, turn_plan_data: dict[str, Any]) -> "TurnPlan":
        return cls(
            task=TaskTurnPlan.from_dict(turn_plan_data['task']) if turn_plan_data.get('task') else None,
            knowledge=KnowledgeTurnPlan.from_dict(turn_plan_data['knowledge']) if turn_plan_data.get(
                'knowledge') else None,
            chitchat=ChitChatTurnPlan() if turn_plan_data.get('chitchat') else None,
        )



    def activated_tracks(self):
        tracks=[]

        if self.task is not None:
            tracks.append("task")
        if self.knowledge is not None:
            tracks.append("knowledge")
        if self.chitchat is not None:
            tracks.append("chichat")


        return tracks




class ClarifyReason(Enum):
    MISSING_TRACK = "missing_track"
    MULTIPLE_TRACKS = "multiple_tracks"
    MISSING_TASK_COMMANDS = "missing_task_commands"
    MISSING_KNOWLEDGE_INTENT = "missing_knowledge_intent"
    INVALID_TASK_COMMANDS = "invalid_task_commands"
    MULTIPLE_TASK_FLOWS = "multiple_task_flows"
    UNKNOWN_TASK_FLOW = "unknown_task_flow"
    MISSING_FOCUSED_OBJECT = "missing_focused_object"
    OBJECT_REQUIRES_INTENT = "object_requires_intent"


@dataclass
class TurnPlanValidateResult:
    """
    校验器的校验结果
    """

    valid: bool  # 校验通过或者失败
    reason:ClarifyReason | None = None
