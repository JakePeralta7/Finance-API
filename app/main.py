"""
Finance API – containerised Yahoo Finance proxy.

Entry point for the FastAPI application.  Wires together:
  - Application metadata (title, version, description)
  - Routers
  - Startup / shutdown lifecycle events
  - CORS middleware (permissive defaults; restrict via env vars in production)
"""

from __future__ import annotations

import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers.stock import router as stock_router
from app.services.yahoo_session import yahoo_session

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
)
logger = logging.getLogger(__name__)


app = FastAPI(
    title="Finance API",
    version="1.0.0",
    description=(
        "A lightweight proxy that retrieves financial data from Yahoo Finance "
        "and returns it as clean, structured JSON.  "
        "Data is sourced in real-time; no caching is applied."
    ),
    license_info={"name": "MIT"},
)

# ---------------------------------------------------------------------------
# CORS
# Allow all origins by default so the API is easy to use when self-hosted.
# Override with the CORS_ORIGINS environment variable (comma-separated list).
# ---------------------------------------------------------------------------
_raw_origins = os.getenv("CORS_ORIGINS", "*")
_origins = [o.strip() for o in _raw_origins.split(",")] if _raw_origins != "*" else ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=_raw_origins != "*",
    allow_methods=["GET"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------
app.include_router(stock_router)


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------
@app.on_event("startup")
async def _startup() -> None:
    """Pre-warm the Yahoo Finance session so the first request isn't slow."""
    logger.info("Pre-warming Yahoo Finance authentication session …")
    try:
        await yahoo_session.crumb()
        logger.info("Yahoo Finance session ready.")
    except Exception as exc:
        # Non-fatal: the session will re-auth on the first real request.
        logger.warning("Could not pre-warm Yahoo Finance session: %s", exc)


@app.on_event("shutdown")
async def _shutdown() -> None:
    await yahoo_session.close()
    logger.info("Yahoo Finance session closed.")
