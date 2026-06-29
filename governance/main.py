"""
IncuBrix Governance Layer v2 – FastAPI application entry point.

Run with:
    uvicorn governance.main:app --reload --port 8001

API docs available at:
    http://localhost:8001/docs
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Import all models so create_all_tables() registers them
import governance.models  # noqa: F401

from governance.database import create_all_tables
from governance.scheduler import start_scheduler, stop_scheduler
from governance.routers import (
    requests, assets, reviews, exceptions, events, policies, auth,
    legal_holds, incidents, provider_profiles, simulate, webhooks, retention
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    create_all_tables()
    start_scheduler()
    yield
    # Shutdown
    stop_scheduler()


app = FastAPI(
    title="IncuBrix Governance Layer",
    description=(
        "Production-grade governance control plane for video generation workflows. "
        "v2 adds: legal holds, incident management, provider policy intelligence, "
        "publish-readiness gate, provenance records, structured rights manifests, "
        "policy simulation, and tamper-evident audit hash chaining."
    ),
    version="2.0.0",
    lifespan=lifespan,
)

# Allow the Vite dev server (port 5174) and any localhost origin
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Core v1 routers ───────────────────────────────────────────────────────────
app.include_router(requests.router)
app.include_router(assets.router)
app.include_router(reviews.router)
app.include_router(exceptions.router)
app.include_router(events.router)
app.include_router(policies.router)
app.include_router(auth.router)

# ── New v2 routers ────────────────────────────────────────────────────────────
app.include_router(legal_holds.router)
app.include_router(incidents.router)
app.include_router(provider_profiles.router)
app.include_router(simulate.router)
app.include_router(webhooks.router)
app.include_router(retention.router)


@app.get("/health", tags=["Health"])
def health():
    return {"status": "ok", "service": "governance-layer", "version": "2.0.0"}
