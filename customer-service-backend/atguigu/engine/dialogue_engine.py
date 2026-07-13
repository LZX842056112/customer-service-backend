import time

from atguigu.domain.state import DialogueState
from atguigu.domain.messages import ProcessResult, BotMessage, UserMessage, MessageType
from atguigu.plan.planner import TurnPlanner
from atguigu.task.handler import TaskHandler
from atguigu.knowledge.handler import KnowledgeHandler
from atguigu.chitchat.handler import ChitChatHandler
from atguigu.task.flow.flows import FlowsList


class DialogueEngine:
    """
    对话引擎（调用LLM /推进流程...）
    """

    def __init__(self,
                 planner: TurnPlanner,
                 task_handler: TaskHandler,
                 knowledge_handler: KnowledgeHandler,
                 chitchat_handler: ChitChatHandler

                 ):
        self.planner = planner
        self.task_handler = task_handler
        self.knowledge_handler = knowledge_handler
        self.chitchat_handler = chitchat_handler

    async def hand_message(self,
                           user_message: UserMessage,
                           state: DialogueState) -> ProcessResult:
        """
        引擎处理消息
        :param dialogue_state:
        :return:
        """

        # 1. 准备session对象
        self._prepare_session(state)

        # 2. 创建turn
        self._begin_turn(user_message, state)

        # 3. 判断消息类型
        # 3.1 文本消息类型
        if user_message.type is MessageType.TEXT:
            bot_msgs = await self._hand_text_msg(user_message, state=state, flow_list=self.task_handler.flow_list)


        # 3.2 对象消息类型
        else:
            # 不会调用LLL 去路由对应的轨道（消息类型是对象的话，明确了，要做的事）接收卡片内容，处理卡片内容
            # state.focused_object= user_message.object
            self._hand_obj_msg()

        return ProcessResult(sender_id="1001", message_id="11111",
                             messages=[BotMessage(text="我是电商客服，请问你有什么问题需要我帮助的嘛")])

    def _prepare_session(self, state: DialogueState):
        """
        确保session要有
        :param state:
        :return:
        """

        # 1. 获取当前session
        current_session = state.current_session()

        # 2. 当前session是否存在
        # 2.1 session不存在
        if current_session is None:
            state.start_session()
            return

        # 3. 当前session存在
        now = time.time()
        # 3.1 判断当前session是否有有效（session的时间是否超时60min）
        if now - current_session.last_activity_at > 60 * 60:
            # a) 关闭过期的session
            state.close_session()
            # b) 重置过期信息
            state.reset_running_state_for_new_session()
            # c) 创建session
            state.start_session()
        # 3.2 当前session没有过期，继续使用
        else:
            # 修改最后一次激活时间
            current_session.last_activity_at = now

        return

    def _begin_turn(self,
                    user_message: UserMessage,
                    state: DialogueState):
        state.start_turn(user_message)

    async def _hand_text_msg(self,
                             user_message: UserMessage,
                             *,
                             state: DialogueState,
                             flow_list: FlowsList) -> list[BotMessage]:
        """
        1. 调用大语言模型，目的：TurnPlanner根据任务路由对应的轨道(轨道一:业务任务轨道 轨道二:知识查询任务轨道 轨道三:闲聊任务轨道)
        2. TurnPlanValidator校验器校验大语言模型结果的'封装对象'
        # 2.1 校验失败---ClarifyResponder意图澄清器做意图澄清--内部自己产生了消息
        # 2.2 校验成功---根据对应的任务轨道，处理该轨道的逻辑(各自轨道的处理器：TaskHandler/KnowledgeHandler/ChitChatHandler)---内部产生机器人消息
        # 3. 提交turn
        # 4. 内部机器人的消息返回
        :param user_message:
        :param state:
        :return:
        调用LLM（1.给LLM什么数据 2.获取什么的数据）prompt的提示词---->程序自己根据业务定义的
        """
        turn_plan = await self.planner.predict(user_message, state=state, flow_list=flow_list)

        return [BotMessage(text="你好")]

    def _hand_obj_msg(self):
        pass
