from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, Optional, Callable, Tuple, List
from .sma_indicator import SMAIndicator
from .rsi_indicator import RSIIndicator


class IndicatorEngine:
    def __init__(self, bar_fetcher: Optional[Callable[[str, str, int], List[Dict[str, Any]]]] = None):
        self._indicator_inputs: Dict[str, Dict[str, Any]] = {
            "sma": {"source": "close", "length": 20, "timeframe": "chart"},
            "rsi": {"length": 14, "source": "close", "overbought": 70, "oversold": 30, "timeframe": "chart"},
        }
        self._sma_indicator = SMAIndicator(
            bar_fetcher=bar_fetcher,
            default_config=self._indicator_inputs["sma"],
        )
        self._rsi_indicator = RSIIndicator(
            bar_fetcher=bar_fetcher,
            default_config=self._indicator_inputs["rsi"],
        )
        self._indicator_handlers: Dict[str, Callable[[Optional[Dict[str, Any]]], Tuple[Any, Any]]] = {
            "sma": self._calculate_sma,
            "rsi": self._calculate_rsi,
        }

    def set_inputs(self, indicator_inputs: Dict[str, Dict[str, Any]]) -> None:
        merged = dict(self._indicator_inputs)
        for name, values in (indicator_inputs or {}).items():
            if name not in merged or not isinstance(values, dict):
                continue
            merged[name] = {**merged[name], **values}
        self._indicator_inputs = merged
        self._sma_indicator.set_config(self._indicator_inputs.get("sma", {}))
        self._rsi_indicator.set_config(self._indicator_inputs.get("rsi", {}))

    def get_inputs(self) -> Dict[str, Dict[str, Any]]:
        return {name: dict(values) for name, values in self._indicator_inputs.items()}

    def set_runtime_context(self, symbol: Optional[str], interval: Optional[str]) -> None:
        self._sma_indicator.set_runtime_context(symbol, interval)
        self._rsi_indicator.set_runtime_context(symbol, interval)

    def _calculate_sma(self, current_bar: Optional[Dict[str, Any]]) -> Tuple[Optional[float], str]:
        return self._sma_indicator.calculate(current_bar)

    def _calculate_rsi(self, current_bar: Optional[Dict[str, Any]]) -> Tuple[Optional[float], str]:
        return self._rsi_indicator.calculate(current_bar)

    def calculate_all(self, current_bar: Optional[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        indicators: Dict[str, Any] = {}
        signals: Dict[str, Any] = {}
        if not self._indicator_handlers:
            return {"indicators": indicators, "signals": signals}

        with ThreadPoolExecutor(max_workers=len(self._indicator_handlers)) as executor:
            future_map = {
                executor.submit(handler, current_bar): indicator_name
                for indicator_name, handler in self._indicator_handlers.items()
            }

            for future in as_completed(future_map):
                indicator_name = future_map[future]
                indicator_value, signal_value = future.result()
                indicators[indicator_name] = indicator_value
                signals[f"{indicator_name}_signal"] = signal_value

        return {"indicators": indicators, "signals": signals}
