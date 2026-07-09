# 电商智能客服系统 Code Wiki

## 目录

1. [项目概述](#1-项目概述)
2. [整体架构](#2-整体架构)
3. [技术栈](#3-技术栈)
4. [模块详细说明](#4-模块详细说明)
5. [核心数据模型](#5-核心数据模型)
6. [流程编排系统](#6-流程编排系统)
7. [对话处理流程](#7-对话处理流程)
8. [依赖关系](#8-依赖关系)
9. [项目配置与运行](#9-项目配置与运行)
10. [设计理念与关键模式](#10-设计理念与关键模式)

---

## 1. 项目概述

### 1.1 项目背景

本项目是一套基于大语言模型（LLM）的电商智能客服系统，旨在用工程化的方式驯服 LLM 的不确定性，保证业务结果稳定可控。系统支持用户用自然语言描述需求，由系统判断意图并路由到相应的处理轨道。

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
├── customer-service-backend/      ← 客服后端（AI 对话引擎）
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
| `DialogueService` | 加载 state → 调引擎 → 保存 state，一次完整对话事务 | `atguigu/services/` |
| `DialogueEngine` | 顶层调度，根据本轮规划走任务/知识/闲聊三条轨道之一 | `atguigu/engine/` |
| `TurnPlanner` | 把上下文喂给 LLM，让它输出结构化"行动计划" | `atguigu/plan/` |
| `TurnPlanValidator` | 校验 LLM 输出，防止幻觉出未注册的 flow / intent | `atguigu/plan/` |
| `ClarifyResponder` | 校验失败时，生成澄清回复反问用户 | `atguigu/clarify/` |
| `TaskHandler` | task 轨道总入口，组织 CommandProcessor 和 FlowExecutor | `atguigu/task/` |
| `FlowExecutor` | YAML 流程图的解释器 | `atguigu/task/` |
| `ActionRunner` | 流程中 action 步骤的执行器，注册表模式 | `atguigu/task/` |
| `KnowledgeHandler` | 知识问答轨道总入口 | `atguigu/knowledge/` |
| `ChitchatHandler` | 闲聊轨道 | `atguigu/chitchat/` |
| `DialogueState` | 聚合根，承载活跃任务、暂停任务栈、聚焦对象、会话历史 | `atguigu/domain/state.py` |
| `DialogueStateRepository` | DialogueState 序列化为 JSON 存到 MySQL 单表 | `atguigu/repository/` |

---

## 3. 技术栈

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

### 3.2 设计特点

- **全异步架构**：`async/await` 一捅到底。LLM 调用是高延迟 I/O（单次 1~5 秒），同步模型并发上不去
- **配置即代码**：业务流程用 YAML 定义，代码只实现通用执行器
- **DDD 分层**：Service 管 I/O，Engine 管计算，状态集中管理

---

## 4. 模块详细说明

### 4.1 目录结构

```
customer-service-backend/
├── atguigu/
│   ├── api/                      ← FastAPI 路由层
│   ├── services/                 ← 应用服务层
│   ├── engine/                   ← 对话引擎
│   ├── plan/                     ← LLM 路由决策
│   ├── clarify/                  ← 校验失败时的澄清兜底
│   ├── task/                     ← 任务流程编排
│   ├── knowledge/                ← 知识问答
│   ├── chitchat/                 ← 闲聊
│   ├── domain/                   ← 领域模型
│   │   ├── contexts.py           ← 上下文模型
│   │   ├── messages.py           ← 消息模型
│   │   └── state.py              ← 对话状态聚合根
│   ├── repository/               ← 仓储层
│   ├── infrastructure/           ← 基础设施
│   │   ├── llm_client.py         ← LangChain LLM 单例
│   │   ├── http_client.py        ← httpx 客户端单例
│   │   └── db.py                 ← SQLAlchemy 异步引擎
│   └── config/
│       └── settings.py           ← pydantic-settings 读取 .env
├── flow_config/                  ← YAML 流程定义
│   ├── user_flows.yml            ← 业务流程
│   └── system_flows.yml          ← 系统流程
└── pyproject.toml
```

### 4.2 config 配置模块

**文件**: [settings.py](file:///workspace/customer-service-backend/atguigu/config/settings.py)

使用 `pydantic-settings` 从 `.env` 文件加载配置，支持类型校验。

**配置项**:

| 配置项 | 类型 | 说明 |
|--------|------|------|
| `llm_model` | `str` | LLM 模型名称（如 qwen-plus） |
| `llm_base_url` | `str` | LLM API 基础地址 |
| `llm_api_key` | `str` | LLM API 密钥 |
| `commerce_api_base_url` | `str` | 电商业务后端 API 地址 |
| `database_url` | `str` | 数据库连接 URL |
| `app_host` | `str` | 应用监听地址 |
| `app_port` | `int` | 应用监听端口 |

### 4.3 infrastructure 基础设施层

#### 4.3.1 LLM 客户端

**文件**: [llm_client.py](file:///workspace/customer-service-backend/atguigu/infrastructure/llm_client.py)

基于 LangChain 的 `init_chat_model()` 初始化 LLM 客户端单例，使用 OpenAI 兼容协议。

**关键配置**:
- `temperature=0`：尽最大努力保证输出稳定性
- `timeout=120`：超时时间 120 秒
- 使用 `openai` 模型 provider 兼容协议

#### 4.3.2 数据库引擎

**文件**: [db.py](file:///workspace/customer-service-backend/atguigu/infrastructure/db.py)

基于 SQLAlchemy 2.0 的异步数据库引擎。

**关键函数**:

| 函数 | 说明 |
|------|------|
| `init_db_engine()` | 初始化异步引擎和 session 工厂 |
| `dispose_engine()` | 释放数据库连接 |

**重要设计**:
- `expire_on_commit=False`：异步环境下提交后不自动过期，避免访问已提交对象时报错
- `echo=True`：控制台打印 SQL 语句，便于调试

#### 4.3.3 HTTP 客户端

**文件**: [http_client.py](file:///workspace/customer-service-backend/atguigu/infrastructure/http_client.py)

基于 httpx 的异步 HTTP 客户端，用于调用电商业务后端接口。

**关键函数**:

| 函数 | 说明 |
|------|------|
| `init_http_client()` | 初始化 HTTP 客户端 |
| `dispose_http_client()` | 关闭 HTTP 客户端 |

### 4.4 domain 领域层

领域层是整个系统的数据核心，包含三大模型：
- **消息模型** (`messages.py`)：用户消息、机器人消息
- **上下文模型** (`contexts.py`)：任务上下文、系统上下文
- **状态模型** (`state.py`)：对话状态聚合根

详见第 5 章「核心数据模型」。

### 4.5 engine 引擎层

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

详见第 7 章「对话处理流程」。

### 4.6 plan 规划层

**目录**: [plan/](file:///workspace/customer-service-backend/atguigu/plan/)

LLM 路由决策层，核心组件是 `TurnPlanner`。

**核心职责**:
- 把用户问题、对话历史、当前状态喂给 LLM
- 让 LLM 输出结构化的「本轮计划」(TurnPlan)
- 由 `TurnPlanValidator` 做白名单校验，防止幻觉

**TurnPlan 包含三类决策**:
- **业务任务命令**：启动/恢复/取消哪个流程、设置哪些槽位
- **知识问答意图**：问哪类知识问题
- **闲聊**：自然回复即可

### 4.7 clarify 澄清层

**目录**: [clarify/](file:///workspace/customer-service-backend/atguigu/clarify/)

当 `TurnPlanValidator` 校验失败时，由 `ClarifyResponder` 生成澄清追问。

**常见需要澄清的情况**:

| 类别 | 包含 | 本质 |
|------|------|------|
| 轨道层面 | `MISSING_TRACK` / `MULTIPLE_TRACKS` | 没选出轨道 / 选了太多轨道 |
| 轨道内容缺失 | `MISSING_TASK_COMMANDS` / `MISSING_KNOWLEDGE_INTENT` | 选对了轨道，但里面是空的 |
| 对象相关 | `MISSING_FOCUSED_OBJECT` / `OBJECT_REQUIRES_INTENT` | 缺对象 / 只有对象没意图 |

### 4.8 task 任务层

**目录**: [task/](file:///workspace/customer-service-backend/atguigu/task/)

任务流程编排层，是三条轨道中最复杂的一条。

**子模块**:

| 子模块 | 作用 |
|--------|------|
| `handler.py` | TaskHandler，task 轨道总入口 |
| `command/` | 4 种命令处理器：start / cancel / resume / set_slots |
| `flow/` | Flow 数据模型 + FlowExecutor 流程执行器 |
| `action/` | Action 注册表 + 内置/自定义动作 |

**命令处理器（CommandProcessor）**:
把 LLM 输出的命令翻译成 `DialogueState` 的变更。支持四种命令：

| 命令 | 作用 |
|------|------|
| `start_task` | 启动新任务（可能打断当前任务） |
| `cancel_task` | 取消当前或挂起的任务 |
| `resume_task` | 恢复挂起的任务 |
| `set_slots` | 填充当前任务的槽位 |

**FlowExecutor（流程执行器）**:
YAML 流程图的解释器，按流程定义一步步推进。支持的 step 类型：
- `start`：流程起点
- `collect`：收集槽位
- `action`：执行动作
- `end`：流程结束

**ActionRunner（动作执行器）**:
注册表模式，执行流程中 `action` 步骤定义的动作。

### 4.9 knowledge 知识层

**目录**: [knowledge/](file:///workspace/customer-service-backend/atguigu/knowledge/)

知识问答轨道，处理不需要走流程的信息咨询类问题。

**子模块**:

| 子模块 | 作用 |
|--------|------|
| `handler.py` | KnowledgeHandler，知识轨道总入口 |
| `intents.py` | KnowledgeIntent 注册表 |
| `providers.py` | FAQ / RAG / 订单 API / 商品 API 等知识源 |
| `registry.py` | KnowledgeProviderRegistry 知识来源注册表 |
| `responder.py` | 知识回复生成器 |

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

### 4.10 chitchat 闲聊层

**目录**: [chitchat/](file:///workspace/customer-service-backend/atguigu/chitchat/)

闲聊兜底轨道，处理既不属于明确任务、也不适合走知识检索的轻量输入。

### 4.11 repository 仓储层

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

### 4.12 api 接口层

**目录**: [api/](file:///workspace/customer-service-backend/atguigu/api/)

FastAPI 路由层，提供 HTTP 接口。

**预期接口**:

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/chat` | POST | 发送消息，获取回复 |
| `/api/chat/history` | GET | 获取对话历史 |

### 4.13 services 服务层

**目录**: [services/](file:///workspace/customer-service-backend/atguigu/services/)

应用服务层，把一次对话处理串起来。

**核心流程**:
1. 从 Repository 加载 `DialogueState`
2. 调用 `DialogueEngine` 处理消息
3. 保存 `DialogueState` 回 Repository
4. 返回机器人回复

> Service 层是事务边界——所有持久化操作集中在这一层，引擎层是纯计算。

---

## 5. 核心数据模型

### 5.1 消息模型 (messages.py)

**文件**: [messages.py](file:///workspace/customer-service-backend/atguigu/domain/messages.py)

#### 5.1.1 MessageType 枚举

```python
class MessageType(Enum):
    TEXT = "text"
    OBJECT = "object"
```

消息分为两种类型：文本消息和对象消息（订单卡片、商品卡片）。

#### 5.1.2 FocusedObject 聚焦对象

```python
@dataclass(slots=True)
class FocusedObject:
    id: str                    # 对象唯一标识
    type: str                  # 对象类型："order" or "product"
    title: str | None = None   # 显示标题
    attributes: dict = field(default_factory=dict)  # 扩展属性
```

用户当前聚焦的业务对象（订单 / 商品）。前端点击卡片后发送对象消息，后端记录下来供后续对话使用。

#### 5.1.3 UserMessage 用户消息

```python
@dataclass(slots=True)
class UserMessage:
    sender_id: str                    # 用户ID
    message_id: str                   # 消息ID
    type: MessageType                 # 消息类型
    text: str | None = None           # 文本内容
    object: FocusedObject | None = None  # 对象内容
```

用户发送的消息，文本和对象二选一（也可能同时存在）。

#### 5.1.4 BotMessage 机器人消息

```python
@dataclass(slots=True)
class BotMessage:
    text: str | None = None           # 文本回复
    object: FocusedObject | None = None  # 对象回复（扩展点）
```

机器人回复的消息。

### 5.2 上下文模型 (contexts.py)

**文件**: [contexts.py](file:///workspace/customer-service-backend/atguigu/domain/contexts.py)

上下文模型分为两类：
- **TaskContext**：业务任务的执行快照（用户想做的事）
- **SystemContext**：系统流程的执行快照（系统插播的过场）

#### 5.2.1 TaskContext 业务任务上下文

```python
@dataclass(slots=True)
class TaskContext:
    flow_id: str                      # 业务流程ID
    step_id: str                      # 当前步骤ID
    slots: dict[str, Any] = field(default_factory=dict)  # 收集到的槽位数据
```

类比成一份正在填的表单：
- `flow_id`：这是哪一种表单（退款单 / 物流单）
- `step_id`：当前填到了哪一格
- `slots`：已经填写好的内容

#### 5.2.2 SystemContext 系统上下文基类

```python
@dataclass(slots=True)
class SystemContext:
    system_flow_id: str               # 系统流程ID
    system_step_id: str               # 系统流程步骤ID
```

系统流程的基类，有 5 个具体子类。`from_dict` 方法通过 `SYSTEM_CONTEXT_TO_CLASS` 查表反序列化为正确的子类。

#### 5.2.3 五个 SystemContext 子类

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
@dataclass(slots=True)
class StartedSystemContext(SystemContext):
    started_flow_id: str     # 新开始的业务流程ID
    started_flow_name: str   # 新开始的业务流程名称

# 任务被打断
@dataclass(slots=True)
class InterruptedSystemContext(SystemContext):
    interrupted_flow_id: str    # 被中断的业务流程ID
    interrupted_flow_name: str  # 被中断的业务流程名称
    started_flow_id: str        # 新开启的业务流程ID
    started_flow_name: str      # 新开启的业务流程名称

# 任务被恢复
@dataclass(slots=True)
class ResumedSystemContext(SystemContext):
    resumed_flow_id: str     # 被恢复的业务流程ID
    resumed_flow_name: str   # 被恢复的业务流程名称

# 任务被取消
@dataclass(slots=True)
class CanceledSystemContext(SystemContext):
    canceled_flow_id: str    # 被取消的业务流程ID
    canceled_flow_name: str  # 被取消的业务流程名称

# 收集槽位
@dataclass(slots=True)
class CollectedSystemContext(SystemContext):
    response: dict[str, Any]  # 展示给用户的提示内容
    slot_name: str            # 要收集的槽位名
```

#### 5.2.4 反序列化映射表

```python
SYSTEM_CONTEXT_TO_CLASS: dict[str, Any] = {
    "system_task_started": StartedSystemContext,
    "system_task_resumed": ResumedSystemContext,
    "system_collect_information": CollectedSystemContext,
    "system_task_interrupted": InterruptedSystemContext,
    "system_task_canceled": CanceledSystemContext
}
```

### 5.3 对话状态模型 (state.py)

**文件**: [state.py](file:///workspace/customer-service-backend/atguigu/domain/state.py)

`DialogueState` 是整个对话状态的**聚合根**，引擎操作的核心对象。

#### 5.3.1 Turn 对话轮次

```python
@dataclass(slots=True)
class Turn:
    turn_id: str                      # 轮次ID
    user_message: UserMessage         # 用户消息
    bot_messages: list[BotMessage]    # 机器人回复列表
```

一次完整的问答交互：用户说一句话，机器人给出多条回复。

#### 5.3.2 Session 会话

```python
@dataclass(slots=True)
class Session:
    session_id: str                   # 会话ID
    started_at: float                 # 开始时间戳
    last_activity_at: float           # 最后活动时间戳
    closed_at: float | None = None    # 关闭时间戳
    turns: list[Turn] = field(default_factory=list)  # 轮次列表
```

一段连续的聊天，超时（默认 60 分钟）后关闭，下次开启新会话。

#### 5.3.3 DialogueState 聚合根

```python
@dataclass(slots=True)
class DialogueState:
    sender_id: str                            # 用户ID
    active_task: TaskContext | None = None   # 当前活跃业务任务
    interrupted_active_tasks: list[TaskContext] = field(default_factory=list)  # 挂起的任务栈
    active_system_task: SystemContext | None = None  # 当前活跃系统流程
    focused_objet: FocusedObject | None = None  # 聚焦的业务对象
    sessions: list[Session] = field(default_factory=list)  # 历史会话
    current_session_id: str | None = None    # 当前活跃会话ID
    pending_turn: Turn | None = None         # 正在处理中的轮次（暂存区）
```

#### 5.3.4 字段分组说明

| 分组 | 字段 | 说明 |
|------|------|------|
| **任务相关** | `active_task` | 当前活跃的业务任务 |
| | `interrupted_active_tasks` | 被挂起的任务列表（栈结构，LIFO） |
| | `active_system_task` | 当前活跃的系统过场 |
| **聚焦对象** | `focused_objet` | 用户当前聚焦的订单/商品 |
| **会话历史** | `sessions` | 历史会话列表 |
| | `current_session_id` | 当前活跃会话 ID |
| **本轮处理** | `pending_turn` | 正在处理中的轮次（暂存区） |

#### 5.3.5 pending_turn 设计

`pending_turn` 是一个重要的设计——处理中的轮次先放在暂存区，处理完成后再通过 `commit_pending_turn()` 提交到会话。

**好处**:
- 处理失败时只要丢掉 `pending_turn` 即可，`turns` 始终干净
- 决定不入库时只要不调用 commit，简单高效
- `turns` 里的每一条 Turn 都是完整的

---

## 6. 流程编排系统

### 6.1 设计理念

业务流程不写在代码里，而是写在 YAML 配置文件里。代码只实现一个通用的「流程执行器」按定义往前推。

**优势**:
- 新增业务流程不需要改代码，只需加一份 YAML
- 非程序员也可以编辑流程定义
- 流程变更不需要重新部署

### 6.2 流程配置文件

| 文件 | 作用 |
|------|------|
| [user_flows.yml](file:///workspace/customer-service-backend/flow_config/user_flows.yml) | 业务流程定义 |
| [system_flows.yml](file:///workspace/customer-service-backend/flow_config/system_flows.yml) | 系统流程定义 |

### 6.3 业务流程 (user_flows.yml)

#### 6.3.1 槽位定义

```yaml
slots:
  order_number:
    type: text
    label: 订单号
    description: 用户的订单号
  order_status:
    type: text
    label: 订单状态
    description: 订单当前状态
  # ...更多槽位
```

#### 6.3.2 已定义的业务流程

| 流程ID | 名称 | 说明 |
|--------|------|------|
| `onboarding` | 欢迎引导 | 初次打开时欢迎用户，介绍助手能力 |
| `order_status_query` | 订单状态查询 | 查询订单处理状态 |
| `logistics_tracking` | 物流查询 | 查询物流进度、单号、配送公司 |
| `refund_request` | 退款申请 | 提交退款申请，收集订单号和原因 |
| `similar_product_recommendation` | 相似商品推荐 | 基于当前商品推荐类似商品 |
| `human_handoff` | 人工客服 | 转交给人工客服 |

#### 6.3.3 流程结构示例

以退款申请为例：

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
        text: "好的，订单{{ slots.order_number }}的退款申请已提交..."
      next: end

    - id: end
      type: end
      next: []
```

### 6.4 系统流程 (system_flows.yml)

| 流程ID | 名称 | 触发时机 |
|--------|------|----------|
| `system_task_started` | task started acknowledgement | 开启新业务任务时 |
| `system_task_resumed` | task resumed acknowledgement | 恢复挂起任务时 |
| `system_collect_information` | collect information | 需要收集槽位时 |
| `system_task_interrupted` | task interrupted acknowledgement | 任务被打断时 |
| `system_task_canceled` | task canceled acknowledgement | 任务被取消时 |
| `system_cannot_handle` | cannot handle request | 无法处理请求时 |

### 6.5 Step 类型

| 类型 | 说明 | 关键字段 |
|------|------|----------|
| `start` | 流程起点 | `next` |
| `collect` | 收集槽位 | `slot_name`, `response`, `next` |
| `action` | 执行动作 | `action`, `args`, `next` |
| `end` | 流程结束 | - |

### 6.6 Action 类型

| Action | 说明 |
|--------|------|
| `action_response` | 生成文本回复（支持模板变量） |
| `action_listen` | 停止执行，等待用户输入 |
| `action_lookup_order_status` | 查询订单状态 |
| `action_lookup_logistics` | 查询物流信息 |
| `action_recommend_similar_products` | 推荐相似商品 |

### 6.7 条件分支

流程支持条件分支，使用 `if/then/else` 语法：

```yaml
- id: start
  type: start
  next:
    - if: "slots.get('product_id')"
      then: respond
    - else: ask_product_id
```

### 6.8 模板变量

回复文本支持 Jinja2 风格的模板变量：

| 变量 | 说明 |
|------|------|
| `{{ slots.xxx }}` | 当前任务的槽位值 |
| `{{ context.xxx }}` | 系统上下文的字段 |
| `{history}` | 对话历史（Prompt 模板中） |
| `{user_message}` | 用户最后一条消息（Prompt 模板中） |

---

## 7. 对话处理流程

### 7.1 一条消息的完整旅程

```
用户发送消息
    ↓
API层接收请求
    ↓
Service层加载DialogueState
    ↓
Engine层处理
    ├─ 1. 准备会话（检查超时）
    ├─ 2. 创建本轮记录（begin_turn）
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

### 7.2 会话准备流程

```
检查当前会话是否存在
    ├─ 不存在 → 创建新会话
    └─ 存在
        ├─ 未超时 → 继续使用
        └─ 已超时 → 关闭旧会话，创建新会话，重置运行时状态
```

**超时重置会清空**:
- `active_task` 当前业务任务
- `interrupted_active_tasks` 暂停任务栈
- `active_system_task` 系统流程
- `focused_objet` 聚焦对象
- `pending_turn` 暂存轮次
- `current_session_id` 当前会话ID

### 7.3 文本消息处理流程

文本消息是最常见的类型，需要 LLM 理解用户意图。

**TurnPlanner 参考的信息**:
- 当前对话（用户问题）
- 最近对话历史（避免只看一句话造成误判）
- `active_task`（判断用户是否在继续上一件事）
- `interrupted_active_tasks`（判断用户是否想回到之前的事）
- `focused_objet`（利用订单或商品上下文）
- `flows`（系统支持哪些业务流程）
- `knowledge_intents`（系统支持哪些知识问答意图）

### 7.4 对象消息处理流程

对象消息通常来自前端点击（订单卡片、商品卡片）。

**处理逻辑**:
1. 把对象写入 `DialogueState.focused_objet`
2. 如果对象能补齐当前任务需要的信息 → 继续业务任务
3. 如果只能知道「用户点了对象」但不知道「想做什么」 → 追问

### 7.5 任务切换机制

系统支持复杂的任务切换，使用**栈结构**管理挂起的任务（LIFO - 后进先出）。

#### 7.5.1 打断（Interrupt）

用户在任务 A 中途切到任务 B：
- A 从 `active_task` 移到 `interrupted_active_tasks` 栈顶
- B 成为新的 `active_task`
- 触发 `InterruptedSystemContext` 过场白

#### 7.5.2 恢复（Resume）

用户要求恢复之前的任务：
- 默认恢复栈顶任务（LIFO）
- 用户明确指名时，按 `flow_id` 精确匹配恢复（可跨过栈顶）
- 触发 `ResumedSystemContext` 过场白

#### 7.5.3 取消（Cancel）

用户取消任务：
- 可以取消当前活跃任务
- 也可以取消挂起栈里的某个任务
- 被取消的任务直接丢弃（不进栈）
- 触发 `CanceledSystemContext` 过场白

#### 7.5.4 连环打断示例

```
用户: 查订单状态          → active_task = 订单状态查询
用户: 先查物流            → 订单状态查询进栈，active_task = 物流查询
用户: 我要退款            → 物流查询进栈，active_task = 退款申请
用户: (退款完成)          → active_task = 空
用户: 继续刚才的          → 恢复栈顶（物流查询）
```

栈变化：`[] → [订单状态查询] → [订单状态查询, 物流查询] → [订单状态查询, 物流查询] → [订单状态查询]`

### 7.6 校验与澄清机制

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

## 8. 依赖关系

### 8.1 Python 依赖

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

### 8.2 外部服务依赖

| 服务 | 用途 | 配置项 |
|------|------|--------|
| **LLM API** | 大语言模型推理 | `llm_base_url`, `llm_api_key`, `llm_model` |
| **MySQL 数据库** | 对话状态持久化 | `database_url` |
| **电商业务后端** | 订单/物流/商品数据查询 | `commerce_api_base_url` |

### 8.3 内部模块依赖图

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

**依赖方向规则**:
- 上层依赖下层，下层不依赖上层
- 所有层都可以依赖 domain 层（数据模型）和 infrastructure 层（基础设施）
- domain 层不依赖任何其他层

---

## 9. 项目配置与运行

### 9.1 环境要求

- Python >= 3.12
- MySQL 数据库
- 可用的 LLM API（通义千问兼容 OpenAI 协议）
- 电商业务后端服务

### 9.2 配置文件

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

### 9.3 依赖安装

项目使用 `uv` 作为 Python 包管理器：

```bash
cd customer-service-backend
uv sync
```

### 9.4 数据库初始化

需要创建 `customer_service` 数据库和 `dialogue_states` 表：

```sql
CREATE DATABASE customer_service CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

USE customer_service;

CREATE TABLE dialogue_states (
    sender_id VARCHAR(255) PRIMARY KEY,
    state_json TEXT
);
```

### 9.5 启动顺序

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

### 9.6 验证安装

各模块都提供了 `__main__` 测试入口：

```bash
# 测试 LLM 连接
uv run python -m atguigu.infrastructure.llm_client

# 测试数据库连接
uv run python -m atguigu.infrastructure.db

# 测试 HTTP 客户端
uv run python -m atguigu.infrastructure.http_client

# 测试配置加载
uv run python -m atguigu.config.settings
```

---

## 10. 设计理念与关键模式

### 10.1 五大设计原则

1. **三条轨道分离** —— 任务、知识、闲聊各走各的代码路径，互不污染
2. **LLM 路由 + 白名单校验 + 澄清兜底** —— 永远不"裸用" LLM 的输出，留有兜底
3. **YAML 描述流程，代码执行流程** —— 可枚举的业务逻辑从 LLM 手里拿出来，交给状态机
4. **DialogueState 集中状态，Engine 集中计算** —— 状态读写在边缘（Service），计算在中心（Engine）
5. **业务隔离** —— AI 客服永远以"业务消费者"身份调电商接口，不直连业务数据库

### 10.2 关键设计模式

| 模式 | 应用位置 | 作用 |
|------|----------|------|
| **聚合根模式** | `DialogueState` | 集中管理所有对话状态，保证一致性 |
| **注册表模式** | Action、KnowledgeProvider | 灵活扩展，新增能力不改动核心代码 |
| **策略模式** | 三条轨道处理 | 不同轨道不同处理策略 |
| **状态机模式** | FlowExecutor | YAML 定义的有限状态机驱动流程推进 |
| **两步提交** | pending_turn | 处理中与已提交分离，保证数据完整性 |
| **模板方法** | SystemContext 子类 | 基类定义序列化接口，子类实现具体数据 |

### 10.3 DDD 思想应用

- **事务脚本 + 充血模型**：Service 层是事务脚本（管 I/O），Engine 层是纯计算（管逻辑）
- **仓储模式**：Repository 封装持久化细节，领域层不关心存储
- **领域模型与基础设施分离**：domain 层纯数据和业务规则，infrastructure 层管外部依赖

### 10.4 工程化驯服 LLM 的手段

1. **结构化输出**：让 LLM 输出 JSON 而不是自由文本
2. **白名单校验**：对 LLM 输出做 schema 校验 + 业务白名单校验
3. **澄清兜底**：校验不通过时，用 LLM 生成追问而不是硬执行
4. **流程编排**：确定性逻辑用 YAML 状态机，不让 LLM 直接控制流程
5. **任务栈管理**：多任务切换用栈结构，LIFO 语义符合人类直觉

---

## 附录：代码实现进度

根据当前仓库状态，各模块实现进度如下：

| 模块 | 状态 | 说明 |
|------|------|------|
| **config** | ✅ 已实现 | settings.py 完整实现 |
| **domain** | ✅ 已实现 | messages.py、contexts.py、state.py 全部实现 |
| **infrastructure** | ✅ 已实现 | llm_client.py、db.py、http_client.py 全部实现 |
| **flow_config** | ✅ 已实现 | user_flows.yml、system_flows.yml 完整定义 |
| **api** | ⚠️ 待实现 | 目录存在，仅有注释 |
| **services** | ⚠️ 待实现 | 目录存在，仅有注释 |
| **engine** | ⚠️ 待实现 | 目录存在，仅有注释 |
| **plan** | ⚠️ 待实现 | 目录存在，仅有注释 |
| **clarify** | ⚠️ 待实现 | 目录存在，仅有注释 |
| **task** | ⚠️ 待实现 | 目录存在，仅有注释 |
| **knowledge** | ⚠️ 待实现 | 目录存在，仅有注释 |
| **chitchat** | ⚠️ 待实现 | 目录存在，仅有注释 |
| **repository** | ⚠️ 待实现 | 目录存在，仅有注释 |

> 项目当前处于数据模型和基础设施层已完成、上层业务逻辑待实现的阶段。
