# Web 层搭建（web / service / repository）

---

## 第1章 任务目标

到前面为止，我们已经把两类"静态资料"准备好了：

- **领域模型**：`UserMessage` / `BotMessage` / `DialogueState` / `TaskContext` …（消息长什么样、状态长什么样）
- **流程定义**：`FlowsList`（流程长什么样，从 YAML 加载好了）

但这些目前都只是"躺在内存里的对象"，没有一个**入口**让外界把消息送进来、把回复拿回去，也没有一个地方把对话状态**存下来、读出来**。这一节就来搭这条主链路。

### 1.1 搭建三层

<img src="images/28、 搭建三层.png" style="zoom:50%;" />

三层各管一件事：

| 层 | 职责 | 本节实现 |
| --- | --- | --- |
| Web（API） | 收 HTTP 请求、校验参数、转成领域对象、把结果转回 JSON | ✅ 完整实现 |
| Service | 编排一次完整处理：加载状态 → 调引擎 → 保存状态 | ✅ 完整实现 |
| Repository | 把 `DialogueState` 存进数据库、从数据库读出来 | ✅ 完整实现 |
| Engine | 真正的对话逻辑（路由、推流程、调 LLM） | ⛔ 本节用**占位实现**，下一节再做 |

### 1.2 为什么 Engine 先放占位

`DialogueService` 在编排时要调用 `self.dialogue_engine.process_message(state, user_message)`。引擎本身很复杂（要做 LLM 路由、流程推进、知识检索），如果等它全部写完再来搭 web，周期太长，也不利于先把"骨架"跑通。

所以这一节我们给引擎写一个**最小占位实现**——它不做任何智能处理，只回一句固定的话。这样做的好处是：

- 整条链路（HTTP → Service → Repository → DB → 返回）可以**当场跑通、当场验证**
- 等下一节真正实现引擎时，只要把占位换成真货，上下游一行都不用改

这是一种很常见的开发节奏：**先用假实现打通骨架，再逐个替换成真实现**。

---

## 第2章 数据模型的两套体系

在写代码之前，必须先想清楚一件事：**这条链路上其实有"两套"数据模型**，它们长得像，但职责完全不同。

### 2.1 两套模型

| | 领域模型（domain） | 接口模型（schema） |
| --- | --- | --- |
| 在哪 | `atguigu/domain/messages.py` | `atguigu/api/schemas.py` |
| 基类 | `@dataclass` | `pydantic.BaseModel` |
| 代表 | `UserMessage` / `BotMessage` / `ProcessResult` | `ChatRequest` / `ChatResponse` … |
| 用途 | 系统内部流转、业务逻辑 | 和外部（HTTP）打交道，负责校验和序列化 |

### 2.2 为什么要分两套

直接拿领域模型当接口模型不行吗？分开有几个实在的好处：

1. **校验归 Pydantic 管**：`ChatRequest` 是 Pydantic 模型，FastAPI 会自动校验请求 JSON（字段缺失、类型不对会自动返回 422），领域 `dataclass` 没这个能力
2. **内外解耦**：接口字段是给前端看的"契约"，内部模型是给业务用的。两者分开，将来内部重构不会破坏对外契约，反之亦然
3. **职责清晰**：领域模型不该关心"怎么序列化成 JSON"，接口模型不该掺杂业务逻辑

所以 Web 层有一个核心动作就是**翻译**：把进来的 `ChatRequest`（schema）翻成 `UserMessage`（domain），把出去的 `ProcessResult`（domain）翻成 `ChatResponse`（schema）。

<img src="images/29、核心交互转换.png" style="zoom: 67%;" />

### 2.3 用到 / 定义哪些模型

| 模型 | 类型 | 这一节 |
| --- | --- | --- |
| `UserMessage` / `BotMessage` / `MessageObject` / `MessageType` | domain | 上一节已定义，直接用 |
| `DialogueState` | domain | 上一节已定义，直接用 |
| `ProcessResult` | domain | **本节定义**（引擎返回值，目前占位也要用它） |
| `ChatRequest` / `ChatObject` | schema | **本节定义**（chat 接口入参） |
| `ChatResponse` / `ChatBotMessage` | schema | **本节定义**（chat 接口返回） |
| `HistoryResponse` / `HistoryMessage` | schema | **本节定义**（history 接口返回） |
| `DialogueStateRecord` | ORM | **本节定义**（数据库表映射） |

下面按"模型先行"的顺序，逐个把它们建起来，再串成三层。

