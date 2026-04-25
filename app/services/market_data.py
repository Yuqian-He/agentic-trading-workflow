import asyncio
import math
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Protocol


class MarketDataSource(Protocol):
    async def connect(self) -> None:
        ...

    async def close(self) -> None:
        ...

    async def next_tick(self) -> Dict[str, Any]:
        ...


class IBMarketDataSource:
    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 7497,
        client_id: int = 1,
        symbol: str = "AAPL",
        exchange: str = "SMART",
        currency: str = "USD",
        market_data_type: int = 3,
        account: Optional[str] = None,
    ):
        self.host = host
        self.port = port
        self.client_id = client_id
        self.symbol = symbol
        self.exchange = exchange
        self.currency = currency
        self.market_data_type = market_data_type
        self.account = account
        self._ib = None
        self._contract = None
        self._ticker = None
        self._last_snapshot = None

    async def connect(self) -> None:
        try:
            from ib_insync import IB, Stock
            from ib_insync import client, connection, util
        except ImportError as exc:
            raise RuntimeError("ib_insync is required for IB market data. Install backend requirements first.") from exc

        self._patch_ib_insync_loop(util, client, connection)
        self._ib = IB()
        connect_kwargs = {
            "host": self.host,
            "port": self.port,
            "clientId": self.client_id,
        }
        if self.account:
            connect_kwargs["account"] = self.account

        await self._ib.connectAsync(**connect_kwargs)
        self._contract = Stock(self.symbol, self.exchange, self.currency)
        self._ib.reqMarketDataType(self.market_data_type)
        self._ticker = self._ib.reqMktData(self._contract, "", False, False)

    async def close(self) -> None:
        if self._ib and self._contract:
            self._ib.cancelMktData(self._contract)
        if self._ib and self._ib.isConnected():
            self._ib.disconnect()

    async def next_tick(self) -> Dict[str, Any]:
        if not self._ib or not self._ticker:
            raise RuntimeError("IB market data source is not connected.")

        while True:
            await self._ib.updateEvent
            normalized_tick = self._normalize_ticker()
            if normalized_tick and normalized_tick != self._last_snapshot:
                self._last_snapshot = normalized_tick
                return normalized_tick
            await asyncio.sleep(0.1)

    def _normalize_ticker(self) -> Optional[Dict[str, Any]]:
        bid = self._to_float(self._ticker.bid)
        ask = self._to_float(self._ticker.ask)
        last = self._to_float(self._ticker.last)
        close = self._to_float(self._ticker.close)
        market_price = self._to_float(self._ticker.marketPrice())
        volume = self._to_non_negative_float(self._ticker.volume) or 0
        price = last or market_price or close

        if price is None and bid is not None and ask is not None:
            price = (bid + ask) / 2
        if price is None:
            price = bid or ask
        if price is None:
            return None

        return {
            "symbol": self.symbol,
            "price": price,
            "bid": bid,
            "ask": ask,
            "volume": volume,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "source": "ib_delayed_market_data" if self.market_data_type in (3, 4) else "ib_market_data",
        }

    @staticmethod
    def _timestamp_to_iso(value):
        if value is None:
            return datetime.now(timezone.utc).isoformat()
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc).isoformat()
        return value.astimezone(timezone.utc).isoformat()

    @staticmethod
    def _to_float(value):
        if value is None:
            return None
        value = float(value)
        if math.isnan(value) or math.isinf(value) or value < 0:
            return None
        return value

    @classmethod
    def _to_non_negative_float(cls, value):
        return cls._to_float(value)

    @staticmethod
    def _patch_ib_insync_loop(util, client, connection) -> None:
        def get_running_loop():
            return asyncio.get_running_loop()

        util.getLoop = get_running_loop
        client.getLoop = get_running_loop
        connection.getLoop = get_running_loop
