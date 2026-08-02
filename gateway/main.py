from contextlib import asynccontextmanager

from fastapi import FastAPI

from gateway.db import engine
from gateway.routes.chat import router


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await engine.dispose()


app = FastAPI(title="AI Gateway", lifespan=lifespan)
app.include_router(router)