---

## 第3章 领域模型补全

`UserMessage` / `BotMessage` 上一节已经有了。这一节补上引擎的**返回值类型** `ProcessResult`，放在 `atguigu/domain/messages.py`。

```python
@dataclass
class ProcessResult:
    sender_id: str
    message_id: str
    messages: list[BotMessage]
```

| 字段 | 含义 |
| --- | --- |
| `sender_id` | 这次回复给哪个用户 |
| `message_id` | 本轮消息的 id（和请求里的对应） |
| `messages` | 机器人本轮要回复的消息列表（可能多条） |

`ProcessResult` 是引擎处理一轮对话的**结果**。它带着回复列表，还带着 `sender_id` 和 `message_id`，方便 Web 层直接拼出响应。

回顾一下 `BotMessage`（上一节已定义）：

```python
@dataclass
class BotMessage:
    text: str | None = None
    object: MessageObject | None = None
```

所以 `ProcessResult.messages` 是一个 `BotMessage` 列表，每条要么是文本、要么是结构化对象。

---

## 第4章 接口模型

接口模型全部放在 `atguigu/api/schemas.py`，用 Pydantic 定义。

### 4.1 完整代码

```python
from pydantic import BaseModel


class ChatObject(BaseModel):
    type: str
    id: str
    title: str | None = None
    attributes: dict = {}


class ChatRequest(BaseModel):
    sender_id: str
    message_id: str | None = None
    text: str | None = None
    object: ChatObject | None = None


class ChatBotMessage(BaseModel):
    text: str | None = None
    object: ChatObject | None = None


class ChatResponse(BaseModel):
    sender_id: str
    message_id: str
    messages: list[ChatBotMessage]


class HistoryMessage(BaseModel):
    role: str  # user or bot
    text: str | None = None
    object: ChatObject | None = None


class HistoryResponse(BaseModel):
    sender_id: str
    messages: list[HistoryMessage]
```

### 4.2 模型说明

**ChatObject**：对象消息的载体，对应前端点击订单/商品卡片时带的数据。

| 字段 | 含义 |
| --- | --- |
| `type` | 对象类型，`order` / `product` |
| `id` | 对象 id |
| `title` | 对象标题（可选） |
| `attributes` | 扩展属性，默认空字典 |

**ChatRequest**：`POST /api/chat` 的请求体。

| 字段 | 必填 | 含义 |
| --- | --- | --- |
| `sender_id` | 是 | 用户唯一标识 |
| `message_id` | 否 | 客户端消息 id，不传则服务端生成 |
| `text` | 否 | 文本消息内容 |
| `object` | 否 | 对象消息内容 |

注意 `text` 和 `object` 都是可选的，但实际使用中至少要传一个——文本消息传 `text`，对象消息传 `object`。

**ChatBotMessage / ChatResponse**：返回体。`ChatResponse.messages` 是一个 `ChatBotMessage` 列表，对应 `ProcessResult.messages`。

**HistoryMessage / HistoryResponse**：`GET /api/chat/history` 的返回体。`HistoryMessage` 比 `ChatBotMessage` 多一个 `role` 字段，用来区分这条历史消息是用户发的（`user`）还是机器人发的（`bot`）。

### 4.3 为什么用 Pydantic 而不是 dataclass

FastAPI 和 Pydantic 是深度集成的。当你把 `ChatRequest` 写成接口函数的参数类型时，FastAPI 会自动：

- 把请求体 JSON 解析成 `ChatRequest` 实例
- 校验字段（类型不对、必填缺失 → 自动返回 `422`）
- 在 `/docs` 里生成交互式 API 文档

这些都是 dataclass 给不了的，所以**对外接口一律用 Pydantic 模型**。

---

## 第5章 数据库映射：ORM 模型

`DialogueState` 要存进数据库，需要一张表来承载。这一节用 SQLAlchemy 的 ORM 把表映射成 Python 类。

### 5.1 Base 基类

所有 ORM 模型的共同父类，放在 `atguigu/models/base.py`：

```python
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
```

`DeclarativeBase` 是 SQLAlchemy 2.x 推荐的声明式基类。所有表模型都继承它，SQLAlchemy 才能统一管理它们的元数据。

### 5.2 DialogueStateRecord

放在 `atguigu/models/dialogue_state.py`：

