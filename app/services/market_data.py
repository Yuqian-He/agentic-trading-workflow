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


class BarDataSource(Protocol):
    async def connect(self) -> None:
        ...

    async def close(self) -> None:
        ...

    async def next_bar(self) -> Dict[str, Any]:
        ...


class IBConnection:
    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 7497,
        client_id: int = 1,
        account: Optional[str] = None,
    ):
        self.host = host
        self.port = port
        self.client_id = client_id
        self.account = account
        self._ib = None
        self._contract = None

    async def connect(self, symbol: str, exchange: str, currency: str) -> None:
        try:
            from ib_insync import IB, Stock
            from ib_insync import client, connection, util
        except ImportError as exc:
            raise RuntimeError("ib_insync is required for IB connection. Install backend requirements first.") from exc

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
        self._contract = Stock(symbol, exchange, currency)

    async def close(self) -> None:
        if self._ib and self._ib.isConnected():
            self._ib.disconnect()

    @property
    def ib(self):
        return self._ib

    @property
    def contract(self):
        return self._contract

    @staticmethod
    def _patch_ib_insync_loop(util, client, connection) -> None:
        def get_running_loop():
            return asyncio.get_running_loop()

        util.getLoop = get_running_loop
        client.getLoop = get_running_loop
        connection.getLoop = get_running_loop


