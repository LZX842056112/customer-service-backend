from atguigu.domain.messages import ProcessResult, UserMessage
from atguigu.repository.dialogue_repository import DialogueRepository
from atguigu.domain.state import DialogueState
from atguigu.engine.dialogue_engine import DialogueEngine


class DialogueService:
    """
    处理对话的服务类
    """

    def __init__(self,
                 repository: DialogueRepository,
                 engine: DialogueEngine):
        print(f"repository:{id(repository)}")
        print(f"engine:{id(engine)}")

        self.repository = repository
        self.engine = engine

    async def hand_dialogue(self, user_message: UserMessage) -> ProcessResult:
        """
        IO：【读写数据库：repository】/计算[engine]
        :param user_message:
        :return:
        """

        # 1. 从数据库中读取之前的DialogueState
        dialogue_state: DialogueState = await self.repository.load_dialogue(user_message.sender_id)

        # 2. 引擎层使用(修改DialogueState的状态) 今天不做（TODO）
        process_result: ProcessResult = await self.engine.hand_message(user_message, dialogue_state)

        # 3. 将修改后的修改DialogueState的状态 存储到数据库中
        await  self.repository.save_dialogue(dialogue_state)

        return process_result
