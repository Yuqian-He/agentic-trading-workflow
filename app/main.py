from pathlib import Path
from contextlib import asynccontextmanager
import asyncio
import signal

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .api.routes import router
from .agent_loop import agent_loop
from .core.config import settings
from .services.historical_importer import HistoricalBarImporter

BASE_DIR = Path(__file__).resolve().parent
_shutdown_registered = False


def _register_shutdown_signals() -> None:
    global _shutdown_registered
    if _shutdown_registered:
        return
    _shutdown_registered = True
    loop = asyncio.get_running_loop()

    def _graceful_stop():
        if not agent_loop._running:
            return
        loop.create_task(agent_loop.stop())

    for sig_name in ("SIGINT", "SIGTERM"):
        sig = getattr(signal, sig_name, None)
        if sig is None:
            continue
        try:
            loop.add_signal_handler(sig, _graceful_stop)
        except NotImplementedError:
            # Some environments (for example Windows event loop policies)
            # may not support signal handlers here.
            continue

@asynccontextmanager
async def lifespan(app):
    _register_shutdown_signals()
    if settings.historical_seed_enabled:
        importer = HistoricalBarImporter(settings.bar_db_path)
        importer.ensure_seeded(
            file_path=settings.historical_seed_file,
            symbol=settings.historical_seed_symbol,
            interval=settings.historical_seed_interval,
            input_timezone=settings.historical_seed_timezone,
        )
    yield
    await agent_loop.stop()

app = FastAPI(title="Trading Workflow AI", lifespan=lifespan)
app.include_router(router, prefix="/api")
app.mount("/", StaticFiles(directory=BASE_DIR / "static", html=True), name="static")