class IBBarDataSource:
    BAR_INTERVAL_MAP = {
        "1m": "1 min",
        "3m": "3 mins",
        "5m": "5 mins",
        "15m": "15 mins",
        "30m": "30 mins",
        "45m": "45 mins",
        "1H": "1 hour",
        "2H": "2 hours",
        "3H": "3 hours",
        "4H": "4 hours",
    }

    @classmethod
    def supported_intervals(cls):
        return list(cls.BAR_INTERVAL_MAP.keys())

    def __init__(
        self,
        ib_connection: IBConnection,
        bar_interval: str = "1m",
    ):
        self.ib_connection = ib_connection
        self.bar_interval = bar_interval
        self.bar_size_setting = self._translate_interval(bar_interval)
        self._last_emitted_timestamp: Optional[str] = None

    @classmethod
    def interval_seconds(cls, interval: str) -> int:
        # Keep in sync with BAR_INTERVAL_MAP keys.
        if interval.endswith("m"):
            return int(interval[:-1]) * 60
        if interval.endswith("H"):
            return int(interval[:-1]) * 60 * 60
        raise ValueError(f"Unsupported bar interval: {interval}")

    @classmethod
    def _translate_interval(cls, interval: str) -> str:
        if interval not in cls.BAR_INTERVAL_MAP:
            raise ValueError(f"Unsupported bar interval: {interval}")
        return cls.BAR_INTERVAL_MAP[interval]

    def set_bar_interval(self, interval: str):
        self.bar_interval = interval
        self.bar_size_setting = self._translate_interval(interval)
        self._last_emitted_timestamp = None

    async def connect(self) -> None:
        # Connection is managed externally by IBConnection.
        if self.ib_connection.ib is None or self.ib_connection.contract is None:
            raise RuntimeError("IB connection is not established.")
        # For demo mode (no paid subscriptions), we avoid realtime bar streams and
        # instead poll historical bars using delayed market data (reqMarketDataType=3).
        self.ib_connection.ib.reqMarketDataType(3)

    async def close(self) -> None:
        # Connection close is handled by the shared IBConnection.
        self._last_emitted_timestamp = None

    def _duration_str_for_interval(self) -> str:
        # IB expects integer{SPACE}unit where unit is S|D|W|M|Y (no "H").
        seconds = self.interval_seconds(self.bar_interval)
        # Pull a small window that should always contain the latest completed bar.
        if seconds <= 15 * 60:
            return "7200 S"  # 2 hours
        if seconds <= 60 * 60:
            return "1 D"
        return "2 D"

    async def next_bar(self) -> Dict[str, Any]:
        if not self.ib_connection.ib or not self.ib_connection.contract:
            raise RuntimeError("IB bar data source is not connected.")
        while True:
            bar = await self.fetch_latest_bar()

            if not bar:
                await asyncio.sleep(1)
                continue

            # Only emit once per new bar timestamp (matches "each interval store one bar").
            ts = bar.get("timestamp")
            if ts and ts != self._last_emitted_timestamp:
                self._last_emitted_timestamp = ts
                return bar

            # Not a new bar yet — wait until next boundary for this interval.
            await asyncio.sleep(self._seconds_until_next_boundary())

    async def fetch_latest_bar(self) -> Optional[Dict[str, Any]]:
        if not self.ib_connection.ib or not self.ib_connection.contract:
            raise RuntimeError("IB bar data source is not connected.")

        bars = await self.ib_connection.ib.reqHistoricalDataAsync(
            self.ib_connection.contract,
            endDateTime="",
            durationStr=self._duration_str_for_interval(),
            barSizeSetting=self.bar_size_setting,
            whatToShow="TRADES",
            useRTH=False,
            formatDate=1,
            keepUpToDate=False,
        )

        if not bars:
            return None

        latest = bars[-1]
        return {
            "symbol": self.ib_connection.contract.symbol,
            "open": self._to_float(latest.open),
            "high": self._to_float(latest.high),
            "low": self._to_float(latest.low),
            "close": self._to_float(latest.close),
            "volume": int(latest.volume or 0),
            "timestamp": self._timestamp_to_iso(latest.date),
            "source": "ib_delayed_historical_bar",
        }

    @staticmethod
    def _timestamp_to_iso(value):
        if value is None:
            return datetime.now(timezone.utc).isoformat()
        if isinstance(value, str):
            return datetime.fromisoformat(value).astimezone(timezone.utc).isoformat()
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

    def _seconds_until_next_boundary(self) -> float:
        seconds = self.interval_seconds(self.bar_interval)
        now = datetime.now(timezone.utc).timestamp()
        next_boundary = ((int(now) // seconds) + 1) * seconds
        return max(0.25, next_boundary - now)

    @staticmethod
    def _to_non_negative_float(value):
        return IBMarketDataSource._to_float(value)

    @staticmethod
    def _patch_ib_insync_loop(util, client, connection) -> None:
        def get_running_loop():
            return asyncio.get_running_loop()

        util.getLoop = get_running_loop
        client.getLoop = get_running_loop
        connection.getLoop = get_running_loop


class IBMarketDataSource:
    def __init__(
        self,
        ib_connection: IBConnection,
        market_data_type: int = 3,
    ):
        self.ib_connection = ib_connection
        self.market_data_type = market_data_type
        self._ticker = None
        self._last_snapshot = None

    async def connect(self) -> None:
        if self.ib_connection.ib is None or self.ib_connection.contract is None:
            raise RuntimeError("IB connection is not established.")

        self.ib_connection.ib.reqMarketDataType(self.market_data_type)
        self._ticker = self.ib_connection.ib.reqMktData(self.ib_connection.contract, "", False, False)

    async def close(self) -> None:
        # Do not close shared connection here.
        if self._ticker and self.ib_connection.ib:
            self.ib_connection.ib.cancelMktData(self.ib_connection.contract)

    async def next_tick(self) -> Dict[str, Any]:
        if not self.ib_connection.ib or not self._ticker:
            raise RuntimeError("IB market data source is not connected.")

        while True:
            await self.ib_connection.ib.updateEvent
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
            "symbol": self.ib_connection.contract.symbol,
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
        if isinstance(value, str):
            return datetime.fromisoformat(value).astimezone(timezone.utc).isoformat()
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


def _max_opt(a, b):
    if a is None:
        return b
    if b is None:
        return a
    return max(a, b)


def _min_opt(a, b):
    if a is None:
        return b
    if b is None:
        return a
    return min(a, b)
