import asyncio
import math
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Protocol


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
        client_id_fallback_span: int = 8,
        connect_timeout_seconds: int = 20,
        connect_retries: int = 3,
        connect_retry_delay_seconds: float = 1.5,
    ):
        self.host = host
        self.port = port
        self.client_id = client_id
        self.account = account
        self.client_id_fallback_span = max(0, int(client_id_fallback_span))
        self.connect_timeout_seconds = max(3, int(connect_timeout_seconds))
        self.connect_retries = max(1, int(connect_retries))
        self.connect_retry_delay_seconds = max(0.1, float(connect_retry_delay_seconds))
        self._active_client_id = client_id
        self._ib = None
        self._contract = None

    async def connect(self, symbol: str, exchange: str, currency: str) -> None:
        try:
            from ib_insync import IB, Stock
            from ib_insync import client, connection, util
        except ImportError as exc:
            raise RuntimeError("ib_insync is required for IB connection. Install backend requirements first.") from exc

        self._patch_ib_insync_loop(util, client, connection)
        last_exc: Optional[Exception] = None
        candidates = self._client_id_candidates()

        for cid in candidates:
            for attempt in range(1, self.connect_retries + 1):
                self._ib = IB()
                connect_kwargs = {
                    "host": self.host,
                    "port": self.port,
                    "clientId": cid,
                    "timeout": self.connect_timeout_seconds,
                }
                if self.account:
                    connect_kwargs["account"] = self.account
                try:
                    await self._ib.connectAsync(**connect_kwargs)
                    self._active_client_id = cid
                    self._contract = Stock(symbol, exchange, currency)
                    return
                except Exception as exc:
                    last_exc = exc
                    message = str(exc).lower()
                    try:
                        if self._ib and self._ib.isConnected():
                            self._ib.disconnect()
                    except Exception:
                        pass

                    # If this clientId is occupied, immediately try next candidate.
                    if "already in use" in message or "clientid" in message and "in use" in message:
                        break
                    if attempt < self.connect_retries:
                        await asyncio.sleep(self.connect_retry_delay_seconds)

        raise RuntimeError(
            f"IB connect failed after trying clientIds={candidates} with "
            f"timeout={self.connect_timeout_seconds}s and retries={self.connect_retries} "
            f"(host={self.host}, port={self.port}): {last_exc}"
        ) from last_exc

    async def close(self) -> None:
        if self._ib and self._ib.isConnected():
            self._ib.disconnect()

    @property
    def ib(self):
        return self._ib

    @property
    def contract(self):
        return self._contract

    @property
    def active_client_id(self) -> int:
        return int(self._active_client_id)

    def _client_id_candidates(self) -> List[int]:
        out: List[int] = []
        # Try last successful clientId first.
        if int(self._active_client_id) not in out:
            out.append(int(self._active_client_id))
        for i in range(self.client_id, self.client_id + self.client_id_fallback_span + 1):
            if i not in out:
                out.append(i)
        return out

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

    async def fetch_recent_bars(self, limit: int = 500) -> List[Dict[str, Any]]:
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
            return []
        result: List[Dict[str, Any]] = []
        for bar in bars[-max(1, int(limit)) :]:
            result.append(
                {
                    "symbol": self.ib_connection.contract.symbol,
                    "open": self._to_float(bar.open),
                    "high": self._to_float(bar.high),
                    "low": self._to_float(bar.low),
                    "close": self._to_float(bar.close),
                    "volume": int(bar.volume or 0),
                    "timestamp": self._timestamp_to_iso(bar.date),
                    "source": "ib_delayed_historical_bar",
                }
            )
        return result

    async def fetch_bars_between(
        self,
        *,
        start_exclusive_iso: str,
        end_inclusive_iso: str,
        chunk_duration: str = "1 D",
        max_chunks: int = 30,
    ) -> List[Dict[str, Any]]:
        """Fetch bars in (start, end] by paging backward from endDateTime."""
        if not self.ib_connection.ib or not self.ib_connection.contract:
            raise RuntimeError("IB bar data source is not connected.")

        start_dt = self._parse_iso_utc(start_exclusive_iso)
        end_dt = self._parse_iso_utc(end_inclusive_iso)
        if start_dt is None or end_dt is None or start_dt >= end_dt:
            return []

        cursor = end_dt
        out: Dict[str, Dict[str, Any]] = {}
        chunks = 0

        while cursor > start_dt and chunks < max_chunks:
            bars = await self.ib_connection.ib.reqHistoricalDataAsync(
                self.ib_connection.contract,
                endDateTime=self._ib_end_datetime(cursor),
                durationStr=chunk_duration,
                barSizeSetting=self.bar_size_setting,
                whatToShow="TRADES",
                useRTH=False,
                formatDate=1,
                keepUpToDate=False,
            )
            chunks += 1
            if not bars:
                break

            min_dt_in_chunk: Optional[datetime] = None
            for bar in bars:
                ts_iso = self._timestamp_to_iso(bar.date)
                ts_dt = self._parse_iso_utc(ts_iso)
                if ts_dt is None:
                    continue
                if ts_dt <= start_dt or ts_dt > end_dt:
                    continue
                out[ts_iso] = {
                    "symbol": self.ib_connection.contract.symbol,
                    "open": self._to_float(bar.open),
                    "high": self._to_float(bar.high),
                    "low": self._to_float(bar.low),
                    "close": self._to_float(bar.close),
                    "volume": int(bar.volume or 0),
                    "timestamp": ts_iso,
                    "source": "ib_gap_backfill_bar",
                }
                if min_dt_in_chunk is None or ts_dt < min_dt_in_chunk:
                    min_dt_in_chunk = ts_dt

            if min_dt_in_chunk is None:
                break
            cursor = min_dt_in_chunk - timedelta(seconds=1)

        rows = list(out.values())
        rows.sort(key=lambda x: x.get("timestamp") or "")
        return rows

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
    def _parse_iso_utc(value: str) -> Optional[datetime]:
        try:
            ts = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            return ts.astimezone(timezone.utc)
        except Exception:
            return None

    @staticmethod
    def _ib_end_datetime(value: datetime) -> str:
        # IB accepts "YYYYMMDD HH:MM:SS UTC".
        return value.astimezone(timezone.utc).strftime("%Y%m%d %H:%M:%S UTC")

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


