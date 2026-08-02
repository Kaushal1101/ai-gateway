from fastapi import FastAPI

from gateway.routes.chat import router

app = FastAPI(title="AI Gateway")
app.include_router(router)
