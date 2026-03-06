"""
Yahoo Finance API client.

Hits two internal endpoints in parallel:
  - /v7/finance/quote         → real-time price, bid/ask, volume, market state
  - /v10/finance/quoteSummary → fundamentals, company profile, key statistics

Both results are normalised into clean Pydantic models (no raw/fmt wrappers).
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException

from app.models.responses import (
    CompanyInfo,
    Fundamentals,
    PriceInfo,
    SymbolResponse,
)
from app.services.yahoo_session import yahoo_session

logger = logging.getLogger(__name__)

_QUOTE_URL = "https://query1.finance.yahoo.com/v7/finance/quote"
_SUMMARY_URL = "https://query2.finance.yahoo.com/v10/finance/quoteSummary/{symbol}"

_SUMMARY_MODULES = "summaryDetail,assetProfile,defaultKeyStatistics,quoteType,financialData"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def get_symbol_data(symbol: str) -> SymbolResponse:
    """
    Fetch and normalise quote + summary data for *symbol* from Yahoo Finance.

    Raises
    ------
    HTTPException 404  – symbol not found / empty result from Yahoo.
    HTTPException 503  – upstream Yahoo Finance API unavailable.
    """
    crumb = await yahoo_session.crumb()

    try:
        quote_data, summary_data = await asyncio.gather(
            _fetch_quote(symbol, crumb),
            _fetch_summary(symbol, crumb),
            return_exceptions=False,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Unexpected error fetching data for %s", symbol)
        raise HTTPException(status_code=503, detail="Upstream data provider unavailable.") from exc

    price = _build_price_info(quote_data)
    company = _build_company_info(summary_data)
    fundamentals = _build_fundamentals(quote_data, summary_data)
    quote_type = _extract_quote_type(summary_data)

    return SymbolResponse(
        symbol=symbol.upper(),
        quote_type=quote_type,
        as_of=datetime.now(timezone.utc),
        price=price,
        company=company,
        fundamentals=fundamentals,
    )


# ---------------------------------------------------------------------------
# Private fetch helpers
# ---------------------------------------------------------------------------


async def _fetch_quote(symbol: str, crumb: str) -> dict[str, Any]:
    response = await yahoo_session.get(
        _QUOTE_URL,
        params={"symbols": symbol, "crumb": crumb},
        timeout=10,
    )
    _raise_for_upstream_error(response, symbol)

    body: dict = response.json()
    results: list = (body.get("quoteResponse") or {}).get("result") or []
    if not results:
        raise HTTPException(status_code=404, detail=f"Symbol '{symbol}' not found.")
    return results[0]


async def _fetch_summary(symbol: str, crumb: str) -> dict[str, Any]:
    response = await yahoo_session.get(
        _SUMMARY_URL.format(symbol=symbol),
        params={
            "modules": _SUMMARY_MODULES,
            "crumb": crumb,
            "formatted": "false",
            "corsDomain": "finance.yahoo.com",
        },
        timeout=10,
    )
    _raise_for_upstream_error(response, symbol)

    body: dict = response.json()
    error = (body.get("quoteSummary") or {}).get("error")
    if error:
        code = (error.get("code") or "").lower()
        if "not found" in code or code == "no_data_available":
            raise HTTPException(status_code=404, detail=f"Symbol '{symbol}' not found.")
        raise HTTPException(
            status_code=503,
            detail=f"Yahoo Finance returned an error: {error.get('description', error)}",
        )

    results: list = (body.get("quoteSummary") or {}).get("result") or []
    if not results:
        raise HTTPException(status_code=404, detail=f"Symbol '{symbol}' not found.")
    return results[0]


def _raise_for_upstream_error(response: Any, symbol: str) -> None:
    if response.status_code == 404:
        raise HTTPException(status_code=404, detail=f"Symbol '{symbol}' not found.")
    if response.status_code == 429:
        raise HTTPException(status_code=503, detail="Yahoo Finance rate limit reached. Retry later.")
    if response.status_code >= 400:
        raise HTTPException(
            status_code=503,
            detail=f"Yahoo Finance returned HTTP {response.status_code}.",
        )


# ---------------------------------------------------------------------------
# Normalisation helpers
# ---------------------------------------------------------------------------


def _v(value: Any) -> Any:
    """Unwrap Yahoo's {'raw': ..., 'fmt': ...} objects; pass scalars through."""
    if isinstance(value, dict):
        return value.get("raw")
    return value


def _build_price_info(q: dict[str, Any]) -> PriceInfo:
    return PriceInfo(
        price=_v(q.get("regularMarketPrice")),
        currency=q.get("currency"),
        change=_v(q.get("regularMarketChange")),
        change_pct=_v(q.get("regularMarketChangePercent")),
        previous_close=_v(q.get("regularMarketPreviousClose")),
        open=_v(q.get("regularMarketOpen")),
        day_high=_v(q.get("regularMarketDayHigh")),
        day_low=_v(q.get("regularMarketDayLow")),
        volume=_v(q.get("regularMarketVolume")),
        avg_volume_3m=_v(q.get("averageDailyVolume3Month")),
        market_cap=_v(q.get("marketCap")),
        bid=_v(q.get("bid")),
        ask=_v(q.get("ask")),
        week_52_high=_v(q.get("fiftyTwoWeekHigh")),
        week_52_low=_v(q.get("fiftyTwoWeekLow")),
        market_state=q.get("marketState"),
        exchange=q.get("exchange"),
        exchange_delay_minutes=q.get("exchangeDataDelayedBy"),
    )


def _build_company_info(s: dict[str, Any]) -> CompanyInfo:
    profile: dict = s.get("assetProfile") or {}
    quote_type: dict = s.get("quoteType") or {}
    return CompanyInfo(
        name=quote_type.get("shortName"),
        long_name=quote_type.get("longName"),
        sector=profile.get("sector"),
        industry=profile.get("industry"),
        country=profile.get("country"),
        website=profile.get("website"),
        description=profile.get("longBusinessSummary"),
        employees=profile.get("fullTimeEmployees"),
    )


def _build_fundamentals(q: dict[str, Any], s: dict[str, Any]) -> Fundamentals:
    detail: dict = s.get("summaryDetail") or {}
    stats: dict = s.get("defaultKeyStatistics") or {}
    fin: dict = s.get("financialData") or {}
    return Fundamentals(
        trailing_pe=_v(detail.get("trailingPE")),
        forward_pe=_v(detail.get("forwardPE")),
        beta=_v(detail.get("beta")),
        dividend_yield=_v(detail.get("dividendYield")),
        eps_trailing=_v(stats.get("trailingEps")),
        eps_forward=_v(stats.get("forwardEps")),
        book_value=_v(stats.get("bookValue")),
        price_to_book=_v(stats.get("priceToBook")),
        enterprise_value=_v(stats.get("enterpriseValue")),
        profit_margins=_v(fin.get("profitMargins")),
        shares_outstanding=_v(stats.get("sharesOutstanding")),
    )


def _extract_quote_type(s: dict[str, Any]) -> str | None:
    return (s.get("quoteType") or {}).get("quoteType")
