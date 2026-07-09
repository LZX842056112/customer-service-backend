"""
整个对话的完整信息（聚合根） DDD(领域数据模型)
存储某个一个用户的对话完整信息

三个部分：
1.流程相关
2.卡片相关
3.会话相关：Session:会话  开启一次会话创建一个Session对象（会话的额外信息：会话时间、关闭时间... 核心信息：用户对话内容（Q->A）Turn:属性：turns:List[Turn] Turn:user_message bot_message列表）

"""
from typing import Any
from dataclasses import dataclass, field
from atguigu.domain.messages import UserMessage, BotMessage, FocusedObject
from atguigu.domain.contexts import TaskContext, SystemContext


@dataclass(slots=True)
class Turn:
    """
    对话的轮次
    """
    turn_id: str  # 对话轮次标识
    user_message: UserMessage
    bot_messages: list[BotMessage]

    def to_dict(self) -> dict[str, Any]:
        return {
            "turn_id": self.turn_id,
            "user_message": self.user_message.to_dict(),
            "bot_messages": [bot_message.to_dict() for bot_message in self.bot_messages]
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Turn":
        return cls(
            turn_id=data['turn_id'],
            user_message=data['user_message'],
            bot_messages=[BotMessage.from_dict(bot_message_dict) for bot_message_dict in data.get('bot_messages', [])]
        )


@dataclass(slots=True)
class Session:
    """
    会话：存活时间（1.会话超时[60分钟],重新创建session 2.扩展：手动触发session失效，重新创建新的session ）
    """
    session_id: str  # 会话标识
    started_at: float  # session开启时间
    last_activity_at: float  # session最后一次激活时间（超时判定）
    closed_at: float | None = None  # session关闭时间 如果closed_at有值：session关了 没有值是None:代表session可以继续用
    turns: list[Turn] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "started_at": self.started_at,
            "last_activity_at": self.last_activity_at,
            "closed_at": self.closed_at,
            "turns": [turn.to_dict() for turn in self.turns]
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Session":
        return cls(
            session_id=data['session_id'],
            started_at=data['started_at'],
            last_activity_at=data['last_activity_at'],
            closed_at=data['closed_at'],
            turns=[Turn.from_dict(turn_dict) for turn_dict in data.get('turns', [])]
        )


@dataclass(slots=True)
class DialogueState:
    """
    整个引擎操作的就是一个大对象DialogueState聚合根
    对话聚合根对象 (每一个用户都是一份独立的对话状态)

    DialogueState对象涉及到持久化（IO）

    """

    # 1.流程相关字段(当前业务流程 中断的业务流程  当前系统流程)
    # 2.卡片相关字段(focused_object)
    # 3.会话相关字段(sessions  current_session_id  pending_turn)

    sender_id: str  # 用户ID
    active_task: TaskContext | None = None  # 当前业务流程
    interrupted_active_tasks: list[TaskContext] = field(default_factory=list)  # 当前中断的业务流程
    active_system_task: SystemContext | None = None  # 当前系统流程
    focused_objet: FocusedObject | None = None  # 卡片对象
    sessions: list[Session] = field(default_factory=list)
    current_session_id: str | None = None
    pending_turn: Turn | None = None

    def to_dict(self) -> dict:
        """
        将DialogueState转成字典对象

        :return:
        """

        return {
            "sender_id": self.sender_id,
            "active_task": self.active_task.to_dict() if self.active_task is not None else None,
            "interrupted_active_tasks": [interrupted_task.to_dict() for interrupted_task in
                                         self.interrupted_active_tasks],
            "active_system_task": self.active_system_task.to_dict() if self.active_system_task is not None else None,
            "focused_objet": self.focused_objet.to_dict() if self.focused_objet is not None else None,
            "sessions": [session.to_dict() for session in
                         self.sessions],
            "current_session_id": self.current_session_id,
            "pending_turn": self.pending_turn.to_dict() if self.pending_turn is not None else None,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DialogueState":
        return cls(
            sender_id=data['sender_id'],
            active_task=TaskContext.from_dict(data['active_task']) if data.get('active_task') else None,
            interrupted_active_tasks=[TaskContext.from_dict(interrupted_tasks_dict) for interrupted_tasks_dict in
                                      data['interrupted_active_tasks']] if data.get('interrupted_active_tasks') else [],
            active_system_task=SystemContext.from_dict(data['active_system_task']) if data.get(
                'active_system_task') else None,
            focused_objet=FocusedObject.from_dict(data['focused_objet']) if data.get('focused_objet') else None,

            sessions=[Session.from_dict(session_dict) for session_dict in
                      data['sessions']] if data.get('sessions') else [],

            current_session_id=data.get('current_session_id'),
            pending_turn=Turn.from_dict(data['pending_turn']) if data.get('pending_turn') else None
        )







