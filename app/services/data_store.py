from typing import Dict, Any


class MarketDataStore:
    def __init__(self):
        self.tick_count = 0
        self.current = {"price": 0.0, "volume": 0}
        self.signals = {"sma": None, "rsi": None}
        self.last_bar_ts = None

    def update_tick(self):
        self.tick_count += 1
        # TODO: 添加 IB 或历史市场数据采集逻辑
        self.current = {"price": 100.0 + self.tick_count * 0.1, "volume": 1000}
        self.signals = {"sma": "bullish", "rsi": "neutral"}

    def is_new_bar(self):
        # TODO: 检查是否新 bar（例如每分钟）
        return self.tick_count % 60 == 0  # 模拟每60 tick 新 bar

    def current_bar_timestamp(self):
        # TODO: 返回当前 bar 时间戳
        return self.tick_count // 60

    def get_indicators(self):
        # TODO: 计算 indicators 如 SMA, RSI
        return {"sma": 100.0, "rsi": 50.0}

    def current_signals(self):
        return self.signals

    def market_summary(self):
        return {"ticker": "AAPL", "price": self.current["price"], "volume": self.current["volume"]}

    def signals_summary(self):
        return self.signals

    def execute_order(self, decision: Dict[str, Any]):
        # TODO: IB 下单 / 模拟下单实现
        print(f"Executing order: {decision}")


class NewsStore:
    def __init__(self):
        self.latest_news = []

    def update(self):
        # TODO: 添加新闻采集逻辑
        self.latest_news = [{"title": "Market headline", "source": "news"}]

    def recent(self):
        return self.latest_news


class HistoricalStore:
    def __init__(self):
        self.documents = []

    def load(self):
        # TODO: 读取历史行情、策略、持仓等文档用于 RAG
        self.documents = [{"id": "history-1", "text": "Historical market context."}]

    def get_documents(self):
        return self.documents
