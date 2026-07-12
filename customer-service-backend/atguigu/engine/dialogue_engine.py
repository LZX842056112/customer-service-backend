from atguigu.domain.state import DialogueState
from atguigu.domain.messages import ProcessResult, BotMessage,FocusedObject


class DialogueEngine:
    """
    对话引擎（调用LLM /推进流程...）
    """

    def hand_message(self, dialogue_state: DialogueState) -> ProcessResult:
        dialogue_state.focused_object = FocusedObject(
            id="A1001",
            type="order",
            title="买了个飞机",
            attributes={
                "price":1800,
                "cover_ulr":"http://www.example.png"
            }
        )

        return ProcessResult(sender_id="1001", message_id="11111",
                             messages=[BotMessage(text="我是电商客服，请问你有什么问题需要我帮助的嘛")])