```python
from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from atguigu.models.base import Base


class DialogueStateRecord(Base):
    """dialogue_states 表：每个用户一行，state_json 存储完整对话状态。"""

    __tablename__ = "dialogue_states"

    sender_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    state_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
```

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| `sender_id` | `VARCHAR(255)`，主键 | 用户唯一标识，一个用户一行 |
| `state_json` | `TEXT` | 整份 `DialogueState` 序列化后的 JSON 字符串 |

### 5.3 存 整份JSON原因

这是一个值得停下来想的设计取舍。

一份 `DialogueState` 里有活跃任务、暂停任务栈、聚焦对象、会话历史（里面又嵌套了一堆 Turn、消息）……如果按传统关系建模，要拆成好多张表，外键关联一大堆。

而这里只用了**一张表、两列**：用户 id 当主键，剩下整份状态压成一个 JSON 字符串塞进 `state_json`。

| | 拆多张表 | 整存 JSON（本项目） |
| --- | --- | --- |
| 写入 | 多表事务，复杂 | 一次 upsert |
| 读取 | 多表 join | 一次主键查询 |
| 单字段查询 | 方便（SQL where） | 不方便（要解析 JSON） |
| 适合场景 | 需要按状态字段检索、统计 | 整份读写、不需要按内部字段查 |

我们的场景是"每次处理对话，整份读出来、整份写回去"，从不需要"查所有 active_task 是退款的用户"这种内部字段检索。所以整存 JSON 简单又够用，特别适合学习阶段理解多轮对话。

> 这种"一个聚合整存一份"的思路，和 DDD 里"聚合根作为持久化单元"是一致的。生产环境如果有复杂检索需求，再考虑拆表或上文档数据库。

---

## 第6章 基础设施：数据库引擎

ORM 模型有了，还需要一个**异步数据库引擎**和**会话工厂**来真正连数据库。放在 `atguigu/infrastructure/database.py`。（已经实现）

```python
from sqlalchemy.ext.asyncio import (
    AsyncEngine, async_sessionmaker, AsyncSession, create_async_engine,
)

from atguigu.conf.config import settings

engine: AsyncEngine | None = None
session_factory: async_sessionmaker[AsyncSession] | None = None


def init_db_engine():
    global engine, session_factory
    engine = create_async_engine(settings.database_url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)


async def close_db_engine():
    await engine.dispose()
```

几个要点：

- `engine` 和 `session_factory` 是**模块级全局变量**，整个应用共享一个引擎（引擎内部维护连接池，不能每次请求都新建）
- `init_db_engine()` 在应用启动时调用一次，创建引擎和会话工厂
- `close_db_engine()` 在应用关闭时调用，释放连接池
- `create_async_engine` 用的是**异步**引擎——因为客服后端整体是 async 的，数据库访问也必须异步，否则会阻塞事件循环
- `expire_on_commit=False`：commit 之后对象字段仍可访问，不会被标记过期（异步场景下常用这个设置避免意外的额外查询）

> `settings.database_url` 来自配置（`.env` 里的 `DATABASE_URL`），形如 `mysql+aiomysql://user:pwd@host:3306/db`。`aiomysql` 是异步 MySQL 驱动。

应用启动时怎么调用 `init_db_engine`，会在讲生命周期那一节细说。这一节先知道：用之前必须先 init。

---

## 第7章 Repository 层

**状态的存与取**，这是这一节的重点之一。Repository 负责把 `DialogueState` 在"内存对象"和"数据库 JSON"之间来回转换。放在 `atguigu/repository/dialogue_state_repository.py`。

### 7.1 类结构

```python
import json

from sqlalchemy import select
from sqlalchemy.dialects.mysql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from atguigu.domain.state import DialogueState
from atguigu.models.dialogue_state import DialogueStateRecord


class DialogueStateRepository:
    def __init__(self, session: AsyncSession):
        self.session = session
```

`DialogueStateRepository` 持有一个 `AsyncSession`（数据库会话）。会话从哪来？由依赖注入传进来（后面讲），Repository 自己不创建会话——它只管用。

### 7.2 load_state：读取状态

```python
async def load_state(self, sender_id: str) -> DialogueState:
    sql = select(DialogueStateRecord).where(
        DialogueStateRecord.sender_id == sender_id
    )
    result = await self.session.execute(sql)
    state = result.scalar_one_or_none()
    if state:
        # 将 state.state_json 反序列化成一个 DialogueState 对象
        dialogue_state: DialogueState = DialogueState.from_dict(
            json.loads(state.state_json)
        )
        return dialogue_state
    else:
        return DialogueState(sender_id=sender_id)
```

