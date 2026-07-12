from fastapi import FastAPI
from contextlib import asynccontextmanager
from atguigu.api.router.chat_router import router
from atguigu.infrastructure.db import init_db_engine, dispose_engine
from atguigu.infrastructure.http_client import init_http_client, dispose_http_client


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    在web服务器也即应用启动的时候，会来调用，接着在处理路由之前把初始化的一些信息都可以提前做好
    :param app:
    :return:
    """
    await init_db_engine()
    init_http_client()

    yield  # FASTAPI正常处理请求

    # 清理资源（应用关闭）
    await  dispose_engine()
    await  dispose_http_client()


app = FastAPI(description="智能客服V1.0", lifespan=lifespan)
app.include_router(router)
