"""
Stock router – exposes:

  GET /stock/{symbol}   Full price + company info + fundamentals for a symbol
  GET /health           Liveness probe for Docker / Kubernetes
"""

from __future__ import annotations

import re

from fastapi import APIRouter, HTTPException, Path

from app.models.responses import SymbolResponse
from app.services.yahoo_client import get_symbol_data

router = APIRouter(tags=["Stock"])

# Ticker symbols: 1–10 uppercase letters, digits, dots, or hyphens.
# Covers equities (AAPL), indices (^GSPC), forex (EURUSD=X), and common ETFs.
_SYMBOL_RE = re.compile(r"^[A-Z0-9.\-\^]{1,20}$")


@router.get(
    "/stock/{symbol}",
    response_model=SymbolResponse,
    summary="Get data for a stock symbol",
    description=(
        "Returns current price, market state, company profile, and key fundamental "
        "ratios for the requested ticker symbol.  Data is sourced live from Yahoo Finance."
    ),
)
async def get_stock(
    symbol: str = Path(
        ...,
        description="Ticker symbol (e.g. AAPL, TSLA, ^GSPC)",
        examples={"equity": {"value": "AAPL"}, "index": {"value": "^GSPC"}},
    ),
) -> SymbolResponse:
    upper = symbol.upper()
    if not _SYMBOL_RE.match(upper):
        raise HTTPException(
            status_code=400,
            detail=(
                f"Invalid symbol '{symbol}'. "
                "Symbols must be 1–20 characters and contain only letters, digits, "
                "dots, hyphens, or caret (^)."
            ),
        )
    return await get_symbol_data(upper)


@router.get(
    "/health",
    summary="Health check",
    description="Returns 200 OK when the service is running.",
    response_model=dict,
)
async def health() -> dict:
    return {"status": "ok"}
