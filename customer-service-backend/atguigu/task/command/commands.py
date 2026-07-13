from dataclasses import dataclass
from typing import Any


@dataclass
class Command:
    command: str

    @classmethod
    def from_dict(cls, command_data: dict[str, Any]) -> "Command":
        command_type = command_data['command']
        clz = COMMAND_TO_CLASS.get(command_type)
        return clz(**command_data)


@dataclass
class StartedFlowCommand(Command):
    flow: str  # 开启的业务流程流程ID


@dataclass
class ResumedFlowCommand(Command):
    flow: str | None = None


@dataclass
class CancelFlowCommand(Command):
    pass


@dataclass
class SetSlotsCommand(Command):
    slots: dict[str, Any]


COMMAND_TO_CLASS: dict[str, type[Command]] = {

    "start_flow": StartedFlowCommand,
    "resume_flow": ResumedFlowCommand,
    "cancel_flow": CancelFlowCommand,
    "set_slots": SetSlotsCommand,
}
