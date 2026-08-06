import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from gateway.db import engine
from gateway.routes.chat import app_router

_REQUIRED_API_KEYS = ["OPENAI_API_KEY", "GEMINI_API_KEY", "ANTHROPIC_API_KEY"]


@asynccontextmanager
async def lifespan(app: FastAPI):
    missing = [k for k in _REQUIRED_API_KEYS if not os.getenv(k)]
    if missing:
        raise RuntimeError(f"Missing required API keys: {missing}")
    yield
    await engine.dispose()


app = FastAPI(title="AI Gateway", lifespan=lifespan)
app.include_router(app_router)


@app.get("/metrics")
def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
