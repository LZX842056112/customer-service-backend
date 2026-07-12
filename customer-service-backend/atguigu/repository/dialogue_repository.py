import json

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.dialects.mysql import insert  # 注意

from atguigu.model.state_record import DialogueStateRecord
from atguigu.domain.state import DialogueState


class DialogueRepository:
    """
    对话的持久层组件(读写数据库 customer_service库 dialogue_states表)
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    async def load_dialogue(self, sender_id: str) -> DialogueState:
        """
        根据sender_id 查询用户的对话状态
        :param sender_id:
        :return:
        """

        # 1. 定义查询的SQL
        stmt = select(DialogueStateRecord).where(DialogueStateRecord.sender_id == sender_id)

        # 2. 执行SQL
        cursor = await self.session.execute(stmt)

        # 3. 获取结果
        result = cursor.scalar_one_or_none()

        if result:
            return DialogueState.from_dict(json.loads(result.state_json))

        return DialogueState(sender_id=sender_id)

    async def save_dialogue(self, dialogue_state: DialogueState):
        """
        json.dumps---->序列    dump
        json.loads---->反序列化 load
        :param dialogue_state:
        :return:
        新增以及修改
        如果sender_id:不存在新增 （sender_id/state_json）
        如果sender_id:存在，修改 state_json的数据

        """

        # 1. 序列化
        dialogue_str = json.dumps(dialogue_state.to_dict(), ensure_ascii=False)

        # 2. 定义SQL
        insert_stmt = insert(DialogueStateRecord).values(
            sender_id=dialogue_state.sender_id, state_json=dialogue_str
        )

        # SQL语句升级：insert 语句升级到update 语句  条件重复的key[主键]
        upsert_stmt = insert_stmt.on_duplicate_key_update(
            state_json=insert_stmt.inserted.state_json
        )

        # 3. 执行SQL
        await self.session.execute(upsert_stmt)

        # 4. commit
        await self.session.commit()
