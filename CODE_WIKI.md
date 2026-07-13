# 电商智能客服系统 Code Wiki

> 基于仓库实际代码编写，完整反映项目架构、模块职责、关键实现及运行方式。

---

## 目录

1. [项目概述](#1-项目概述)
2. [整体架构](#2-整体架构)
3. [技术栈与依赖](#3-技术栈与依赖)
4. [项目结构](#4-项目结构)
5. [后端服务 (customer-service-backend)](#5-后端服务-customer-service-backend)
6. [电商业务后端 (ecommerce-service-backend)](#6-电商业务后端-ecommerce-service-backend)
7. [前端应用 (customer-service-frontend)](#7-前端应用-customer-service-frontend)
8. [核心领域模型](#8-核心领域模型)
9. [流程编排系统](#9-流程编排系统)
10. [对话引擎与处理流程](#10-对话引擎与处理流程)
11. [API 接口设计](#11-api-接口设计)
12. [基础设施层](#12-基础设施层)
13. [模块依赖关系](#13-模块依赖关系)
14. [项目配置与运行](#14-项目配置与运行)
15. [设计理念与关键模式](#15-设计理念与关键模式)
16. [实现进度与待办](#16-实现进度与待办)
17. [附录：核心类速查表](#附录核心类速查表)

---

## 1. 项目概述

### 1.1 项目背景

本项目是一套基于大语言模型（LLM）的电商智能客服系统，支持用户用自然语言描述需求，由系统判断意图并路由到相应的处理轨道。

**项目组成**：
- **customer-service-backend**：AI 客服后端，承担所有对话与 LLM 调用
- **ecommerce-service-backend**：电商业务后端，提供订单、物流、商品的查询接口
- **customer-service-frontend**：前端聊天界面，集成数字人交互

**核心理念**：AI 客服不直接读电商数据库，而是以"业务系统消费者"的身份调用电商后端的 HTTP 接口，实现业务隔离。

### 1.2 系统能力

系统设计支持三条处理轨道，三者互斥：

| 轨道 | 说明 | 示例场景 |
|------|------|----------|
| **任务流程（Task）** | 步骤明确、可按步骤推进的业务 | 查订单、查物流、申请退款 |
| **信息检索（Knowledge）** | 知识性问答，不需要走流程 | 商品信息、退款政策、退货政策 |
| **闲聊（Chitchat）** | 轻量交互兜底 | "你好"、"你挺聪明的" |

### 1.3 技术亮点

- **YAML 驱动的流程编排**：业务流程从代码中抽离，非程序员可编辑
- **LLM 路由 + 白名单校验**：永远不"裸用"LLM 输出
- **聚合根模式**：DialogueState 集中管理所有对话状态
- **两步提交设计**：pending_turn 保证数据完整性
- **业务隔离**：AI 客服以消费者身份调用电商接口

---

## 2. 整体架构

### 2.1 三层服务架构

```
┌─────────────────────────────────────────────────────────┐
│  前端层 (customer-service-frontend)                      │
│  Vue 3 + Vite + 数字人 SDK                               │
│  聊天界面、卡片交互、WebSocket 实时通信                    │
└────────────────────┬────────────────────────────────────┘
                     │ HTTP/WebSocket
                     ↓
┌─────────────────────────────────────────────────────────┐
│  AI 客服层 (customer-service-backend)                    │
│  FastAPI + LangChain + SQLAlchemy                        │
│  对话引擎、流程编排、LLM 调用、状态管理                    │
└────────────────────┬────────────────────────────────────┘
                     │ HTTP
                     ↓
┌─────────────────────────────────────────────────────────┐
│  电商业务层 (ecommerce-service-backend)                  │
│  FastAPI + SQLAlchemy + MySQL                            │
│  订单、物流、商品数据查询接口                              │
└─────────────────────────────────────────────────────────┘
```

### 2.2 AI 客服后端分层架构

客服后端采用清晰的分层设计，遵循 DDD（领域驱动设计）思想：

```
┌──────────────────────────────────────────────┐
│  API 层 (api/)                                │
│  FastAPI 路由、请求/响应 Schema、依赖注入       │
├──────────────────────────────────────────────┤
│  Service 层 (services/)                       │
│  加载状态 → 调引擎 → 保存状态，一次完整对话事务  │
├──────────────────────────────────────────────┤
│  Engine 层 (engine/)                          │
│  顶层调度，决定走哪条处理轨道                   │
├──────────────────────────────────────────────┤
│  Plan / Clarify / Task / Knowledge / Chitchat │
│  各轨道的具体处理逻辑                          │
├──────────────────────────────────────────────┤
│  Domain 层 (domain/)                          │
│  消息、上下文、对话状态等核心领域模型            │
├──────────────────────────────────────────────┤
│  Repository 层 (repository/)                  │
│  把 DialogueState 持久化到数据库               │
├──────────────────────────────────────────────┤
│  Infrastructure 层 (infrastructure/)          │
│  LLM、HTTP 客户端、数据库引擎等底层资源          │
└──────────────────────────────────────────────┘
```

### 2.3 整体调用关系

```
用户消息 → 前端 → API层 → Service层 → Engine层
                                   ↓
                            ┌───────┼───────┐
                            ↓       ↓       ↓
                        Task轨道  Knowledge  Chitchat
                            ↓       ↓       ↓
                            └───────┼───────┘
                                    ↓
                            Service层（保存状态）→ 返回回复 → 前端
```

---

## 3. 技术栈与依赖

### 3.1 后端技术栈 (customer-service-backend)

| 技术 | 作用 |
|------|------|
| **FastAPI** | 提供 HTTP 接口 |
| **Uvicorn** | ASGI 服务器 |
| **LangChain + langchain-openai** | LLM 编排，统一抽象 prompt → model → parser 流水线 |
| **Pydantic / pydantic-settings** | 数据校验与配置加载 |
| **Jinja2** | Prompt 模板渲染 |
| **SQLAlchemy + aiomysql** | 异步访问 MySQL |
| **httpx** | 异步调用电商后端 HTTP 接口 |
| **PyYAML** | YAML 流程配置解析 |
| **dashscope** | 阿里达摩院灵积模型服务 |
| **alibabacloud-lingmou20250527** | 阿里云灵摹（数字人）SDK |

### 3.2 电商后端技术栈 (ecommerce-service-backend)

| 技术 | 作用 |
|------|------|
| **FastAPI** | 提供 HTTP 接口 |
| **SQLAlchemy** | ORM 框架 |
| **PyMySQL** | MySQL 驱动 |
| **Pydantic** | 数据校验 |

### 3.3 前端技术栈 (customer-service-frontend)

| 技术 | 作用 |
|------|------|
| **Vue 3** | 前端框架（Composition API） |
| **Vite** | 构建工具 |
| **lm-avatar-chat-sdk** | 数字人交互 SDK |
| **WebSocket** | 实时通信 |

### 3.4 Python 依赖清单

**customer-service-backend/pyproject.toml**

| 依赖包 | 版本要求 | 用途 |
|--------|----------|------|
| `aiomysql` | >=0.3.2 | 异步 MySQL 驱动 |
| `cryptography` | >=46.0.7 | 加密库（MySQL 连接需要） |
| `fastapi` | >=0.136.0 | Web 框架 |
| `httpx` | >=0.28.1 | 异步 HTTP 客户端 |
| `jinja2` | >=3.1.6 | 模板引擎（Prompt 模板） |
| `langchain` | >=1.2.15 | LLM 编排框架 |
| `langchain-openai` | >=1.1.14 | LangChain OpenAI 兼容适配器 |
| `pydantic-settings` | >=2.13.1 | 配置管理 |
| `pyyaml` | >=6.0.3 | YAML 解析 |
| `sqlalchemy` | >=2.0.49 | ORM 框架 |
| `uvicorn[standard]` | >=0.44.0 | ASGI 服务器 |
| `alibabacloud-lingmou20250527` | >=1.0.0 | 阿里云灵摹（数字人） |
| `alibabacloud-tea-openapi` | >=0.3.12 | 阿里云 OpenAPI 工具 |
| `alibabacloud-tea-util` | >=0.3.13 | 阿里云工具库 |
| `dashscope` | - | 阿里达摩院灵积模型服务 |

**ecommerce-service-backend/pyproject.toml**

| 依赖包 | 版本要求 | 用途 |
|--------|----------|------|
| `fastapi` | >=0.115.0 | Web 框架 |
| `sqlalchemy` | >=2.0.0 | ORM 框架 |
| `pymysql` | >=1.1.0 | MySQL 驱动 |
| `cryptography` | >=46.0.7 | 加密库 |
| `uvicorn[standard]` | >=0.34.0 | ASGI 服务器 |
| `pydantic` | >=2.0.0 | 数据校验 |

---

## 4. 项目结构

```
ecommerce-customer-service/
├── customer-service-backend/          ← AI 客服后端（核心）
│   ├── atguigu/
│   │   ├── __init__.py
│   │   ├── main.py                    ← 应用启动入口
│   │   ├── api/                       ← FastAPI 路由层
│   │   │   ├── app.py                 ← FastAPI 应用实例 + lifespan
│   │   │   ├── dependencies.py        ← 依赖注入
│   │   │   ├── schemas.py             ← 接口层 Pydantic 模型
│   │   │   └── router/
│   │   │       └── chat_router.py     ← 聊天接口路由
│   │   ├── config/                    ← 配置模块
│   │   │   └── settings.py            ← pydantic-settings 读取 .env
│   │   ├── domain/                    ← 领域模型层
│   │   │   ├── contexts.py            ← 上下文模型
│   │   │   ├── messages.py            ← 消息模型
│   │   │   └── state.py               ← 对话状态聚合根
│   │   ├── engine/                    ← 对话引擎
│   │   │   └── dialogue_engine.py     ← DialogueEngine
│   │   ├── infrastructure/            ← 基础设施层
│   │   │   ├── db.py                  ← SQLAlchemy 异步引擎
│   │   │   ├── http_client.py         ← httpx 异步客户端
│   │   │   └── llm_client.py          ← LangChain LLM 客户端
│   │   ├── model/                     ← SQLAlchemy ORM 模型
│   │   │   ├── base.py                ← DeclarativeBase 基类
│   │   │   └── state_record.py        ← DialogueStateRecord 表映射
│   │   ├── repository/                ← 仓储层
│   │   │   └── dialogue_repository.py ← DialogueRepository
│   │   ├── services/                  ← 应用服务层
│   │   │   └── dialogue_service.py    ← DialogueService
│   │   ├── task/                      ← 任务流程编排层
│   │   │   ├── loader.py              ← FlowLoader 流程加载器
│   │   │   ├── handler.py             ← TaskHandler（占位）
│   │   │   ├── command/
│   │   │   │   └── commands.py        ← 命令数据模型
│   │   │   └── flow/                  ← 流程数据模型
│   │   │       ├── flows.py           ← Flow / FlowSlot / FlowsList
│   │   │       ├── links.py           ← FlowStepLink 边模型
│   │   │       └── steps.py           ← FlowStep 步骤模型
│   │   ├── plan/                      ← LLM 路由决策
│   │   │   └── planner.py             ← TurnPlanner
│   │   ├── clarify/                   ← 澄清兜底（待实现）
│   │   ├── knowledge/                 ← 知识问答轨道（待实现）
│   │   │   └── handler.py             ← 占位文件
│   │   └── chitchat/                  ← 闲聊轨道（待实现）
│   │       └── handler.py             ← 占位文件
│   ├── flow_config/                   ← YAML 流程定义（权威副本）
│   │   ├── system_flows.yml
│   │   └── user_flows.yml
│   ├── pyproject.toml
│   └── uv.lock
│
├── ecommerce-service-backend/         ← 电商业务后端
│   ├── app/
│   │   ├── app.py                     ← FastAPI 应用实例
│   │   ├── api.py                     ← API 路由与业务逻辑
│   │   ├── models.py                  ← SQLAlchemy ORM 模型
│   │   └── schemas.py                 ← Pydantic 数据模型
│   ├── pyproject.toml
│   └── README.md
│
└── customer-service-frontend/         ← 前端应用
    ├── src/
    │   ├── main.js                    ← Vue 应用入口
    │   └── App.vue                    ← 主组件（聊天界面 + 数字人）
    ├── index.html
    ├── vite.config.js                 ← Vite 配置
    ├── package.json
    └── dist/                          ← 构建产物
```

---

## 5. 后端服务 (customer-service-backend)

### 5.1 配置模块 (config)

**文件**: [settings.py](file:///workspace/customer-service-backend/atguigu/config/settings.py)

使用 `pydantic-settings` 的 `BaseSettings` 从 `.env` 文件加载配置，支持类型校验。

#### Settings 类字段

所有字段均为**必填**（无默认值），若 `.env` 缺失对应项，导入本模块时即抛出 `ValidationError`（启动期校验）：

| 字段 | 类型 | 说明 | 示例值 |
|--------|------|------|--------|
| `llm_model` | `str` | LLM 模型名称 | `qwen-plus` |
| `llm_base_url` | `str` | LLM API 基础地址 | `https://dashscope.aliyuncs.com/compatible-mode/v1` |
| `llm_api_key` | `str` | LLM API 密钥 | `sk-xxxx` |
| `commerce_api_base_url` | `str` | 电商业务后端 API 地址 | `http://127.0.0.1:18081` |
| `database_url` | `str` | 数据库连接 URL | `mysql+aiomysql://root:root@localhost:3306/customer_service` |
| `app_host` | `str` | 应用监听地址 | `0.0.0.0` |
| `app_port` | `int` | 应用监听端口 | `18082` |

#### 模块级单例

```python
settings = Settings()  # type: ignore
```

### 5.2 基础设施层 (infrastructure)

#### LLM 客户端

**文件**: [llm_client.py](file:///workspace/customer-service-backend/atguigu/infrastructure/llm_client.py)

基于 LangChain 1.x 的 `init_chat_model()` 创建 LLM 客户端单例，使用 OpenAI 兼容协议接入 DashScope（通义千问）。

```python
llm_client: BaseChatModel = init_chat_model(
    model=settings.llm_model,
    model_provider="openai",      # OpenAI 兼容协议
    base_url=settings.llm_base_url,
    api_key=settings.llm_api_key,
    temperature=0,                # 保证输出稳定性
    timeout=120                   # 超时 120 秒
)
```

**关键设计**:
- `temperature=0`：降低随机性，保证输出稳定
- `model_provider="openai"`：用 OpenAI 兼容接口接 DashScope
- 模块级单例，导入即创建

#### 数据库引擎

**文件**: [db.py](file:///workspace/customer-service-backend/atguigu/infrastructure/db.py)

基于 SQLAlchemy 2.0 的异步数据库引擎与 session 工厂。

**关键函数**:

| 函数 | 签名 | 说明 |
|------|------|------|
| `init_db_engine` | `async () -> None` | 初始化异步引擎和 session 工厂 |
| `dispose_engine` | `async () -> None` | 释放数据库连接 |

**重要设计**:
- `expire_on_commit=False`：异步环境下提交后不自动过期，避免访问已过期属性报错
- `echo=True`：控制台打印 SQL 语句，便于调试
- 采用"全局变量 + init/dispose 生命周期函数"模式，由 FastAPI lifespan 统一管理

#### HTTP 客户端

**文件**: [http_client.py](file:///workspace/customer-service-backend/atguigu/infrastructure/http_client.py)

基于 httpx 的异步 HTTP 客户端单例，用于调用电商业务后端接口。

**关键参数**:
- `timeout=120`：120 秒超时
- `trust_env=False`：不读取系统环境变量代理配置

### 5.3 领域模型层 (domain)

领域层是整个系统的数据核心，所有模型使用 `@dataclass(slots=True)` 定义。

#### 消息模型 (messages.py)

**文件**: [messages.py](file:///workspace/customer-service-backend/atguigu/domain/messages.py)

##### MessageType 枚举

```python
class MessageType(Enum):
    TEXT = "text"       # 文本消息
    OBJECT = "object"   # 对象消息（订单卡片、商品卡片）
```

##### FocusedObject 聚焦对象

用户当前聚焦的业务对象（订单 / 商品卡片）。前端点击卡片后发送对象消息，后端记录下来供后续对话使用。

```python
@dataclass(slots=True)
class FocusedObject:
    id: str                    # 对象唯一标识（订单号 or 商品ID）
    type: str                  # 对象类型："order" or "product"
    title: str | None = None   # 显示标题
    attributes: dict = field(default_factory=dict)  # 扩展属性
```

##### UserMessage 用户消息

```python
@dataclass(slots=True)
class UserMessage:
    sender_id: str                    # 用户ID
    message_id: str                   # 消息ID
    type: MessageType                 # 消息类型
    text: str | None = None           # 文本内容
    object: FocusedObject | None = None  # 对象内容
```

##### BotMessage 机器人消息

```python
@dataclass(slots=True)
class BotMessage:
    text: str | None = None           # 文本回复
    object: FocusedObject | None = None  # 对象回复（扩展点）
```

##### ProcessResult 处理结果

```python
@dataclass(slots=True)
class ProcessResult:
    sender_id: str                    # 用户ID
    message_id: str                   # 消息ID
    messages: list[BotMessage]        # 机器人回复列表
```

`ProcessResult` 是引擎处理完成后的输出结构，由 Service 层返回给 API 层，最终序列化为 HTTP 响应。

#### 上下文模型 (contexts.py)

**文件**: [contexts.py](file:///workspace/customer-service-backend/atguigu/domain/contexts.py)

上下文模型分为两类：
- **TaskContext**：业务任务的执行快照（用户想做的事）
- **SystemContext**：系统流程的执行快照（系统插播的过场）

##### TaskContext 业务任务上下文

```python
@dataclass(slots=True)
class TaskContext:
    flow_id: str                      # 业务流程ID
    step_id: str                      # 当前步骤ID
    slots: dict[str, Any] = field(default_factory=dict)  # 收集到的槽位数据
```

类比成一份正在填的表单：`flow_id` 是表单种类，`step_id` 是当前填到哪格，`slots` 是已填写内容。

##### SystemContext 系统上下文基类

```python
@dataclass(slots=True)
class SystemContext:
    system_flow_id: str               # 系统流程ID
    system_step_id: str               # 系统流程步骤ID
```

##### 五个 SystemContext 子类

| 子类 | 触发时机 | 额外字段 |
|------|----------|----------|
| `StartedSystemContext` | 用户刚发起一个新任务 | `started_flow_id`, `started_flow_name` |
| `InterruptedSystemContext` | 用户在 A 任务中切到 B 任务 | `interrupted_flow_id/name`, `started_flow_id/name` |
| `CanceledSystemContext` | 用户主动取消当前任务 | `canceled_flow_id`, `canceled_flow_name` |
| `ResumedSystemContext` | 用户要求恢复挂起的任务 | `resumed_flow_id`, `resumed_flow_name` |
| `CollectedSystemContext` | 业务流程跑到 collect 步骤 | `response: dict`, `slot_name: str` |

#### 对话状态模型 (state.py)

**文件**: [state.py](file:///workspace/customer-service-backend/atguigu/domain/state.py)

`DialogueState` 是整个对话状态的**聚合根**，引擎操作的核心对象。

##### Turn 对话轮次

```python
@dataclass(slots=True)
class Turn:
    turn_id: str                      # 轮次ID
    user_message: UserMessage         # 用户消息
    bot_messages: list[BotMessage]    # 机器人回复列表
```

##### Session 会话

```python
@dataclass(slots=True)
class Session:
    session_id: str                   # 会话ID
    started_at: float                 # 开始时间戳
    last_activity_at: float           # 最后活动时间戳
    closed_at: float | None = None    # 关闭时间戳（None 代表会话可用）
    turns: list[Turn] = field(default_factory=list)  # 轮次列表
```

##### DialogueState 聚合根

```python
@dataclass(slots=True)
class DialogueState:
    sender_id: str                                     # 用户ID
    active_task: TaskContext | None = None             # 当前活跃业务任务
    interrupted_active_tasks: list[TaskContext] = []   # 挂起的任务栈（LIFO）
    active_system_task: SystemContext | None = None    # 当前活跃系统流程
    focused_object: FocusedObject | None = None        # 聚焦的业务对象
    sessions: list[Session] = []                       # 历史会话
    current_session_id: str | None = None              # 当前活跃会话ID
    pending_turn: Turn | None = None                   # 正在处理中的轮次（暂存区）
```

##### 字段分组

| 分组 | 字段 | 说明 |
|------|------|------|
| **任务相关** | `active_task` | 当前活跃的业务任务 |
| | `interrupted_active_tasks` | 被挂起的任务列表（栈结构，LIFO） |
| | `active_system_task` | 当前活跃的系统过场 |
| **聚焦对象** | `focused_object` | 用户当前聚焦的订单/商品 |
| **会话历史** | `sessions`、`current_session_id` | 历史会话管理 |
| **本轮处理** | `pending_turn` | 正在处理中的轮次（暂存区） |

##### 关键方法速查

**流程管理**:

| 方法 | 说明 |
|------|------|
| `start_active_system_task(system_context)` | 开启并激活系统流程 |
| `end_activating_system_task()` | 结束正在激活的系统流程 |
| `start_active_business_task(task_context)` | 开启并激活业务流程 |
| `end_activating_business_task()` | 结束正在激活的业务流程 |
| `end_activating_task()` | 同时清空业务流程和系统流程 |
| `interrupted_activating_task()` | 将当前业务流程压入栈并清空 active_task |
| `resumed_interrupted_business_task(flow_id=None) -> bool` | 从栈中恢复任务（LIFO 或精确匹配） |
| `current_activating_task()` | 返回当前活跃流程，**系统流程优先于业务流程** |

**槽位管理**:

| 方法 | 说明 |
|------|------|
| `set_slots(slots: dict)` | 更新到 `active_task.slots` |
| `get_slot(slot_name) -> Any` | 从 `active_task.slots` 读取槽位值 |

**会话管理**:

| 方法 | 说明 |
|------|------|
| `current_session() -> Session \| None` | 按 `current_session_id` 查找当前会话 |
| `start_session()` | 创建新 Session，更新 `current_session_id` |
| `close_session()` | 设置 `closed_at`，清空 `current_session_id` |
| `reset_running_state_for_new_session()` | 会话超时时清空所有任务/卡片/pending_turn |

**轮次管理**:

| 方法 | 说明 |
|------|------|
| `start_turn(user_message)` | 创建 Turn 放入 `pending_turn` 缓冲区 |
| `commit_pending_turn()` | 将 `pending_turn` 提交到 `current_session().turns` |

##### pending_turn 两步提交设计

`pending_turn` 是重要的设计——处理中的轮次先放在暂存区，处理完成后再通过 `commit_pending_turn()` 提交到会话。好处：
- 处理失败时只要丢掉 `pending_turn` 即可，`turns` 始终干净
- 决定不入库时只要不调用 commit，简单高效

### 5.4 ORM 模型层 (model)

#### Base 基类

**文件**: [base.py](file:///workspace/customer-service-backend/atguigu/model/base.py)

```python
from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    pass
```

SQLAlchemy 2.0 声明式基类，所有 ORM 模型继承此类。

#### DialogueStateRecord

**文件**: [state_record.py](file:///workspace/customer-service-backend/atguigu/model/state_record.py)

```python
class DialogueStateRecord(Base):
    __tablename__ = 'dialogue_states'

    sender_id: Mapped[str] = mapped_column(primary_key=True)
    state_json: Mapped[str] = mapped_column(TEXT, nullable=False, default={})
```

**数据库表结构** (`dialogue_states`):

| 字段 | 类型 | 说明 |
|------|------|------|
| `sender_id` | `VARCHAR` 主键 | 用户唯一标识 |
| `state_json` | `TEXT` | DialogueState 序列化后的 JSON 字符串 |

**设计特点**:
- 整份 `DialogueState` 序列化为 JSON 字符串存入单表
- 不拆成多张表，调试直观
- 使用 `mapped_column` 声明式映射，`Mapped` 提供类型推断

### 5.5 流程编排系统 (task)

#### 设计理念

业务流程不写在代码里，而是写在 YAML 配置文件里。代码只实现一个通用的「流程加载器」和「流程执行器」按定义往前推。

**优势**:
- 新增业务流程不需要改代码，只需加一份 YAML
- 非程序员也可以编辑流程定义
- 流程变更不需要重新部署

#### 流程数据模型 (flow/flows.py)

**文件**: [flows.py](file:///workspace/customer-service-backend/atguigu/task/flow/flows.py)

```python
@dataclass(slots=True)
class FlowSlot:
    name: str         # 槽位名字
    type: str         # 槽位的类型
    label: str        # 显示标签
    description: str  # 描述

@dataclass(slots=True)
class Flow:
    flow_id: str      # 流程ID
    flow_name: str    # 流程名字
    description: str  # 流程描述（提供给 LLM 用于选择业务流程）
    steps: list[FlowStep] = field(default_factory=list)
    slots: dict[str, FlowSlot] = field(default_factory=dict)

@dataclass(slots=True)
class FlowsList:
    flows: list[Flow] = field(default_factory=list)
    slots: dict[str, FlowSlot] = field(default_factory=dict)
```

> `Flow.description` 字段非常重要：未来会把所有业务流程的描述提供给 LLM，让 LLM 根据用户任务选择要开启哪个业务流程。

#### 边（转移）模型 (flow/links.py)

**文件**: [links.py](file:///workspace/customer-service-backend/atguigu/task/flow/links.py)

```python
@dataclass(slots=True)
class FlowStepLink:
    """边的基类：提供下一个 step_id"""
    target: str

@dataclass(slots=True)
class FlowStepStaticLink(FlowStepLink):
    """静态非条件边，对应 next: ask_refund_reason"""
    pass

@dataclass(slots=True)
class FlowStepConditionLink(FlowStepLink):
    """条件边，对应 if/then 语法"""
    condition: str

@dataclass(slots=True)
class FlowStepFallbackLink(FlowStepLink):
    """兜底 else 边"""
    pass
```

#### 步骤模型 (flow/steps.py)

**文件**: [steps.py](file:///workspace/customer-service-backend/atguigu/task/flow/steps.py)

##### FlowStepType 枚举

```python
class FlowStepType(Enum):
    START = "start"      # 流程起点
    COLLECT = "collect"  # 收集槽位（仅业务流程）
    ACTION = "action"    # 执行动作
    END = "end"          # 流程结束
```

##### FlowStep 基类与子类

| 子类 | 额外字段 | 说明 |
|------|----------|------|
| `StartFlowStep` | 无 | 仅复用基类字段 |
| `EndFlowStep` | 无 | 仅复用基类字段 |
| `ActionFlowStep` | `action: str`、`args: dict` | 执行动作步骤 |
| `CollectFlowStep` | `slot_name: str`、`response: ResponseDefinition`、`validate: SlotValidation \| None` | 收集槽位步骤 |

**三种 action 动作**:
- `action_listen`：让执行引擎停下来，把控制权交给用户
- `action_response`：告诉用户信息（开场白、槽位填写提示、查询结果）
- `action_xxx`：找外部要数据（调电商接口）

**关键规则**:
- 系统流程的 action 只有 `action_response` 和 `action_listen`
- 业务流程一定有 `action_xxx` 和 `action_response`，但不会有 `action_listen`
- `action_listen` 只出现在 `system_collect_information` 流程中

##### ResponseDefinition 响应定义

```python
@dataclass(slots=True)
class ResponseDefinition:
    text: str                    # 响应内容
    mode: str = "static"         # static 直接渲染 / rephrase 用 LLM 改写
    prompt: str | None = None    # rephrase 模式下的 LLM 提示词
```

##### SlotValidation 槽位校验

```python
@dataclass(slots=True)
class SlotValidation:
    condition: str                              # 校验条件表达式
    failure_response: ResponseDefinition | None = None  # 校验失败的响应
```

##### from_dict 多态分发

`FlowStep.from_dict()` 根据 `type` 字段通过 `FLOW_STEP_TYPE_TO_CLASS` 查找表分派到具体子类：

```python
FLOW_STEP_TYPE_TO_CLASS: dict[str, type[FlowStep]] = {
    "start": StartFlowStep,
    "end": EndFlowStep,
    "collect": CollectFlowStep,
    "action": ActionFlowStep
}
```

##### build_links 解析逻辑

`FlowStep.build_links()` 将 YAML 中的 `next` 字段解析为边对象列表：
- `next` 是字符串 → 创建 `FlowStepStaticLink`
- `next` 是列表：
  - 含 `if` 键 → 创建 `FlowStepConditionLink`（`if` 作为 condition，`then` 作为 target）
  - 含 `else` 键 → 创建 `FlowStepFallbackLink`（`else` 作为 target）

#### 流程加载器 (task/loader.py)

**文件**: [loader.py](file:///workspace/customer-service-backend/atguigu/task/loader.py)

`FlowLoader` 类负责将 YAML 配置文件解析为内存中的 `FlowsList` 对象树。

##### FlowLoader 方法

| 方法 | 说明 |
|------|------|
| `load_many_yaml(paths: list[str \| Path]) -> FlowsList` | 加载多份 YAML 并合并 flows 和 slots |
| `load_yaml(path: Path) -> FlowsList` | 加载单份 YAML：读取 → 加载 slots → 加载 flows |
| `load_slots(slots: dict) -> dict[str, FlowSlot]` | 将槽位字典转成 FlowSlot 对象 |
| `load_flows(flows: dict, loaded_slots) -> list[Flow]` | 加载所有流程，关联槽位 |
| `_load_flow_slot(steps, loaded_slots) -> dict[str, FlowSlot]` | 私有方法，提取流程用到的槽位 |

##### 加载流程

```
YAML 文件
   ↓ yaml.safe_load
dict 对象
   ↓ load_slots()
dict[str, FlowSlot]      ← 全局槽位定义
   ↓ load_flows()
   ├─ FlowStep.from_dict()    ← 步骤对象（自动分发子类）
   ├─ build_links()           ← 边对象列表
   └─ _load_flow_slot()       ← 流程专属槽位
list[Flow]
   ↓
FlowsList（flows + slots 合并）
```

#### YAML 流程定义

##### 流程配置文件

| 文件 | 作用 |
|------|------|
| [user_flows.yml](file:///workspace/customer-service-backend/flow_config/user_flows.yml) | 业务流程定义 |
| [system_flows.yml](file:///workspace/customer-service-backend/flow_config/system_flows.yml) | 系统流程定义 |

> 项目中存在两份 YAML 副本：`flow_config/`（权威副本）和 `atguigu/task/`（开发副本）。`loader.py` 的 `__main__` 测试块指向 `flow_config/` 路径。

##### 业务流程槽位定义

共定义 **8 个槽位**，type 均为 `text`：

| 槽位名 | label | 说明 |
|--------|-------|------|
| `order_number` | 订单号 | 用户的订单号 |
| `order_status` | 订单状态 | 订单当前状态 |
| `order_summary` | 订单摘要 | 订单摘要信息 |
| `tracking_number` | 物流单号 | 物流单号 |
| `logistics_company` | 物流公司 | 物流公司名称 |
| `logistics_status` | 物流进度 | 物流当前进度 |
| `product_id` | 商品ID | 当前咨询商品的唯一标识 |
| `refund_reason` | 退款原因 | 申请退款的原因 |

##### 业务流程定义

共定义 **6 个业务流程**：

| 流程ID | 名称 | 步骤概览 |
|--------|------|----------|
| `onboarding` | 欢迎引导 | start → respond(action_response) → end |
| `order_status_query` | 订单状态查询 | start → ask_order_number(collect) → lookup_order_status(action) → show_order_status(action_response) → end |
| `logistics_tracking` | 物流查询 | start → ask_order_number(collect) → lookup_logistics(action) → show_logistics(action_response) → end |
| `refund_request` | 退款申请 | start → ask_order_number(collect) → ask_refund_reason(collect) → refund_submitted(action_response) → end |
| `similar_product_recommendation` | 相似商品推荐 | start → 条件分支 → ask_product_id(collect) → respond(action) → end |
| `human_handoff` | 人工客服 | start → respond(action_response) → end |

##### 系统流程定义

共定义 **6 个系统流程**（无 slots）：

| 流程ID | 名称 | 触发时机 |
|--------|------|----------|
| `system_task_started` | task started acknowledgement | 开启新业务任务时 |
| `system_task_resumed` | task resumed acknowledgement | 恢复挂起任务时 |
| `system_collect_information` | collect information | 需要收集槽位时 |
| `system_task_interrupted` | task interrupted acknowledgement | 任务被打断时 |
| `system_task_canceled` | task canceled acknowledgement | 任务被取消时 |
| `system_cannot_handle` | cannot handle request | 无法处理请求时 |

##### 模板变量

回复文本支持 Jinja2 风格的模板变量：

| 变量 | 说明 | 使用场景 |
|------|------|----------|
| `{{ slots.xxx }}` | 当前任务的槽位值 | 业务流程的 action_response |
| `{{ context.xxx }}` | 系统上下文的字段 | 系统流程的 action_response |
| `{history}` | 对话历史 | rephrase 模式的 prompt |
| `{user_message}` | 用户最后一条消息 | rephrase 模式的 prompt |
| `{current_response}` | 建议回复 | rephrase 模式的 prompt |

### 5.6 服务层 (services)

#### DialogueService

**文件**: [dialogue_service.py](file:///workspace/customer-service-backend/atguigu/services/dialogue_service.py)

应用服务层，把一次对话处理串起来，是事务边界。

```python
class DialogueService:
    def __init__(self, repository: DialogueRepository, engine: DialogueEngine):
        self.repository = repository
        self.engine = engine

    async def hand_dialogue(self, user_message: UserMessage) -> ProcessResult:
```

**核心处理流程**:
1. 从 Repository 加载 `DialogueState`（`await self.repository.load_dialogue()`）
2. 调用 `DialogueEngine.hand_message(dialogue_state)` 处理消息
3. 保存 `DialogueState` 回 Repository（`await self.repository.save_dialogue()`）
4. 返回 `ProcessResult`

> Service 层是事务边界——所有持久化操作集中在这一层，引擎层是纯计算。

### 5.7 引擎层 (engine)

#### DialogueEngine

**文件**: [dialogue_engine.py](file:///workspace/customer-service-backend/atguigu/engine/dialogue_engine.py)

对话引擎，一轮消息处理的调度中心。当前处于 **stub 阶段**，返回硬编码的回复。

```python
class DialogueEngine:
    def hand_message(self, dialogue_state: DialogueState) -> ProcessResult:
```

**当前 stub 实现**:
- 设置 `focused_object` 为示例订单
- 返回固定的欢迎语 `"我是电商客服，请问你有什么问题需要我服务的嘛"`

**预期职责**（后续实现）:
1. 准备会话（检查超时、创建新会话）
2. 创建本轮记录（pending_turn）
3. 判断消息类型（文本 / 对象）
4. 调用 TurnPlanner 理解用户意图
5. 校验理解结果
6. 分发到 Task / Knowledge / Chitchat 三条轨道
7. 提交本轮记录

### 5.8 仓储层 (repository)

#### DialogueRepository

**文件**: [dialogue_repository.py](file:///workspace/customer-service-backend/atguigu/repository/dialogue_repository.py)

负责 `DialogueState` 的持久化，封装 MySQL 读写操作。

```python
class DialogueRepository:
    def __init__(self, session: AsyncSession):
        self.session = session
```

**关键方法**:

| 方法 | 说明 |
|------|------|
| `load_dialogue(sender_id) -> DialogueState` | 根据 sender_id 查询对话状态，不存在则返回新实例 |
| `save_dialogue(dialogue_state)` | 保存对话状态（MySQL INSERT ON DUPLICATE KEY UPDATE） |

**load_dialogue 实现**:
```python
stmt = select(DialogueStateRecord).where(DialogueStateRecord.sender_id == sender_id)
cursor = await self.session.execute(stmt)
result = cursor.scalar_one_or_none()
if result:
    return DialogueState.from_dict(json.loads(result.state_json))
return DialogueState(sender_id=sender_id)
```

**save_dialogue 实现**:
```python
dialogue_str = json.dumps(dialogue_state.to_dict(), ensure_ascii=False)
insert_stmt = insert(DialogueStateRecord).values(
    sender_id=dialogue_state.sender_id, state_json=dialogue_str
)
upsert_stmt = insert_stmt.on_duplicate_key_update(
    state_json=insert_stmt.inserted.state_json
)
await self.session.execute(upsert_stmt)
await self.session.commit()
```

使用 MySQL 特有的 `INSERT ... ON DUPLICATE KEY UPDATE` 实现 upsert 语义（存在则更新，不存在则插入）。

### 5.9 API 接口层 (api)

#### FastAPI 应用实例

**文件**: [app.py](file:///workspace/customer-service-backend/atguigu/api/app.py)

```python
app = FastAPI(description="智能客服V1.0", lifespan=lifespan)
app.include_router(router)
```

##### lifespan 生命周期

使用 `@asynccontextmanager` 管理应用生命周期：

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db_engine()       # 初始化数据库引擎
    init_http_client()           # 初始化 HTTP 客户端
    init_dialogue_engine()       # 初始化对话引擎
    yield                        # FastAPI 正常处理请求
    await dispose_engine()       # 释放数据库连接
    await dispose_http_client()  # 关闭 HTTP 客户端
```

#### 接口 Schema

**文件**: [schemas.py](file:///workspace/customer-service-backend/atguigu/api/schemas.py)

API 层与领域层使用不同的数据模型，通过转换函数进行映射：

| 类 | 方向 | 说明 |
|------|------|------|
| `ChatObject` | 入/出 | 卡片对象（id, type, title, attributes） |
| `ChatRequest` | 入 | 请求模型（sender_id, text, object） |
| `ChatBotMessage` | 出 | 机器人回复（text, object） |
| `ChatResponse` | 出 | 响应模型（sender_id, message_id, messages） |

**数据转换流程**:
```
前端 JSON → ChatRequest → UserMessage (domain) → 业务处理 → ProcessResult (domain) → ChatResponse → 前端 JSON
```

#### 聊天路由

**文件**: [chat_router.py](file:///workspace/customer-service-backend/atguigu/api/router/chat_router.py)

| 接口 | 方法 | 说明 |
|------|------|------|
| `/hello` | GET | 健康检查 |
| `/api/chat` | POST | 发送消息，获取回复 |

**POST /api/chat 处理流程**:
1. 将 `ChatRequest` 转为 `UserMessage`（`_build_user_message`）
2. 调用 `DialogueService.hand_dialogue(user_message)` 获取 `ProcessResult`
3. 将 `ProcessResult` 转为 `ChatResponse`（`_build_chat_response`）

#### 依赖注入

**文件**: [dependencies.py](file:///workspace/customer-service-backend/atguigu/api/dependencies.py)

使用 FastAPI 的 `Depends` + `Annotated` 实现依赖注入链：

```
get_engine() → DialogueEngineDep
get_session() → RepositorySessionDep
get_repository(session) → DialogueRepositoryDep
get_dialogue_service(engine, repo) → DialogueServiceDep
```

最终通过 `DialogueServiceDep` 注入到路由处理函数中。

**关键设计**:
- `get_session()` 使用 `async with` + `yield` 模式，确保请求结束后自动释放数据库 session
- 所有依赖通过 `Annotated[Type, Depends(factory)]` 定义别名类型，路由函数签名简洁

---

## 6. 电商业务后端 (ecommerce-service-backend)

### 6.1 项目概述

电商业务后端是一个模拟的电商数据服务，提供订单、物流、商品等查询接口，供 AI 客服后端调用。

**技术栈**：
- FastAPI：Web 框架
- SQLAlchemy：ORM 框架
- PyMySQL：MySQL 驱动
- Pydantic：数据校验

### 6.2 数据模型 (models.py)

**文件**: [models.py](file:///workspace/ecommerce-service-backend/app/models.py)

#### User 用户模型

```python
class User(Base):
    __tablename__ = 'users'
    
    user_id: Mapped[str] = mapped_column(primary_key=True)
    nickname: Mapped[str]
    level: Mapped[int]
    mobile: Mapped[str]
```

#### Product 商品模型

```python
class Product(Base):
    __tablename__ = 'products'
    
    product_id: Mapped[str] = mapped_column(primary_key=True)
    title: Mapped[str]
    price: Mapped[float]
    stock: Mapped[int]
    attributes: Mapped[dict]  # JSON 字段
```

#### Order 订单模型

```python
class Order(Base):
    __tablename__ = 'orders'
    
    order_id: Mapped[str] = mapped_column(primary_key=True)
    user_id: Mapped[str]
    status: Mapped[str]  # pending/shipped/delivered/canceled
    amount: Mapped[float]
    created_at: Mapped[datetime]
    shipping_address: Mapped[str]
```

#### OrderItem 订单项模型

```python
class OrderItem(Base):
    __tablename__ = 'order_items'
    
    item_id: Mapped[str] = mapped_column(primary_key=True)
    order_id: Mapped[str]
    product_id: Mapped[str]
    quantity: Mapped[int]
    price: Mapped[float]
```

#### LogisticsRecord 物流记录模型

```python
class LogisticsRecord(Base):
    __tablename__ = 'logistics_records'
    
    record_id: Mapped[str] = mapped_column(primary_key=True)
    order_id: Mapped[str]
    tracking_number: Mapped[str]
    company: Mapped[str]
    status: Mapped[str]
```

#### LogisticsTrace 物流追踪模型

```python
class LogisticsTrace(Base):
    __tablename__ = 'logistics_traces'
    
    trace_id: Mapped[str] = mapped_column(primary_key=True)
    record_id: Mapped[str]
    timestamp: Mapped[datetime]
    location: Mapped[str]
    description: Mapped[str]
```

#### RefundRequest 退款申请模型

```python
class RefundRequest(Base):
    __tablename__ = 'refund_requests'
    
    request_id: Mapped[str] = mapped_column(primary_key=True)
    order_id: Mapped[str]
    reason: Mapped[str]
    status: Mapped[str]  # pending/approved/rejected
    created_at: Mapped[datetime]
```

#### ShippingUrgeRequest 催单申请模型

```python
class ShippingUrgeRequest(Base):
    __tablename__ = 'shipping_urge_requests'
    
    request_id: Mapped[str] = mapped_column(primary_key=True)
    order_id: Mapped[str]
    created_at: Mapped[datetime]
```

### 6.3 API 接口 (api.py)

**文件**: [api.py](file:///workspace/ecommerce-service-backend/app/api.py)

#### 健康检查

```python
GET /health
```

返回数据库连接状态。

#### 用户订单查询

```python
GET /api/users/{user_id}/orders
```

返回用户最近的订单列表（摘要信息）。

**响应示例**:
```json
{
  "user_id": "u001",
  "orders": [
    {
      "order_id": "o001",
      "status": "shipped",
      "amount": 299.0,
      "created_at": "2024-01-15T10:30:00",
      "items_count": 2
    }
  ]
}
```

#### 用户商品查询

```python
GET /api/users/{user_id}/products
```

返回用户最近浏览的商品列表。

#### 订单详情查询

```python
GET /api/orders/{order_id}
```

返回订单完整信息，包括订单项。

#### 订单状态查询

```python
GET /api/orders/{order_id}/status
```

返回订单当前状态。

#### 物流信息查询

```python
GET /api/orders/{order_id}/logistics
```

返回物流记录及追踪信息。

#### 商品详情查询

```python
GET /api/products/{product_id}
```

返回商品完整信息。

#### 催单申请

```python
POST /api/orders/{order_id}/urge-shipping
```

创建催单申请。

**请求体**:
```json
{
  "user_id": "u001"
}
```

#### 退款申请

```python
POST /api/orders/{order_id}/refund
```

创建退款申请。

**请求体**:
```json
{
  "user_id": "u001",
  "reason": "商品质量问题"
}
```

### 6.4 启动方式

```bash
cd ecommerce-service-backend
uvicorn app.app:app --host 0.0.0.0 --port 18081
```

---

## 7. 前端应用 (customer-service-frontend)

### 7.1 项目概述

前端应用是一个基于 Vue 3 的聊天界面，集成数字人交互能力，通过 HTTP 和 WebSocket 与后端通信。

**技术栈**：
- Vue 3（Composition API）
- Vite（构建工具）
- lm-avatar-chat-sdk（数字人 SDK）
- WebSocket（实时通信）

### 7.2 项目结构

```
customer-service-frontend/
├── src/
│   ├── main.js          ← Vue 应用入口
│   └── App.vue          ← 主组件（聊天界面 + 数字人）
├── index.html           ← HTML 入口
├── vite.config.js       ← Vite 配置
├── package.json         ← 依赖配置
└── dist/                ← 构建产物
```

### 7.3 主组件 (App.vue)

**文件**: [App.vue](file:///workspace/customer-service-frontend/src/App.vue)

App.vue 是一个大型单文件组件（约 1500 行），包含完整的聊天界面逻辑。

#### 核心功能模块

##### 1. 聊天界面

- 消息列表展示（用户消息 + 机器人回复）
- 输入框（文本输入 + 发送按钮）
- 对象卡片展示（订单卡片、商品卡片）
- 消息气泡样式

##### 2. 数字人集成

使用 `lm-avatar-chat-sdk` 实现数字人交互：

```javascript
import { LMAvatarChat } from 'lm-avatar-chat-sdk'
```

**数字人功能**：
- 连接数字人 Avatar
- 语音合成（TTS）
- 语音打断
- 会话管理

##### 3. 后端通信

**HTTP 接口**：
- `/api/chat`：发送消息，获取回复
- `/api/users/{user_id}/orders`：获取用户订单
- `/api/users/{user_id}/products`：获取用户商品

**WebSocket 接口**：
- `/ws/chat`：实时聊天通信
- 支持 JSON 消息（文本、对象）
- 支持二进制消息（音频数据）

##### 4. 消息处理流程

```
用户输入文本/点击卡片
    ↓
构建 payload（text 或 object）
    ↓
HTTP POST /api/chat
    ↓
接收 ChatResponse
    ↓
渲染消息到界面
    ↓
（可选）通过 WebSocket 发送音频
    ↓
数字人播报
```

##### 5. 对象卡片交互

前端支持展示和交互业务对象：

**订单卡片**：
```javascript
{
  id: "o001",
  type: "order",
  title: "订单 o001",
  attributes: {
    status: "shipped",
    amount: 299.0
  }
}
```

**商品卡片**：
```javascript
{
  id: "p001",
  type: "product",
  title: "商品标题",
  attributes: {
    price: 99.0,
    stock: 100
  }
}
```

用户点击卡片后，前端发送对象消息给后端，后端记录 `focused_object` 供后续对话使用。

### 7.4 Vite 配置

**文件**: [vite.config.js](file:///workspace/customer-service-frontend/vite.config.js)

```javascript
export default defineConfig({
  plugins: [vue()],
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:18082',
        changeOrigin: true
      },
      '/ws': {
        target: 'ws://localhost:18082',
        ws: true
      },
      '/commerce': {
        target: 'http://localhost:18081',
        changeOrigin: true
      }
    }
  }
})
```

**代理配置**：
- `/api` → AI 客服后端（18082）
- `/ws` → AI 客服后端 WebSocket（18082）
- `/commerce` → 电商业务后端（18081）

### 7.5 启动方式

```bash
cd customer-service-frontend
npm install
npm run dev
```

开发服务器运行在 `http://localhost:5173`。

---

## 8. 核心领域模型

### 8.1 领域模型关系图

```
DialogueState (聚合根)
    ├─ active_task: TaskContext
    │   ├─ flow_id: str
    │   ├─ step_id: str
    │   └─ slots: dict
    ├─ interrupted_active_tasks: list[TaskContext]
    ├─ active_system_task: SystemContext
    │   ├─ system_flow_id: str
    │   └─ system_step_id: str
    ├─ focused_object: FocusedObject
    │   ├─ id: str
    │   ├─ type: str
    │   └─ attributes: dict
    ├─ sessions: list[Session]
    │   ├─ session_id: str
    │   ├─ started_at: float
    │   ├─ last_activity_at: float
    │   └─ turns: list[Turn]
    │       ├─ turn_id: str
    │       ├─ user_message: UserMessage
    │       └─ bot_messages: list[BotMessage]
    ├─ current_session_id: str
    └─ pending_turn: Turn
```

### 8.2 消息流转

```
UserMessage (输入)
    ↓
DialogueEngine.hand_message()
    ↓
ProcessResult (输出)
    ├─ sender_id: str
    ├─ message_id: str
    └─ messages: list[BotMessage]
        ├─ text: str
        └─ object: FocusedObject
```

### 8.3 上下文切换

**任务打断**：
```
active_task (A) → interrupted_active_tasks 栈顶
active_task = None
active_system_task = InterruptedSystemContext
```

**任务恢复**：
```
interrupted_active_tasks 栈顶 → active_task
active_system_task = ResumedSystemContext
```

**任务取消**：
```
active_task = None
active_system_task = CanceledSystemContext
```

---

## 9. 流程编排系统

### 9.1 流程数据模型

```
FlowsList
    ├─ flows: list[Flow]
    │   ├─ flow_id: str
    │   ├─ flow_name: str
    │   ├─ description: str
    │   ├─ steps: list[FlowStep]
    │   │   ├─ step_id: str
    │   │   ├─ type: FlowStepType
    │   │   ├─ links: list[FlowStepLink]
    │   │   └─ (子类特有字段)
    │   └─ slots: dict[str, FlowSlot]
    └─ slots: dict[str, FlowSlot]
```

### 9.2 步骤类型

```
FlowStep (基类)
    ├─ StartFlowStep
    ├─ EndFlowStep
    ├─ ActionFlowStep
    │   ├─ action: str
    │   └─ args: dict
    └─ CollectFlowStep
        ├─ slot_name: str
        ├─ response: ResponseDefinition
        └─ validate: SlotValidation
```

### 9.3 边类型

```
FlowStepLink (基类)
    ├─ FlowStepStaticLink (静态边)
    ├─ FlowStepConditionLink (条件边)
    │   └─ condition: str
    └─ FlowStepFallbackLink (兜底边)
```

### 9.4 流程执行逻辑

```
当前步骤 (step)
    ↓
执行步骤动作
    ├─ start: 无动作，直接前进
    ├─ end: 结束流程
    ├─ collect: 收集槽位 → 等待用户输入
    └─ action: 执行动作 → 根据 action 类型处理
        ├─ action_listen: 暂停，等待用户
        ├─ action_response: 返回响应
        └─ action_xxx: 调用外部接口
    ↓
根据 links 选择下一步
    ├─ 静态边: 直接跳转
    ├─ 条件边: 判断 condition
    └─ 兜底边: 其他条件都不满足时
    ↓
下一个步骤
```

---

## 10. 对话引擎与处理流程

### 10.1 一条消息的完整旅程

```
用户发送消息
    ↓
API层 (chat_router.py)
    ├─ ChatRequest → UserMessage（数据转换）
    └─ 调用 DialogueServiceDep
    ↓
Service层 (dialogue_service.py)
    ├─ 1. load_dialogue(sender_id) → DialogueState
    ├─ 2. engine.hand_message(dialogue_state) → ProcessResult
    └─ 3. save_dialogue(dialogue_state)
    ↓
Engine层 (dialogue_engine.py)
    └─ 处理消息（当前 stub：返回固定回复）
    ↓
API层
    ├─ ProcessResult → ChatResponse（数据转换）
    └─ 返回 JSON 响应
```

### 10.2 任务切换机制

系统设计支持复杂的任务切换，使用**栈结构**管理挂起的任务（LIFO - 后进先出）。

#### 打断（Interrupt）
- A 从 `active_task` 移到 `interrupted_active_tasks` 栈顶
- B 成为新的 `active_task`
- 触发 `InterruptedSystemContext` 过场白

#### 恢复（Resume）
- 默认恢复栈顶任务（LIFO）
- 可按 `flow_id` 精确匹配恢复

#### 取消（Cancel）
- 可取消当前活跃任务或挂起栈中的任务
- 被取消的任务直接丢弃

### 10.3 预期引擎流程（待实现）

```
1. 准备会话
   ├─ 检查会话是否超时
   └─ 创建新会话（如需要）

2. 创建本轮记录
   └─ start_turn(user_message) → pending_turn

3. 判断消息类型
   ├─ 文本消息 → 进入意图识别
   └─ 对象消息 → 更新 focused_object

4. 意图识别 (TurnPlanner)
   ├─ 调用 LLM 理解用户意图
   ├─ 白名单校验（流程ID必须在已定义流程中）
   └─ 返回 Command（start_flow / set_slot / cancel_flow 等）

5. 校验与澄清
   ├─ 校验通过 → 执行 Command
   └─ 校验失败 → 进入澄清流程 (ClarifyResponder)

6. 分发到轨道
   ├─ Task 轨道 → TaskHandler → FlowExecutor
   ├─ Knowledge 轨道 → KnowledgeHandler
   └─ Chitchat 轨道 → ChitchatHandler

7. 提交本轮记录
   └─ commit_pending_turn()
```

---

## 11. API 接口设计

### 11.1 AI 客服后端接口

#### 健康检查

```
GET /hello
```

**响应**:
```json
{
  "status": "ok"
}
```

#### 聊天接口

```
POST /api/chat
```

**请求体**:
```json
{
  "sender_id": "u001",
  "text": "我想查一下订单状态",
  "object": null
}
```

或发送对象消息：
```json
{
  "sender_id": "u001",
  "text": null,
  "object": {
    "id": "o001",
    "type": "order",
    "title": "订单 o001",
    "attributes": {
      "status": "shipped"
    }
  }
}
```

**响应体**:
```json
{
  "sender_id": "u001",
  "message_id": "m001",
  "messages": [
    {
      "text": "好的，请提供您的订单号",
      "object": null
    }
  ]
}
```

### 11.2 电商业务后端接口

详见 [第 6 节](#6-电商业务后端-ecommerce-service-backend)。

---

## 12. 基础设施层

### 12.1 LLM 客户端

**文件**: [llm_client.py](file:///workspace/customer-service-backend/atguigu/infrastructure/llm_client.py)

基于 LangChain 的 LLM 客户端，使用 OpenAI 兼容协议接入通义千问。

**关键配置**:
- `model_provider="openai"`：使用 OpenAI 兼容接口
- `temperature=0`：保证输出稳定性
- `timeout=120`：120 秒超时

**测试方式**:
```bash
uv run python -m atguigu.infrastructure.llm_client
```

### 12.2 数据库引擎

**文件**: [db.py](file:///workspace/customer-service-backend/atguigu/infrastructure/db.py)

基于 SQLAlchemy 2.0 的异步数据库引擎。

**关键配置**:
- `echo=True`：打印 SQL 语句
- `expire_on_commit=False`：异步环境下的必要配置

**测试方式**:
```bash
uv run python -m atguigu.infrastructure.db
```

### 12.3 HTTP 客户端

**文件**: [http_client.py](file:///workspace/customer-service-backend/atguigu/infrastructure/http_client.py)

基于 httpx 的异步 HTTP 客户端，用于调用电商后端接口。

**关键配置**:
- `timeout=120`：120 秒超时
- `trust_env=False`：不读取环境变量代理

**测试方式**:
```bash
uv run python -m atguigu.infrastructure.http_client
```

---

## 13. 模块依赖关系

### 13.1 外部服务依赖

| 服务 | 用途 | 配置项 |
|------|------|--------|
| **LLM API** | 大语言模型推理 | `llm_base_url`, `llm_api_key`, `llm_model` |
| **MySQL 数据库** | 对话状态持久化 | `database_url` |
| **电商业务后端** | 订单/物流/商品数据查询 | `commerce_api_base_url` |

### 13.2 内部模块依赖图

```
api → services → engine
          ↓          ↓
      repository   domain
          ↓
        model
          ↓
    infrastructure (db)
          ↓
       config/settings

所有层 → domain（数据模型）
infrastructure → config（配置）
```

### 13.3 已实现模块的依赖链

```
config/settings.py
    ↓
infrastructure/llm_client.py（依赖 settings）
infrastructure/db.py（依赖 settings）
infrastructure/http_client.py（无依赖）

model/base.py（无依赖）
model/state_record.py（依赖 base）

domain/messages.py（无依赖）
domain/contexts.py（无依赖）
domain/state.py（依赖 messages + contexts）

task/flow/links.py（无依赖）
task/flow/steps.py（依赖 links）
task/flow/flows.py（依赖 steps）
task/loader.py（依赖 flows + steps）

repository/dialogue_repository.py（依赖 model + domain）
engine/dialogue_engine.py（依赖 domain）
services/dialogue_service.py（依赖 engine + repository + domain）
api/dependencies.py（依赖 engine + repository + services + infrastructure）
api/router/chat_router.py（依赖 api/dependencies + api/schemas + domain）
api/app.py（依赖 api/router + infrastructure）
main.py（依赖 api/app + config）
```

### 13.4 依赖方向规则

- 上层依赖下层，下层不依赖上层
- 所有层都可以依赖 domain 层（数据模型）和 infrastructure 层（基础设施）
- domain 层不依赖任何其他层

---

## 14. 项目配置与运行

### 14.1 环境要求

- Python >= 3.12
- MySQL 数据库
- 可用的 LLM API（通义千问兼容 OpenAI 协议）
- Node.js >= 18（前端开发）
- `uv` 包管理器

### 14.2 创建 .env 配置文件

在 `customer-service-backend/` 目录下创建 `.env` 文件：

```bash
# LLM 配置
LLM_MODEL=qwen-plus
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_API_KEY=sk-your-api-key-here

# 数据库配置
DATABASE_URL=mysql+aiomysql://root:root@localhost:3306/customer_service?charset=utf8mb4

# 电商后端 API
COMMERCE_API_BASE_URL=http://127.0.0.1:18081

# 服务器配置
APP_HOST=0.0.0.0
APP_PORT=18082
```

> 若必填项缺失，Pydantic 启动时会直接报错——这是设计如此的"启动期校验"。

### 14.3 依赖安装

**后端**:
```bash
cd customer-service-backend
uv sync
```

**前端**:
```bash
cd customer-service-frontend
npm install
```

### 14.4 数据库初始化

```sql
CREATE DATABASE customer_service CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

USE customer_service;

CREATE TABLE dialogue_states (
    sender_id VARCHAR(255) PRIMARY KEY,
    state_json TEXT
);
```

### 14.5 启动服务

**1. 启动电商业务后端**:
```bash
cd ecommerce-service-backend
uvicorn app.app:app --host 0.0.0.0 --port 18081
```

**2. 启动 AI 客服后端**:
```bash
cd customer-service-backend
uv run python atguigu/main.py
```

**3. 启动前端**:
```bash
cd customer-service-frontend
npm run dev
```

启动后：
- 电商后端运行在 `http://0.0.0.0:18081`
- AI 客服后端运行在 `http://0.0.0.0:18082`
- 前端运行在 `http://localhost:5173`

### 14.6 验证安装

各基础设施模块都提供了 `__main__` 测试入口：

```bash
# 测试 LLM 连接
uv run python -m atguigu.infrastructure.llm_client

# 测试数据库连接
uv run python -m atguigu.infrastructure.db

# 测试 HTTP 客户端
uv run python -m atguigu.infrastructure.http_client

# 测试配置加载
uv run python -m atguigu.config.settings

# 测试流程加载
uv run python -m atguigu.task.loader
```

---

## 15. 设计理念与关键模式

### 15.1 五大设计原则

1. **三条轨道分离** —— 任务、知识、闲聊各走各的代码路径，互不污染
2. **LLM 路由 + 白名单校验 + 澄清兜底** —— 永远不"裸用" LLM 的输出
3. **YAML 描述流程，代码执行流程** —— 可枚举的业务逻辑从 LLM 手里拿出来
4. **DialogueState 集中状态，Engine 集中计算** —— 状态读写在边缘（Service），计算在中心（Engine）
5. **业务隔离** —— AI 客服永远以"业务消费者"身份调电商接口

### 15.2 关键设计模式

| 模式 | 应用位置 | 作用 |
|------|----------|------|
| **聚合根模式** | `DialogueState` | 集中管理所有对话状态，保证一致性 |
| **注册表模式** | `SYSTEM_CONTEXT_TO_CLASS`、`FLOW_STEP_TYPE_TO_CLASS` | 通过字典查表实现多态分发 |
| **工厂方法模式** | `FlowStep.from_dict`、`SystemContext.from_dict` | 根据 type 字段创建对应子类 |
| **模板方法模式** | `SystemContext` 子类 | 基类定义序列化接口，子类实现具体数据 |
| **两步提交** | `pending_turn` | 处理中与已提交分离，保证数据完整性 |
| **仓储模式** | `DialogueRepository` | 封装持久化细节，领域层不关心存储 |
| **依赖注入** | `api/dependencies.py` | FastAPI Depends 链式注入 |

### 15.3 DDD 思想应用

- **事务脚本 + 充血模型**：Service 层是事务脚本（管 I/O），Engine 层是纯计算（管逻辑）
- **仓储模式**：Repository 封装持久化细节，领域层不关心存储
- **领域模型与基础设施分离**：domain 层纯数据和业务规则，infrastructure 层管外部依赖

### 15.4 dataclass + slots 设计

所有领域模型使用 `@dataclass(slots=True)`，好处：
1. 访问速度快（`__slots__` 代替 `__dict__`）
2. 占用内存空间更小
3. 对象的属性个数固定

---

## 16. 实现进度与待办

### 16.1 已实现模块

| 模块 | 文件 | 状态 | 说明 |
|------|------|------|------|
| **config** | `config/settings.py` | 已完成 | Settings 类完整实现，含 7 个配置项 |
| **domain** | `domain/messages.py` | 已完成 | MessageType、FocusedObject、UserMessage、BotMessage、ProcessResult |
| | `domain/contexts.py` | 已完成 | TaskContext、SystemContext 及 5 个子类 |
| | `domain/state.py` | 已完成 | Turn、Session、DialogueState 聚合根，含完整方法 |
| **infrastructure** | `infrastructure/llm_client.py` | 已完成 | LangChain LLM 客户端单例 |
| | `infrastructure/db.py` | 已完成 | SQLAlchemy 异步引擎与 session 工厂 |
| | `infrastructure/http_client.py` | 已完成 | httpx 异步 HTTP 客户端单例 |
| **model** | `model/base.py` | 已完成 | SQLAlchemy DeclarativeBase 基类 |
| | `model/state_record.py` | 已完成 | DialogueStateRecord ORM 模型 |
| **task/flow** | `task/flow/flows.py` | 已完成 | FlowSlot、Flow、FlowsList |
| | `task/flow/links.py` | 已完成 | FlowStepLink 及 3 个子类 |
| | `task/flow/steps.py` | 已完成 | FlowStepType、ResponseDefinition、SlotValidation、FlowStep 及 4 个子类 |
| **task/loader** | `task/loader.py` | 已完成 | FlowLoader 流程加载器 |
| **flow_config** | `flow_config/*.yml` | 已完成 | 6 个业务流程 + 6 个系统流程 |
| **api** | `api/app.py` | 已完成 | FastAPI 应用实例 + lifespan |
| | `api/schemas.py` | 已完成 | ChatRequest、ChatResponse 等接口 Schema |
| | `api/router/chat_router.py` | 已完成 | `/api/chat` 聊天接口 |
| | `api/dependencies.py` | 已完成 | 依赖注入链 |
| **services** | `services/dialogue_service.py` | 已完成 | DialogueService 对话服务 |
| **engine** | `engine/dialogue_engine.py` | Stub | DialogueEngine 对话引擎（返回固定回复） |
| **repository** | `repository/dialogue_repository.py` | 已完成 | DialogueRepository 持久化 |
| **main** | `main.py` | 已完成 | uvicorn 启动入口 |
| **ecommerce-backend** | 全部 | 已完成 | 电商业务后端完整实现 |
| **frontend** | 全部 | 已完成 | 前端聊天界面 + 数字人集成 |

### 16.2 待实现模块

| 模块 | 预期内容 | 说明 |
|------|----------|------|
| **plan** | `plan/planner.py` | LLM 路由决策（TurnPlanner）- 已有占位文件 |
| **clarify** | `clarify/` | 校验失败澄清兜底（ClarifyResponder） |
| **task/handler** | `task/handler.py` | TaskHandler 任务轨道总入口 - 已有占位文件 |
| **task/command** | `task/command/` | 4 种命令处理器（start/cancel/resume/set_slots）- 已有数据模型 |
| **task/executor** | `task/executor.py` | FlowExecutor 流程执行器 |
| **task/action** | `task/action/` | Action 动作执行器 |
| **knowledge** | `knowledge/handler.py` | 知识问答轨道 - 已有占位文件 |
| **chitchat** | `chitchat/handler.py` | 闲聊兜底轨道 - 已有占位文件 |

### 16.3 总结

项目当前处于**基础设施层、领域模型层、API 层、服务层、仓储层、流程加载层已完成，引擎层仅有 stub，上层业务逻辑（plan、clarify、task handler/executor、knowledge、chitchat）待实现**的阶段。

**已完成部分**：
- 完整的基础设施（LLM、数据库、HTTP 客户端）
- 清晰的领域模型（消息、上下文、状态）
- 完善的流程编排系统（YAML 解析、数据模型）
- API 接口层与服务层
- 电商业务后端
- 前端聊天界面

**待完成部分**：
- 对话引擎的核心逻辑
- LLM 意图识别与路由
- 流程执行器
- 知识问答与闲聊轨道

已实现部分设计清晰、结构完整，为后续上层模块的实现奠定了坚实基础。

---

## 附录：核心类速查表

| 类名 | 文件 | 类型 | 说明 |
|------|------|------|------|
| `Settings` | config/settings.py | 配置类 | pydantic-settings 配置类 |
| `MessageType` | domain/messages.py | 枚举 | TEXT / OBJECT |
| `FocusedObject` | domain/messages.py | dataclass | 聚焦对象（订单/商品卡片） |
| `UserMessage` | domain/messages.py | dataclass | 用户消息 |
| `BotMessage` | domain/messages.py | dataclass | 机器人消息 |
| `ProcessResult` | domain/messages.py | dataclass | 引擎处理结果 |
| `TaskContext` | domain/contexts.py | dataclass | 业务任务上下文 |
| `SystemContext` | domain/contexts.py | dataclass | 系统流程上下文基类 |
| `StartedSystemContext` | domain/contexts.py | dataclass | 任务开始系统上下文 |
| `InterruptedSystemContext` | domain/contexts.py | dataclass | 任务中断系统上下文 |
| `ResumedSystemContext` | domain/contexts.py | dataclass | 任务恢复系统上下文 |
| `CanceledSystemContext` | domain/contexts.py | dataclass | 任务取消系统上下文 |
| `CollectedSystemContext` | domain/contexts.py | dataclass | 收集槽位系统上下文 |
| `Turn` | domain/state.py | dataclass | 对话轮次 |
| `Session` | domain/state.py | dataclass | 会话 |
| `DialogueState` | domain/state.py | dataclass | 对话状态聚合根 |
| `Base` | model/base.py | class | SQLAlchemy 声明式基类 |
| `DialogueStateRecord` | model/state_record.py | class | 对话状态 ORM 映射 |
| `DialogueRepository` | repository/dialogue_repository.py | class | 对话持久化仓储 |
| `DialogueService` | services/dialogue_service.py | class | 对话应用服务 |
| `DialogueEngine` | engine/dialogue_engine.py | class | 对话引擎 |
| `FlowSlot` | task/flow/flows.py | dataclass | 槽位定义 |
| `Flow` | task/flow/flows.py | dataclass | 流程定义 |
| `FlowsList` | task/flow/flows.py | dataclass | 流程列表（多 YAML 合并） |
| `FlowStepLink` | task/flow/links.py | dataclass | 边基类 |
| `FlowStepStaticLink` | task/flow/links.py | dataclass | 静态边 |
| `FlowStepConditionLink` | task/flow/links.py | dataclass | 条件边 |
| `FlowStepFallbackLink` | task/flow/links.py | dataclass | 兜底边 |
| `FlowStepType` | task/flow/steps.py | 枚举 | START / COLLECT / ACTION / END |
| `ResponseDefinition` | task/flow/steps.py | dataclass | 响应定义 |
| `SlotValidation` | task/flow/steps.py | dataclass | 槽位校验 |
| `FlowStep` | task/flow/steps.py | dataclass | 步骤基类 |
| `StartFlowStep` | task/flow/steps.py | dataclass | 开始步骤 |
| `EndFlowStep` | task/flow/steps.py | dataclass | 结束步骤 |
| `ActionFlowStep` | task/flow/steps.py | dataclass | 动作步骤 |
| `CollectFlowStep` | task/flow/steps.py | dataclass | 收集步骤 |
| `FlowLoader` | task/loader.py | class | 流程加载器 |
| `ChatObject` | api/schemas.py | Pydantic | 卡片对象 Schema |
| `ChatRequest` | api/schemas.py | Pydantic | 请求 Schema |
| `ChatBotMessage` | api/schemas.py | Pydantic | 机器人回复 Schema |
| `ChatResponse` | api/schemas.py | Pydantic | 响应 Schema |

---

**文档版本**: 1.0  
**最后更新**: 2026-07-13  
**基于代码版本**: customer-service-backend (当前实现状态)
