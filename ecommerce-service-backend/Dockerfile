# 使用官方 Python 轻量级镜像
# FROM python:3.11-slim
FROM docker.1ms.run/library/python:3.11-slim
# 设置工作目录
WORKDIR /app

# 安装 uv (使用极速安装脚本或 pip)
RUN pip install uv -i https://mirrors.aliyun.com/pypi/simple/

ENV UV_INDEX_URL=https://mirrors.aliyun.com/pypi/simple/

# 先复制依赖文件，利用 Docker 缓存机制加速构建
COPY pyproject.toml uv.lock ./

# 同步依赖 (不安装开发环境依赖)
RUN uv sync --frozen --no-dev

# 复制项目的所有代码到容器中
COPY . .

# 暴露 README 中写的 18081 端口
EXPOSE 18081

# 启动服务
CMD ["uv", "run", "uvicorn", "app.app:app", "--host", "0.0.0.0", "--port", "18081"]
