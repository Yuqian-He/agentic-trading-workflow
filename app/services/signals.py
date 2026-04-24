from typing import Dict, Any


class SignalsEngine:
    def __init__(self):
        # 初始化策略，如 SMA, RSI
        pass

    def generate(self, indicators: Dict[str, Any]) -> Dict[str, Any]:
        # 基于 indicators 生成 signals
        signals = {}
        if "sma" in indicators:
            signals["sma_signal"] = "buy" if indicators["sma"] > 100 else "sell"
        if "rsi" in indicators:
            signals["rsi_signal"] = "overbought" if indicators["rsi"] > 70 else "oversold" if indicators["rsi"] < 30 else "neutral"
        return signals