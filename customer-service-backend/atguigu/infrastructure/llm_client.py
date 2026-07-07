"""
llm的客户端
init_chat_model()  # 1.x 版本之后的写法
ChatOpenAI() # 1.x 版本的写法

PEP8(coding标准 建议遵循)
1. 基础包 from pathlib import Path
2. 三方包  from langchain.chat_models import init_chat_model
3. 自己定义的包
"""
from langchain.chat_models import init_chat_model
from langchain_core.language_models import BaseChatModel
from atguigu.config.settings import settings

llm_client: BaseChatModel = init_chat_model(
    model=settings.llm_model,
    model_provider="openai",
    base_url=settings.llm_base_url,
    api_key=settings.llm_api_key,
    temperature=0,  # 尽最大努力保证输出的稳定性
    timeout=120
)

if __name__ == '__main__':
    response = llm_client.invoke("你好，我现在心情不好，给我讲一个幽默的笑话，确保能让我笑")

    print(response.content)
