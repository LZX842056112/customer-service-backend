from atguigu.domain.state import Turn
from atguigu.domain.messages import UserMessage, BotMessage, FocusedObject, MessageType


class ChatHistoryBuilder:

    @staticmethod
    def build(turns: list[Turn]) -> str:
        """
        构建历史对话
        :return:
        Q:
        A:
        Q:
        A:
        ....
        """
        chat_messages = []
        for turn in turns:
            # 1. 先获取用户角色消息(Q)
            user_message = turn.user_message
            user_msg_str = ChatHistoryBuilder.process_user_message(user_message)
            chat_messages.append(f"USER: {user_msg_str}")

            # 2. 接着处理机器人回复消息(A)
            bot_messages = turn.bot_messages
            for bot_msg in bot_messages:
                bot_msg_str = ChatHistoryBuilder._process_bot_message(bot_msg)
                chat_messages.append(f"BOT: {bot_msg_str}")

        return "\n".join(chat_messages)

    @staticmethod
    def process_user_message(user_message: UserMessage) -> str:

        if user_message.type is MessageType.TEXT:
            return ChatHistoryBuilder._render_text_msg(user_message.text)

        return ChatHistoryBuilder._render_obj_msg(user_message.object)

    @staticmethod
    def _process_bot_message(bot_msg: BotMessage) -> str:
        if bot_msg.text:  # 有值
            return ChatHistoryBuilder._render_text_msg(bot_msg.text)

        return ChatHistoryBuilder._render_obj_msg(bot_msg.object)

    @staticmethod
    def _render_text_msg(text: str):
        return text.strip()

    @staticmethod
    def _render_obj_msg(object: FocusedObject) -> str:

        label = "订单" if object.type == "order" else "商品"
        id = object.id
        title = object.title
        attributes_str = " ".join([f"{k}={v}" for k, v in object.attributes.items()])

        return f"[id={id} label={label} title={title} attributes={attributes_str}]"
