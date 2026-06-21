"""FastAPI application entrypoint.

Run:  uvicorn app.main:app --reload  (from the backend/ directory)
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_config
from .routers import analyze, parcels

app = FastAPI(
    title="Buildable Land Analysis API",
    version="0.1.0",
    description="Compute buildable area for a parcel given constraint layers + setbacks.",
)

# Dev CORS: the Vite frontend runs on localhost:5173.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:4173",
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(parcels.router)
app.include_router(analyze.router)


@app.get("/api/health")
def health():
    cfg = get_config()
    return {"status": "ok", "county": cfg.county}
