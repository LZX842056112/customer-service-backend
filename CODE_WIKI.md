# 电商智能客服系统 Code Wiki

> 本文档基于仓库实际代码编写，反映 `customer-service-backend` 当前的真实实现状态。

## 目录

1. [项目概述](#1-项目概述)
2. [整体架构](#2-整体架构)
3. [技术栈与依赖](#3-技术栈与依赖)
4. [目录结构](#4-目录结构)
5. [配置模块 (config)](#5-配置模块-config)
6. [基础设施层 (infrastructure)](#6-基础设施层-infrastructure)
7. [领域模型层 (domain)](#7-领域模型层-domain)
8. [流程编排系统 (task)](#8-流程编排系统-task)
9. [YAML 流程定义](#9-yaml-流程定义)
10. [上层模块设计说明](#10-上层模块设计说明)
11. [对话处理流程](#11-对话处理流程)
12. [模块依赖关系](#12-模块依赖关系)
13. [项目配置与运行](#13-项目配置与运行)
14. [设计理念与关键模式](#14-设计理念与关键模式)
15. [代码实现进度](#15-代码实现进度)

---

## 1. 项目概述

### 1.1 项目背景

本项目是一套基于大语言模型（LLM）的电商智能客服系统，旨在用工程化的方式驯服 LLM 的不确定性，保证业务结果稳定可控。系统支持用户用自然语言描述需求，由系统判断意图并路由到相应的处理轨道。

- **项目名**：`customer-service-1208`
- **版本**：1.0
- **Python 版本**：>= 3.12
- **包管理器**：`uv`
- **配置文件**：[pyproject.toml](file:///workspace/customer-service-backend/pyproject.toml)

### 1.2 系统能力

系统支持三条处理轨道，三者互斥——任何一句话只会走其中一条：

| 轨道 | 说明 | 示例场景 |
|------|------|----------|
| **任务流程（Task）** | 步骤明确、可按步骤推进的业务 | 查订单、查物流、申请退款 |
| **信息检索（Knowledge）** | 知识性问答，不需要走流程 | 商品信息、退款政策、退货政策 |
| **闲聊（Chitchat）** | 轻量交互兜底 | "你好"、"你挺聪明的" |

### 1.3 项目组成

整套项目由三个独立服务组成：

```
ecommerce-customer-service/
├── customer-service-backend/      ← 客服后端（AI 对话引擎，本仓库主战场）
├── customer-service-frontend/     ← 前端可视化控制台
└── ecommerce-service-backend/     ← 模拟电商业务后端
```

| 服务 | 角色 |
|------|------|
| `customer-service-backend` | AI 客服后端，承担所有对话与 LLM 调用 |
| `ecommerce-service-backend` | 电商业务后端，提供订单、物流、商品的查询接口 |
| `customer-service-frontend` | 前端聊天界面 |

**核心理念**：AI 客服不直接读电商数据库，而是以"业务系统消费者"的身份调用电商后端的 HTTP 接口，实现业务隔离。

---

## 2. 整体架构

### 2.1 分层架构

客服后端采用清晰的分层设计，遵循 DDD（领域驱动设计）思想：

| 层 | 主要职责 | 关键模块 |
|----|----------|----------|
| API 层 | 接收 HTTP 请求，组织请求与响应 | `atguigu/api/` |
| Service 层 | 把一次对话处理串起来：加载状态 → 调引擎 → 保存状态 | `atguigu/services/` |
| Engine 层 | 顶层调度，决定走哪条处理轨道 | `atguigu/engine/` |
| Plan 层 | 用 LLM 做本轮规划、校验、澄清兜底 | `atguigu/plan/` `atguigu/clarify/` |
| Task 层 | 推进固定任务流，执行各类 Action | `atguigu/task/` |
| Knowledge 层 | 检索信息并生成回复 | `atguigu/knowledge/` |
| Chitchat 层 | 闲聊兜底 | `atguigu/chitchat/` |
| Domain 层 | 消息、上下文、对话状态等领域模型 | `atguigu/domain/` |
| Repository 层 | 把 DialogueState 持久化到数据库 | `atguigu/repository/` |
| Infrastructure 层 | LLM、HTTP 客户端、数据库引擎等底层资源 | `atguigu/infrastructure/` |

### 2.2 整体调用关系

```
用户消息 → API层 → Service层 → Engine层
                           ↓
                    ┌───────┼───────┐
                    ↓       ↓       ↓
                Task轨道  Knowledge  Chitchat
                    ↓       ↓       ↓
                    └───────┼───────┘
                            ↓
                    Service层（保存状态）→ 返回回复
```

### 2.3 核心组件一览

| 组件 | 职责 | 源码位置 |
|------|------|----------|
| `DialogueService` | 加载 state → 调引擎 → 保存 state，一次完整对话事务 | `atguigu/services/`（待实现） |
| `DialogueEngine` | 顶层调度，根据本轮规划走任务/知识/闲聊三条轨道之一 | `atguigu/engine/`（待实现） |
| `TurnPlanner` | 把上下文喂给 LLM，让它输出结构化"行动计划" | `atguigu/plan/`（待实现） |
| `TurnPlanValidator` | 校验 LLM 输出，防止幻觉出未注册的 flow / intent | `atguigu/plan/`（待实现） |
| `ClarifyResponder` | 校验失败时，生成澄清回复反问用户 | `atguigu/clarify/`（待实现） |
| `TaskHandler` | task 轨道总入口，组织 CommandProcessor 和 FlowExecutor | `atguigu/task/`（待实现） |
| `FlowLoader` | 从 YAML 加载流程定义为内存对象树 | `atguigu/task/loader.py`（已实现） |
| `FlowExecutor` | YAML 流程图的解释器 | `atguigu/task/`（待实现） |
| `KnowledgeHandler` | 知识问答轨道总入口 | `atguigu/knowledge/`（待实现） |
| `ChitchatHandler` | 闲聊轨道 | `atguigu/chitchat/`（待实现） |
| `DialogueState` | 聚合根，承载活跃任务、暂停任务栈、聚焦对象、会话历史 | `atguigu/domain/state.py`（已实现） |
| `DialogueStateRepository` | DialogueState 序列化为 JSON 存到 MySQL 单表 | `atguigu/repository/`（待实现） |

---

## 3. 技术栈与依赖

### 3.1 后端技术栈

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

### 3.2 Python 依赖清单

**文件**: [pyproject.toml](file:///workspace/customer-service-backend/pyproject.toml)

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

### 3.3 设计特点

- **全异步架构**：`async/await` 一捅到底。LLM 调用是高延迟 I/O（单次 1~5 秒），同步模型并发上不去
- **配置即代码**：业务流程用 YAML 定义，代码只实现通用执行器
- **DDD 分层**：Service 管 I/O，Engine 管计算，状态集中管理

---

## 4. 目录结构

### 4.1 完整目录树

```
customer-service-backend/
├── atguigu/
│   ├── api/                      ← FastAPI 路由层（待实现）
│   │   └── __init__.py
│   ├── chitchat/                 ← 闲聊轨道（待实现）
│   │   └── __init__.py
│   ├── clarify/                  ← 校验失败时的澄清兜底（待实现）
│   │   └── __init__.py
│   ├── config/                   ← 配置模块（已实现）
│   │   ├── __init__.py
│   │   └── settings.py           ← pydantic-settings 读取 .env
│   ├── domain/                   ← 领域模型层（已实现）
│   │   ├── __init__.py
│   │   ├── contexts.py           ← 上下文模型
│   │   ├── messages.py           ← 消息模型
│   │   └── state.py              ← 对话状态聚合根
│   ├── engine/                   ← 对话引擎（待实现）
│   │   └── __init__.py
│   ├── infrastructure/           ← 基础设施层（已实现）
│   │   ├── __init__.py
│   │   ├── db.py                 ← SQLAlchemy 异步引擎
│   │   ├── http_client.py        ← httpx 客户端单例
│   │   └── llm_client.py         ← LangChain LLM 单例
│   ├── knowledge/                ← 知识问答轨道（待实现）
│   │   └── __init__.py
│   ├── plan/                     ← LLM 路由决策（待实现）
│   │   └── __init__.py
│   ├── repository/               ← 仓储层（待实现）
│   │   └── __init__.py
│   ├── services/                 ← 应用服务层（待实现）
│   │   └── __init__.py
│   ├── task/                     ← 任务流程编排层
│   │   ├── flow/                 ← 流程数据模型（已实现）
│   │   │   ├── __init__.py
│   │   │   ├── flows.py          ← Flow / FlowSlot / FlowsList
│   │   │   ├── links.py          ← FlowStepLink 边模型
│   │   │   └── steps.py          ← FlowStep 步骤模型
│   │   ├── system_flows.yml      ← 系统流程定义（副本）
│   │   ├── user_flows.yml        ← 业务流程定义（副本）
│   │   ├── __init__.py
│   │   └── loader.py             ← FlowLoader 流程加载器（已实现）
│   └── __init__.py
├── flow_config/                  ← YAML 流程定义（权威副本）
│   ├── system_flows.yml
│   └── user_flows.yml
├── pyproject.toml
└── uv.lock
```

### 4.2 YAML 文件位置说明

项目中存在两份 YAML 副本：

| 位置 | 说明 |
|------|------|
| `customer-service-backend/flow_config/` | **权威副本**，`loader.py` 的 `__main__` 测试块指向此路径 |
| `customer-service-backend/atguigu/task/` | 开发副本，`user_flows.yml` 多了一处空的 `validate` 占位块 |

两份 `system_flows.yml` 内容完全一致；两份 `user_flows.yml` 仅在 `logistics_tracking` 流程的 `ask_order_number` 步骤有微小差异（开发副本多了空的 validate 块）。

---

## 5. 配置模块 (config)

### 5.1 settings.py

**文件**: [settings.py](file:///workspace/customer-service-backend/atguigu/config/settings.py)

使用 `pydantic-settings` 的 `BaseSettings` 从 `.env` 文件加载配置，支持类型校验。

### 5.2 模块级常量

```python
PROJECT_ROOT_DIR = Path(__file__).resolve().parents[2]  # customer-service-backend/
ENV_FILE_PATH = PROJECT_ROOT_DIR / ".env"
```

### 5.3 Settings 类字段

所有字段均为**必填**（无默认值），若 `.env` 缺失对应项，导入本模块时即抛出 `ValidationError`（启动期校验）：

| 字段 | 类型 | 说明 | 示例值 |
|--------|------|------|--------|
| `llm_model` | `str` | LLM 模型名称 | `qwen-plus` |
| `llm_base_url` | `str` | LLM API 基础地址 | `https://dashscope.aliyuncs.com/compatible-mode/v1` |
| `llm_api_key` | `str` | LLM API 密钥 | `sk-xxxx` |
| `commerce_api_base_url` | `str` | 电商业务后端 API 地址 | `http://127.0.0.1:18081` |
| `database_url` | `str` | 数据库连接 URL | `mysql+aiomysql://root:root@localhost:3306/customer_service?charset=utf8mb4` |
| `app_host` | `str` | 应用监听地址 | `0.0.0.0` |
| `app_port` | `int` | 应用监听端口 | `18082` |

### 5.4 model_config 配置

```python
model_config = SettingsConfigDict(
    env_file=ENV_FILE_PATH,
    env_file_encoding="utf-8",
    extra="ignore"  # 忽略 .env 中未声明的字段
)
```

### 5.5 模块级单例

```python
settings = Settings()  # type: ignore
```

模块导入即创建单例，全局共享。

> **注意**：项目中 `.env` 文件实际不存在，运行前需手动创建。

---

## 6. 基础设施层 (infrastructure)

### 6.1 LLM 客户端

**文件**: [llm_client.py](file:///workspace/customer-service-backend/atguigu/infrastructure/llm_client.py)

基于 LangChain 1.x 的 `init_chat_model()` 创建 LLM 客户端单例，使用 OpenAI 兼容协议接入 DashScope（通义千问）。

```python
llm_client: BaseChatModel = init_chat_model(
    model=settings.llm_model,
    model_provider="openai",      # OpenAI 兼容协议
    base_url=settings.llm_base_url,
    api_key=settings.llm_api_key,
    temperature=0,                # 尽最大努力保证输出稳定性
    timeout=120                   # 超时 120 秒
)
```

**关键设计**:
- `temperature=0`：降低随机性，保证输出稳定
- `model_provider="openai"`：用 OpenAI 兼容接口接 DashScope
- 模块级单例，导入即创建

### 6.2 数据库引擎

**文件**: [db.py](file:///workspace/customer-service-backend/atguigu/infrastructure/db.py)

基于 SQLAlchemy 2.0 的异步数据库引擎与 session 工厂。

**模块级全局变量**:
```python
engine: AsyncEngine | None = None
session_factory: async_sessionmaker[AsyncSession] | None = None
```

**关键函数**:

| 函数 | 签名 | 说明 |
|------|------|------|
| `init_db_engine` | `async () -> None` | 初始化异步引擎和 session 工厂 |
| `dispose_engine` | `async () -> None` | 释放数据库连接 |

**init_db_engine 实现要点**:
```python
engine = create_async_engine(settings.database_url, echo=True)
session_factory = async_sessionmaker(engine, expire_on_commit=False)
```

**重要设计**:
- `expire_on_commit=False`：异步环境下提交后不自动过期。同步环境 commit 后属性过期会自动查库；异步环境访问已过期属性会报错，必须设为 False
- `echo=True`：控制台打印 SQL 语句，便于调试

> 采用"全局变量 + init/dispose 生命周期函数"模式，预期由未来的 FastAPI lifespan 统一初始化与释放。

### 6.3 HTTP 客户端

**文件**: [http_client.py](file:///workspace/customer-service-backend/atguigu/infrastructure/http_client.py)

基于 httpx 的异步 HTTP 客户端单例，用于调用电商业务后端接口。

**模块级全局变量**:
```python
http_client: AsyncClient | None = None
```

**关键函数**:

| 函数 | 签名 | 说明 |
|------|------|------|
| `init_http_client` | `() -> None`（同步） | 初始化 HTTP 客户端 |
| `dispose_http_client` | `async () -> None` | 关闭 HTTP 客户端 |

**init_http_client 实现要点**:
```python
http_client = AsyncClient(timeout=120, trust_env=False)
```

- `timeout=120`：与 LLM 客户端一致的 120 秒超时
- `trust_env=False`：不读取系统环境变量代理配置

---

## 7. 领域模型层 (domain)

领域层是整个系统的数据核心，包含三大模型，全部使用 `@dataclass(slots=True)` 定义。

### 7.1 消息模型 (messages.py)

**文件**: [messages.py](file:///workspace/customer-service-backend/atguigu/domain/messages.py)

#### MessageType 枚举

```python
class MessageType(Enum):
    TEXT = "text"       # 文本消息
    OBJECT = "object"   # 对象消息（订单卡片、商品卡片）
```

#### FocusedObject 聚焦对象

用户当前聚焦的业务对象（订单 / 商品）。前端点击卡片后发送对象消息，后端记录下来供后续对话使用。

```python
@dataclass(slots=True)
class FocusedObject:
    id: str                    # 对象唯一标识（订单号 or 商品ID）
    type: str                  # 对象类型："order" or "product"
    title: str | None = None   # 显示标题
    attributes: dict = field(default_factory=dict)  # 扩展属性
```

**方法**: `to_dict()`（对 attributes 做浅拷贝隔离）、`from_dict()` 类方法

#### UserMessage 用户消息

```python
@dataclass(slots=True)
class UserMessage:
    sender_id: str                    # 用户ID
    message_id: str                   # 消息ID
    type: MessageType                 # 消息类型
    text: str | None = None           # 文本内容
    object: FocusedObject | None = None  # 对象内容
```

用户发送的消息，文本和对象二选一（也可能同时存在）。`to_dict()` 会把 `type` 转为 `.value`。

#### BotMessage 机器人消息

```python
@dataclass(slots=True)
class BotMessage:
    text: str | None = None           # 文本回复
    object: FocusedObject | None = None  # 对象回复（扩展点）
```

### 7.2 上下文模型 (contexts.py)

**文件**: [contexts.py](file:///workspace/customer-service-backend/atguigu/domain/contexts.py)

上下文模型分为两类：
- **TaskContext**：业务任务的执行快照（用户想做的事）
- **SystemContext**：系统流程的执行快照（系统插播的过场）

#### TaskContext 业务任务上下文

```python
@dataclass(slots=True)
class TaskContext:
    flow_id: str                      # 业务流程ID
    step_id: str                      # 当前步骤ID
    slots: dict[str, Any] = field(default_factory=dict)  # 收集到的槽位数据
```

类比成一份正在填的表单：`flow_id` 是表单种类，`step_id` 是当前填到哪格，`slots` 是已填写内容。

#### SystemContext 系统上下文基类

```python
@dataclass(slots=True)
class SystemContext:
    system_flow_id: str               # 系统流程ID
    system_step_id: str               # 系统流程步骤ID
```

`from_dict` 方法通过 `SYSTEM_CONTEXT_TO_CLASS` 查表反序列化为正确的子类；`to_dict` 用 `asdict(self)` 转字典。

#### 五个 SystemContext 子类

| 子类 | 触发时机 | 系统会说的话（举例） |
|------|----------|---------------------|
| `StartedSystemContext` | 用户刚发起一个新任务 | "好的，我们先处理退款申请。" |
| `InterruptedSystemContext` | 用户在 A 任务过程中切到 B 任务 | "好的，我们先把退款放一放，先处理物流查询。" |
| `CanceledSystemContext` | 用户主动取消当前任务 | "好的，退款申请已为你取消。" |
| `ResumedSystemContext` | 用户要求恢复之前挂起的任务 | "好的，我们继续刚才的退款申请。" |
| `CollectedSystemContext` | 业务流程跑到 collect 步骤，需要用户补数据 | "请告诉我你的订单号。" |

**子类字段详情**:

```python
# 任务开始
class StartedSystemContext(SystemContext):
    started_flow_id: str     # 新开始的业务流程ID
    started_flow_name: str   # 新开始的业务流程名称

# 任务被打断
class InterruptedSystemContext(SystemContext):
    interrupted_flow_id: str    # 被中断的业务流程ID
    interrupted_flow_name: str  # 被中断的业务流程名称
    started_flow_id: str        # 新开启的业务流程ID
    started_flow_name: str      # 新开启的业务流程名称

# 任务被恢复
class ResumedSystemContext(SystemContext):
    resumed_flow_id: str     # 被恢复的业务流程ID
    resumed_flow_name: str   # 被恢复的业务流程名称

# 任务被取消
class CanceledSystemContext(SystemContext):
    canceled_flow_id: str    # 被取消的业务流程ID
    canceled_flow_name: str  # 被取消的业务流程名称

# 收集槽位
class CollectedSystemContext(SystemContext):
    response: dict[str, Any]  # 展示给用户的提示内容 {"text": "请告诉我你的订单号。"}
    slot_name: str            # 要收集的槽位名 "order_number"
```

#### 反序列化映射表

```python
SYSTEM_CONTEXT_TO_CLASS: dict[str, Any] = {
    "system_task_started": StartedSystemContext,
    "system_task_resumed": ResumedSystemContext,
    "system_collect_information": CollectedSystemContext,
    "system_task_interrupted": InterruptedSystemContext,
    "system_task_canceled": CanceledSystemContext
}
```

> 注意：`system_cannot_handle` 流程不需要专属上下文，故不在映射表中。

### 7.3 对话状态模型 (state.py)

**文件**: [state.py](file:///workspace/customer-service-backend/atguigu/domain/state.py)

`DialogueState` 是整个对话状态的**聚合根**，引擎操作的核心对象。

#### Turn 对话轮次

```python
@dataclass(slots=True)
class Turn:
    turn_id: str                      # 轮次ID
    user_message: UserMessage         # 用户消息
    bot_messages: list[BotMessage]    # 机器人回复列表
```

一次完整的问答交互：用户说一句话，机器人给出多条回复。

#### Session 会话

```python
@dataclass(slots=True)
class Session:
    session_id: str                   # 会话ID
    started_at: float                 # 开始时间戳
    last_activity_at: float           # 最后活动时间戳
    closed_at: float | None = None    # 关闭时间戳（None 代表会话可用）
    turns: list[Turn] = field(default_factory=list)  # 轮次列表
```

一段连续的聊天，超时（默认 60 分钟）后关闭，下次开启新会话。

#### DialogueState 聚合根

```python
@dataclass(slots=True)
class DialogueState:
    sender_id: str                                     # 用户ID
    active_task: TaskContext | None = None             # 当前活跃业务任务
    interrupted_active_tasks: list[TaskContext] = field(default_factory=list)  # 挂起的任务栈
    active_system_task: SystemContext | None = None    # 当前活跃系统流程
    focused_object: FocusedObject | None = None        # 聚焦的业务对象
    sessions: list[Session] = field(default_factory=list)  # 历史会话
    current_session_id: str | None = None              # 当前活跃会话ID
    pending_turn: Turn | None = None                   # 正在处理中的轮次（暂存区）
```

#### 字段分组说明

| 分组 | 字段 | 说明 |
|------|------|------|
| **任务相关** | `active_task` | 当前活跃的业务任务 |
| | `interrupted_active_tasks` | 被挂起的任务列表（栈结构，LIFO） |
| | `active_system_task` | 当前活跃的系统过场 |
| **聚焦对象** | `focused_object` | 用户当前聚焦的订单/商品 |
| **会话历史** | `sessions` | 历史会话列表 |
| | `current_session_id` | 当前活跃会话 ID |
| **本轮处理** | `pending_turn` | 正在处理中的轮次（暂存区） |

#### DialogueState 关键方法

**流程管理方法**:

| 方法 | 说明 |
|------|------|
| `start_active_system_task(system_context)` | 开启并激活系统流程 |
| `end_activating_system_task()` | 结束正在激活的系统流程 |
| `start_active_business_task(task_context)` | 开启并激活业务流程 |
| `end_activating_business_task()` | 结束正在激活的业务流程 |
| `end_activating_task()` | 同时清空业务流程和系统流程 |
| `interrupted_activating_task()` | 将当前业务流程压入 `interrupted_active_tasks` 栈并清空 active_task |
| `resumed_interrupted_business_task(flow_id=None) -> bool` | 从栈中恢复任务（可按 flow_id 精确恢复，否则弹栈顶 LIFO） |
| `current_activating_task()` | 返回当前活跃流程，**系统流程优先于业务流程** |

**current_activating_task 优先级逻辑**:
```python
return self.active_system_task or self.active_task
```

**槽位方法**:

| 方法 | 说明 |
|------|------|
| `set_slots(slots: dict)` | 更新到 `active_task.slots` |
| `get_slot(slot_name) -> Any` | 从 `active_task.slots` 读取槽位值 |

**卡片方法**:

| 方法 | 说明 |
|------|------|
| `set_focused_object(focused_object)` | 设置聚焦的业务对象 |

**会话方法**:

| 方法 | 说明 |
|------|------|
| `current_session() -> Session \| None` | 按 `current_session_id` 查找当前会话 |
| `start_session()` | 创建新 Session（生成 uuid），更新 `current_session_id`，追加到 `sessions` |
| `close_session()` | 设置 `closed_at`，清空 `current_session_id`（不从 sessions 移除） |
| `reset_running_state_for_new_session()` | 会话超时时清空所有任务/卡片/pending_turn |

**轮次方法**:

| 方法 | 说明 |
|------|------|
| `start_turn(user_message)` | 创建 Turn 放入 `pending_turn` 缓冲区 |
| `commit_pending_turn()` | 将 `pending_turn` 提交到 `current_session().turns` 并清空缓冲区 |

#### pending_turn 两步提交设计

`pending_turn` 是一个重要的设计——处理中的轮次先放在暂存区，处理完成后再通过 `commit_pending_turn()` 提交到会话。

**好处**:
- 处理失败时只要丢掉 `pending_turn` 即可，`turns` 始终干净
- 决定不入库时只要不调用 commit，简单高效
- `turns` 里的每一条 Turn 都是完整的

#### 序列化方法

`DialogueState` 提供完整的 `to_dict()` / `from_dict()` 序列化方法，支持嵌套对象的递归序列化与反序列化，用于持久化到数据库。

---

## 8. 流程编排系统 (task)

### 8.1 设计理念

业务流程不写在代码里，而是写在 YAML 配置文件里。代码只实现一个通用的「流程加载器」和「流程执行器」按定义往前推。

**优势**:
- 新增业务流程不需要改代码，只需加一份 YAML
- 非程序员也可以编辑流程定义
- 流程变更不需要重新部署

### 8.2 流程数据模型 (flow/flows.py)

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
    slots: dict[str, FlowSlot] = field(default_factory=dict)  # 该流程用到的槽位

@dataclass(slots=True)
class FlowsList:
    flows: list[Flow] = field(default_factory=list)           # 两份 YAML 的 flows 合并
    slots: dict[str, FlowSlot] = field(default_factory=dict)  # 两份 YAML 的 slots 合并
```

> `Flow.description` 字段非常重要：未来会把所有业务流程的描述提供给 LLM，让 LLM 根据用户任务选择要开启哪个业务流程。

### 8.3 边（转移）模型 (flow/links.py)

**文件**: [links.py](file:///workspace/customer-service-backend/atguigu/task/flow/links.py)

定义流程步骤之间的转移关系：

```python
@dataclass(slots=True)
class FlowStepLink:
    """边的基类：提供下一个 step_id"""
    target: str  # 下一个步骤的ID

@dataclass(slots=True)
class FlowStepStaticLink(FlowStepLink):
    """静态非条件边，对应 next: ask_refund_reason"""
    pass

@dataclass(slots=True)
class FlowStepConditionLink(FlowStepLink):
    """条件边，对应 if/then 语法"""
    condition: str  # 用 eval() 计算，例如 "context.get('reason') == 'clarification_rejected'"

@dataclass(slots=True)
class FlowStepFallbackLink(FlowStepLink):
    """兜底 else 边"""
    pass
```

### 8.4 步骤模型 (flow/steps.py)

**文件**: [steps.py](file:///workspace/customer-service-backend/atguigu/task/flow/steps.py)

#### FlowStepType 枚举

```python
class FlowStepType(Enum):
    START = "start"      # 流程起点（通用）
    COLLECT = "collect"  # 收集槽位（仅业务流程）
    ACTION = "action"    # 执行动作
    END = "end"          # 流程结束（通用）
```

**ACTION 步骤的三种动作**:
- `action_listen`：让执行引擎停下来，把控制权交给用户
- `action_response`：告诉用户信息（开场白、槽位填写提示、查询结果）
- `action_xxx`：找外部要数据（调电商接口）

**关键规则**:
- 系统流程的 action 只有 `action_response` 和 `action_listen`
- 业务流程一定有 `action_xxx`（找外部要数据）和 `action_response`，但不会有 `action_listen`
- `action_listen` 只出现在 `system_collect_information` 流程中

#### ResponseDefinition 响应定义

```python
@dataclass(slots=True)
class ResponseDefinition:
    text: str                    # 响应内容
    mode: str = "static"         # static 直接渲染 / rephrase 用 LLM 改写
    prompt: str | None = None    # rephrase 模式下的 LLM 提示词
```

#### SlotValidation 槽位校验

```python
@dataclass(slots=True)
class SlotValidation:
    condition: str                              # 校验条件表达式
    failure_response: ResponseDefinition | None = None  # 校验失败的响应
```

#### FlowStep 基类与子类

```python
@dataclass(slots=True)
class FlowStep:
    """步骤基类"""
    id: str
    type: FlowStepType
    next: list[FlowStepLink] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> Self:
        """根据 type 字段分发到具体子类"""
        step_type = data['type']
        clz = FLOW_STEP_TYPE_TO_CLASS[step_type]
        return clz.from_dict(data)

    @staticmethod
    def load_base_fields(step_data: dict) -> dict:
        """提取通用字段 id / type / next"""

    @classmethod
    def build_links(cls, link: str | list[dict]) -> list[FlowStepLink]:
        """将 YAML 的 next 字段解析为边对象列表"""
```

| 子类 | 额外字段 | 说明 |
|------|----------|------|
| `StartFlowStep` | 无 | 仅复用基类字段 |
| `EndFlowStep` | 无 | 仅复用基类字段 |
| `ActionFlowStep` | `action: str`、`args: dict` | 执行动作步骤 |
| `CollectFlowStep` | `slot_name: str`、`response: ResponseDefinition`、`validate: SlotValidation \| None` | 收集槽位步骤 |

#### build_links 解析逻辑

`FlowStep.build_links()` 将 YAML 中的 `next` 字段解析为边对象列表：

- `next` 是字符串 → 创建 `FlowStepStaticLink`
- `next` 是列表：
  - 含 `if` 键的项 → 创建 `FlowStepConditionLink`（取 `if` 作为 condition，`then` 作为 target）
  - 含 `else` 键的项 → 创建 `FlowStepFallbackLink`（取 `else` 作为 target）

#### 类型映射表

```python
FLOW_STEP_TYPE_TO_CLASS: dict[str, type[FlowStep]] = {
    "start": StartFlowStep,
    "end": EndFlowStep,
    "collect": CollectFlowStep,
    "action": ActionFlowStep
}
```

### 8.5 流程加载器 (task/loader.py)

**文件**: [loader.py](file:///workspace/customer-service-backend/atguigu/task/loader.py)

`FlowLoader` 类负责将 YAML 配置文件解析为内存中的 `FlowsList` 对象树，是流程加载的核心入口。

#### FlowLoader 方法

| 方法 | 说明 |
|------|------|
| `load_many_yaml(paths: list[str \| Path]) -> FlowsList` | 加载多份 YAML 并合并 flows 和 slots |
| `load_yaml(path: Path) -> FlowsList` | 加载单份 YAML：读取 → 加载 slots → 加载 flows |
| `load_slots(slots: dict) -> dict[str, FlowSlot]` | 将槽位字典转成 FlowSlot 对象 |
| `load_flows(flows: dict, loaded_slots) -> list[Flow]` | 加载所有流程，关联槽位 |
| `_load_flow_slot(steps, loaded_slots) -> dict[str, FlowSlot]` | 私有方法，提取流程用到的槽位 |

#### 加载流程

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

#### _load_flow_slot 槽位关联逻辑

遍历流程步骤，仅处理 `CollectFlowStep` 类型，提取其 `slot_name`，从全局 `loaded_slots` 中查找已定义的槽位并收集到该流程专属的 slots 字典中。实现"流程知道自己需要哪些槽位"。

#### load_many_yaml 多文件合并

```python
def load_many_yaml(self, paths: list[str | Path]) -> FlowsList:
    flows: list[Flow] = []
    slots: dict[str, FlowSlot] = {}
    for path in paths:
        loaded = self.load_yaml(path)
        flows.extend(loaded.flows)    # flows 列表合并
        slots.update(loaded.slots)    # slots 字典合并
    return FlowsList(flows=flows, slots=slots)
```

用于同时加载 `system_flows.yml` 和 `user_flows.yml` 两份文件。

---

## 9. YAML 流程定义

### 9.1 流程配置文件

| 文件 | 作用 |
|------|------|
| [user_flows.yml](file:///workspace/customer-service-backend/flow_config/user_flows.yml) | 业务流程定义 |
| [system_flows.yml](file:///workspace/customer-service-backend/flow_config/system_flows.yml) | 系统流程定义 |

### 9.2 业务流程槽位定义 (user_flows.yml)

共定义 **8 个槽位**：

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

所有槽位 `type` 均为 `text`。

### 9.3 业务流程定义 (user_flows.yml)

共定义 **6 个业务流程**：

| 流程ID | 名称 | 步骤概览 |
|--------|------|----------|
| `onboarding` | 欢迎引导 | start → respond(action_response) → end |
| `order_status_query` | 订单状态查询 | start → ask_order_number(collect) → lookup_order_status(action) → show_order_status(action_response) → end |
| `logistics_tracking` | 物流查询 | start → ask_order_number(collect) → lookup_logistics(action) → show_logistics(action_response) → end |
| `refund_request` | 退款申请 | start → ask_order_number(collect) → ask_refund_reason(collect) → refund_submitted(action_response) → end |
| `similar_product_recommendation` | 相似商品推荐 | start → 条件分支（有 product_id 走 respond，否则 ask_product_id）→ respond(action_recommend_similar_products) → end |
| `human_handoff` | 人工客服 | start → respond(action_response) → end |

**退款申请流程示例**:

```yaml
refund_request:
  name: 退款申请
  description: 帮用户提交简单的退款申请，收集订单号和退款原因。
  steps:
    - id: start
      type: start
      next: ask_order_number

    - id: ask_order_number
      type: collect
      slot_name: order_number
      response:
        text: "请告诉我你的订单号。"
      next: ask_refund_reason

    - id: ask_refund_reason
      type: collect
      slot_name: refund_reason
      response:
        text: "请简单说一下退款原因。"
      next: refund_submitted

    - id: refund_submitted
      type: action
      action: action_response
      args:
        text: "好的，订单{{ slots.order_number }}的退款申请已提交，原因是：{{ slots.refund_reason }}。后续会尽快为你处理。"
      next: end

    - id: end
      type: end
      next: []
```

**条件分支示例（相似商品推荐）**:

```yaml
- id: start
  type: start
  next:
    - if: "slots.get('product_id')"
      then: respond
    - else: ask_product_id
```

### 9.4 系统流程定义 (system_flows.yml)

共定义 **6 个系统流程**（无 slots）：

| 流程ID | 名称 | 触发时机 |
|--------|------|----------|
| `system_task_started` | task started acknowledgement | 开启新业务任务时 |
| `system_task_resumed` | task resumed acknowledgement | 恢复挂起任务时 |
| `system_collect_information` | collect information | 需要收集槽位时 |
| `system_task_interrupted` | task interrupted acknowledgement | 任务被打断时 |
| `system_task_canceled` | task canceled acknowledgement | 任务被取消时 |
| `system_cannot_handle` | cannot handle request | 无法处理请求时 |

**system_collect_information 流程（含 action_listen）**:

```yaml
system_collect_information:
  steps:
    - id: start
      type: start
      next: ask
    - id: ask
      type: action
      action: action_response
      args: context.response   # 动态参数，运行时由上下文提供
      next: listen
    - id: listen
      type: action
      action: action_listen    # 引擎停止执行，把控制权交给用户
      next: end
    - id: end
      type: end
      next: []
```

**system_cannot_handle 流程（最复杂，含 4 个条件分支）**:

根据 `context.get('reason')` 的值路由到不同回复：
- `clarification_rejected` → 澄清被拒绝
- `not_supported` → 能力未接入
- `no_relevant_answer` → 无相关信息
- else → 请求用户重新表述

所有分支均为 `mode: rephrase`（需 LLM 改写），每个都带 `prompt` 提示词模板。

### 9.5 Step 类型汇总

| 类型 | 说明 | 关键字段 |
|------|------|----------|
| `start` | 流程起点 | `next` |
| `collect` | 收集槽位 | `slot_name`, `response`, `next`, `validate`(可选) |
| `action` | 执行动作 | `action`, `args`, `next` |
| `end` | 流程结束 | - |

### 9.6 Action 类型汇总

| Action | 说明 | 出现位置 |
|--------|------|----------|
| `action_response` | 生成文本回复（支持模板变量） | 业务流程 + 系统流程 |
| `action_listen` | 停止执行，等待用户输入 | 仅 `system_collect_information` |
| `action_lookup_order_status` | 查询订单状态 | `order_status_query` |
| `action_lookup_logistics` | 查询物流信息 | `logistics_tracking` |
| `action_recommend_similar_products` | 推荐相似商品 | `similar_product_recommendation` |

### 9.7 模板变量

回复文本支持 Jinja2 风格的模板变量：

| 变量 | 说明 | 使用场景 |
|------|------|----------|
| `{{ slots.xxx }}` | 当前任务的槽位值 | 业务流程的 action_response |
| `{{ context.xxx }}` | 系统上下文的字段 | 系统流程的 action_response |
| `{history}` | 对话历史 | rephrase 模式的 prompt |
| `{user_message}` | 用户最后一条消息 | rephrase 模式的 prompt |
| `{current_response}` | 建议回复 | rephrase 模式的 prompt |

---

## 10. 上层模块设计说明

> 以下模块在代码中尚未实现（仅有 `__init__.py` docstring 占位），此处根据项目设计文档和 `__init__.py` 注释描述预期职责。

### 10.1 api 接口层

**目录**: [api/](file:///workspace/customer-service-backend/atguigu/api/)

FastAPI 路由层，提供 HTTP 接口。

**预期接口**:

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/chat` | POST | 发送消息，获取回复 |
| `/api/chat/history` | GET | 获取对话历史 |

### 10.2 services 服务层

**目录**: [services/](file:///workspace/customer-service-backend/atguigu/services/)

应用服务层，把一次对话处理串起来。

**核心流程**:
1. 从 Repository 加载 `DialogueState`
2. 调用 `DialogueEngine` 处理消息
3. 保存 `DialogueState` 回 Repository
4. 返回机器人回复

> Service 层是事务边界——所有持久化操作集中在这一层，引擎层是纯计算。

### 10.3 engine 引擎层

**目录**: [engine/](file:///workspace/customer-service-backend/atguigu/engine/)

`DialogueEngine` 是一轮消息处理的调度中心，接收用户消息和 `DialogueState`，判断本轮走哪条处理路径，并返回机器人回复。

**核心职责**:
1. 准备会话（检查超时、创建新会话）
2. 创建本轮记录（pending_turn）
3. 判断消息类型（文本 / 对象）
4. 调用 TurnPlanner 理解用户意图
5. 校验理解结果
6. 分发到 Task / Knowledge / Chitchat 三条轨道
7. 提交本轮记录

### 10.4 plan 规划层

**目录**: [plan/](file:///workspace/customer-service-backend/atguigu/plan/)

LLM 路由决策层，核心组件是 `TurnPlanner`。

**核心职责**:
- 把用户问题、对话历史、当前状态喂给 LLM
- 让 LLM 输出结构化的「本轮计划」(TurnPlan)
- 由 `TurnPlanValidator` 做白名单校验，防止幻觉

### 10.5 clarify 澄清层

**目录**: [clarify/](file:///workspace/customer-service-backend/atguigu/clarify/)

当 `TurnPlanValidator` 校验失败时，由 `ClarifyResponder` 生成澄清追问。

**常见需要澄清的情况**:

| 类别 | 包含 | 本质 |
|------|------|------|
| 轨道层面 | `MISSING_TRACK` / `MULTIPLE_TRACKS` | 没选出轨道 / 选了太多轨道 |
| 轨道内容缺失 | `MISSING_TASK_COMMANDS` / `MISSING_KNOWLEDGE_INTENT` | 选对了轨道，但里面是空的 |
| 对象相关 | `MISSING_FOCUSED_OBJECT` / `OBJECT_REQUIRES_INTENT` | 缺对象 / 只有对象没意图 |

### 10.6 task 任务层（待实现部分）

**目录**: [task/](file:///workspace/customer-service-backend/atguigu/task/)

**子模块**:

| 子模块 | 作用 | 状态 |
|--------|------|------|
| `loader.py` | FlowLoader，流程加载 | 已实现 |
| `flow/` | Flow 数据模型 | 已实现 |
| `handler.py` | TaskHandler，task 轨道总入口 | 待实现 |
| `command/` | 4 种命令处理器：start / cancel / resume / set_slots | 待实现 |
| `executor` | FlowExecutor 流程执行器 | 待实现 |
| `action/` | Action 注册表 + 内置/自定义动作 | 待实现 |

**命令处理器（CommandProcessor）设计**:

| 命令 | 作用 |
|------|------|
| `start_task` | 启动新任务（可能打断当前任务） |
| `cancel_task` | 取消当前或挂起的任务 |
| `resume_task` | 恢复挂起的任务 |
| `set_slots` | 填充当前任务的槽位 |

### 10.7 knowledge 知识层

**目录**: [knowledge/](file:///workspace/customer-service-backend/atguigu/knowledge/)

知识问答轨道，处理不需要走流程的信息咨询类问题。

**知识意图分类**:

| 知识意图 | 示例问题 | 信息源 |
|----------|----------|--------|
| 商品信息咨询 | "这件商品多少钱？" | 商品 API |
| 订单信息咨询 | "这个订单现在啥情况？" | 订单 API |
| 退款政策咨询 | "退款多久能到账？" | FAQ |
| 退货政策咨询 | "支持七天无理由吗？" | FAQ |
| 配送政策咨询 | "多久发货？" | FAQ |
| 平台规则咨询 | "平台有哪些限制？" | RAG 知识库 |
| 通用电商问题 | "优惠券怎么领？" | FAQ + RAG |

### 10.8 chitchat 闲聊层

**目录**: [chitchat/](file:///workspace/customer-service-backend/atguigu/chitchat/)

闲聊兜底轨道，处理既不属于明确任务、也不适合走知识检索的轻量输入。

### 10.9 repository 仓储层

**目录**: [repository/](file:///workspace/customer-service-backend/atguigu/repository/)

负责 `DialogueState` 的持久化。

**设计特点**:
- 整份 `DialogueState` 序列化为 JSON 字符串
- 存到 `dialogue_states` 表的 `state_json` 字段
- 不拆成多张表，学习阶段调试直观

**数据库表结构**:

| 字段 | 类型 | 说明 |
|------|------|------|
| `sender_id` | `VARCHAR(255)` 主键 | 用户唯一标识 |
| `state_json` | `TEXT` | DialogueState 序列化后的 JSON |

---

## 11. 对话处理流程

### 11.1 一条消息的完整旅程

```
用户发送消息
    ↓
API层接收请求
    ↓
Service层加载DialogueState
    ↓
Engine层处理
    ├─ 1. 准备会话（检查超时）
    ├─ 2. 创建本轮记录（start_turn）
    ├─ 3. 判断消息类型
    │   ├─ 文本消息 → TurnPlanner规划
    │   └─ 对象消息 → 设置focused_object
    ├─ 4. 校验规划结果
    │   ├─ 校验失败 → ClarifyResponder澄清
    │   └─ 校验通过 → 继续
    ├─ 5. 分发到三条轨道
    │   ├─ Task轨道 → TaskHandler → FlowExecutor
    │   ├─ Knowledge轨道 → KnowledgeHandler
    │   └─ Chitchat轨道 → ChitchatHandler
    └─ 6. 提交本轮记录（commit_pending_turn）
    ↓
Service层保存DialogueState
    ↓
返回机器人回复
```

### 11.2 会话准备流程

```
检查当前会话是否存在
    ├─ 不存在 → 创建新会话
    └─ 存在
        ├─ 未超时 → 继续使用
        └─ 已超时 → 关闭旧会话，创建新会话，重置运行时状态
```

**reset_running_state_for_new_session 清空内容**:
- `active_task` 当前业务任务
- `interrupted_active_tasks` 暂停任务栈
- `active_system_task` 系统流程
- `focused_object` 聚焦对象
- `pending_turn` 暂存轮次

### 11.3 任务切换机制

系统支持复杂的任务切换，使用**栈结构**管理挂起的任务（LIFO - 后进先出）。

#### 打断（Interrupt）

用户在任务 A 中途切到任务 B：
- A 从 `active_task` 移到 `interrupted_active_tasks` 栈顶（`interrupted_activating_task()`）
- B 成为新的 `active_task`
- 触发 `InterruptedSystemContext` 过场白

#### 恢复（Resume）

用户要求恢复之前的任务（`resumed_interrupted_business_task(flow_id=None)`）：
- 默认恢复栈顶任务（LIFO）
- 用户明确指名时，按 `flow_id` 精确匹配恢复（可跨过栈顶）
- 触发 `ResumedSystemContext` 过场白

#### 取消（Cancel）

用户取消任务：
- 可以取消当前活跃任务
- 也可以取消挂起栈里的某个任务
- 被取消的任务直接丢弃（不进栈）
- 触发 `CanceledSystemContext` 过场白

#### 连环打断示例

```
用户: 查订单状态          → active_task = 订单状态查询
用户: 先查物流            → 订单状态查询进栈，active_task = 物流查询
用户: 我要退款            → 物流查询进栈，active_task = 退款申请
用户: (退款完成)          → active_task = 空
用户: 继续刚才的          → 恢复栈顶（物流查询）
```

栈变化：`[] → [订单状态查询] → [订单状态查询, 物流查询] → [订单状态查询, 物流查询] → [订单状态查询]`

### 11.4 校验与澄清机制

LLM 的输出不能直接使用，必须经过白名单校验。

**校验不通过时**:
- 不执行业务逻辑
- 由 `ClarifyResponder` 生成澄清追问
- 本轮只回复追问，不推进任务

**校验维度**:
- 轨道层面：有没有选出轨道？是不是选了多条？
- 轨道内容：选了任务轨道但没给具体命令？选了知识轨道但没给具体意图？
- 对象相关：需要对象但没有？只有对象没有意图？

---

## 12. 模块依赖关系

### 12.1 外部服务依赖

| 服务 | 用途 | 配置项 |
|------|------|--------|
| **LLM API** | 大语言模型推理 | `llm_base_url`, `llm_api_key`, `llm_model` |
| **MySQL 数据库** | 对话状态持久化 | `database_url` |
| **电商业务后端** | 订单/物流/商品数据查询 | `commerce_api_base_url` |

### 12.2 内部模块依赖图

```
api → services → engine → plan → clarify
                    ↓
            ┌───────┼───────┐
            ↓       ↓       ↓
          task  knowledge  chitchat
            ↓
       flow/action/command

所有层 → domain（数据模型）
所有层 → infrastructure（基础设施）
services → repository（持久化）
```

### 12.3 已实现模块的依赖链

```
config/settings.py
    ↓
infrastructure/llm_client.py（依赖 settings）
infrastructure/db.py（依赖 settings）
infrastructure/http_client.py（无依赖）

domain/messages.py（无依赖）
domain/contexts.py（无依赖）
domain/state.py（依赖 messages + contexts）

task/flow/links.py（无依赖）
task/flow/steps.py（依赖 links）
task/flow/flows.py（依赖 steps）
task/loader.py（依赖 flows + steps）
```

### 12.4 依赖方向规则

- 上层依赖下层，下层不依赖上层
- 所有层都可以依赖 domain 层（数据模型）和 infrastructure 层（基础设施）
- domain 层不依赖任何其他层

---

## 13. 项目配置与运行

### 13.1 环境要求

- Python >= 3.12
- MySQL 数据库
- 可用的 LLM API（通义千问兼容 OpenAI 协议）
- 电商业务后端服务
- `uv` 包管理器

### 13.2 创建 .env 配置文件

在 `customer-service-backend/` 目录下创建 `.env` 文件（项目中默认不存在，需手动创建）：

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

> 若 `LLM_API_KEY` 等必填项缺失，Pydantic 启动时会直接报错——这是设计如此的"启动期校验"。

### 13.3 依赖安装

项目使用 `uv` 作为 Python 包管理器：

```bash
cd customer-service-backend
uv sync
```

### 13.4 数据库初始化

需要创建 `customer_service` 数据库和 `dialogue_states` 表：

```sql
CREATE DATABASE customer_service CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

USE customer_service;

CREATE TABLE dialogue_states (
    sender_id VARCHAR(255) PRIMARY KEY,
    state_json TEXT
);
```

### 13.5 启动顺序

```bash
# 1. 启动数据库（Docker 方式）
cd docker
docker compose up -d

# 2. 启动模拟电商后端
cd ecommerce-service-backend
uv sync
uv run python main.py

# 3. 启动客服后端
cd customer-service-backend
uv sync
uv run python main.py

# 4. 启动前端
cd customer-service-frontend
npm install
npm run dev
```

启动后访问 [http://127.0.0.1:5173](http://127.0.0.1:5173)。

> **注意**：客服后端的 `main.py` / `app.py` 入口文件当前尚未实现，需先创建应用入口。

### 13.6 验证安装

已实现的基础设施模块都提供了 `__main__` 测试入口：

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

## 14. 设计理念与关键模式

### 14.1 五大设计原则

1. **三条轨道分离** —— 任务、知识、闲聊各走各的代码路径，互不污染
2. **LLM 路由 + 白名单校验 + 澄清兜底** —— 永远不"裸用" LLM 的输出，留有兜底
3. **YAML 描述流程，代码执行流程** —— 可枚举的业务逻辑从 LLM 手里拿出来，交给状态机
4. **DialogueState 集中状态，Engine 集中计算** —— 状态读写在边缘（Service），计算在中心（Engine）
5. **业务隔离** —— AI 客服永远以"业务消费者"身份调电商接口，不直连业务数据库

### 14.2 关键设计模式

| 模式 | 应用位置 | 作用 |
|------|----------|------|
| **聚合根模式** | `DialogueState` | 集中管理所有对话状态，保证一致性 |
| **注册表模式** | `SYSTEM_CONTEXT_TO_CLASS`、`FLOW_STEP_TYPE_TO_CLASS` | 通过字典查表实现多态分发 |
| **工厂方法模式** | `FlowStep.from_dict`、`SystemContext.from_dict` | 根据 type 字段创建对应子类 |
| **模板方法模式** | `SystemContext` 子类 | 基类定义序列化接口，子类实现具体数据 |
| **两步提交** | `pending_turn` | 处理中与已提交分离，保证数据完整性 |
| **状态机模式** | FlowExecutor（待实现） | YAML 定义的有限状态机驱动流程推进 |
| **策略模式** | 三条轨道处理（待实现） | 不同轨道不同处理策略 |

### 14.3 DDD 思想应用

- **事务脚本 + 充血模型**：Service 层是事务脚本（管 I/O），Engine 层是纯计算（管逻辑）
- **仓储模式**：Repository 封装持久化细节，领域层不关心存储
- **领域模型与基础设施分离**：domain 层纯数据和业务规则，infrastructure 层管外部依赖

### 14.4 工程化驯服 LLM 的手段

1. **结构化输出**：让 LLM 输出 JSON 而不是自由文本
2. **白名单校验**：对 LLM 输出做 schema 校验 + 业务白名单校验
3. **澄清兜底**：校验不通过时，用 LLM 生成追问而不是硬执行
4. **流程编排**：确定性逻辑用 YAML 状态机，不让 LLM 直接控制流程
5. **任务栈管理**：多任务切换用栈结构，LIFO 语义符合人类直觉

### 14.5 dataclass + slots 设计

所有领域模型使用 `@dataclass(slots=True)`，好处：
1. 访问速度快（`__slots__` 代替 `__dict__`）
2. 占用内存空间更小
3. 对象的属性个数固定

---

## 15. 代码实现进度

根据当前仓库状态，各模块实现进度如下：

### 15.1 已实现模块

| 模块 | 文件 | 状态 | 说明 |
|------|------|------|------|
| **config** | `config/settings.py` | 已实现 | Settings 类完整实现，含 7 个配置项 |
| **domain** | `domain/messages.py` | 已实现 | MessageType、FocusedObject、UserMessage、BotMessage |
| | `domain/contexts.py` | 已实现 | TaskContext、SystemContext 及 5 个子类 |
| | `domain/state.py` | 已实现 | Turn、Session、DialogueState 聚合根，含完整方法 |
| **infrastructure** | `infrastructure/llm_client.py` | 已实现 | LangChain LLM 客户端单例 |
| | `infrastructure/db.py` | 已实现 | SQLAlchemy 异步引擎与 session 工厂 |
| | `infrastructure/http_client.py` | 已实现 | httpx 异步 HTTP 客户端单例 |
| **task/flow** | `task/flow/flows.py` | 已实现 | FlowSlot、Flow、FlowsList |
| | `task/flow/links.py` | 已实现 | FlowStepLink 及 3 个子类 |
| | `task/flow/steps.py` | 已实现 | FlowStepType、ResponseDefinition、SlotValidation、FlowStep 及 4 个子类 |
| **task/loader** | `task/loader.py` | 已实现 | FlowLoader 流程加载器 |
| **flow_config** | `flow_config/*.yml` | 已实现 | 6 个业务流程 + 6 个系统流程 |

### 15.2 待实现模块

| 模块 | 预期文件 | 状态 | 说明 |
|------|----------|------|------|
| **api** | `api/app.py`、`api/routers.py` 等 | 待实现 | 仅有 docstring 占位 |
| **services** | `services/dialogue_service.py` | 待实现 | 仅有 docstring 占位 |
| **engine** | `engine/dialogue_engine.py`、`engine/builder.py` | 待实现 | 仅有 docstring 占位 |
| **plan** | `plan/turn_planner.py`、`plan/validator.py` 等 | 待实现 | 仅有 docstring 占位 |
| **clarify** | `clarify/responder.py` | 待实现 | 仅有 docstring 占位 |
| **task/handler** | `task/handler.py` | 待实现 | TaskHandler |
| **task/command** | `task/command/processor.py` | 待实现 | 4 种命令处理器 |
| **task/executor** | `task/flow/executor.py` | 待实现 | FlowExecutor 流程执行器 |
| **task/action** | `task/action/runner.py` | 待实现 | ActionRunner 动作执行器 |
| **knowledge** | `knowledge/handler.py` 等 | 待实现 | 仅有 docstring 占位 |
| **chitchat** | `chitchat/handler.py` | 待实现 | 仅有 docstring 占位 |
| **repository** | `repository/dialogue_state_repository.py` | 待实现 | 仅有 docstring 占位 |
| **应用入口** | `main.py` / `app.py` | 不存在 | 无 FastAPI 实例化或 uvicorn.run |

### 15.3 已实现的代码链路

已实现部分构成了一条清晰的**配置加载与领域模型链路**：

```
YAML (flow_config/)
   ↓ FlowLoader.load_many_yaml / load_yaml
FlowLoader (task/loader.py)
   ↓ FlowStep.from_dict (steps.py) + build_links (links.py)
Flow / FlowSlot / FlowsList (flow/flows.py)
   ↓ 供引擎使用（engine/ 待实现）

DialogueState (domain/state.py)  ← 聚合根
   ├─ TaskContext / SystemContext (contexts.py)
   ├─ UserMessage / BotMessage / FocusedObject (messages.py)
   └─ Turn / Session (state.py)
   ↓ 持久化（repository/ 待实现）

DB (infrastructure/db.py) + HTTP (infrastructure/http_client.py) + LLM (infrastructure/llm_client.py)
```

### 15.4 总结

项目当前处于**数据模型层、基础设施层、流程加载层已完成，上层业务逻辑（引擎、服务、API、仓储等）待实现**的阶段。已实现部分设计清晰、结构完整，为后续上层模块的实现奠定了坚实基础。

---

## 附录：核心类速查表

| 类名 | 文件 | 类型 | 说明 |
|------|------|------|------|
| `Settings` | config/settings.py | 配置 | pydantic-settings 配置类 |
| `MessageType` | domain/messages.py | 枚举 | TEXT / OBJECT |
| `FocusedObject` | domain/messages.py | dataclass | 聚焦对象（订单/商品卡片） |
| `UserMessage` | domain/messages.py | dataclass | 用户消息 |
| `BotMessage` | domain/messages.py | dataclass | 机器人消息 |
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
