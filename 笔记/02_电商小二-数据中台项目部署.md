# ecommerce-service-backend 部署文档

> 本文档记录将 `ecommerce-service-backend` 子服务通过 Docker 容器部署到虚拟机的完整流程，部署完成后，本地的 `customer-service-backend` 可直接通过 IP + 端口调用电商服务接口。验证可用的配置文件和操作步骤。
>

---

## 1、部署架构概览

本项目由三个子服务组成：

| 子项目 | 部署位置 | 说明 |
|--------|----------|------|
| `customer-service-backend`（客服服务后端） | 本地开发 | 主要开发对象 |
| `customer-service-frontend`（前端） | 本地开发 | — |
| `ecommerce-service-backend`（电商服务后端） | **虚拟机 Docker** | 仅作为依赖，打包部署 |

部署后，本地客服服务通过 `http://<虚拟机IP>:18081` 调用电商服务接口。

---

## 2、需要准备的文件

部署前，在 `ecommerce-service-backend` 根目录下需要有以下三个新增文件：

```
ecommerce-service-backend/
├── app/                        # 业务代码（包含 app.py，里面定义了 FastAPI 实例）
├── mysql/
│   └── initdb/                 # 存放数据库初始化 SQL 脚本
│       └── *.sql
├── pyproject.toml              # 已有
├── uv.lock                     # 已有
├── .env                        # 已有
├── Dockerfile                  # 【新建】
├── docker-compose.yml          # 【新建】
└── .dockerignore               # 【新建】
```

### 2.1 Dockerfile

```dockerfile
# 使用官方 Python 轻量级镜像
FROM python:3.11-slim

# 设置工作目录
WORKDIR /app

# 【加速 1】使用阿里云镜像源安装 uv，解决国内下载慢的问题
RUN pip install uv -i https://mirrors.aliyun.com/pypi/simple/

# 【加速 2】配置环境变量，让 uv 在后续装包时也走阿里云镜像
ENV UV_INDEX_URL=https://mirrors.aliyun.com/pypi/simple/

# 先复制依赖文件，利用 Docker 缓存机制加速后续构建
COPY pyproject.toml uv.lock ./

# 严格按照 uv.lock 安装依赖，且不安装开发依赖
RUN uv sync --frozen --no-dev

# 复制项目全部代码到容器中
COPY . .

# 暴露服务端口
EXPOSE 18081

# 启动服务
# 注意：FastAPI 实例位于 app/app.py 中，因此入口路径为 app.app:app
CMD ["uv", "run", "uvicorn", "app.app:app", "--host", "0.0.0.0", "--port", "18081"]
```

**关于启动入口的说明：**
- `app.app:app` 三部分含义：第一个 `app` 是包名（文件夹），第二个 `app` 是模块名（`app.py` 文件），冒号后的 `app` 是 FastAPI 实例变量名。
- 如果你的 FastAPI 实例文件名是 `main.py`，则改为 `app.main:app`，按实际代码调整。

### 2.2 docker-compose.yml

```yaml
services:
  # 1. 数据库服务
  mysql:
    image: mysql:8.4
    container_name: customer-service-mysql
    restart: unless-stopped
    environment:
      MYSQL_ROOT_PASSWORD: root
      MYSQL_DATABASE: commerce
      MYSQL_USER: atguigu
      MYSQL_PASSWORD: Atguigu.123
    ports:
      - "3306:3306"
    command:
      - --character-set-server=utf8mb4
      - --collation-server=utf8mb4_unicode_ci
    volumes:
      - mysql_data:/var/lib/mysql
      - ./mysql/initdb:/docker-entrypoint-initdb.d

  # 2. 电商后端 API 服务
  api:
    build: .
    container_name: ecommerce-api
    restart: always
    ports:
      - "18081:18081"
    depends_on:
      - mysql
    environment:
      # 直接使用完整的 URL，并把 IP 替换为服务名 mysql（Docker 内部 DNS 会自动解析）
      DATABASE_URL: "mysql+pymysql://atguigu:Atguigu.123@mysql:3306/commerce?charset=utf8mb4"
      APP_PORT: 18081

volumes:
  mysql_data:   # 持久化 MySQL 数据，防止容器重启后数据丢失
```

**几个关键点：**

- **数据库账密一致性**：`MYSQL_USER`/`MYSQL_PASSWORD`/`MYSQL_DATABASE` 必须和 `DATABASE_URL` 中的用户名、密码、库名完全匹配，否则 API 启动后连不上数据库。

- **服务名即主机名**：Docker Compose 会自动创建一个默认网络，同一 compose 文件下的服务可以通过服务名互访，因此 `DATABASE_URL` 中的主机名直接写 `mysql` 即可，**无需任何 IP**。