逻辑分四步：

1. 构造一条按 `sender_id` 查询的 SQL
2. `execute` 执行，`scalar_one_or_none()` 取唯一一行（没有则返回 `None`）
3. **查到了**：`json.loads` 把 JSON 字符串变回字典，再 `DialogueState.from_dict` 还原成对象
4. **没查到**（新用户第一次来）：直接 创建一个空的 `DialogueState` 返回

第 4 步很关键：**新用户没有历史状态，不报错，而是给一个全新的空状态**。这样上层逻辑不用区分"老用户/新用户"，拿到的永远是一个可用的 `DialogueState`。

<img src="images/30、读取状态.png" style="zoom:50%;" />

### 7.3 save_state：保存状态

```python
async def save_state(self, state: DialogueState):
    # 将 state 序列化为一个 json 字符串
    state_json: str = json.dumps(state.to_dict())
    insert_stmt = insert(DialogueStateRecord).values(
        sender_id=state.sender_id, state_json=state_json
    )
    upsert_stmt = insert_stmt.on_duplicate_key_update(
        state_json=insert_stmt.inserted.state_json
    )
    await self.session.execute(upsert_stmt)
    await self.session.commit()
```

逻辑：

1. `state.to_dict()` 把整份状态变成字典，`json.dumps` 再变成 JSON 字符串
2. 构造一条 `INSERT` 语句
3. `on_duplicate_key_update` 把它变成 **upsert**：如果这个 `sender_id` 已存在，就改成 `UPDATE state_json`
4. 执行 + 提交

### 7.4 为什么用 upsert

`save_state` 会在两种情况下被调用：

- **新用户**：表里还没有这一行 → 应该 `INSERT`
- **老用户**：表里已有这一行 → 应该 `UPDATE`

如果分别判断"先查、再决定 insert 还是 update"，要两次数据库往返，还可能有并发问题。`on_duplicate_key_update` 是 MySQL 的原生能力——**主键冲突时自动转为更新**，一条语句搞定，既简洁又避免竞态。

> 这里 `from sqlalchemy.dialects.mysql import insert` 用的是 MySQL 方言的 insert，才有 `on_duplicate_key_update` 方法。标准的 `sqlalchemy.insert` 没有这个方法。

### 7.5 Repository 的本质

<img src="images/31、Repository 的本质.png" style="zoom:50%;" />

Repository 把"业务对象"和"存储格式"之间的转换完全封装起来。上层（Service）只调 `load_state` / `save_state`，完全不知道底层是 MySQL 还是 JSON 还是别的——这就是 Repository 模式的价值：**隔离持久化细节**。

---

## 第8章 占位 Engine

让链路先跑起来，Service 要调引擎，但引擎这一节不实现。我们写一个**最小占位实现**，只回一句固定的话，让链路能通。

放在 `atguigu/engine/dialogue_engine.py`（下一节会把它整个替换成真实现）：

```python
from atguigu.domain.messages import UserMessage, ProcessResult, BotMessage
from atguigu.domain.state import DialogueState


class DialogueEngine:
    """占位实现：暂不做任何对话逻辑，仅回固定话术，用于打通 web 层链路。
    下一节将替换为真正的引擎。"""

    async def process_message(self, state: DialogueState, user_message: UserMessage) -> ProcessResult:
        return ProcessResult(
            sender_id=user_message.sender_id,
            message_id=user_message.message_id,
            messages=[BotMessage(text="（占位回复）我已经收到你的消息了。")],
        )
```

注意它的方法签名和真实引擎**完全一致**：`process_message(self, state, user_message) -> ProcessResult`。这样下一节实现真引擎时，Service 调用它的那行代码一个字都不用改。

> 这就是"面向接口编程"的好处——只要签名（契约）不变，实现可以随时替换。占位实现也是合法实现，它满足了同样的契约。

---

## 第9章 Service 层

**编排一次完整处理**，Service 是这一节的另一个重点。它把 Repository 和 Engine 串起来，完成一次对话处理的完整编排。放在 `atguigu/service/dialogue_service.py`。

### 9.1 完整代码

