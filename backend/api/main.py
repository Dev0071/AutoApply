from contextlib import asynccontextmanager

from fastapi import FastAPI

from backend.config import settings  # noqa: F401 — validates env at startup


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(title="AutoApply", lifespan=lifespan)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
