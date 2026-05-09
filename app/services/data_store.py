from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Protocol


class TickRepository(Protocol):
    def save_tick(self, tick: Dict[str, Any]) -> None:
        ...


class BarRepository(Protocol):
    def save_bar(self, bar: Dict[str, Any], interval: str) -> None:
        ...


class MarketDataStore:
    def __init__(
        self,
        tick_repository: Optional[TickRepository] = None,
        bar_repository: Optional[BarRepository] = None,
        bar_interval: str = "1m",
    ):
        self.current_tick: Dict[str, Any] = {
            "symbol": None,
            "price": 0.0,
            "bid": None,
            "ask": None,
            "volume": 0,
            "timestamp": None,
            "source": None,
        }
        self.current_bar: Optional[Dict[str, Any]] = None
        self.tick_repository = tick_repository
        self.bar_repository = bar_repository
        self.bar_interval = bar_interval

    def update_tick(self, tick: Dict[str, Any]) -> Dict[str, Any]:
        # Tick data is used by execution and risk layers; bar data is used by strategy logic.
        normalized_tick = {
            "symbol": tick.get("symbol"),
            "price": tick.get("price"),
            "bid": tick.get("bid"),
            "ask": tick.get("ask"),
            "volume": tick.get("volume", tick.get("size", 0)),
            "timestamp": tick.get("timestamp") or datetime.now(timezone.utc).isoformat(),
            "source": tick.get("source", "unknown"),
        }

        self.current_tick = normalized_tick

        if self.tick_repository:
            self.tick_repository.save_tick(normalized_tick)

        return normalized_tick

    def update_bar(self, bar: Dict[str, Any], interval: Optional[str] = None) -> Dict[str, Any]:
        self.current_bar = bar
        if self.bar_repository:
            self.bar_repository.save_bar(bar, interval=interval or self.bar_interval)
        return bar

    def fetch_recent_bars(self, symbol: str, interval: str, limit: int) -> List[Dict[str, Any]]:
        repo = self.bar_repository
        if not repo or not hasattr(repo, "fetch_recent_bars"):
            return []
        return repo.fetch_recent_bars(symbol=symbol, interval=interval, limit=limit)

    def market_summary(self):
        latest_price = None
        if self.current_bar and self.current_bar.get("close") is not None:
            latest_price = self.current_bar.get("close")
        elif self.current_tick.get("price") is not None:
            latest_price = self.current_tick.get("price")

        return {
            "symbol": self.current_tick.get("symbol") or (self.current_bar.get("symbol") if self.current_bar else None),
            "latest_price": latest_price,
            "tick": self.current_tick,
            "bar": self.current_bar,
        }


class NewsStore:
    def __init__(self):
        self.latest_news = []

    def update(self):
        # TODO: Add news ingestion.
        self.latest_news = [{"title": "Market headline", "source": "news"}]

    def recent(self):
        return self.latest_news


class SignalStore:
    def __init__(self):
        self._signals: Dict[str, Any] = {}
        self._indicators: Dict[str, Any] = {}
        self._last_run: Optional[str] = None

    def update(self, signals: Dict[str, Any], indicators: Optional[Dict[str, Any]] = None, last_run: Optional[str] = None) -> Dict[str, Any]:
        self._signals = dict(signals or {})
        if indicators is not None:
            self._indicators = dict(indicators or {})
        if last_run is not None:
            self._last_run = last_run
        return self._signals

    def summary(self) -> Dict[str, Any]:
        return {
            "signals": dict(self._signals),
            "indicators": dict(self._indicators),
            "last_run": self._last_run,
        }


class FeatureStore:
    def __init__(self):
        self.current: Dict[str, Any] = {}
        self.history = []
        self._last_run: Optional[str] = None

    def update(self, features: Dict[str, Any], last_run: Optional[str] = None) -> Dict[str, Any]:
        snapshot = dict(features or {})
        self.current = snapshot
        if last_run is not None:
            self._last_run = last_run
        self.history.append(
            {
                "timestamp": last_run,
                "features": snapshot,
            }
        )
        # Keep memory bounded for UI/API usage.
        if len(self.history) > 500:
            self.history = self.history[-500:]
        return self.current

    def summary(self) -> Dict[str, Any]:
        return {
            "features": dict(self.current),
            "last_run": self._last_run,
        }


class HistoricalStore:
    def __init__(self):
        self.documents = []

    def load(self):
        # TODO: Load historical market, strategy, and position context for RAG.
        self.documents = [{"id": "history-1", "text": "Historical market context."}]

    def get_documents(self):
        return self.documents