```python
from atguigu.domain.messages import UserMessage, ProcessResult
from atguigu.domain.state import DialogueState
from atguigu.engine.dialogue_engine import DialogueEngine
from atguigu.repository.dialogue_state_repository import DialogueStateRepository


class DialogueService:
    def __init__(self,
                 dialogue_state_repository: DialogueStateRepository,
                 dialogue_engine: DialogueEngine):
        self.dialogue_state_repository = dialogue_state_repository
        self.dialogue_engine = dialogue_engine

    async def process_message(self, user_message: UserMessage) -> ProcessResult:
        # 1. 通过 repository 根据 sender_id 加载对话状态
        state: DialogueState = await self.dialogue_state_repository.load_state(user_message.sender_id)
        # 2. 使用 engine 根据对话状态处理最新消息
        process_result: ProcessResult = await self.dialogue_engine.process_message(state, user_message)
        # 3. 通过 repository 保存最新的对话状态
        await self.dialogue_state_repository.save_state(state)
        # 4. 返回本轮处理结果
        return process_result
```

### 9.2 三步编排

`process_message` 的逻辑非常清晰，就是三步：

<img src="images/32、三步编排.png" style="zoom:50%;" />

| 步骤 | 做什么 |
| --- | --- |
| ① 加载 | 按 `sender_id` 从数据库读出这个用户的 `DialogueState` |
| ② 处理 | 把状态和新消息交给引擎，引擎**就地修改** `state`，返回回复 |
| ③ 保存 | 把被引擎改过的 `state` 写回数据库 |

### 9.3 一个关键设计：I/O 在两端，计算在中间

注意这个编排的形状：

- **①加载** 和 **③保存** 是仅有的两次数据库 I/O，都在 Service 这一层
- 中间的 **②引擎处理** 完全不碰数据库——它只在内存里读改 `state` 对象

这种"**I/O 集中在两端、计算集中在中间**"的设计有两个好处：

1. **引擎是纯计算、无副作用的**——给它一个 state 和 message，它就改 state、返回结果，不依赖数据库。这让引擎极易做单元测试（构造一个内存 state 直接调就行）
2. **事务边界清晰**——什么时候读、什么时候写，一目了然，都在 Service 里

> 即便这一节引擎是占位实现，这个结构也已经立住了。下一节换上真引擎，编排逻辑完全不变。

**注意：引擎是"就地修改"state**

第 ② 步有个容易忽略的点：`engine.process_message(state, user_message)` 会**直接修改传进去的 `state` 对象**（比如往里面追加 Turn、更新 active_task）。所以第 ③ 步保存的，正是被引擎改过的同一个 `state`。

引擎**不需要**把 state 当返回值传回来——因为 Python 对象是引用传递，Service 手里的 `state` 和引擎改的是同一个对象。引擎的返回值 `ProcessResult` 只装"这一轮要回复什么"，不装状态。

---

## 第10章 Web 层

**路由与翻译**，最后是最外层的 Web 层。它负责收 HTTP、做模型翻译、调 Service、返回 JSON。放在 `atguigu/api/routers/chat_router.py`。

### 10.1 chat 接口

```python
import uuid

from fastapi import APIRouter, Depends

from atguigu.api.dependencies import get_dialogue_service
from atguigu.api.schemas import ChatRequest, ChatResponse, ChatBotMessage, ChatObject
from atguigu.domain.messages import UserMessage, ProcessResult, MessageType, MessageObject
from atguigu.service.dialogue_service import DialogueService

chat_router = APIRouter()


@chat_router.post('/api/chat')
async def chat(
        chat_request: ChatRequest,
        dialogue_service: DialogueService = Depends(get_dialogue_service)
) -> ChatResponse:
    process_result: ProcessResult = await dialogue_service.process_message(
        _build_user_message(chat_request)
    )
    return _build_chat_response(process_result)
```

接口函数本身只有两行：

1. 把请求翻译成 `UserMessage`，交给 service 处理
2. 把 service 返回的 `ProcessResult` 翻译成 `ChatResponse` 返回

`dialogue_service` 从哪来？通过 `Depends(get_dialogue_service)` 注入——这是 FastAPI 的依赖注入，细节留到讲依赖注入那一节，这里先理解为"框架帮我把 service 准备好传进来了"。

### 10.2 请求翻译

**schema → domain**

```python
def _build_user_message(chat_request: ChatRequest) -> UserMessage:
    return UserMessage(
        sender_id=chat_request.sender_id,
        message_id=chat_request.message_id or str(uuid.uuid4()),
        type=MessageType.TEXT if chat_request.text else MessageType.OBJECT,
        text=chat_request.text,
        object=MessageObject(
            type=chat_request.object.type,
            id=chat_request.object.id,
            title=chat_request.object.title,
            attributes=chat_request.object.attributes,
        ) if chat_request.object else None,
    )
```

