from typing import Annotated
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from atguigu.services.dialogue_service import DialogueService
from atguigu.engine.dialogue_engine import DialogueEngine
from atguigu.repository.dialogue_repository import DialogueRepository
from atguigu.infrastructure import db  # 没问题  相当于把整个模块导入过来
# from atguigu.infrastructure.db import session_factory  # 有bug  session_factory() 返回的是个None  只把模块的变量拷贝过来了。

"""
async通常修饰的都是名字 await 通常修饰的是通常是动词
导模块？模块的成员期初的时候没有初始值，而是一个默认值，且后续可能有人修改它。对于后续的使用者来说，就需要在自己的py模块中选择模块级别的导入
导入模块的成员呢? 模块的成员期初的时候已经有初始值，后续也不会在被别人修改。接下来使用者来，只需要在自己的py模块中选择模块成员级别的导入

"""


def get_engine():
    return DialogueEngine()


DialogueEngineDep = Annotated[DialogueEngine, Depends(get_engine)]


async def get_session():
    async with db.session_factory() as session:
        yield session  # FASTAPI 处理完请求（业务用完了）自动进入到该位置


RepositorySessionDep = Annotated[AsyncSession, Depends(get_session)]


def get_repository(session: RepositorySessionDep):
    return DialogueRepository(session=session)


DialogueRepositoryDep = Annotated[DialogueRepository, Depends(get_repository)]


def get_dialogue_service(engine: DialogueEngineDep,
                         repo: DialogueRepositoryDep
                         ):
    return DialogueService(
        repository=repo,
        engine=engine
    )


# Annotated:将类型以及类型的元素
DialogueServiceDep = Annotated[DialogueService, Depends(get_dialogue_service)]
