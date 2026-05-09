from typing import List

from ..core.config import settings
from .market_data import IBBarDataSource


class UISettingsService:
    @staticmethod
    def ticker_options() -> List[str]:
        raw_items = (settings.ib_ticker_options_csv or "").split(",")
        parsed = [item.strip().upper() for item in raw_items if item and item.strip()]
        return parsed or ["QQQ", "AAPL", "MSFT"]

    @staticmethod
    def bar_interval_options() -> List[str]:
        return IBBarDataSource.supported_intervals()
