# 电商智能客服系统 Code Wiki

> 基于仓库实际代码编写，完整反映项目架构、模块职责、关键实现及运行方式。

---

## 目录

1. [项目概述](#1-项目概述)
2. [整体架构](#2-整体架构)
3. [技术栈与依赖](#3-技术栈与依赖)
4. [项目结构](#4-项目结构)
5. [后端核心模块详解](#5-后端核心模块详解)
   - [5.1 配置模块](#51-配置模块-config)
   - [5.2 基础设施层](#52-基础设施层-infrastructure)
   - [5.3 领域模型层](#53-领域模型层-domain)
   - [5.4 ORM 模型层](#54-orm-模型层-model)
   - [5.5 仓储层](#55-仓储层-repository)
   - [5.6 流程编排系统](#56-流程编排系统-task)
   - [5.7 命令系统](#57-命令系统-taskcommand)
   - [5.8 动作系统](#58-动作系统-taskaction)
   - [5.9 对话历史构建器](#59-对话历史构建器-history)
   - [5.10 Prompt 提示词模块](#510-prompt-提示词模块-prompts)
   - [5.11 对话规划器](#511-对话规划器-plan)
   - [5.12 意图澄清器](#512-意图澄清器-clarify)
   - [5.13 知识检索轨道](#513-知识检索轨道-knowledge)
   - [5.14 闲聊轨道](#514-闲聊轨道-chitchat)
   - [5.15 任务处理轨道](#515-任务处理轨道-task-handler)
   - [5.16 对话引擎](#516-对话引擎-engine)
   - [5.17 引擎构建器](#517-引擎构建器-engine-builder)
   - [5.18 服务层](#518-服务层-services)
   - [5.19 API 接口层](#519-api-接口层-api)
6. [前端应用](#6-前端应用)
7. [对话处理完整流程](#7-对话处理完整流程)
8. [API 接口设计](#8-api-接口设计)
9. [项目配置与运行](#9-项目配置与运行)
10. [设计理念与关键模式](#10-设计理念与关键模式)
11. [实现进度总览](#11-实现进度总览)
12. [附录：核心类速查表](#12-附录核心类速查表)

---

## 1. 项目概述

### 1.1 项目背景

本项目是一套基于大语言模型（LLM）的**电商智能客服系统**，支持用户用自然语言描述需求，由系统判断意图并路由到相应的处理轨道。

**项目组成**：
- **customer-service-backend**：AI 客服后端（FastAPI + LangChain），承担所有对话与 LLM 调用
- **customer-service-frontend**：前端聊天界面（Vue 3 + Vite），集成数字人交互

**核心理念**：AI 客服不直接读电商数据库，而是以"业务系统消费者"的身份调用中台/电商后端的 HTTP 接口，实现业务隔离。

### 1.2 系统能力

系统设计支持三条处理轨道，三者互斥：

| 轨道 | 说明 | 示例场景 |
|------|------|----------|
| **任务流程（Task）** | 步骤明确、可按步骤推进的业务 | 查订单状态、查物流、申请退款 |
| **信息检索（Knowledge）** | 知识性问答，不需要走流程 | 商品信息、退款政策、退货政策 |
| **闲聊（Chitchat）** | 轻量交互兜底 | "你好"、"你挺聪明的" |

### 1.3 技术亮点

- **YAML 驱动的流程编排**：业务流程从代码中抽离，非程序员可编辑
- **LLM 路由 + 白名单校验 + 澄清兜底**：永远不"裸用"LLM 输出
- **聚合根模式**：DialogueState 集中管理所有对话状态
- **两步提交设计**：pending_turn 保证数据完整性
- **命令模式**：LLM 输出转为 Command，由 CommandProcessor 统一处理
- **Action 注册/发现机制**：内置 Action + 自定义 Action 自动扫描注册
- **业务隔离**：AI 客服以消费者身份调用中台接口

---

## 2. 整体架构

### 2.1 两层服务架构

```
┌─────────────────────────────────────────────────────────┐
│  前端层 (customer-service-frontend)                      │
│  Vue 3 + Vite + 数字人 SDK (lm-avatar-chat-sdk)          │
│  聊天界面、卡片交互、WebSocket 实时通信                    │
└────────────────────┬────────────────────────────────────┘
                     │ HTTP/WebSocket
                     ↓
┌─────────────────────────────────────────────────────────┐
│  AI 客服层 (customer-service-backend)                    │
│  FastAPI + LangChain + SQLAlchemy                        │
│  对话引擎、TurnPlanner、流程编排、LLM 调用、状态管理        │
│           │
│           │ HTTP (httpx)
│           ↓
│  中台/电商后端 (Commerce API)                             │
│  订单、物流、商品数据查询接口                               │
└─────────────────────────────────────────────────────────┘
```

### 2.2 AI 客服后端分层架构

```
┌──────────────────────────────────────────────┐
│  API 层 (api/)                                │
│  FastAPI 路由、请求/响应 Schema、依赖注入       │
├──────────────────────────────────────────────┤
│  Service 层 (services/)                       │
│  加载状态 → 调引擎 → 保存状态，一次完整对话事务  │
├──────────────────────────────────────────────┤
│  Engine 层 (engine/)                          │
│  顶层调度，判断消息类型，路由到三条处理轨道       │
├──────────────────────────────────────────────┤
│  Plan / Clarify / Task / Knowledge / Chitchat │
│  各轨道的具体处理逻辑                          │
│  ├─ plan/         TurnPlanner + Validator     │
│  ├─ clarify/      ClarifyResponser            │
│  ├─ task/         流程编排 + 命令处理 + 动作执行 │
│  ├─ knowledge/    KnowledgeHandler             │
│  └─ chitchat/     ChitChatHandler              │
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

---

## 3. 技术栈与依赖

### 3.1 后端技术栈

| 技术 | 版本要求 | 作用 |
|------|----------|------|
| **FastAPI** | >=0.136.0 | Web 框架 |
| **Uvicorn** | >=0.44.0 | ASGI 服务器 |
| **LangChain** | >=1.2.15 | LLM 编排框架 |
| **langchain-openai** | >=1.1.14 | LangChain OpenAI 兼容适配器 |
| **Pydantic / pydantic-settings** | >=2.13.1 | 数据校验与配置加载 |
| **Jinja2** | >=3.1.6 | Prompt 模板渲染 |
| **SQLAlchemy** | >=2.0.49 | ORM 框架 |
| **aiomysql** | >=0.3.2 | 异步 MySQL 驱动 |
| **httpx** | >=0.28.1 | 异步 HTTP 客户端 |
| **PyYAML** | >=6.0.3 | YAML 流程配置解析 |
| **dashscope** | - | 阿里达摩院灵积模型服务 |
| **alibabacloud-lingmou** | >=1.0.0 | 阿里云灵摹（数字人）SDK |
| **cryptography** | >=46.0.7 | 加密库（MySQL 连接需要） |

### 3.2 前端技术栈

| 技术 | 作用 |
|------|------|
| **Vue 3** (Composition API) | 前端框架 |
| **Vite** >=6.2.0 | 构建工具 |
| **lm-avatar-chat-sdk** >=1.1.2 | 数字人交互 SDK |
| **WebSocket** | 实时语音/文本通信 |

---

## 4. 项目结构

```
workspace/
├── customer-service-backend/          ← AI 客服后端（核心）
│   ├── atguigu/
│   │   ├── __init__.py
│   │   ├── main.py                    ← 应用启动入口
│   │   │
│   │   ├── api/                       ← FastAPI 路由层
│   │   │   ├── __init__.py
│   │   │   ├── app.py                 ← FastAPI 应用实例 + lifespan
│   │   │   ├── dependencies.py        ← 依赖注入链
│   │   │   ├── schemas.py             ← 接口层 Pydantic 模型
│   │   │   └── router/
│   │   │       ├── __init__.py
│   │   │       └── chat_router.py     ← 聊天接口路由
│   │   │
│   │   ├── config/                    ← 配置模块
│   │   │   ├── __init__.py
│   │   │   └── settings.py            ← pydantic-settings 读取 .env
│   │   │
│   │   ├── domain/                    ← 领域模型层
│   │   │   ├── __init__.py
│   │   │   ├── contexts.py            ← 上下文模型（TaskContext + SystemContext 子类）
│   │   │   ├── messages.py            ← 消息模型（UserMessage, BotMessage, ProcessResult）
│   │   │   └── state.py               ← 对话状态聚合根（DialogueState, Session, Turn）
│   │   │
│   │   ├── engine/                    ← 对话引擎
│   │   │   ├── __init__.py
│   │   │   ├── builder.py             ← 引擎构建器（build_dialogue_engine）
│   │   │   └── dialogue_engine.py     ← DialogueEngine 核心调度
│   │   │
│   │   ├── infrastructure/            ← 基础设施层
│   │   │   ├── __init__.py
│   │   │   ├── db.py                  ← SQLAlchemy 异步引擎
│   │   │   ├── http_client.py         ← httpx 异步客户端
│   │   │   └── llm_client.py          ← LangChain LLM 客户端
│   │   │
│   │   ├── model/                     ← SQLAlchemy ORM 模型
│   │   │   ├── __init__.py
│   │   │   ├── base.py                ← DeclarativeBase 基类
│   │   │   └── state_record.py        ← DialogueStateRecord 表映射
│   │   │
│   │   ├── repository/                ← 仓储层
│   │   │   ├── __init__.py
│   │   │   └── dialogue_repository.py ← DialogueRepository
│   │   │
│   │   ├── services/                  ← 应用服务层
│   │   │   ├── __init__.py
│   │   │   └── dialogue_service.py    ← DialogueService
│   │   │
│   │   ├── history/                   ← 对话历史构建器
│   │   │   ├── __init__.py
│   │   │   └── builder.py             ← ChatHistoryBuilder
│   │   │
│   │   ├── prompts/                   ← Prompt 提示词模块
│   │   │   ├── __init__.py
│   │   │   ├── loader.py              ← 提示词模板加载器
│   │   │   └── jinja2/
│   │   │       ├── turn_plan.jinja2   ← TurnPlanner 提示词模板
│   │   │       └── clarify_respond.jinja2 ← 澄清响应提示词模板
│   │   │
│   │   ├── plan/                      ← 对话规划器
│   │   │   ├── __init__.py
│   │   │   ├── planner.py             ← TurnPlanner（LLM 路由决策）
│   │   │   ├── turn_plan.py           ← TurnPlan 数据模型 + ClarifyReason
│   │   │   └── validator.py           ← TurnPlanValidator（白名单校验）
│   │   │
│   │   ├── clarify/                   ← 意图澄清
│   │   │   ├── __init__.py
│   │   │   └── responder.py           ← ClarifyResponser（澄清兜底）
│   │   │
│   │   ├── knowledge/                 ← 知识检索轨道
│   │   │   ├── __init__.py
│   │   │   ├── handler.py             ← KnowledgeHandler
│   │   │   └── intents.py             ← 知识意图清单（KNOWLEDGE_INTENTS）
│   │   │
│   │   ├── chitchat/                  ← 闲聊轨道
│   │   │   ├── __init__.py
│   │   │   └── handler.py             ← ChitChatHandler
│   │   │
│   │   └── task/                      ← 任务流程编排层
│   │       ├── __init__.py
│   │       ├── handler.py             ← TaskHandler（任务轨道总入口）
│   │       ├── loader.py              ← FlowLoader（YAML 流程加载器）
│   │       ├── system_flows.yml       ← 系统流程定义（副本）
│   │       ├── user_flows.yml         ← 业务流程定义（副本）
│   │       │
│   │       ├── flow/                  ← 流程数据模型
│   │       │   ├── __init__.py
│   │       │   ├── flows.py           ← Flow / FlowSlot / FlowsList
│   │       │   ├── links.py           ← FlowStepLink 边模型
│   │       │   ├── steps.py           ← FlowStep 步骤模型
│   │       │   ├── executor.py        ← FlowExecutor（流程执行器，stub）
│   │       │   └── loader.py          ← FlowLoader（流程加载器）
│   │       │
│   │       ├── command/               ← 命令系统
│   │       │   ├── __init__.py
│   │       │   ├── commands.py        ← Command 及 4 个子类
│   │       │   └── processor.py       ← CommandProcessor（命令处理器）
│   │       │
│   │       └── action/                ← 动作系统
│   │           ├── __init__.py
│   │           ├── base.py            ← Action 基类 / ActionResult / ActionCall
│   │           ├── register.py        ← ActionRegister（动作注册中心）
│   │           ├── runner.py          ← ActionRunner（动作执行器）
│   │           ├── builder.py         ← 动作构建器（自动扫描注册）
│   │           ├── builtin/           ← 内置动作
│   │           │   ├── __init__.py
│   │           │   ├── listener.py    ← ActionListener（action_listen）
│   │           │   └── response.py    ← ActionResponse（action_response）
│   │           └── customer/          ← 自定义业务动作
│   │               ├── __init__.py
│   │               ├── lookup_order_status.py    ← 查询订单状态
│   │               ├── lookup_logistics.py        ← 查询物流
│   │               └── recommend_similar_products.py ← 推荐相似商品
│   │
│   ├── flow_config/                   ← YAML 流程定义（权威副本）
│   │   ├── system_flows.yml
│   │   └── user_flows.yml
│   ├── pyproject.toml
│   └── uv.lock
│
└── customer-service-frontend/         ← 前端应用
    ├── src/
    │   ├── main.js                    ← Vue 应用入口
    │   ├── App.vue                    ← 主组件（聊天界面 + 数字人）
    │   └── assets/
    │       └── logo.webp
    ├── index.html
    ├── package.json
    └── dist/                          ← 构建产物
```

---

## 5. 后端核心模块详解

### 5.1 配置模块 (config)

**文件**: [settings.py](file:///workspace/customer-service-backend/atguigu/config/settings.py)

使用 `pydantic-settings` 的 `BaseSettings` 从 `.env` 文件加载配置，所有字段必填（缺失则启动期 `ValidationError`）。

| 字段 | 类型 | 说明 | 示例值 |
|--------|------|------|--------|
| `llm_model` | `str` | LLM 模型名称 | `qwen-plus` |
| `llm_base_url` | `str` | LLM API 基础地址 | `https://dashscope.aliyuncs.com/compatible-mode/v1` |
| `llm_api_key` | `str` | LLM API 密钥 | `sk-xxxx` |
| `commerce_api_base_url` | `str` | 中台电商 API 地址 | `http://192.168.200.125:18081` |
| `database_url` | `str` | 数据库连接 URL | `mysql+aiomysql://root:root@localhost:3306/customer_service?charset=utf8mb4` |
| `app_host` | `str` | 应用监听地址 | `0.0.0.0` |
| `app_port` | `int` | 应用监听端口 | `18082` |

---

### 5.2 基础设施层 (infrastructure)

#### LLM 客户端

**文件**: [llm_client.py](file:///workspace/customer-service-backend/atguigu/infrastructure/llm_client.py)

基于 LangChain 1.x 的 `init_chat_model()` 创建 LLM 客户端模块级单例，使用 OpenAI 兼容协议接入 DashScope（通义千问）。

```python
llm_client: BaseChatModel = init_chat_model(
    model=settings.llm_model,
    model_provider="openai",
    base_url=settings.llm_base_url,
    api_key=settings.llm_api_key,
    temperature=0,      # 保证输出稳定性
    timeout=120         # 120 秒超时
)
```

#### 数据库引擎

**文件**: [db.py](file:///workspace/customer-service-backend/atguigu/infrastructure/db.py)

基于 SQLAlchemy 2.0 的异步数据库引擎与 session 工厂。使用「全局变量 + init/dispose 生命周期函数」模式，由 FastAPI lifespan 统一管理。

| 函数 | 说明 |
|------|------|
| `init_db_engine()` | 初始化异步引擎和 session 工厂 |
| `dispose_engine()` | 释放数据库连接 |

关键配置：`expire_on_commit=False`（异步环境下必要），`echo=True`（打印 SQL）。

#### HTTP 客户端

**文件**: [http_client.py](file:///workspace/customer-service-backend/atguigu/infrastructure/http_client.py)

基于 httpx 的异步 HTTP 客户端单例，用于调用中台电商后端接口。参数：`timeout=120`，`trust_env=False`。

---

### 5.3 领域模型层 (domain)

所有领域模型使用 `@dataclass(slots=True)` 定义，访问速度快、内存占用小。

#### 5.3.1 消息模型

**文件**: [messages.py](file:///workspace/customer-service-backend/atguigu/domain/messages.py)

| 类 | 说明 | 关键字段 |
|------|------|----------|
| `MessageType` (Enum) | 消息类型 | `TEXT`, `OBJECT` |
| `FocusedObject` | 聚焦的业务对象（订单/商品卡片） | `id`, `type`, `title`, `attributes` |
| `UserMessage` | 用户消息 | `sender_id`, `message_id`, `type`, `text`, `object` |
| `BotMessage` | 机器人回复 | `text`, `object` |
| `ProcessResult` | 引擎处理结果 | `sender_id`, `message_id`, `messages: list[BotMessage]` |

#### 5.3.2 上下文模型

**文件**: [contexts.py](file:///workspace/customer-service-backend/atguigu/domain/contexts.py)

分为两类：
- **TaskContext**：业务任务的执行快照（用户想做的事）
- **SystemContext**：系统流程的执行快照（系统插播的过场）

| 类 | 触发时机 | 关键字段 |
|------|----------|----------|
| `TaskContext` | 业务流程激活 | `flow_id`, `step_id`, `slots` |
| `StartedSystemContext` | 开启新业务任务 | `started_flow_id`, `started_flow_name` |
| `InterruptedSystemContext` | A 任务中切到 B 任务 | `interrupted_flow_id/name`, `started_flow_id/name` |
| `CanceledSystemContext` | 用户取消当前任务 | `canceled_flow_id`, `canceled_flow_name` |
| `ResumedSystemContext` | 恢复挂起的任务 | `resumed_flow_id`, `resumed_flow_name` |
| `CollectedSystemContext` | 业务流程跑到 collect 步骤 | `response: dict`, `slot_name: str` |

通过 `SYSTEM_CONTEXT_TO_CLASS` 字典实现 `from_dict()` 多态分发。

#### 5.3.3 对话状态聚合根

**文件**: [state.py](file:///workspace/customer-service-backend/atguigu/domain/state.py)

`DialogueState` 是整个对话状态的**聚合根**，引擎操作的核心对象。

```
DialogueState (聚合根)
├─ sender_id: str                          # 用户ID
├─ active_task: TaskContext | None         # 当前活跃业务任务
├─ interrupted_active_tasks: list[TaskContext]  # 挂起的任务栈（LIFO）
├─ active_system_task: SystemContext | None     # 当前活跃系统流程
├─ focused_object: FocusedObject | None         # 聚焦的业务对象
├─ sessions: list[Session]                      # 历史会话
│   ├─ session_id, started_at, last_activity_at, closed_at
│   └─ turns: list[Turn]
│       ├─ turn_id
│       ├─ user_message: UserMessage
│       └─ bot_messages: list[BotMessage]
├─ current_session_id: str | None               # 当前活跃会话ID
└─ pending_turn: Turn | None                    # 正在处理中的轮次（暂存区）
```

**关键方法分类**：

| 分类 | 方法 | 说明 |
|------|------|------|
| 流程管理 | `start_active_system_task()`, `end_activating_system_task()` | 系统流程启停 |
| | `start_active_business_task()`, `end_activating_business_task()` | 业务流程启停 |
| | `interrupted_activating_task()` | 将当前业务流程压入栈 |
| | `resumed_interrupted_business_task(flow_id)` | 从栈中恢复任务（LIFO 或精确匹配） |
| | `current_activating_task()` | 返回当前活跃流程，**系统流程优先** |
| 槽位管理 | `set_slots(slots)`, `get_slot(slot_name)` | 读写 active_task.slots |
| 会话管理 | `current_session()`, `start_session()`, `close_session()` | 60 分钟超时机制 |
| | `reset_running_state_for_new_session()` | 超时时清空所有任务/卡片/pending_turn |
| 轮次管理 | `start_turn(user_message)`, `commit_pending_turn()` | 两步提交 |

**pending_turn 两步提交设计**：处理中的轮次先放在暂存区，处理完成后提交到会话。处理失败时只需丢弃 pending_turn，turns 列表始终干净。

---

### 5.4 ORM 模型层 (model)

**文件**: [base.py](file:///workspace/customer-service-backend/atguigu/model/base.py), [state_record.py](file:///workspace/customer-service-backend/atguigu/model/state_record.py)

```python
class Base(DeclarativeBase):
    pass

class DialogueStateRecord(Base):
    __tablename__ = 'dialogue_states'
    sender_id: Mapped[str] = mapped_column(primary_key=True)
    state_json: Mapped[str] = mapped_column(TEXT, nullable=False, default={})
```

整份 `DialogueState` 序列化为 JSON 字符串存入单表，不拆多表，调试直观。

---

### 5.5 仓储层 (repository)

**文件**: [dialogue_repository.py](file:///workspace/customer-service-backend/atguigu/repository/dialogue_repository.py)

| 方法 | 说明 |
|------|------|
| `load_dialogue(sender_id) -> DialogueState` | 根据 sender_id 查询，不存在则返回 `DialogueState(sender_id=sender_id)` |
| `save_dialogue(dialogue_state)` | 保存，使用 MySQL `INSERT ... ON DUPLICATE KEY UPDATE` 实现 upsert |

---

### 5.6 流程编排系统 (task)

#### 设计理念

业务流程不写在代码里，而是写在 YAML 配置文件里。代码实现通用的「流程加载器」和「流程执行器」按定义推进。

#### 流程数据模型

**文件**: [flows.py](file:///workspace/customer-service-backend/atguigu/task/flow/flows.py)

| 类 | 说明 |
|------|------|
| `FlowSlot` | 槽位定义：`name`, `type`, `label`, `description` |
| `Flow` | 流程定义：`flow_id`, `flow_name`, `description`, `steps`, `slots` |
| `FlowsList` | 多 YAML 合并结果：`flows: list[Flow]`, `slots: dict[str, FlowSlot]` |

`Flow.description` 字段是关键——提供给 LLM 用于根据用户任务选择要开启哪个业务流程。

#### 步骤模型

**文件**: [steps.py](file:///workspace/customer-service-backend/atguigu/task/flow/steps.py)

| 步骤类型 | 枚举值 | 说明 | 特有字段 |
|----------|--------|------|----------|
| `StartFlowStep` | `start` | 流程起点 | 无 |
| `EndFlowStep` | `end` | 流程结束 | 无 |
| `ActionFlowStep` | `action` | 执行动作 | `action: str`, `args: dict` |
| `CollectFlowStep` | `collect` | 收集槽位（仅业务流程） | `slot_name`, `response`, `validate` |

三种 action 动作名称：
- `action_listen`：暂停执行，把控制权交给用户（仅系统流程使用）
- `action_response`：告诉用户信息（开场白、槽位提示、查询结果）
- `action_xxx`：调用外部接口获取数据（仅业务流程使用）

`FlowStep.from_dict()` 通过 `FLOW_STEP_TYPE_TO_CLASS` 查找表实现多态分发。`build_links()` 将 YAML 的 `next` 字段解析为 `StaticLink` / `ConditionLink` / `FallbackLink`。

#### 边模型

**文件**: [links.py](file:///workspace/customer-service-backend/atguigu/task/flow/links.py)

| 类 | 说明 | YAML 示例 |
|------|------|-----------|
| `FlowStepStaticLink` | 静态非条件边 | `next: ask_refund_reason` |
| `FlowStepConditionLink` | 条件边（if/then） | `if: "slots.get('product_id')" then: respond` |
| `FlowStepFallbackLink` | 兜底 else 边 | `else: ask_rephrase` |

#### 流程加载器

**文件**: [loader.py](file:///workspace/customer-service-backend/atguigu/task/flow/loader.py)（位于 `task/flow/`）

`FlowLoader` 负责将 YAML 配置文件解析为内存中的 `FlowsList` 对象树。

| 方法 | 说明 |
|------|------|
| `load_many_yaml(paths) -> FlowsList` | 加载多份 YAML 并合并 |
| `load_yaml(path) -> FlowsList` | 加载单份 YAML |
| `load_slots(slots) -> dict[str, FlowSlot]` | 解析槽位定义 |
| `load_flows(flows, loaded_slots) -> list[Flow]` | 解析流程定义，关联槽位 |

#### YAML 流程定义

**文件**: [flow_config/system_flows.yml](file:///workspace/customer-service-backend/flow_config/system_flows.yml), [flow_config/user_flows.yml](file:///workspace/customer-service-backend/flow_config/user_flows.yml)

##### 业务流程（6 个）

| 流程ID | 名称 | 步骤概览 |
|--------|------|----------|
| `onboarding` | 欢迎引导 | start → respond(action_response) → end |
| `order_status_query` | 订单状态查询 | start → ask_order_number(collect) → lookup_order_status(action) → show_order_status(action_response) → end |
| `logistics_tracking` | 物流查询 | start → ask_order_number(collect) → lookup_logistics(action) → show_logistics(action_response) → end |
| `refund_request` | 退款申请 | start → ask_order_number(collect) → ask_refund_reason(collect) → refund_submitted(action_response) → end |
| `similar_product_recommendation` | 相似商品推荐 | start → 条件分支 → ask_product_id(collect) → respond(action) → end |
| `human_handoff` | 人工客服 | start → respond(action_response) → end |

##### 系统流程（6 个）

| 流程ID | 名称 | 触发时机 |
|--------|------|----------|
| `system_task_started` | 任务开始确认 | 开启新业务任务时 |
| `system_task_resumed` | 任务恢复确认 | 恢复挂起任务时 |
| `system_collect_information` | 收集信息 | 需要收集槽位时（含 action_listen 暂停） |
| `system_task_interrupted` | 任务中断确认 | 任务被打断时 |
| `system_task_canceled` | 任务取消确认 | 任务被取消时 |
| `system_cannot_handle` | 无法处理 | 澄清/不支持/无答案/要求重述 |

##### 槽位定义（8 个）

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

##### 模板变量

| 变量 | 说明 | 使用场景 |
|------|------|----------|
| `{{ slots.xxx }}` | 当前任务的槽位值 | 业务流程的 action_response |
| `{{ context.xxx }}` | 系统上下文的字段 | 系统流程的 action_response |
| `{history}` | 对话历史 | rephrase 模式的 prompt |
| `{user_message}` | 用户最后一条消息 | rephrase 模式的 prompt |
| `{current_response}` | 建议回复 | rephrase 模式的 prompt |

---

### 5.7 命令系统 (task/command)

**文件**: [commands.py](file:///workspace/customer-service-backend/atguigu/task/command/commands.py)

LLM 输出的规划结果被转换为 Command 对象，由 `CommandProcessor` 统一处理。

| 命令类 | `command` 字段 | 说明 |
|--------|---------------|------|
| `StartedFlowCommand` | `start_flow` | 开启指定业务流程 |
| `ResumedFlowCommand` | `resume_flow` | 恢复中断的业务流程（可选指定 flow） |
| `CancelFlowCommand` | `cancel_flow` | 取消当前业务流程 |
| `SetSlotsCommand` | `set_slots` | 设置槽位值 |

通过 `COMMAND_TO_CLASS` 字典实现 `from_dict()` 多态分发。

**文件**: [processor.py](file:///workspace/customer-service-backend/atguigu/task/command/processor.py)

`CommandProcessor` 是命令处理的核心，负责根据命令类型修改 `DialogueState`：

| 方法 | 处理逻辑 |
|------|----------|
| `_process_start_flow()` | 激活指定业务流程 + 激活开始系统流程。如有活跃任务则中断（压栈）并激活中断系统流程 |
| `_process_slots_fill()` | 将 command.slots 合并到 `state.active_task.slots` |
| `_process_cancel_flow()` | 激活取消系统流程，清空所有流程 |
| `_process_resume_flow()` | 从栈中恢复指定或最近的中断任务，激活恢复/中断系统流程 |

**设计要点**：
- 中断栈采用 LIFO 策略
- 支持按 flow_id 精确恢复
- 同一流程重复开启时不做任何操作（幂等）
- 任务切换时会自动激活对应的系统过场流程

---

### 5.8 动作系统 (task/action)

#### 核心组件

**文件**: [base.py](file:///workspace/customer-service-backend/atguigu/task/action/base.py)

| 类 | 说明 |
|------|------|
| `Action` (ABC) | 动作抽象基类，定义 `name` 属性和 `run(state, action_args) -> ActionResult` 抽象方法 |
| `ActionResult` | 动作执行结果：`messages: list[BotMessage]`, `slot_updates: dict` |
| `ActionCall` | 动作调用描述：`action_name`, `action_kwargs` |

**文件**: [register.py](file:///workspace/customer-service-backend/atguigu/task/action/register.py)

`ActionRegister` 动作注册中心，提供 `register(action)` 和 `get(name) -> Action`。

**文件**: [runner.py](file:///workspace/customer-service-backend/atguigu/task/action/runner.py)

`ActionRunner` 动作执行器，根据 `ActionCall` 的 `action_name` 从注册中心取 Action 并调用 `run()`。

**文件**: [builder.py](file:///workspace/customer-service-backend/atguigu/task/action/builder.py)

`build_action_runner()` 构建函数，自动注册内置 Action 和扫描 `customer/` 包下所有 Action 子类。

#### 内置动作

| 类 | `name` | 说明 |
|------|--------|------|
| `ActionListener` | `action_listen` | 暂停执行，等待用户输入 |
| `ActionResponse` | `action_response` | 生成回复模板渲染 |

#### 自定义业务动作

| 类 | `name` | 预期功能 |
|------|--------|----------|
| `LookupOrderStatusAction` | `action_lookup_order_status` | 调用中台查询订单状态 |
| `LookupLogisticsAction` | `action_lookup_logistics` | 调用中台查询物流信息 |
| `RecommendSimilarProductsAction` | `action_recommend_similar_products` | 调用中台推荐相似商品 |

> 当前自定义 Action 的 `run()` 方法为 `pass`（占位），后续需集成中台 HTTP 调用。

---

### 5.9 对话历史构建器 (history)

**文件**: [builder.py](file:///workspace/customer-service-backend/atguigu/history/builder.py)

`ChatHistoryBuilder` 将 `Turn` 列表格式化为 LLM 可读的对话历史字符串。支持文本消息和对象消息（订单/商品卡片）的渲染。

| 静态方法 | 说明 |
|----------|------|
| `build(turns) -> str` | 构建 `USER: ...\nBOT: ...` 格式的对话历史 |
| `process_user_message(msg) -> str` | 处理单条用户消息（文本/对象） |

---

### 5.10 Prompt 提示词模块 (prompts)

**文件**: [loader.py](file:///workspace/customer-service-backend/atguigu/prompts/loader.py)

`load_prompt_template(name)` 从 `jinja2/` 目录加载 `.jinja2` 模板文件。

#### TurnPlanner 提示词模板

**文件**: [turn_plan.jinja2](file:///workspace/customer-service-backend/atguigu/prompts/jinja2/turn_plan.jinja2)

LLM 被要求分析对话上下文，生成一个 TurnPlan JSON，顶层只允许三个字段：`task`、`knowledge`、`chitchat`。模板注入：
- 可用业务流程清单（`available_flows_json`）
- 知识意图清单（`knowledge_intents_json`）
- 当前活跃任务、中断任务、聚焦对象
- 对话历史

#### 澄清响应提示词模板

**文件**: [clarify_respond.jinja2](file:///workspace/customer-service-backend/atguigu/prompts/jinja2/clarify_respond.jinja2)

将系统澄清提示改写为自然对话语气，注入：澄清原因、建议回复、聚焦对象、对话历史、用户最后一句。

---

### 5.11 对话规划器 (plan)

#### TurnPlanner

**文件**: [planner.py](file:///workspace/customer-service-backend/atguigu/plan/planner.py)

`TurnPlanner` 是 LLM 路由决策的核心，负责分析用户消息并生成 `TurnPlan`。

**核心方法**：

| 方法 | 说明 |
|------|------|
| `predict(user_message, state, flow_list, intents) -> TurnPlan` | 主入口：准备 prompt 输入 → 调用 LLM → 解析结果 |
| `_prepare_prompt_inputs(...) -> dict` | 构建 prompt 输入，包含：用户消息、对话历史（最近 10 轮）、可用业务流程、知识意图、活跃任务、中断任务、聚焦对象 |
| `predict_from_prompt_inputs(prompt_inputs) -> TurnPlan` | 加载模板 → 构建 LangChain 链（prompt \| llm_client \| JsonOutputParser）→ 调用 LLM → 返回 TurnPlan |

**设计要点**：
- 只给 LLM [业务流程](file:///workspace/customer-service-backend/atguigu/task/flow/flows.py)（不含 steps），系统流程不暴露给 LLM
- 对话历史截取最近 10 轮
- 使用 `temperature=0` 保证输出稳定性

#### TurnPlan 数据模型

**文件**: [turn_plan.py](file:///workspace/customer-service-backend/atguigu/plan/turn_plan.py)

| 类 | 说明 |
|------|------|
| `TaskTurnPlan` | 任务轨道规划：`commands: list[Command]` |
| `KnowledgeTurnPlan` | 知识轨道规划：`intents: list[str]` |
| `ChitChatTurnPlan` | 闲聊轨道规划（空对象） |
| `TurnPlan` | 顶层规划：`task`, `knowledge`, `chitchat`（三选一） |

`activated_tracks()` 方法返回被激活的轨道列表。

#### ClarifyReason 枚举

| 枚举值 | 说明 |
|--------|------|
| `MISSING_TRACK` | 未命中任何轨道 |
| `MULTIPLE_TRACKS` | 命中了多条轨道 |
| `MISSING_TASK_COMMANDS` | 任务轨道没有 commands |
| `MISSING_KNOWLEDGE_INTENT` | 知识轨道没有 intents |
| `INVALID_TASK_COMMANDS` | 命令类型不在白名单 |
| `MULTIPLE_TASK_FLOWS` | 同时开启了多个业务流程 |
| `UNKNOWN_TASK_FLOW` | 指定的流程 ID 不存在 |
| `MISSING_FOCUSED_OBJECT` | 缺少聚焦对象 |
| `OBJECT_REQUIRES_INTENT` | 对象需要指定意图 |

#### TurnPlanValidator

**文件**: [validator.py](file:///workspace/customer-service-backend/atguigu/plan/validator.py)

`TurnPlanValidator` 对 LLM 输出进行白名单校验，确保安全可靠。

**校验流程**：
1. 外层校验：轨道数必须恰好为 1（不能为 0 也不能多于 1）
2. 任务轨道校验（四重）：
   - commands 不能为空
   - command 类型必须在白名单（`StartedFlowCommand`, `CancelFlowCommand`, `ResumedFlowCommand`, `SetSlotsCommand`）
   - 只允许一个 `StartedFlowCommand`
   - 指定的流程 ID 必须在已定义的流程列表中
3. 知识轨道校验：intents 非空，且需要聚焦对象时检查对象是否存在且类型匹配
4. 闲聊轨道：直接通过

---

### 5.12 意图澄清器 (clarify)

**文件**: [responder.py](file:///workspace/customer-service-backend/atguigu/clarify/responder.py)

`ClarifyResponser` 在 TurnPlanValidator 校验失败时触发，负责生成友好的澄清回复。

**核心方法**：

| 方法 | 说明 |
|------|------|
| `respond(reason, state) -> list[BotMessage]` | 主入口：构建 prompt → 调用 LLM 改写 → 返回消息 |
| `_build_clarify_prompt_inputs(reason, state) -> dict` | 构建 prompt 输入 |
| `_build_base_script(reason, state) -> str` | 根据 ClarifyReason 选择基础话术 |

每种 `ClarifyReason` 对应不同的澄清话术，通过 LLM 改写为自然语气。

---

### 5.13 知识检索轨道 (knowledge)

**文件**: [handler.py](file:///workspace/customer-service-backend/atguigu/knowledge/handler.py), [intents.py](file:///workspace/customer-service-backend/atguigu/knowledge/intents.py)

`KnowledgeHandler` 接收 `KnowledgeIntent` 字典，处理知识问答。当前为 stub 实现。

**已定义的知识意图**（7 个）：

| 意图ID | 描述 | 数据来源 | 是否需要聚焦对象 |
|--------|------|----------|------------------|
| `product_info` | 商品信息咨询 | api.product | product |
| `order_info` | 订单信息咨询 | api.order | order |
| `refund_policy` | 退款政策咨询 | faq.default, rag.default | - |
| `return_policy` | 退货政策咨询 | faq.default, rag.default | - |
| `shipping_policy` | 配送政策咨询 | faq.default, rag.default | - |
| `platform_rule` | 平台规则咨询 | rag.default | - |
| `general_ecommerce_info` | 电商通用信息咨询 | faq.default, rag.default | - |

---

### 5.14 闲聊轨道 (chitchat)

**文件**: [handler.py](file:///workspace/customer-service-backend/atguigu/chitchat/handler.py)

`ChitChatHandler` 处理闲聊消息。当前为 stub 实现（`pass`）。

---

### 5.15 任务处理轨道 (task-handler)

**文件**: [handler.py](file:///workspace/customer-service-backend/atguigu/task/handler.py)

`TaskHandler` 是任务轨道的总入口，组合 `CommandProcessor` 和 `FlowExecutor`。

```python
class TaskHandler:
    def __init__(self, flow_list, command_processor, executor):
        self.flow_list = flow_list
        self.command_processor = command_processor
        self.executor = executor

    async def hand(self, state, commands) -> list[BotMessage]:
        # 1. 使用 command_processor 处理命令
        self.command_processor.run(state, self.flow_list, commands)
        # 2. 使用流程执行器推进流程（TODO）
        return [BotMessage(text="11111")]
```

`FlowExecutor` 当前为 stub（空类）。

---

### 5.16 对话引擎 (engine)

**文件**: [dialogue_engine.py](file:///workspace/customer-service-backend/atguigu/engine/dialogue_engine.py)

`DialogueEngine` 是对话引擎的核心调度器，对接所有子模块。

**构造函数参数**：
- `planner: TurnPlanner` — LLM 路由决策
- `turn_plan_validator: TurnPlanValidator` — 白名单校验
- `task_handler: TaskHandler` — 任务轨道处理
- `knowledge_handler: KnowledgeHandler` — 知识轨道处理
- `chitchat_handler: ChitChatHandler` — 闲聊轨道处理
- `clarify_responder: ClarifyResponser` — 澄清兜底

**主入口**：`hand_message(user_message, state) -> ProcessResult`

**处理流程**：
1. **准备会话**（`_prepare_session`）：检查是否存在有效会话，超时 60 分钟则创建新会话
2. **创建 Turn**（`_begin_turn`）：调用 `state.start_turn(user_message)`
3. **判断消息类型**：
   - **文本消息**（`_hand_text_msg`）：
     - 调用 `TurnPlanner.predict()` 获取规划结果
     - 调用 `TurnPlanValidator.validate()` 校验
     - 校验失败 → `ClarifyResponser.respond()` 澄清
     - 校验通过 → 分发到对应轨道处理器
   - **对象消息**（`_hand_obj_msg`）：
     - 设置 `state.focused_object`
     - 尝试解析对象为 `SetSlotsCommand`
     - 有流程则推进流程，无流程则澄清
4. **提交 Turn**（`commit_pending_turn`）
5. **返回结果**

**对象消息处理**（`_hand_obj_msg`）：
- 订单卡片 → 尝试构建 `SetSlotsCommand(slots={"order_number": obj.id})`
- 商品卡片 → 尝试构建 `SetSlotsCommand(slots={"product_id": obj.id})`
- 构建条件：当前有活跃流程 + 流程中有对应的 CollectFlowStep + 槽位未填写

---

### 5.17 引擎构建器 (engine-builder)

**文件**: [builder.py](file:///workspace/customer-service-backend/atguigu/engine/builder.py)

`build_dialogue_engine()` 函数负责组装所有组件：

```python
def build_dialogue_engine():
    flow_list = FlowLoader().load_many_yaml([...])
    return DialogueEngine(
        planner=TurnPlanner(),
        task_handler=TaskHandler(
            flow_list=flow_list,
            command_processor=CommandProcessor(),
            executor=FlowExecutor()
        ),
        turn_plan_validator=TurnPlanValidator(),
        knowledge_handler=KnowledgeHandler(intents=KNOWLEDGE_INTENTS),
        chitchat_handler=ChitChatHandler(),
        clarify_responder=ClarifyResponser()
    )
```

---

### 5.18 服务层 (services)

**文件**: [dialogue_service.py](file:///workspace/customer-service-backend/atguigu/services/dialogue_service.py)

`DialogueService` 是应用服务层，把一次对话处理串起来，是事务边界。

```python
async def hand_dialogue(self, user_message: UserMessage) -> ProcessResult:
    # 1. 从数据库加载 DialogueState
    dialogue_state = await self.repository.load_dialogue(user_message.sender_id)
    # 2. 引擎处理消息（纯计算）
    process_result = await self.engine.hand_message(user_message, dialogue_state)
    # 3. 保存修改后的 DialogueState 到数据库
    await self.repository.save_dialogue(dialogue_state)
    return process_result
```

---

### 5.19 API 接口层 (api)

#### FastAPI 应用实例

**文件**: [app.py](file:///workspace/customer-service-backend/atguigu/api/app.py)

```python
app = FastAPI(description="智能客服V1.0", lifespan=lifespan)
app.include_router(router)
```

**lifespan 生命周期**：
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

| 类 | 方向 | 说明 |
|------|------|------|
| `ChatObject` | 入/出 | 卡片对象（id, type, title, attributes） |
| `ChatRequest` | 入 | 请求模型（sender_id, text, object） |
| `ChatBotMessage` | 出 | 机器人回复（text, object） |
| `ChatResponse` | 出 | 响应模型（sender_id, message_id, messages） |

**数据转换流程**：`ChatRequest → UserMessage (domain) → 业务处理 → ProcessResult (domain) → ChatResponse`

#### 路由

**文件**: [chat_router.py](file:///workspace/customer-service-backend/atguigu/api/router/chat_router.py)

| 接口 | 方法 | 说明 |
|------|------|------|
| `/hello` | GET | 健康检查 |
| `/api/chat` | POST | 发送消息，获取回复 |

#### 依赖注入链

**文件**: [dependencies.py](file:///workspace/customer-service-backend/atguigu/api/dependencies.py)

```
get_engine()          → DialogueEngineDep
get_session()         → RepositorySessionDep
get_repository()      → DialogueRepositoryDep
get_dialogue_service() → DialogueServiceDep
```

使用 `Annotated[Type, Depends(factory)]` 定义别名类型，路由函数签名简洁。

---

## 6. 前端应用

### 6.1 项目概述

前端应用是一个基于 Vue 3 的聊天界面，集成数字人交互能力，通过 HTTP 和 WebSocket 与后端通信。

**文件**: [index.html](file:///workspace/customer-service-frontend/index.html), [App.vue](file:///workspace/customer-service-frontend/src/App.vue), [main.js](file:///workspace/customer-service-frontend/src/main.js)

### 6.2 核心功能

| 功能 | 说明 |
|------|------|
| 聊天界面 | 消息列表展示（用户消息 + 机器人回复），Turn 结构分组展示 |
| 文本输入 | 输入框 + 发送按钮，支持快捷短语 |
| 对象卡片 | 订单/商品卡片展示与发送，点击卡片触发对象消息 |
| 数字人集成 | 云渲染数字人，支持语音播报（transcript 模式） |
| WebSocket | 实时文本/PCM 音频通信 |
| 侧边栏 | 订单/商品列表，可点击发送 |
| Canvas 粒子背景 | 交互式粒子背景动画 |

### 6.3 通信方式

| 方式 | 端点 | 说明 |
|------|------|------|
| HTTP POST | `/api/chat` | 发送消息获取回复 |
| WebSocket | `/ws/avatar/chat` | 实时文本 + PCM 音频（数字人模式） |
| HTTP GET | `/commerce/users/{id}/orders` | 获取用户订单列表 |
| HTTP GET | `/commerce/users/{id}/products` | 获取用户商品列表 |

### 6.4 数字人集成

使用 `lm-avatar-chat-sdk` 实现云渲染数字人交互：
- 支持 transcript 模式和音频驱动模式
- 自动管理会话生命周期
- 浏览器卸载时自动释放资源
- 手势交互触发音频播放

---

## 7. 对话处理完整流程

```
用户发送消息
    ↓
API 层 (chat_router.py)
    ├─ ChatRequest → UserMessage（数据转换）
    └─ 调用 DialogueServiceDep
    ↓
Service 层 (dialogue_service.py)
    ├─ 1. repository.load_dialogue(sender_id) → DialogueState
    ├─ 2. engine.hand_message(user_message, dialogue_state) → ProcessResult
    └─ 3. repository.save_dialogue(dialogue_state)
    ↓
Engine 层 (dialogue_engine.py)
    ├─ _prepare_session(state)          ← 检查/创建会话（60 分钟超时）
    ├─ _begin_turn(user_message, state)  ← 创建 pending_turn
    ├─ 判断消息类型
    │   ├─ TEXT  → _hand_text_msg()
    │   │   ├─ TurnPlanner.predict()       ← 调用 LLM 生成 TurnPlan
    │   │   ├─ TurnPlanValidator.validate() ← 白名单校验
    │   │   ├─ 校验失败 → ClarifyResponser.respond() ← 澄清兜底
    │   │   └─ 校验通过 → 分发轨道
    │   │       ├─ task      → TaskHandler.hand(commands)
    │   │       │   ├─ CommandProcessor.run()    ← 处理四种命令
    │   │       │   └─ FlowExecutor (TODO)       ← 推进流程
    │   │       ├─ knowledge → KnowledgeHandler.hand() (stub)
    │   │       └─ chitchat  → ChitChatHandler.hand() (stub)
    │   └─ OBJECT → _hand_obj_msg()
    │       ├─ 设置 focused_object
    │       ├─ 尝试解析对象为 SetSlotsCommand
    │       └─ 推进流程 / 澄清
    ├─ commit_pending_turn()            ← 提交 Turn 到 Session
    └─ 返回 ProcessResult
    ↓
API 层
    ├─ ProcessResult → ChatResponse（数据转换）
    └─ 返回 JSON 响应
```

---

## 8. API 接口设计

### 8.1 健康检查

```
GET /hello
→ {"success": "ok"}
```

### 8.2 聊天接口

```
POST /api/chat
```

**请求体**（文本消息）：
```json
{
  "sender_id": "u1001",
  "text": "我想查一下订单状态",
  "object": null
}
```

**请求体**（对象消息）：
```json
{
  "sender_id": "u1001",
  "text": null,
  "object": {
    "id": "A20260410001",
    "type": "order",
    "title": "订单 A20260410001",
    "attributes": {"status": "待发货"}
  }
}
```

**响应体**：
```json
{
  "sender_id": "1001",
  "message_id": "11111",
  "messages": [
    {
      "text": "我是电商客服，请问你有什么问题需要我帮助的嘛",
      "object": null
    }
  ]
}
```

---

## 9. 项目配置与运行

### 9.1 环境要求

- Python >= 3.12
- MySQL 数据库
- 可用的 LLM API（通义千问兼容 OpenAI 协议）
- Node.js >= 18（前端开发）
- `uv` 包管理器

### 9.2 创建 .env 配置文件

在 `customer-service-backend/` 目录下创建 `.env` 文件：

```bash
LLM_MODEL=qwen-plus
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_API_KEY=sk-your-api-key-here
DATABASE_URL=mysql+aiomysql://root:root@localhost:3306/customer_service?charset=utf8mb4
COMMERCE_API_BASE_URL=http://192.168.200.125:18081
APP_HOST=0.0.0.0
APP_PORT=18082
```

### 9.3 依赖安装

```bash
# 后端
cd customer-service-backend
uv sync

# 前端
cd customer-service-frontend
npm install
```

### 9.4 数据库初始化

```sql
CREATE DATABASE customer_service CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE customer_service;
CREATE TABLE dialogue_states (
    sender_id VARCHAR(255) PRIMARY KEY,
    state_json TEXT
);
```

### 9.5 启动服务

```bash
# 启动 AI 客服后端
cd customer-service-backend
uv run python atguigu/main.py
# 或：uv run python -m atguigu.main

# 启动前端开发服务器
cd customer-service-frontend
npm run dev
```

启动后：
- AI 客服后端运行在 `http://0.0.0.0:18082`
- 前端运行在 `http://localhost:5173`

### 9.6 验证安装

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
uv run python -m atguigu.task.flow.loader
```

---

## 10. 设计理念与关键模式

### 10.1 五大设计原则

1. **三条轨道分离** — 任务、知识、闲聊各走各的代码路径，互不污染
2. **LLM 路由 + 白名单校验 + 澄清兜底** — 永远不"裸用" LLM 的输出
3. **YAML 描述流程，代码执行流程** — 可枚举的业务逻辑从 LLM 手里拿出来
4. **DialogueState 集中状态，Engine 集中计算** — 状态读写在边缘（Service），计算在中心（Engine）
5. **业务隔离** — AI 客服永远以"业务消费者"身份调中台接口

### 10.2 关键设计模式

| 模式 | 应用位置 | 作用 |
|------|----------|------|
| **聚合根模式** | `DialogueState` | 集中管理所有对话状态，保证一致性 |
| **注册表模式** | `SYSTEM_CONTEXT_TO_CLASS`、`FLOW_STEP_TYPE_TO_CLASS`、`COMMAND_TO_CLASS` | 字典查表实现多态分发 |
| **工厂方法模式** | `FlowStep.from_dict`、`SystemContext.from_dict`、`Command.from_dict` | 根据 type 字段创建对应子类 |
| **命令模式** | `Command` 子类 + `CommandProcessor` | 将 LLM 输出转为结构化命令统一处理 |
| **策略模式** | `Action` 子类 | 不同动作的不同执行策略 |
| **注册/发现模式** | `ActionRegister` + `builder.py` 自动扫描 | 插件式扩展业务动作 |
| **两步提交** | `pending_turn` | 处理中与已提交分离，保证数据完整性 |
| **仓储模式** | `DialogueRepository` | 封装持久化细节，领域层不关心存储 |
| **依赖注入** | `api/dependencies.py` | FastAPI Depends 链式注入 |
| **构建器模式** | `engine/builder.py` | 集中组装所有组件 |

### 10.3 DDD 思想应用

- **事务脚本 + 充血模型**：Service 层管 I/O，Engine 层管计算
- **仓储模式**：Repository 封装持久化，领域层不关心存储
- **领域模型与基础设施分离**：domain 层纯数据和业务规则，infrastructure 层管外部依赖
- **dataclass + slots**：所有领域模型使用 `@dataclass(slots=True)`，访问速度快、内存占用小

---

## 11. 实现进度总览

### 11.1 已完成模块

| 模块 | 状态 | 说明 |
|------|------|------|
| config | 已完成 | 7 个配置项，启动期校验 |
| domain (messages/contexts/state) | 已完成 | 完整领域模型，含序列化/反序列化 |
| infrastructure (llm/db/http) | 已完成 | 三个基础设施客户端 |
| model (base/state_record) | 已完成 | ORM 模型 |
| repository | 已完成 | INSERT ON DUPLICATE KEY UPDATE upsert |
| task/flow (flows/links/steps/loader) | 已完成 | 完整的 YAML 流程编排系统 |
| task/command (commands/processor) | 已完成 | 四种命令 + 完整处理逻辑 |
| task/action (base/register/runner/builder) | 已完成 | 动作注册、发现、执行框架 |
| task/action/builtin (listener/response) | 已完成 | 内置动作 |
| task/action/customer (3 个 Action) | 占位 | 类已定义，run() 尚未实现 |
| history | 已完成 | 对话历史格式化 |
| prompts | 已完成 | 2 个 Jinja2 模板 |
| plan (planner/validator/turn_plan) | 已完成 | LLM 路由 + 白名单校验 |
| clarify | 已完成 | 基于 LLM 改写的澄清兜底 |
| knowledge | 占位 | 意图清单已定义，handler 为 stub |
| chitchat | 占位 | handler 为 stub |
| task/handler | 基本完成 | 命令处理已实现，FlowExecutor 为 stub |
| task/flow/executor | 占位 | 空类，待实现流程推进逻辑 |
| engine (dialogue_engine/builder) | 基本完成 | 核心调度逻辑已实现 |
| services | 已完成 | 完整的事务边界 |
| api (app/router/schemas/dependencies) | 已完成 | 完整 API 层 |
| flow_config | 已完成 | 6 个业务流程 + 6 个系统流程 |
| frontend | 已完成 | 聊天界面 + 数字人集成 |

### 11.2 待完成模块

| 模块 | 预期内容 | 优先级 |
|------|----------|--------|
| `task/flow/executor.py` | 流程推进逻辑（按步骤执行动作） | 高 |
| `task/action/customer/*.py` | 接入中台 HTTP 接口实现业务逻辑 | 高 |
| `task/action/builtin/response.py` | 模板变量渲染 + LLM rephrase | 高 |
| `knowledge/handler.py` | 知识检索实现（FAQ/RAG） | 中 |
| `chitchat/handler.py` | 闲聊回复生成 | 低 |

---

## 12. 附录：核心类速查表

| 类名 | 文件 | 类型 | 说明 |
|------|------|------|------|
| `Settings` | config/settings.py | pydantic | 配置类，7 个必填字段 |
| `MessageType` | domain/messages.py | Enum | TEXT / OBJECT |
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
| `Session` | domain/state.py | dataclass | 会话（60 分钟超时） |
| `DialogueState` | domain/state.py | dataclass | 对话状态聚合根 |
| `Base` | model/base.py | class | SQLAlchemy 声明式基类 |
| `DialogueStateRecord` | model/state_record.py | class | 对话状态 ORM 映射 |
| `DialogueRepository` | repository/dialogue_repository.py | class | 对话持久化仓储 |
| `DialogueService` | services/dialogue_service.py | class | 对话应用服务 |
| `DialogueEngine` | engine/dialogue_engine.py | class | 对话引擎核心调度 |
| `TurnPlanner` | plan/planner.py | class | LLM 路由决策器 |
| `TurnPlan` | plan/turn_plan.py | dataclass | 对话规划结果 |
| `TaskTurnPlan` | plan/turn_plan.py | dataclass | 任务轨道规划 |
| `KnowledgeTurnPlan` | plan/turn_plan.py | dataclass | 知识轨道规划 |
| `ChitChatTurnPlan` | plan/turn_plan.py | class | 闲聊轨道规划 |
| `ClarifyReason` | plan/turn_plan.py | Enum | 澄清原因枚举（9 种） |
| `TurnPlanValidateResult` | plan/turn_plan.py | dataclass | 校验结果 |
| `TurnPlanValidator` | plan/validator.py | class | 白名单校验器 |
| `ClarifyResponser` | clarify/responder.py | class | 意图澄清响应器 |
| `KnowledgeHandler` | knowledge/handler.py | class | 知识检索处理器 |
| `KnowledgeIntent` | knowledge/intents.py | dataclass | 知识意图定义 |
| `ChitChatHandler` | chitchat/handler.py | class | 闲聊处理器 |
| `TaskHandler` | task/handler.py | class | 任务轨道总入口 |
| `FlowExecutor` | task/flow/executor.py | class | 流程执行器（stub） |
| `FlowSlot` | task/flow/flows.py | dataclass | 槽位定义 |
| `Flow` | task/flow/flows.py | dataclass | 流程定义 |
| `FlowsList` | task/flow/flows.py | dataclass | 流程列表（多 YAML 合并） |
| `FlowStepLink` | task/flow/links.py | dataclass | 边基类 |
| `FlowStepStaticLink` | task/flow/links.py | dataclass | 静态边 |
| `FlowStepConditionLink` | task/flow/links.py | dataclass | 条件边（if/then） |
| `FlowStepFallbackLink` | task/flow/links.py | dataclass | 兜底边（else） |
| `FlowStepType` | task/flow/steps.py | Enum | START / COLLECT / ACTION / END |
| `ResponseDefinition` | task/flow/steps.py | dataclass | 响应定义（static/rephrase） |
| `SlotValidation` | task/flow/steps.py | dataclass | 槽位校验 |
| `FlowStep` | task/flow/steps.py | dataclass | 步骤基类 |
| `StartFlowStep` | task/flow/steps.py | dataclass | 开始步骤 |
| `EndFlowStep` | task/flow/steps.py | dataclass | 结束步骤 |
| `ActionFlowStep` | task/flow/steps.py | dataclass | 动作步骤 |
| `CollectFlowStep` | task/flow/steps.py | dataclass | 收集步骤 |
| `FlowLoader` | task/flow/loader.py | class | 流程加载器 |
| `Command` | task/command/commands.py | dataclass | 命令基类 |
| `StartedFlowCommand` | task/command/commands.py | dataclass | 开启流程命令 |
| `ResumedFlowCommand` | task/command/commands.py | dataclass | 恢复流程命令 |
| `CancelFlowCommand` | task/command/commands.py | dataclass | 取消流程命令 |
| `SetSlotsCommand` | task/command/commands.py | dataclass | 设置槽位命令 |
| `CommandProcessor` | task/command/processor.py | class | 命令处理器 |
| `Action` | task/action/base.py | ABC | 动作抽象基类 |
| `ActionResult` | task/action/base.py | dataclass | 动作执行结果 |
| `ActionCall` | task/action/base.py | dataclass | 动作调用描述 |
| `ActionRegister` | task/action/register.py | class | 动作注册中心 |
| `ActionRunner` | task/action/runner.py | class | 动作执行器 |
| `ActionListener` | task/action/builtin/listener.py | class | 内置：暂停监听 |
| `ActionResponse` | task/action/builtin/response.py | class | 内置：生成回复 |
| `LookupOrderStatusAction` | task/action/customer/lookup_order_status.py | class | 查询订单状态 |
| `LookupLogisticsAction` | task/action/customer/lookup_logistics.py | class | 查询物流 |
| `RecommendSimilarProductsAction` | task/action/customer/recommend_similar_products.py | class | 推荐相似商品 |
| `ChatHistoryBuilder` | history/builder.py | class | 对话历史构建器 |
| `ChatObject` | api/schemas.py | Pydantic | 卡片对象 Schema |
| `ChatRequest` | api/schemas.py | Pydantic | 请求 Schema |
| `ChatBotMessage` | api/schemas.py | Pydantic | 机器人回复 Schema |
| `ChatResponse` | api/schemas.py | Pydantic | 响应 Schema |

---

**文档版本**: 2.0
**最后更新**: 2026-07-17
**基于代码版本**: customer-service-backend (对话引擎完整实现版本)