- **`./mysql/initdb` 目录的作用**：MySQL 官方镜像在**第一次启动**（数据库为空时）会自动执行 `/docker-entrypoint-initdb.d` 目录里的所有 `.sql` 文件，因此把你的初始化脚本放到 `./mysql/initdb/` 下即可自动建表插数据。看到这个就该知道：建表 DDL 和种子数据（订单、商品、物流轨迹）就在 `mysql/initdb/` 下

- **重新初始化数据库**：如果改了 SQL 脚本想重跑，必须先执行 `docker compose down -v` 删除数据卷，再 `up`。

- **为什么 docker-compose 里没有 AI 客服后端 (18082)？**

  这是本节的关键问题。完整生产环境里你会看到 4 个服务（前端 + AI 后端 + 电商后端 + DB），但本仓库的 `docker-compose.yml` 故意只编排了"业务基座 + DB"。**这是有意之举**：

  | 角色                     | 启动方式                                 | 原因                                           |
  | ------------------------ | ---------------------------------------- | ---------------------------------------------- |
  | MySQL + 电商后端 (18081) | `docker compose up` 一键                 | **稳定的"基础设施"**，不需要改它，容器化最省事 |
  | AI 后端 (18082)          | 本地 `uv run uvicorn`（开发模式 reload） | **每天要改的核心代码**，需要断点调试           |
  | 前端 (5173)              | 本地 `npm run dev`                       | 同上                                           |

  **生产工程师的类比**：这就是 IDEA 里"基础设施服务跑 Docker，业务代码跑本地 Run/Debug"的常见姿势。**容器化的边界画在"不常改"的服务上**，开发体验和工程严谨性的最佳平衡。

  > **思维升级**：架构不是"一刀切上 Docker"。**容器化的真正价值是隔离"不变的部分"，给"变的部分"让路**。

### 2.3 .dockerignore

```text
# Python
.venv/
__pycache__/
*.pyc

# 环境配置
.env

# Git
.git/
```



## 3、Dockerfile 关键点解析

### 3.1 为什么要分两次 COPY？

```dockerfile
COPY pyproject.toml uv.lock ./   # 第 1 步：只复制依赖清单
RUN uv sync --frozen --no-dev    # 第 2 步：安装依赖
COPY . .                          # 第 3 步：复制业务代码
```

Docker 镜像是分层构建的，每一层都会被缓存。只要某一层的输入文件没变，Docker 就会直接复用缓存。

- 业务代码每天都在改，依赖清单几周才改一次。
- 如果一次性 `COPY . .` 再 `uv sync`，那每改一行代码都要重新装一遍所有依赖，非常慢。
- 分开后，只要 `pyproject.toml` 和 `uv.lock` 没变，第 2 步就直接走缓存，秒级跳过。

### 3.2 `uv sync --frozen --no-dev` 的两个参数

- **`--frozen`**：严格按照 `uv.lock` 里记录的精确版本号安装，禁止 uv 自动升级或修改 lock 文件。保证本地和生产环境的依赖版本完全一致。
- **`--no-dev`**：不安装开发依赖（如 `pytest`、`ruff` 等）。让镜像更小、更安全。

### 3.3 `COPY . .` 的精确含义

- 第一个 `.`：宿主机当前上下文目录（Dockerfile 所在目录）。
- 第二个 `.`：容器内当前工作目录（由 `WORKDIR /app` 设定，即 `/app`）。

即：将宿主机当前目录下的所有文件，复制到容器内的 `/app` 目录下。配合 `.dockerignore` 排除不需要的文件。

---

## 4、虚拟机环境准备

### 4.1 必备软件

确保虚拟机已安装：

- Docker
- Docker Compose（v2 版本，命令为 `docker compose`，注意没有横杠）



## 5、部署操作流程

### 步骤 1：本地打包

> ⚠️ **打包前务必删除（或排除）`.venv` 目录**。它体积大、文件多、且是 Windows 下生成的，在 Linux 虚拟机上完全无法使用。

1. 找到 `ecommerce-service-backend` 文件夹。
2. 右键 → "压缩为 ZIP 文件"，生成 `ecommerce-service-backend.zip`。

### 步骤 2：上传到虚拟机

使用 SFTP 客户端（MobaXterm / Xftp / WinSCP / FileZilla 等）将 zip 包上传到虚拟机目录，例如：

```
/root/web/
```

### 步骤 3：登录虚拟机并解压

```bash
ssh root@<虚拟机IP>
cd /root/web/
unzip ecommerce-service-backend.zip
cd ecommerce-service-backend
```

### 步骤 4：构建并启动

```bash
docker compose up -d --build
```

这条命令的含义：

