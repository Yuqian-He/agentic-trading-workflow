from collections import deque
from typing import Any, Callable, Dict, List, Optional, Tuple


class SMAIndicator:
    def __init__(
        self,
        bar_fetcher: Optional[Callable[[str, str, int], List[Dict[str, Any]]]] = None,
        default_config: Optional[Dict[str, Any]] = None,
    ):
        self._bar_fetcher = bar_fetcher
        self._runtime_symbol: Optional[str] = None
        self._runtime_interval: Optional[str] = None
        self._config: Dict[str, Any] = dict(default_config or {"source": "close", "length": 20, "timeframe": "chart"})
        self._price_buffers: Dict[str, deque] = {}
        self._rolling_sums: Dict[str, float] = {}

    def set_runtime_context(self, symbol: Optional[str], interval: Optional[str]) -> None:
        symbol_changed = symbol != self._runtime_symbol
        interval_changed = interval != self._runtime_interval
        self._runtime_symbol = symbol
        self._runtime_interval = interval
        if symbol_changed or interval_changed:
            self.clear_state()

    def set_config(self, config: Dict[str, Any]) -> None:
        next_cfg = {**self._config, **(config or {})}
        if next_cfg != self._config:
            self._config = next_cfg
            self.clear_state()

    def get_config(self) -> Dict[str, Any]:
        return dict(self._config)

    def clear_state(self) -> None:
        self._price_buffers.clear()
        self._rolling_sums.clear()

    def _resolve_source_value(self, bar: Optional[Dict[str, Any]], source: str) -> Optional[float]:
        if not bar:
            return None
        source = (source or "close").lower()
        o = float(bar.get("open", 0.0))
        h = float(bar.get("high", 0.0))
        l = float(bar.get("low", 0.0))
        c = float(bar.get("close", 0.0))
        if source == "open":
            return o
        if source == "high":
            return h
        if source == "low":
            return l
        if source == "hl2":
            return (h + l) / 2.0
        if source == "ohlc4":
            return (o + h + l + c) / 4.0
        return c

    def calculate(self, current_bar: Optional[Dict[str, Any]]) -> Tuple[Optional[float], str]:
        source = str(self._config.get("source", "close"))
        try:
            length = max(1, int(self._config.get("length", 20)))
        except Exception:
            length = 20
        timeframe = str(self._config.get("timeframe", "chart"))
        symbol = self._runtime_symbol or (current_bar or {}).get("symbol")
        effective_interval = self._runtime_interval if timeframe == "chart" else timeframe

        if timeframe != "chart":
            if not self._bar_fetcher or not symbol or not effective_interval:
                return None, "hold"
            bars = self._bar_fetcher(symbol, effective_interval, length)
            if len(bars) < length:
                return None, "hold"
            prices: List[float] = []
            for bar in bars:
                value = self._resolve_source_value(bar, source)
                if value is None:
                    return None, "hold"
                prices.append(value)
            sma = sum(prices) / float(length)
            price = prices[-1]
            if price > sma:
                return sma, "buy"
            if price < sma:
                return sma, "sell"
            return sma, "hold"

        price = self._resolve_source_value(current_bar, source)
        if price is None:
            return None, "hold"

        buffer_key = f"{symbol}|{effective_interval}|{source}|{length}"
        if buffer_key not in self._price_buffers:
            self._price_buffers[buffer_key] = deque(maxlen=length)
            self._rolling_sums[buffer_key] = 0.0

        bucket = self._price_buffers[buffer_key]
        rolling_sum = self._rolling_sums[buffer_key]
        if len(bucket) == bucket.maxlen:
            rolling_sum -= bucket[0]
        bucket.append(price)
        rolling_sum += price
        self._rolling_sums[buffer_key] = rolling_sum

        if len(bucket) < length:
            return None, "hold"

        sma = rolling_sum / float(length)
        if price > sma:
            return sma, "buy"
        if price < sma:
            return sma, "sell"
        return sma, "hold"
