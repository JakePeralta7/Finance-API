from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class PriceInfo(BaseModel):
    price: Optional[float] = Field(None, description="Current regular market price")
    currency: Optional[str] = Field(None, description="Trading currency (e.g. USD)")
    change: Optional[float] = Field(None, description="Price change from previous close")
    change_pct: Optional[float] = Field(None, description="Percentage change from previous close")
    previous_close: Optional[float] = Field(None, description="Previous closing price")
    open: Optional[float] = Field(None, description="Opening price of current session")
    day_high: Optional[float] = Field(None, description="Intraday high")
    day_low: Optional[float] = Field(None, description="Intraday low")
    volume: Optional[int] = Field(None, description="Current session volume")
    avg_volume_3m: Optional[int] = Field(None, description="3-month average daily volume")
    market_cap: Optional[int] = Field(None, description="Market capitalisation in base currency")
    bid: Optional[float] = Field(None, description="Current bid price")
    ask: Optional[float] = Field(None, description="Current ask price")
    week_52_high: Optional[float] = Field(None, alias="week_52_high", description="52-week high")
    week_52_low: Optional[float] = Field(None, alias="week_52_low", description="52-week low")
    market_state: Optional[str] = Field(
        None,
        description="Market state: REGULAR | PRE | POST | CLOSED",
    )
    exchange: Optional[str] = Field(None, description="Exchange code (e.g. NMS, NYQ)")
    exchange_delay_minutes: Optional[int] = Field(
        None, description="Quote delay in minutes (0 = real-time)"
    )

    model_config = {"populate_by_name": True}


class CompanyInfo(BaseModel):
    name: Optional[str] = Field(None, description="Company short name")
    long_name: Optional[str] = Field(None, description="Company full legal name")
    sector: Optional[str] = Field(None, description="Sector (e.g. Technology)")
    industry: Optional[str] = Field(None, description="Industry (e.g. Consumer Electronics)")
    country: Optional[str] = Field(None, description="Country of headquarters")
    website: Optional[str] = Field(None, description="Company website URL")
    description: Optional[str] = Field(None, description="Business summary")
    employees: Optional[int] = Field(None, description="Full-time employee count")


class Fundamentals(BaseModel):
    trailing_pe: Optional[float] = Field(None, description="Trailing 12-month P/E ratio")
    forward_pe: Optional[float] = Field(None, description="Forward P/E ratio")
    beta: Optional[float] = Field(None, description="Beta (5-year monthly vs S&P 500)")
    dividend_yield: Optional[float] = Field(
        None, description="Trailing annual dividend yield (e.g. 0.0045 = 0.45%)"
    )
    eps_trailing: Optional[float] = Field(None, description="Trailing EPS")
    eps_forward: Optional[float] = Field(None, description="Forward EPS estimate")
    book_value: Optional[float] = Field(None, description="Book value per share")
    price_to_book: Optional[float] = Field(None, description="Price-to-book ratio")
    enterprise_value: Optional[int] = Field(None, description="Enterprise value in base currency")
    profit_margins: Optional[float] = Field(None, description="Net profit margin")
    shares_outstanding: Optional[int] = Field(None, description="Total shares outstanding")


class SymbolResponse(BaseModel):
    symbol: str = Field(..., description="Stock ticker symbol (uppercased)")
    quote_type: Optional[str] = Field(None, description="Instrument type: EQUITY, ETF, MUTUALFUND, …")
    as_of: datetime = Field(..., description="UTC timestamp of the response")
    price: PriceInfo
    company: CompanyInfo
    fundamentals: Fundamentals


class ErrorResponse(BaseModel):
    detail: str
