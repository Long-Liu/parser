import os
from dataclasses import dataclass

import yaml


@dataclass(frozen=True)
class Config:
    DEBUG: bool
    DB_HOST: str
    DB_PORT: int
    DB_USER: str
    DB_PASSWORD: str
    DB_NAME: str
    DB_POOL_SIZE: int
    SECRET_KEY: str
    JWT_EXPIRY_HOURS: int

    @property
    def DB_URL(self) -> str:
        return (
            f"mysql+aiomysql://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}?charset=utf8mb4"
        )


def load_config(env: str = None) -> Config:
    """启动时调用一次，加载指定环境的 YAML 配置"""
    env = env or os.getenv("APP_ENV", "local")
    path = os.path.join(os.path.dirname(__file__), "..", "config", f"{env}.yaml")

    if not os.path.exists(path):
        raise FileNotFoundError(f"Config not found: {path}")

    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    return Config(
        DEBUG=data.get("debug", False),
        DB_HOST=data["db"]["host"],
        DB_PORT=data["db"]["port"],
        DB_USER=data["db"]["user"],
        DB_PASSWORD=data["db"]["password"],
        DB_NAME=data["db"]["database"],
        DB_POOL_SIZE=data["db"]["pool_size"],
        SECRET_KEY=data["jwt"]["secret"],
        JWT_EXPIRY_HOURS=data["jwt"]["expiry_hours"],
    )