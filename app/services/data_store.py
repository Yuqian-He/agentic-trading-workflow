from datetime import datetime, timezone
from typing import Any, Dict, Optional, Protocol


class TickRepository(Protocol):
    def save_tick(self, tick: Dict[str, Any]) -> None:
        ...


class MarketDataStore:
    def __init__(self, tick_repository: Optional[TickRepository] = None):
        self.current = {
            "symbol": None,
            "price": 0.0,
            "bid": None,
            "ask": None,
            "volume": 0,
            "timestamp": None,
            "source": None,
        }
        self.signals = {"sma": None, "rsi": None}
        self.tick_repository = tick_repository

    def update_tick(self, tick: Dict[str, Any]) -> Dict[str, Any]:
        # Tick data is used by execution and risk layers; indicators use bar data.
        normalized_tick = {
            "symbol": tick.get("symbol"),
            "price": tick.get("price"),
            "bid": tick.get("bid"),
            "ask": tick.get("ask"),
            "volume": tick.get("volume", tick.get("size", 0)),
            "timestamp": tick.get("timestamp") or datetime.now(timezone.utc).isoformat(),
            "source": tick.get("source", "unknown"),
        }

        self.current = normalized_tick

        if self.tick_repository:
            self.tick_repository.save_tick(normalized_tick)

        return normalized_tick

    def get_indicators(self):
        # TODO: Calculate indicators from bar data, such as SMA and RSI.
        return {"sma": 100.0, "rsi": 50.0}

    def current_signals(self):
        return self.signals

    def market_summary(self):
        return {
            "ticker": self.current["symbol"],
            "price": self.current["price"],
            "bid": self.current["bid"],
            "ask": self.current["ask"],
            "volume": self.current["volume"],
            "timestamp": self.current["timestamp"],
        }

    def signals_summary(self):
        return self.signals

    def execute_order(self, decision: Dict[str, Any]):
        # TODO: Implement simulated or IB order execution.
        print(f"Executing order: {decision}")


class NewsStore:
    def __init__(self):
        self.latest_news = []

    def update(self):
        # TODO: Add news ingestion.
        self.latest_news = [{"title": "Market headline", "source": "news"}]

    def recent(self):
        return self.latest_news


class HistoricalStore:
    def __init__(self):
        self.documents = []

    def load(self):
        # TODO: Load historical market, strategy, and position context for RAG.
        self.documents = [{"id": "history-1", "text": "Historical market context."}]

    def get_documents(self):
        return self.documents
