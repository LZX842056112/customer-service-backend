"""
.env中的信息 收集到配置类中
"""
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT_DIR = Path(__file__).resolve().parents[2]
ENV_FILE_PATH = PROJECT_ROOT_DIR / ".env"


class Settings(BaseSettings):
    """
    BaseSetting(利用Pydantic机制对配置信息做类型的校验、配置信息类型做转换)

    LLM_MODEL=qwen-plus
    LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
    LLM_API_KEY=sk-983bea5e73584a92950148b7df36a4b0
    COMMERCE_API_BASE_URL=http://192.168.200.125:18081
    DATABASE_URL=mysql+aiomysql://root:root@localhost:3306/customer_service?charset=utf8mb4
    APP_HOST=0.0.0.0
    APP_PORT=18082
    """
    llm_model: str  # 类型str,且是必填参数
    llm_base_url: str
    llm_api_key: str
    commerce_api_base_url: str
    database_url: str
    app_host: str
    app_port: int

    model_config=SettingsConfigDict(env_file=ENV_FILE_PATH, env_file_encoding="utf-8", extra="ignore")  # extra="ignore"


settings = Settings()  # type: ignore

if __name__ == '__main__':
    print(settings.llm_base_url)
