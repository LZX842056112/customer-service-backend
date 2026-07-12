from atguigu.model.base import Base
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import TEXT


class DialogueStateRecord(Base):
    """
    mapped_column:定义字段的约束[是否为空、是否是主键、是否建立索引] 元数据（默认值）
    Mapped:给静态检查工具做类型提示、自动将类型和属性映射到表中的列中、类型推断
    """
    __tablename__ = 'dialogue_states'

    sender_id: Mapped[str] = mapped_column(primary_key=True)  # Python中定义的字段类型 str---->类型推断(varchar类型)
    state_json: Mapped[str] = mapped_column(TEXT, nullable=False, default={})  # 数据库中该列指定的TEXT(长文本)
