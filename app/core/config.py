try:
    from pydantic_settings import BaseSettings
except ImportError:
    from pydantic.v1 import BaseSettings


class Settings(BaseSettings):
    app_name: str = "Trading Workflow AI"
    environment: str = "development"
    host: str = "0.0.0.0"
    port: int = 8000
    agent_interval_seconds: int = 30
    rag_index_path: str = "data/vecstore.index"
    openai_api_key: str = ""
    ib_host: str = "127.0.0.1"
    ib_port: int = 7497
    ib_client_id: int = 101
    ib_account: str = ""
    ib_symbol: str = "AAPL"
    ib_exchange: str = "SMART"
    ib_currency: str = "USD"
    ib_market_data_type: int = 3
    tick_db_path: str = "data/market_ticks.sqlite3"
    bar_db_path: str = "data/market_bars.sqlite3"

    class Config:
        env_file = ".env"


settings = Settings()
