"""
用户消息、机器消息数据模型
"""
from enum import Enum
from typing import Any, Self
from dataclasses import dataclass, field


class MessageType(Enum):
    TEXT = "text"
    OBJECT = "object"


@dataclass(slots=True)
class FocusedObject:
    id: str  # 订单类型卡片代表订单编号A20260410001 商品类型卡片代表商品ID SKU10002
    type: str  # "order" or "product"
    title: str | None = None  # 标题
    attributes: dict = field(default_factory=dict)  # 其它属性和属性值

    def to_dict(self) -> dict:
        """
        将实例对象转成字典结构
        :return:
        """
        return {
            "id": self.id,
            "type": self.type,
            "title": self.title,
            "attributes": dict(self.attributes)  # 浅拷贝 数据做隔离(可变对象会受到影响) copy.deepcopy()深拷贝
        }

    @classmethod
    def from_dict(cls, data: dict[
        str, Any]) -> "FocusedObject":  # 前向引用的解决方案  1."" 变成一个字符串 python解释器直接忽略掉 2.from __future__ import  annotations(早期) 3. Self:返回类实例
        return cls(
            id=data['id'],
            type=data['type'],
            title=data.get('title'),
            attributes=dict(data.get('attributes'))
        )


@dataclass(slots=True)  # 1. 访问速度快__slots__  __dict__() 2. 占用内存空间更小 3.对象的属性个数固定住
class UserMessage:
    """
    用户角色的消息
    """
    sender_id: str  # 必填参数（用户ID） 前端传过来的
    message_id: str  # 必填参数 (消息ID) 前端没传（扩展） 自己生成自己传入(uuid)
    type: MessageType  # 消息类型(文本以及对象类型)
    text: str | None = None  # 可选
    object: FocusedObject | None = None  # 可选

    def to_dict(self) -> dict[str, Any]:
        return {

            "sender_id": self.sender_id,
            "message_id": self.message_id,
            "type": self.type.value,
            "text": self.text,
            "object": self.object.to_dict() if self.object is not None else None
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "UserMessage":
        return cls(
            sender_id=data['sender_id'],
            message_id=data['message_id'],
            type=MessageType(data['type']),
            text=data.get('text'),
            object=FocusedObject.from_dict(data['object']) if data.get('object') else None
        )


@dataclass(slots=True)
class BotMessage:
    """
    机器人回复的消息
    """
    text: str | None = None  # 应用的内容结果都会给text属性
    object: FocusedObject | None = None  # 扩展点

    def to_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "object": self.object.to_dict() if self.object is not None else None
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        return cls(
            text=data.get('text'),
            object=FocusedObject.from_dict(data['object']) if data.get('object') else None
        )


@dataclass(slots=True)
class ProcessResult:
    sender_id: str
    message_id: str
    messages: list[BotMessage]
