import os
import yaml


def load_config(env: str = None):
    """启动时调用一次，加载指定环境的 YAML 配置"""
    env = env or os.getenv("APP_ENV", "local")
    path = os.path.join(os.path.dirname(__file__), "config", f"{env}.yaml")

    if not os.path.exists(path):
        raise FileNotFoundError(f"Config not found: {path}")

    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    class Config:
        DEBUG = data.get("debug", False)
        DB_HOST = data["db"]["host"]
        DB_PORT = data["db"]["port"]
        DB_USER = data["db"]["user"]
        DB_PASSWORD = data["db"]["password"]
        DB_NAME = data["db"]["database"]
        DB_POOL_SIZE = data["db"]["pool_size"]
        SECRET_KEY = data["jwt"]["secret"]
        JWT_EXPIRY_HOURS = data["jwt"]["expiry_hours"]

        @property
        def DB_URL(self):
            return f"mysql+aiomysql://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}?charset=utf8mb4"

    return Config()
