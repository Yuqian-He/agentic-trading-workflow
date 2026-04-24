from typing import Dict, Any

from .data_store import HistoricalStore


class RAGService:
    def __init__(self, historical_store: HistoricalStore):
        self.historical_store = historical_store
        self.historical_store.load()

    def build_context(self, signals: Dict[str, Any]) -> Dict[str, Any]:
        # TODO: 将市场摘要、信号摘要、新闻和历史检索结果组合成上下文
        return {
            "market": signals,
            "history": self.historical_store.get_documents(),
            "news": [],
        }
