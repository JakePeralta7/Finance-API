"""
Stock router – exposes:

  GET /stock/{symbol}   Full price + company info + fundamentals for a symbol
  GET /health           Liveness probe for Docker / Kubernetes
"""

from __future__ import annotations

import re

from fastapi import APIRouter, HTTPException, Path, Query

from app.models.responses import HistoryResponse, SymbolResponse
from app.services.yahoo_client import get_symbol_data, get_symbol_history

router = APIRouter(tags=["Stock"])

# Ticker symbols: 1–10 uppercase letters, digits, dots, or hyphens.
# Covers equities (AAPL), indices (^GSPC), forex (EURUSD=X), and common ETFs.
_SYMBOL_RE = re.compile(r"^[A-Z0-9.\-\^]{1,20}$")

_VALID_PERIODS = frozenset(
    {"1d", "5d", "1mo", "3mo", "6mo", "1y", "2y", "5y", "10y", "ytd", "max"}
)
_VALID_INTERVALS = frozenset(
    {"1m", "2m", "5m", "15m", "30m", "60m", "90m", "1h", "1d", "5d", "1wk", "1mo", "3mo"}
)


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
    "/stock/{symbol}/history",
    response_model=HistoryResponse,
    summary="Get historical OHLCV data for a symbol",
    description=(
        "Returns historical open, high, low, close, and volume (OHLCV) bars for the "
        "requested ticker symbol.  Use `period` to control the date range and `interval` "
        "to control bar granularity.  Data is sourced live from Yahoo Finance."
    ),
)
async def get_stock_history(
    symbol: str = Path(
        ...,
        description="Ticker symbol (e.g. AAPL, TSLA, ^GSPC)",
        examples={"equity": {"value": "AAPL"}, "index": {"value": "^GSPC"}},
    ),
    period: str = Query(
        "1mo",
        description="Date range: 1d | 5d | 1mo | 3mo | 6mo | 1y | 2y | 5y | 10y | ytd | max",
    ),
    interval: str = Query(
        "1d",
        description="Bar interval: 1m | 2m | 5m | 15m | 30m | 60m | 90m | 1h | 1d | 5d | 1wk | 1mo | 3mo",
    ),
) -> HistoryResponse:
    upper = symbol.upper()
    if not _SYMBOL_RE.match(upper):
        raise HTTPException(
            status_code=400,
            detail=(
                f"Invalid symbol '{symbol}'. "
                "Symbols must be 1\u201320 characters and contain only letters, digits, "
                "dots, hyphens, or caret (^)."
            ),
        )
    if period not in _VALID_PERIODS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid period '{period}'. Valid values: {sorted(_VALID_PERIODS)}",
        )
    if interval not in _VALID_INTERVALS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid interval '{interval}'. Valid values: {sorted(_VALID_INTERVALS)}",
        )
    return await get_symbol_history(upper, period, interval)


@router.get(
    "/health",
    summary="Health check",
    description="Returns 200 OK when the service is running.",
    response_model=dict,
)
async def health() -> dict:
    return {"status": "ok"}
