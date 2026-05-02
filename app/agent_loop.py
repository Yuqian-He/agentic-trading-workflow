import asyncio
from datetime import datetime, timezone
from typing import Dict, Any, Optional

from .core.config import settings
from .db.tick_repository import SQLiteTickRepository
from .db.bar_repository import SQLiteBarRepository
from .db.indicator_settings_repository import SQLiteIndicatorSettingsRepository
from .services.data_store import MarketDataStore, NewsStore, HistoricalStore, SignalStore
from .services.agent import StrategySelectionAgent, ExecutionDecisionAgent
from .services.market_data import IBConnection, IBMarketDataSource, IBBarDataSource
from .services.rag import RAGService
from .services.indicators import IndicatorEngine
from .services.execution import ExecutionService


class AgentLoop:
    def __init__(self):
        self._task = None
        self._running = False
        self._market_store = MarketDataStore(
            tick_repository=SQLiteTickRepository(settings.tick_db_path),
            bar_repository=SQLiteBarRepository(settings.bar_db_path),
            bar_interval="1m",
        )
        self._ib_connection = IBConnection(
            host=settings.ib_host,
            port=settings.ib_port,
            client_id=settings.ib_client_id,
            account=settings.ib_account or None,
        )
        self._market_data_source = IBMarketDataSource(
            ib_connection=self._ib_connection,
            market_data_type=settings.ib_market_data_type,
        )
        self._bar_data_source = self._create_bar_data_source("1m")
        self._indicator_settings_repo = SQLiteIndicatorSettingsRepository(settings.bar_db_path)
        self._news_store = NewsStore()
        self._history_store = HistoricalStore()
        self._signal_store = SignalStore()
        self._indicator_engine = IndicatorEngine(bar_fetcher=self._fetch_recent_bars)
        self._execution_service = ExecutionService()
        self._rag_service = RAGService(self._history_store)
        self._strategy_agent = StrategySelectionAgent()
        self._execution_agent = ExecutionDecisionAgent()
        self._tick_task = None
        self._bar_task = None
        self._reconnect_lock = asyncio.Lock()
        self._reconnecting = False
        self._ready = asyncio.Event()
        self._symbol: str = settings.ib_symbol
        self._state: Dict[str, Any] = {
            "last_run": None,
            "strategy": None,
            "decision": None,
            "status": "stopped",
            "last_error": None,
        }
        self._last_bar_timestamp: Optional[str] = None
        self._indicator_inputs = self._load_indicator_inputs()
        self._indicator_engine.set_inputs(self._indicator_inputs)

    def _create_bar_data_source(self, interval: str) -> IBBarDataSource:
        return IBBarDataSource(
            ib_connection=self._ib_connection,
            bar_interval=interval,
        )

    @property
    def bar_interval(self) -> str:
        return self._bar_data_source.bar_interval

    async def set_bar_interval(self, interval: str):
        self._bar_data_source.set_bar_interval(interval)
        self._market_store.bar_interval = interval
        self._indicator_engine.set_runtime_context(self._symbol, interval)
        if self._running:
            # Use full restart to avoid partial reconnect edge-cases.
            await self.stop()
            await self.start()

    @property
    def symbol(self) -> str:
        return self._symbol

    async def set_ticker(self, symbol: str):
        symbol = (symbol or "").strip().upper()
        if not symbol:
            raise ValueError("Ticker cannot be empty")
        self._symbol = symbol
        self._indicator_engine.set_runtime_context(self._symbol, self.bar_interval)

        # if running, restart the IB connection to apply new contract.
        if self._running:
            await self.stop()
            await self.start()

    def _fetch_recent_bars(self, symbol: str, interval: str, limit: int):
        repo = self._market_store.bar_repository
        if not repo or not hasattr(repo, "fetch_recent_bars"):
            return []
        return repo.fetch_recent_bars(symbol=symbol, interval=interval, limit=limit)

    def _load_indicator_inputs(self) -> Dict[str, Any]:
        stored = self._indicator_settings_repo.load("indicator_inputs")
        defaults = self._indicator_engine.get_inputs()
        merged = dict(defaults)
        for name, cfg in (stored or {}).items():
            if name in merged and isinstance(cfg, dict):
                merged[name] = {**merged[name], **cfg}
        return merged

    def indicator_inputs(self) -> Dict[str, Any]:
        return dict(self._indicator_inputs)

    async def set_indicator_inputs(self, payload: Dict[str, Any]):
        defaults = self._indicator_engine.get_inputs()
        merged = dict(defaults)
        for name, cfg in (payload or {}).items():
            if name in merged and isinstance(cfg, dict):
                merged[name] = {**merged[name], **cfg}

        self._indicator_inputs = merged
        self._indicator_engine.set_inputs(self._indicator_inputs)
        self._indicator_settings_repo.save("indicator_inputs", self._indicator_inputs)

        if self._market_store.current_bar:
            await self._strategy_cycle()

    async def start(self):
        if self._running:
            return
        self._ready.clear()
        self._running = True
        self._state["status"] = "running"
        self._state["last_error"] = None
        self._task = asyncio.create_task(self._loop())
        await self._ready.wait()
        if self._state.get("status") == "error" and self._state.get("last_error"):
            raise RuntimeError(self._state["last_error"])

    async def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._state["status"] = "stopped"


    async def _loop(self):
        try:
            await self._ib_connection.connect(
                symbol=self._symbol,
                exchange=settings.ib_exchange,
                currency=settings.ib_currency,
            )
            await self._market_data_source.connect()
            await self._bar_data_source.connect()
            self._start_worker_tasks()
            self._ready.set()

            while self._running:
                await asyncio.sleep(0.5)
        except asyncio.CancelledError:
            self._ready.set()
            raise
        except Exception as exc:
            self._state["last_error"] = str(exc)
            self._state["status"] = "error"
            self._running = False
            self._ready.set()
        finally:
            if self._tick_task:
                self._tick_task.cancel()
            if self._bar_task:
                self._bar_task.cancel()
            await self._market_data_source.close()
            await self._bar_data_source.close()
            await self._ib_connection.close()

    def _start_worker_tasks(self):
        self._tick_task = asyncio.create_task(self._tick_loop())
        self._bar_task = asyncio.create_task(self._bar_loop())
        self._tick_task.add_done_callback(self._handle_worker_task_done)
        self._bar_task.add_done_callback(self._handle_worker_task_done)

    def _handle_worker_task_done(self, task: asyncio.Task):
        if task.cancelled():
            return
        exc = task.exception()
        if exc is None:
            return
        self._state["last_error"] = f"worker task failed: {exc}"
        if not self._running:
            self._state["status"] = "stopped"
            return

        if "Not connected" in str(exc):
            self._state["status"] = "recovering"
            if not self._reconnecting:
                asyncio.create_task(self._recover_connection())
            return

        self._state["status"] = "error"
        self._running = False

    async def _recover_connection(self):
        if self._reconnecting:
            return
        self._reconnecting = True
        async with self._reconnect_lock:
            try:
                if not self._running:
                    return
                self._state["status"] = "recovering"

                if self._tick_task and not self._tick_task.done():
                    self._tick_task.cancel()
                if self._bar_task and not self._bar_task.done():
                    self._bar_task.cancel()

                await self._market_data_source.close()
                await self._bar_data_source.close()
                await self._ib_connection.close()
                await asyncio.sleep(0.5)

                await self._ib_connection.connect(
                    symbol=self._symbol,
                    exchange=settings.ib_exchange,
                    currency=settings.ib_currency,
                )
                await self._market_data_source.connect()
                await self._bar_data_source.connect()
                self._start_worker_tasks()
                self._state["status"] = "running"
                self._state["last_error"] = None
            except Exception as exc:
                self._state["last_error"] = f"reconnect failed: {exc}"
                self._state["status"] = "error"
                self._running = False
            finally:
                self._reconnecting = False

    async def _tick_loop(self):
        while self._running:
            tick = await self._market_data_source.next_tick()
            self._market_store.update_tick(tick)
            await asyncio.sleep(0)

    async def _bar_loop(self):
        while self._running:
            # Demo-friendly behavior:
            # - During trading hours, IB returns a new bar timestamp each interval.
            # - Off hours/weekends, bar timestamps often stop changing; for demo we still
            #   emit a synthetic bar per interval using the latest delayed tick price.
            await self._sleep_until_next_bar_boundary()

            bar = await self._bar_data_source.fetch_latest_bar()
            bar_ts = bar.get("timestamp") if bar else None

            if bar and bar_ts and bar_ts != self._last_bar_timestamp:
                self._market_store.update_bar(bar)
                self._last_bar_timestamp = bar_ts
                await self._strategy_cycle()
                continue

            # Fallback: synthesize a bar so DB shows periodic updates in demo mode.
            tick = self._market_store.current_tick
            price = tick.get("price")
            if price is None:
                # Nothing to synthesize yet; try again next interval.
                continue

            interval_s = IBBarDataSource.interval_seconds(self.bar_interval)
            now_s = int(datetime.now(timezone.utc).timestamp())
            bucket_start = (now_s // interval_s) * interval_s
            synthetic_ts = datetime.fromtimestamp(bucket_start, tz=timezone.utc).isoformat()
            if synthetic_ts == self._last_bar_timestamp:
                continue

            synthetic_bar = {
                "symbol": tick.get("symbol") or settings.ib_symbol,
                "open": price,
                "high": price,
                "low": price,
                "close": price,
                "volume": 0,
                "timestamp": synthetic_ts,
                "source": "synthetic_bar",
            }
            self._market_store.update_bar(synthetic_bar)
            self._last_bar_timestamp = synthetic_ts
            await self._strategy_cycle()

    async def _strategy_cycle(self):
        last_run = datetime.utcnow().isoformat()
        self._indicator_engine.set_runtime_context(self.symbol, self.bar_interval)
        calc_result = self._indicator_engine.calculate_all(self._market_store.current_bar)
        indicators = calc_result.get("indicators", {})
        signals = calc_result.get("signals", {})
        self._signal_store.update(signals, indicators=indicators, last_run=last_run)

        # Indicator-focused mode:
        # Temporarily disable strategy selection, decision making, and order execution.
        # market_summary = self._market_store.market_summary()
        # rag_context = self._rag_service.build_context(
        #     market_summary=market_summary,
        #     signals=signals
        # )
        #
        # strategy = self._strategy_agent.select_strategy(
        #     market_summary,
        #     signals,
        #     rag_context
        # )
        #
        # decision = self._execution_agent.decide(
        #     strategy,
        #     signals,
        #     rag_context
        # )
        #
        # if decision["action"] != "hold":
        #     self._execution_service.execute_order(decision)
        #
        # self._state["strategy"] = strategy
        # self._state["decision"] = decision
        self._state["last_run"] = last_run

    async def _sleep_until_next_bar_boundary(self):
        # Align bar loop to the selected interval boundary.
        interval = self.bar_interval
        try:
            seconds = IBBarDataSource.interval_seconds(interval)
        except Exception:
            seconds = 60

        now = datetime.now(timezone.utc).timestamp()
        next_boundary = ((int(now) // seconds) + 1) * seconds
        sleep_for = max(0.0, next_boundary - now)
        await asyncio.sleep(max(0.25, sleep_for))

    def status(self):
        return {
            "running": self._running,
            "last_run": self._state["last_run"],
            "strategy": self._state["strategy"],
            "decision": self._state["decision"],
            "status": self._state["status"],
            "last_error": self._state.get("last_error"),
            "symbol": self.symbol,
            "bar_interval": self.bar_interval,
        }

    def market_summary(self):
        return self._market_store.market_summary()

    def signals_summary(self):
        summary = self._signal_store.summary()
        summary["inputs"] = self.indicator_inputs()
        return summary


agent_loop = AgentLoop()
