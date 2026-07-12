import uuid
from fastapi import APIRouter
from atguigu.api.dependencies import DialogueServiceDep
from atguigu.api.schemas import ChatRequest, ChatResponse, ChatBotMessage, ChatObject
from atguigu.domain.messages import ProcessResult, UserMessage, MessageType, FocusedObject

router = APIRouter()


@router.get("/hello")
async def hello():
    return {"success": "ok"}


@router.post("/api/chat", response_model=ChatResponse)
async def chat_endpoint(chat_request: ChatRequest,
                        service: DialogueServiceDep):
    # 1. 将接口数据模型转成领域数据模型
    user_message = _build_user_message(chat_request)

    # 2. 注入service使用
    process_result: ProcessResult = await service.hand_dialogue(user_message)

    # 3. 将领域数据模型转成接口数据模型
    chat_response = _build_chat_response(process_result)

    return chat_response


def _build_user_message(chat_request: ChatRequest) -> UserMessage:
    """
    将接口数据模型转成领域数据模型UserMessage
    :param chat_request:
    :return:
    """
    return UserMessage(
        sender_id=chat_request.sender_id,
        message_id=str(uuid.uuid4()),
        type=MessageType.OBJECT if chat_request.object else MessageType.TEXT,
        text=chat_request.text,
        object=FocusedObject(
            id=chat_request.object.id,
            type=chat_request.object.type,
            title=chat_request.object.title,
            attributes=chat_request.object.attributes,
        ) if chat_request.object else None
    )


def _build_chat_response(process_result: ProcessResult) -> ChatResponse:
    """
    将领域数据模型转成接口数据模型ChatResponse
    :param process_result:
    :return:
    """

    return ChatResponse(
        sender_id=process_result.sender_id,
        message_id=process_result.message_id,
        messages=[ChatBotMessage(text=bot_message.text,
                                 object=ChatObject(
                                     id=bot_message.object.id,
                                     type=bot_message.object.type,
                                     title=bot_message.object.title,
                                     attributes=bot_message.object.attributes,
                                 ) if bot_message.object else None) for bot_message in process_result.messages]
    )
