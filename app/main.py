from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .api.routes import router
from .agent_loop import agent_loop

BASE_DIR = Path(__file__).resolve().parent

@asynccontextmanager
async def lifespan(app):
    yield
    await agent_loop.stop()

app = FastAPI(title="Trading Workflow AI", lifespan=lifespan)
app.include_router(router, prefix="/api")
app.mount("/", StaticFiles(directory=BASE_DIR / "static", html=True), name="static")