class BarAggregator:
    """Aggregate base-interval bars into higher intervals."""

    def __init__(self, base_interval: str = "1m"):
        self.base_interval = base_interval
        self._state: Dict[str, Dict[str, Any]] = {}

    def reset(self) -> None:
        self._state.clear()

    def push(self, bar: Dict[str, Any], target_intervals: List[str]) -> List[Dict[str, Any]]:
        emitted: List[Dict[str, Any]] = []
        for interval in target_intervals:
            if interval == self.base_interval:
                emitted.append({"interval": interval, "bar": dict(bar)})
                continue
            built = self._push_one(bar, interval)
            if built is not None:
                emitted.append({"interval": interval, "bar": built})
        return emitted

    def _push_one(self, bar: Dict[str, Any], interval: str) -> Optional[Dict[str, Any]]:
        target_seconds = IBBarDataSource.interval_seconds(interval)
        ts = self._parse_ts(bar.get("timestamp"))
        if ts is None:
            return None
        epoch = int(ts.timestamp())
        bucket_start = (epoch // target_seconds) * target_seconds

        state = self._state.get(interval)
        if state is None:
            self._state[interval] = self._new_bucket(bar, bucket_start)
            return None

        if bucket_start != state["bucket_start"]:
            finished = self._to_output_bar(state)
            self._state[interval] = self._new_bucket(bar, bucket_start)
            return finished

        self._merge(state, bar)
        return None

    def _new_bucket(self, bar: Dict[str, Any], bucket_start: int) -> Dict[str, Any]:
        return {
            "bucket_start": bucket_start,
            "symbol": bar.get("symbol"),
            "open": bar.get("open"),
            "high": bar.get("high"),
            "low": bar.get("low"),
            "close": bar.get("close"),
            "volume": bar.get("volume") or 0,
            "source": f"aggregated_from_{self.base_interval}",
        }

    def _merge(self, state: Dict[str, Any], bar: Dict[str, Any]) -> None:
        state["high"] = _max_opt(self._to_float(state.get("high")), self._to_float(bar.get("high")))
        state["low"] = _min_opt(self._to_float(state.get("low")), self._to_float(bar.get("low")))
        state["close"] = bar.get("close")
        state["volume"] = (state.get("volume") or 0) + (bar.get("volume") or 0)

    def _to_output_bar(self, state: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "symbol": state.get("symbol"),
            "open": state.get("open"),
            "high": state.get("high"),
            "low": state.get("low"),
            "close": state.get("close"),
            "volume": state.get("volume"),
            "timestamp": datetime.fromtimestamp(int(state["bucket_start"]), tz=timezone.utc).isoformat(),
            "source": state.get("source"),
        }

    @staticmethod
    def _parse_ts(value: Any) -> Optional[datetime]:
        if value is None:
            return None
        try:
            ts = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            if ts.tzinfo is None:
                return ts.replace(tzinfo=timezone.utc)
            return ts.astimezone(timezone.utc)
        except Exception:
            return None

    @staticmethod
    def _to_float(value: Any) -> Optional[float]:
        try:
            if value is None:
                return None
            return float(value)
        except Exception:
            return None
