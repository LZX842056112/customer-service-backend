from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    database_url: str = os.getenv(
        "DATABASE_URL",
        "mysql+pymysql://atguigu:Atguigu.123@192.168.200.145:3306/commerce?charset=utf8mb4",
    )
    app_host: str = os.getenv("APP_HOST", "0.0.0.0")
    app_port: int = int(os.getenv("APP_PORT", "18081"))


settings = Settings()
