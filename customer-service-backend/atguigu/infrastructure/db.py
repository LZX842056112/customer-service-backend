"""
操作数据库的session会话
异步引擎  异步session (session.execute())

"""
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy import text

from atguigu.config.settings import settings

engine: AsyncEngine | None = None

session_factory: async_sessionmaker[AsyncSession] | None = None


async def init_db_engine():
    """
    expire_on_commit:True:提交后自动过期

    update user set user.name="tome" where  id="1001"

    commit--刷盘

    user.name(读)---->查询数据库获取最新的，没有任何问题：同步环境下
    await user.name---报错

    sqlite:轻量级的文件数据库


    :return:
    """
    global engine, session_factory

    engine = create_async_engine(settings.database_url, echo=True)  # echo=True 在控制台可以看到sql语句打印

    session_factory = async_sessionmaker(engine, expire_on_commit=False)  # 异步环境下设置为False


async def dispose_engine():
    await engine.dispose()


async def main():
    await init_db_engine()

    async with session_factory() as session:  # async别漏
        result = await session.execute(text("select 1"))  # 防止sql注入
        print(result.fetchone())

    await dispose_engine()


import asyncio

if __name__ == '__main__':
    asyncio.run(main())