| 部分 | 作用 |
|------|------|
| `docker compose` | 启用 Docker Compose 工具，自动读取当前目录的 `docker-compose.yml` |
| `up` | 创建并启动所有服务（容器、网络、数据卷） |
| `-d` | 后台运行（detach），关闭终端服务不停 |
| `--build` | 强制根据 `Dockerfile` 重新构建镜像，确保使用最新代码 |

> **执行顺序补充**：Docker Compose 是先读取 `docker-compose.yml` 这张"总图纸"，解析到 `build: .` 这一行时，才会去触发 `Dockerfile` 的构建。即 compose 文件是大管家，Dockerfile 是它临时调用的"制造说明书"。

### 步骤 5：验证部署状态

**① 查看容器运行状态**

```bash
docker compose ps
```

或：

```bash
docker ps
```

应当看到 `ecommerce-api` 和 `customer-service-mysql` 两个容器都处于 `Up` 状态。

**② 查看 API 实时日志**

```bash
docker compose logs -f api
```

看到类似 `Application startup complete` 或 `Uvicorn running on http://0.0.0.0:18081` 就说明启动成功。按 `Ctrl+C` 退出日志查看（不会停止服务）。

### 步骤 6：开放虚拟机防火墙端口

为了让本地能访问，需要放行 `18081` 端口：

**CentOS/RHEL (firewalld)：**

```bash
sudo firewall-cmd --zone=public --add-port=18081/tcp --permanent
sudo firewall-cmd --reload
```

**Ubuntu (UFW)：**

```bash
sudo ufw allow 18081/tcp
sudo ufw reload
```

如果是云服务器（阿里云、腾讯云等），还要在云控制台的"安全组"里放行 `18081` 端口。

### 步骤 7：本地访问验证

打开本地浏览器：

```
http://<虚拟机IP>:18081/docs
```

如果能看到 **Atguigu 电商业务服务** 的 Swagger 接口文档界面（包含 `/health`、`/users/{user_id}/orders`、`/orders/{order_id}` 等接口），说明部署完全成功。

---

## 6、修改本地客服服务的配置

部署成功后，回到本地 `customer-service-backend` 项目：

1. 打开 `.env`（或 `flow_config/` 下的相关配置文件）。
2. 找到电商服务地址配置项，把原来指向本机的地址改为虚拟机地址：

```text
# 旧值
ECOMMERCE_API_BASE_URL=http://127.0.0.1:18081

# 新值
ECOMMERCE_API_BASE_URL=http://<虚拟机IP>:18081
```

3. 重启本地客服服务，所有电商接口请求会自动路由到虚拟机的 Docker 容器。

---

## 7、常用运维命令

| 命令 | 用途 |
|------|------|
| `docker compose ps` | 查看本项目所有服务状态 |
| `docker compose logs -f api` | 实时查看 api 日志（`-f` 是跟随模式） |
| `docker compose logs -f mysql` | 实时查看 mysql 日志 |
| `docker compose restart api` | 只重启 api 容器 |
| `docker compose down` | 停止并删除所有容器（保留数据卷） |
| `docker compose down -v` | 停止并删除所有容器**及数据卷**（数据库会被清空重建） |
| `docker compose up -d --build` | 重新构建并启动（代码改动后用） |
| `docker exec -it customer-service-mysql mysql -uroot -proot` | 进入 mysql 容器交互式登录 |
| `docker exec -it ecommerce-api /bin/bash` | 进入 api 容器查看文件 |

---

## 8、常见问题排查

### 问题 1：构建时卡在 `RUN pip install uv`

**原因**：默认走 PyPI 官方源，国内速度极慢。
**解决**：Dockerfile 中已加入阿里云镜像源，如果还慢可尝试其他源（清华、网易等）。

### 问题 2：API 启动后报数据库连不上

**原因**：`docker-compose.yml` 中 `mysql` 服务的账密/库名和 `api` 服务的 `DATABASE_URL` 不一致。
**解决**：逐项核对用户名、密码、库名三处是否完全匹配。

### 问题 3：改了 SQL 初始化脚本但没生效

**原因**：MySQL 只在数据卷为空时执行 `docker-entrypoint-initdb.d` 里的脚本。
**解决**：

```bash
docker compose down -v   # 删除数据卷
docker compose up -d --build
```

---

## 9、部署后的整体效果

- 本地电脑无需再启动电商后端服务和 MySQL，节省内存和 CPU。
- 本地客服服务通过虚拟机 IP 直接调用电商接口，开发不受影响。
- 电商服务由 Docker Compose 统一管理，启停一条命令搞定。
- 数据库数据通过命名卷持久化，重启不丢失。

至此部署完成。后续如电商服务代码变动，只需重新打包上传 → 在虚拟机执行 `docker compose up -d --build` 即可热更新。
