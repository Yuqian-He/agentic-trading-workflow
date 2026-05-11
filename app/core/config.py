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
    ib_client_id_fallback_span: int = 8
    ib_connect_timeout_seconds: int = 20
    ib_connect_retries: int = 3
    ib_connect_retry_delay_seconds: float = 1.5
    ib_account: str = ""
    ib_symbol: str = "QQQ"
    ib_exchange: str = "SMART"
    ib_currency: str = "USD"
    ib_market_data_type: int = 3
    ib_enable_synthetic_bars: bool = False
    historical_seed_enabled: bool = True
    historical_seed_file: str = "data/QQQ_full_1min_adjsplit 1.txt"
    historical_seed_symbol: str = "QQQ"
    historical_seed_interval: str = "1m"
    historical_seed_timezone: str = "America/New_York"
    ib_ticker_options_csv: str = "QQQ,AAPL,MSFT"
    tick_db_path: str = "data/market_ticks.sqlite3"
    bar_db_path: str = "data/market_bars.sqlite3"

    class Config:
        env_file = ".env"


settings = Settings()