几个翻译细节：

- `message_id`：请求没传就用 `uuid4()` 生成一个，保证每条消息都有 id
- `type`：有 `text` 就是 `TEXT` 类型，否则当 `OBJECT` 类型
- `object`：请求带了对象就翻译成 `MessageObject`，否则为 `None`

### 10.3 响应翻译

**domain → schema**

```python
def _build_chat_response(process_result: ProcessResult) -> ChatResponse:
    return ChatResponse(
        sender_id=process_result.sender_id,
        message_id=process_result.message_id,
        messages=[
            ChatBotMessage(
                text=message.text,
                object=ChatObject(
                    type=message.object.type,
                    id=message.object.id,
                    title=message.object.title,
                    attributes=message.object.attributes,
                ) if message.object else None,
            ) for message in process_result.messages
        ],
    )
```

把 `ProcessResult` 里的每条 `BotMessage`（domain）翻译成 `ChatBotMessage`（schema），组装成 `ChatResponse`。

### 10.4 history 接口（本节先返回假数据）

```python
@chat_router.get('/api/chat/history')
async def history(sender_id: str) -> HistoryResponse:
    return HistoryResponse(
        sender_id=sender_id,
        messages=[
            HistoryMessage(role='user', text='你好'),
            HistoryMessage(role='bot', text='我不好'),
        ],
    )
```

历史接口这一节先用**写死的假数据**占位。真正的实现要从 `DialogueState.sessions` 里把历史 Turn 取出来翻译成 `HistoryMessage`，这部分逻辑等讲完会话历史的取用方式后再补。先留一个能返回正确结构的桩，前端联调时不至于报错。

### 10.5 Web 层的本质

<img src="images/33、Web 层的本质.png" style="zoom:50%;" />

Web 层做的事可以概括成一句话：**两次自动转换（FastAPI 负责 JSON ↔ schema），两次手动翻译（我们负责 schema ↔ domain），中间夹一次 Service 调用**。

---

## 第11章 把整条链路串起来

到这里三层都实现了（引擎是占位）。完整看一条 `POST /api/chat` 请求的旅程：

<img src="images/34、整条链路.png" style="zoom:50%;" />

这条链路现在是**完全可运行**的：

- 发一条 `{"sender_id": "u1", "text": "你好"}`
- 会真的去数据库 load → 占位引擎处理 → 真的 save → 返回 `（占位回复）我已经收到你的消息了。`
- 再发一条，能在数据库 `dialogue_states` 表里看到 `u1` 这一行的 `state_json`

虽然引擎还没智能，但**整个骨架已经通了、状态持久化已经work了**。下一节把占位引擎换成真引擎，立刻就有真正的对话能力。

---

## 第12章 小结

### 12.1 这一节实现了什么

| 文件 | 内容 |
| --- | --- |
| `domain/messages.py` | 补上 `ProcessResult` |
| `api/schemas.py` | 接口模型 `ChatRequest` / `ChatResponse` / `HistoryResponse` 等 |
| `models/base.py` / `models/dialogue_state.py` | ORM 基类 + `DialogueStateRecord` 表映射 |
| `infrastructure/database.py` | 异步引擎 + 会话工厂 |
| `repository/dialogue_state_repository.py` | `load_state` / `save_state` |
| `engine/dialogue_engine.py` | **占位**引擎（下节替换） |
| `service/dialogue_service.py` | 三步编排：加载 → 处理 → 保存 |
| `api/routers/chat_router.py` | `chat` / `history` 路由 + 模型翻译 |

### 12.2 几个好的设计

1. **两套模型分工**：schema（对外、Pydantic、负责校验序列化）vs domain（对内、dataclass、负责业务）。Web 层负责在两者间翻译。
2. **Repository 隔离持久化**：上层只调 `load_state` / `save_state`，不关心底层是 MySQL 还是 JSON。新用户自动给空状态，保存用 upsert。
3. **I/O 在两端、计算在中间**：Service 管加载/保存，引擎是纯计算无副作用，便于测试、事务边界清晰。
4. **先占位、再替换**：用最小占位引擎打通骨架，契约（方法签名）不变，下一节无缝换真引擎。

### 12.3 下一节

把占位的 `DialogueEngine.process_message` 换成真正的实现——准备 session、开 turn、LLM 路由、走任务/知识/闲聊三条轨道。这一节搭好的 web/service/repository 三层，到时候一行都不用动。
