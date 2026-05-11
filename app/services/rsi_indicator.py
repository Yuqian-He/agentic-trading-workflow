from collections import deque
from typing import Any, Callable, Dict, List, Optional, Tuple


class RSIIndicator:
    def __init__(
        self,
        bar_fetcher: Optional[Callable[[str, str, int], List[Dict[str, Any]]]] = None,
        default_config: Optional[Dict[str, Any]] = None,
    ):
        self._bar_fetcher = bar_fetcher
        self._runtime_symbol: Optional[str] = None
        self._runtime_interval: Optional[str] = None
        self._config: Dict[str, Any] = dict(
            default_config
            or {
                "length": 14,
                "source": "close",
                "overbought": 70,
                "oversold": 30,
                "timeframe": "chart",
                "neutral_low": 40,
                "neutral_high": 60,
                "cooldown_bars": 3,
            }
        )
        self._states: Dict[str, Dict[str, Any]] = {}

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

    def clear_state(self) -> None:
        self._states.clear()

    def _resolve_source_value(self, bar: Optional[Dict[str, Any]], source: str) -> Optional[float]:
        if not bar:
            return None
        source = (source or "close").lower()
        o = self._safe_positive_float(bar.get("open"))
        h = self._safe_positive_float(bar.get("high"))
        l = self._safe_positive_float(bar.get("low"))
        c = self._safe_positive_float(bar.get("close"))
        if source == "open":
            return o
        if source == "high":
            return h
        if source == "low":
            return l
        if source == "hl2":
            if h is None or l is None:
                return None
            return (h + l) / 2.0
        if source == "ohlc4":
            if o is None or h is None or l is None or c is None:
                return None
            return (o + h + l + c) / 4.0
        return c

    @staticmethod
    def _safe_positive_float(value: Any) -> Optional[float]:
        try:
            if value is None:
                return None
            v = float(value)
            if v <= 0:
                return None
            return v
        except (TypeError, ValueError):
            return None

    def _new_state(self, length: int) -> Dict[str, Any]:
        return {
            "last_price": None,
            "avg_gain": None,
            "avg_loss": None,
            "warmup_gains": deque(maxlen=length),
            "warmup_losses": deque(maxlen=length),
            "initialized": False,
            "current_rsi": None,
            "last_timestamp": None,
            "last_signal": None,
            "cooldown": 0,
        }

    def _rsi_from_avg(self, avg_gain: float, avg_loss: float) -> float:
        if avg_loss == 0 and avg_gain == 0:
            return 50.0
        if avg_loss == 0:
            return 100.0
        rs = avg_gain / avg_loss
        return 100.0 - (100.0 / (1.0 + rs))

    def _update_state_with_price(self, state: Dict[str, Any], price: float, length: int) -> Optional[float]:
        last_price = state.get("last_price")
        if last_price is None:
            state["last_price"] = price
            return None

        delta = price - float(last_price)
        gain = max(delta, 0.0)
        loss = max(-delta, 0.0)
        state["last_price"] = price

        if not state.get("initialized"):
            warmup_gains: deque = state["warmup_gains"]
            warmup_losses: deque = state["warmup_losses"]
            warmup_gains.append(gain)
            warmup_losses.append(loss)
            if len(warmup_gains) < length:
                return None

            avg_gain = sum(warmup_gains) / float(length)
            avg_loss = sum(warmup_losses) / float(length)
            state["avg_gain"] = avg_gain
            state["avg_loss"] = avg_loss
            state["initialized"] = True
            state["current_rsi"] = self._rsi_from_avg(avg_gain, avg_loss)
            return state["current_rsi"]

        avg_gain = float(state["avg_gain"])
        avg_loss = float(state["avg_loss"])
        avg_gain = ((avg_gain * (length - 1)) + gain) / float(length)
        avg_loss = ((avg_loss * (length - 1)) + loss) / float(length)
        state["avg_gain"] = avg_gain
        state["avg_loss"] = avg_loss
        state["current_rsi"] = self._rsi_from_avg(avg_gain, avg_loss)
        return state["current_rsi"]

    def _bootstrap_state_from_prices(self, state: Dict[str, Any], prices: List[float], length: int) -> Optional[float]:
        if len(prices) < length + 1:
            return None
        state["last_price"] = None
        state["avg_gain"] = None
        state["avg_loss"] = None
        state["warmup_gains"] = deque(maxlen=length)
        state["warmup_losses"] = deque(maxlen=length)
        state["initialized"] = False
        state["current_rsi"] = None
        rsi: Optional[float] = None
        for price in prices:
            rsi = self._update_state_with_price(state, float(price), length)
        return rsi

    def _format_level(self, level: float) -> str:
        if float(level).is_integer():
            return str(int(level))
        return str(level)

    def _cross_signal(self, prev_rsi: Optional[float], rsi: float, overbought: float, oversold: float) -> str:
        if prev_rsi is None:
            return "hold"
        ob = self._format_level(overbought)
        os = self._format_level(oversold)

        if prev_rsi <= overbought < rsi:
            return f"rsi_cross_up_{ob}"
        if prev_rsi >= overbought > rsi:
            return f"rsi_cross_down_{ob}"
        if prev_rsi >= oversold > rsi:
            return f"rsi_cross_down_{os}"
        if prev_rsi <= oversold < rsi:
            return f"rsi_cross_up_{os}"
        return "hold"

    def _apply_signal_controls(
        self,
        state: Dict[str, Any],
        signal: str,
        rsi: float,
        neutral_low: float,
        neutral_high: float,
        cooldown_bars: int,
    ) -> str:
        cooldown = int(state.get("cooldown", 0))
        if cooldown > 0:
            state["cooldown"] = cooldown - 1
            return "hold"

        if neutral_low < rsi < neutral_high:
            return "hold"

        if signal != "hold":
            state["last_signal"] = signal
            state["cooldown"] = max(0, int(cooldown_bars))
        return signal

    def calculate(self, current_bar: Optional[Dict[str, Any]]) -> Tuple[Optional[float], str]:
        source = str(self._config.get("source", "close"))
        timeframe = str(self._config.get("timeframe", "chart"))
        try:
            length = max(1, int(self._config.get("length", 14)))
        except Exception:
            length = 14
        try:
            overbought = float(self._config.get("overbought", 70))
        except Exception:
            overbought = 70.0
        try:
            oversold = float(self._config.get("oversold", 30))
        except Exception:
            oversold = 30.0
        try:
            neutral_low = float(self._config.get("neutral_low", 40))
        except Exception:
            neutral_low = 40.0
        try:
            neutral_high = float(self._config.get("neutral_high", 60))
        except Exception:
            neutral_high = 60.0
        try:
            cooldown_bars = max(0, int(self._config.get("cooldown_bars", 3)))
        except Exception:
            cooldown_bars = 3

        if overbought <= oversold:
            return None, "hold"

        symbol = self._runtime_symbol or (current_bar or {}).get("symbol")
        effective_interval = self._runtime_interval if timeframe == "chart" else timeframe
        state_key = f"{symbol}|{effective_interval}|{source}|{length}"
        state = self._states.get(state_key)
        if state is None:
            state = self._new_state(length)
            self._states[state_key] = state

        prev_rsi = state.get("current_rsi")

        if timeframe != "chart":
            if not self._bar_fetcher or not symbol or not effective_interval:
                return None, "hold"
            bars = self._bar_fetcher(symbol, effective_interval, max(length + 1, length * 3))
            if not bars:
                return None, "hold"
            latest_ts = bars[-1].get("timestamp")
            if latest_ts and latest_ts == state.get("last_timestamp"):
                current_rsi = state.get("current_rsi")
                if current_rsi is None:
                    return None, "hold"
                return float(current_rsi), "hold"
            latest_price = self._resolve_source_value(bars[-1], source)
            if latest_price is None:
                return None, "hold"

            if state.get("initialized"):
                rsi = self._update_state_with_price(state, float(latest_price), length)
                if rsi is None:
                    return None, "hold"
            else:
                prices: List[float] = []
                for bar in bars:
                    value = self._resolve_source_value(bar, source)
                    if value is None:
                        return None, "hold"
                    prices.append(value)
                rsi = self._bootstrap_state_from_prices(state, prices, length)
                if rsi is None:
                    return None, "hold"
            state["last_timestamp"] = latest_ts
        else:
            price = self._resolve_source_value(current_bar, source)
            if price is None:
                return None, "hold"
            current_ts = (current_bar or {}).get("timestamp")
            if current_ts and current_ts == state.get("last_timestamp"):
                current_rsi = state.get("current_rsi")
                if current_rsi is None:
                    return None, "hold"
                return float(current_rsi), "hold"
            rsi = self._update_state_with_price(state, float(price), length)
            if rsi is None:
                return None, "hold"
            state["last_timestamp"] = current_ts

        signal = self._cross_signal(prev_rsi, rsi, overbought, oversold)
        signal = self._apply_signal_controls(
            state=state,
            signal=signal,
            rsi=rsi,
            neutral_low=neutral_low,
            neutral_high=neutral_high,
            cooldown_bars=cooldown_bars,
        )
        return rsi, signal
