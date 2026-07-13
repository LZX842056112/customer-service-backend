from dataclasses import dataclass, field
from typing import Any

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
