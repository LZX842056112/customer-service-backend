"""
整个对话的完整信息（聚合根） DDD(领域数据模型)
存储某个一个用户的对话完整信息

三个部分：
1.流程相关
2.卡片相关
3.会话相关：Session:会话  开启一次会话创建一个Session对象（会话的额外信息：会话时间、关闭时间... 核心信息：用户对话内容（Q->A）Turn:属性：turns:List[Turn] Turn:user_message bot_message列表）

"""
import uuid, time
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
            user_message=UserMessage.from_dict(data['user_message']),
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
            "closed_at": self.last_activity_at,
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
    active_task: TaskContext | None = None  # 当前正在运行的业务流程
    interrupted_active_tasks: list[TaskContext] = field(default_factory=list)  # 当前已经中断的业务流程
    active_system_task: SystemContext | None = None  # 当前正在执行的系统流程
    focused_object: FocusedObject | None = None  # 卡片对象
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
            "focused_object": self.focused_object.to_dict() if self.focused_object is not None else None,
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
            focused_object=FocusedObject.from_dict(data['focused_object']) if data.get('focused_object') else None,

            sessions=[Session.from_dict(session_dict) for session_dict in
                      data['sessions']] if data.get('sessions') else [],

            current_session_id=data.get('current_session_id'),
            pending_turn=Turn.from_dict(data['pending_turn']) if data.get('pending_turn') else None
        )

    # ==========================流程相关==========================

    def start_active_system_task(self, system_context: SystemContext) -> None:
        """
        开启并激活系统流程(任务)
        :return:
        """
        self.active_system_task = system_context

    def end_activating_system_task(self):
        """
         结束正在激活的系统流程(任务)
        :return:
        """
        self.active_system_task = None

    def start_active_business_task(self, task_context: TaskContext) -> None:
        """
        开启并激活业务流程(任务)
        :param task_context:
        :return:
        """
        self.active_task = task_context

    def end_activating_business_task(self) -> None:
        """
         结束正在激活的业务流程(任务))
        :return:
        """
        self.active_task = None

    def end_activating_task(self):
        """
        结束正在运行的流程（清空业务流程和系统流程）
        :return:
        """
        self.active_task = None
        self.active_system_task = None

    def interrupted_activating_task(self):
        """
        中断正在运行的业务流程
        :return:
        """
        # 1. 将正在运行的业务流程存储到栈中
        self.interrupted_active_tasks.append(self.active_task)
        # 2. 并且清空当前正在运行的业务流程,准备接收新的业务流程
        self.active_task = None

    def resumed_interrupted_business_task(self, flow_id: str | None = None) -> bool:
        """
         恢复中断的业务流程
        :return:
        """

        # 1. 检验栈中是否有元素
        if not self.interrupted_active_tasks:
            return False

        # 2. 判断流程ID 是否为空
        if flow_id is None:
            interrupted_active_task = self.interrupted_active_tasks.pop()
            self.active_task = interrupted_active_task
            return True

        # 3. 遍历（找指定中断的业务流程）
        for i, interrupted_task in enumerate(self.interrupted_active_tasks):
            if interrupted_task.flow_id == flow_id:
                self.active_task = interrupted_task
                del self.interrupted_active_tasks[i]
                return True
        return False

    def current_activating_task(self):
        """
        当前正在运行的流程(业务流程、系统流程？)
        业务流程有 系统流程没有：获取业务流程
        系统流程有 业务流程没有：获取系统流程
        系统流程有 业务流程也有： 优先获取系统流程：
        :return:
        """

        return self.active_system_task or self.active_task

    # ==========================槽位相关==========================

    def set_slots(self, slots: dict[str, Any]):
        """
        设置槽位
        :param slots:
        :return:
        """
        if self.active_task is not None:
            self.active_task.slots.update(slots)

    def remove_slot(self, slot_name: str) -> Any:
        """
        根据槽位名读取槽位的值
        :param slot_name:
        :return:
        """
        return self.active_task.slots.pop(slot_name)

    # ==========================卡片相关==========================

    def set_focused_object(self, focused_object: FocusedObject):
        self.focused_object = focused_object

    # ==========================session(会话)相关==========================

    def current_session(self) -> Session | None:
        """
        返回当前session对象
        :return:
        """

        for session in self.sessions:
            if session.session_id == self.current_session_id:
                return session
        return None

    def start_session(self):

        now = time.time()
        # 1. 创建session对象
        session = Session(session_id=str(uuid.uuid4()), started_at=now, last_activity_at=now)

        # 2. 更新当前的session_id
        self.current_session_id = session.session_id

        # 3. 将session对象存储到session中
        self.sessions.append(session)

    def close_session(self):
        """
        关闭session对象
        :return:
        """

        if self.current_session() is not None:
            # 1. 修改session的关闭时间
            self.current_session().closed_at = time.time()
            # 2. 清空当前session id
            self.current_session_id = None
            # 3. 不要从sessions中移除

    def reset_running_state_for_new_session(self):
        """
        session超时(session超时时间是60min)
        :return:
        """

        # 1.清空任务相关的
        self.active_task = None
        self.interrupted_active_tasks = list()
        self.active_system_task = None

        # 2.清空卡片
        self.focused_object = None

        # 3.清空缓存区
        self.pending_turn = None

    # ==========================Turn(轮次)相关==========================

    def start_turn(self, user_message: UserMessage):
        """

        :return:
        """
        if self.current_session() is not None:
            turn = Turn(turn_id=str(uuid.uuid4()), user_message=user_message, bot_messages=[])
            self.pending_turn = turn

    def commit_pending_turn(self):
        """
        提交缓冲区的内容
        :return:
        """
        self.current_session().turns.append(self.pending_turn)
        self.pending_turn = None
