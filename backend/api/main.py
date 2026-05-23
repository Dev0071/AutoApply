from contextlib import asynccontextmanager

from fastapi import FastAPI

from backend.config import settings  # noqa: F401 — validates env at startup
from backend.api.routes import applications, jobs, profile


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(
    title="AutoApply",
    description="Vision-driven, quality-gated job application agent.",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(profile.router)
app.include_router(jobs.router)
app.include_router(applications.router)


@app.get("/health", tags=["system"])
async def health() -> dict:
    return {"status": "ok", "version": "0.1.0"}
