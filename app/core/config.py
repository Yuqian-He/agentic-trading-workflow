from pydantic import BaseSettings


class Settings(BaseSettings):
    app_name: str = "Trading Workflow AI"
    environment: str = "development"
    host: str = "0.0.0.0"
    port: int = 8000
    agent_interval_seconds: int = 30
    rag_index_path: str = "data/vecstore.index"
    openai_api_key: str = ""

    class Config:
        env_file = ".env"


settings = Settings()
