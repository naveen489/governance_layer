"""
IncuBrix Governance Layer – FastAPI application entry point.

Run with:
    uvicorn governance.main:app --reload --port 8001

API docs available at:
    http://localhost:8001/docs
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from governance.database import create_all_tables
from governance.scheduler import start_scheduler, stop_scheduler
from governance.routers import requests, assets, reviews, exceptions, events, policies, auth


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
        "Policy and control system for video generation workflows. "
        "Evaluates policy, manages approvals, records audit events, "
        "handles rights manifests, exceptions, and retention."
    ),
    version="1.0.0",
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

# Mount routers
app.include_router(requests.router)
app.include_router(assets.router)
app.include_router(reviews.router)
app.include_router(exceptions.router)
app.include_router(events.router)
app.include_router(policies.router)
app.include_router(auth.router)


@app.get("/health", tags=["Health"])
def health():
    return {"status": "ok", "service": "governance-layer", "version": "1.0.0"}
