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
    HistoryResponse,
    OHLCVBar,
    PriceInfo,
    SymbolResponse,
)
from app.services.yahoo_session import yahoo_session

logger = logging.getLogger(__name__)

_QUOTE_URL = "https://query1.finance.yahoo.com/v7/finance/quote"
_SUMMARY_URL = "https://query2.finance.yahoo.com/v10/finance/quoteSummary/{symbol}"
_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"

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


async def get_symbol_history(symbol: str, period: str, interval: str) -> HistoryResponse:
    """
    Fetch historical OHLCV bars for *symbol* from Yahoo Finance.

    Raises
    ------
    HTTPException 404  – symbol not found / no data for the requested range.
    HTTPException 503  – upstream Yahoo Finance API unavailable.
    """
    crumb = await yahoo_session.crumb()

    try:
        response = await yahoo_session.get(
            _CHART_URL.format(symbol=symbol),
            params={"range": period, "interval": interval, "crumb": crumb},
            timeout=15,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Unexpected error fetching history for %s", symbol)
        raise HTTPException(status_code=503, detail="Upstream data provider unavailable.") from exc

    _raise_for_upstream_error(response, symbol)

    body: dict = response.json()
    chart = body.get("chart") or {}
    error = chart.get("error")
    if error:
        raise HTTPException(
            status_code=503,
            detail=f"Yahoo Finance returned an error: {error.get('description', error)}",
        )

    results: list = chart.get("result") or []
    if not results:
        raise HTTPException(
            status_code=404,
            detail=f"No historical data found for '{symbol}' with period='{period}' interval='{interval}'.",
        )

    result = results[0]
    timestamps: list = result.get("timestamp") or []
    indicators: dict = result.get("indicators") or {}
    quote: dict = (indicators.get("quote") or [{}])[0]

    opens: list = quote.get("open") or []
    highs: list = quote.get("high") or []
    lows: list = quote.get("low") or []
    closes: list = quote.get("close") or []
    volumes: list = quote.get("volume") or []

    _INTRADAY_INTERVALS = {"1m", "2m", "5m", "15m", "30m", "60m", "90m", "1h"}
    use_datetime = interval in _INTRADAY_INTERVALS

    bars: list[OHLCVBar] = []
    for i, ts in enumerate(timestamps):
        dt = datetime.fromtimestamp(ts, tz=timezone.utc)
        date_str = dt.isoformat() if use_datetime else dt.date().isoformat()
        bars.append(
            OHLCVBar(
                date=date_str,
                open=opens[i] if i < len(opens) else None,
                high=highs[i] if i < len(highs) else None,
                low=lows[i] if i < len(lows) else None,
                close=closes[i] if i < len(closes) else None,
                volume=volumes[i] if i < len(volumes) else None,
            )
        )

    return HistoryResponse(
        symbol=symbol,
        period=period,
        interval=interval,
        as_of=datetime.now(timezone.utc),
        data=bars,
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
