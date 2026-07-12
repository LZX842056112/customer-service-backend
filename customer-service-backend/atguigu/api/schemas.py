"""
接口层的数据约束：遵循方: 前端和服务端
前端json字符串----->数据模型（接收前端json数据）------业务层逻辑使用
业务层逻辑使用完（领域数据模型）----->接口数据模型----返回给前端

schema-----转成------domain----service/engine(使用)
domain-----转成------schema----前端用

"""

from pydantic import BaseModel
from typing import Any


class ChatObject(BaseModel):
    id: str
    type: str
    title: str | None = None
    attributes: dict[str, Any] | None = None


class ChatBotMessage(BaseModel):
    text: str | None = None
    object: ChatObject | None = None


class ChatRequest(BaseModel):
    sender_id: str
    text: str | None = None
    object: ChatObject | None = None


class ChatResponse(BaseModel):
    sender_id: str
    message_id: str
    messages: list[ChatBotMessage]
