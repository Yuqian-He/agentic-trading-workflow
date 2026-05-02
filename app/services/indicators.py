from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, Optional, Callable, Tuple


class IndicatorEngine:
    def __init__(self):
        self._indicator_handlers: Dict[str, Callable[[Optional[Dict[str, Any]]], Tuple[Any, Any]]] = {
            "sma": self._calculate_sma,
            "rsi": self._calculate_rsi,
        }

    def _calculate_sma(self, current_bar: Optional[Dict[str, Any]]) -> Tuple[float, str]:
        if not current_bar:
            sma = 100.0
        else:
            sma = float(current_bar.get("close", 0.0))
        signal = "buy" if sma > 100 else "sell"
        return sma, signal

    def _calculate_rsi(self, current_bar: Optional[Dict[str, Any]]) -> Tuple[float, str]:
        # TODO: Replace with real RSI calculation using bar history.
        rsi = 50.0
        if rsi > 70:
            signal = "overbought"
        elif rsi < 30:
            signal = "oversold"
        else:
            signal = "neutral"
        return rsi, signal

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
