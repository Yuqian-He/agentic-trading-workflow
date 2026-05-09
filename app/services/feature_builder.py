from typing import Any, Dict, List, Optional


class FeatureBuilder:
    """Build market-state features from current/historical numeric inputs.

    This layer is intentionally deterministic and AI-free.
    """

    def build(
        self,
        bar: Optional[Dict[str, Any]],
        indicators: Optional[Dict[str, Any]],
        indicator_features: Optional[Dict[str, Any]] = None,
        history: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        indicators = indicators or {}
        indicator_features = indicator_features or {}
        bar = bar or {}
        history = history or []

        close = self._as_float(bar.get("close"))
        sma = self._as_float(indicators.get("sma"))
        rsi = self._as_float(indicators.get("rsi"))
        volume = self._as_float(bar.get("volume"))
        avg_volume = self._avg_volume(history)

        trend = "unknown"
        if close is not None and sma is not None:
            trend = "uptrend" if close >= sma else "downtrend"

        rsi_state = "unknown"
        if rsi is not None:
            if rsi >= 70:
                rsi_state = "overbought"
            elif rsi <= 30:
                rsi_state = "oversold"
            else:
                rsi_state = "neutral"

        price_vs_sma = "unknown"
        if close is not None and sma is not None:
            price_vs_sma = "above" if close >= sma else "below"

        volume_spike = False
        if volume is not None and avg_volume is not None and avg_volume > 0:
            volume_spike = volume >= (avg_volume * 1.5)

        features = {
            "trend": trend,
            "rsi": rsi,
            "rsi_state": rsi_state,
            "price_vs_sma": price_vs_sma,
            "volume_spike": volume_spike,
            # News sentiment should come from NLP output; fallback keeps contract stable.
            "news_sentiment": "unknown",
        }
        # Merge per-indicator semantic states (for example rsi_state / sma_state)
        # while preserving explicit global keys defined above.
        for key, value in indicator_features.items():
            if key not in features:
                features[key] = value
        return features

    @staticmethod
    def _as_float(value: Any) -> Optional[float]:
        try:
            if value is None:
                return None
            return float(value)
        except (TypeError, ValueError):
            return None

    def _avg_volume(self, history: List[Dict[str, Any]]) -> Optional[float]:
        volumes = [self._as_float(item.get("volume")) for item in history if isinstance(item, dict)]
        clean = [v for v in volumes if v is not None]
        if not clean:
            return None
        return sum(clean) / len(clean)
