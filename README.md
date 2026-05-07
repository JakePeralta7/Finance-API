# Finance-API

A containerised REST API proxy that retrieves financial data from Yahoo Finance
and returns it as clean, structured JSON.  No API key required.

[![Build and Push Docker Image](https://github.com/JakePeralta7/Finance-API/actions/workflows/docker-publish.yml/badge.svg)](https://github.com/JakePeralta7/Finance-API/actions/workflows/docker-publish.yml)

---

## Quick Start

```bash
# Pull and run the latest image from GitHub Container Registry
docker pull ghcr.io/JakePeralta7/finance-api:latest
docker run -p 8000:8000 ghcr.io/JakePeralta7/finance-api:latest
```

Or build locally:

```bash
docker build -t finance-api .
docker run -p 8000:8000 finance-api
```

Swagger UI is available at **http://localhost:8000/docs** once the container is running.

---

## Endpoints

### `GET /stock/{symbol}`

Returns the current price quote, company profile, and key fundamental ratios for a ticker symbol.

Supported symbols: equities (`AAPL`), indices (`^GSPC`), forex (`EURUSD=X`), ETFs (`SPY`).

**Example**

```bash
curl http://localhost:8000/stock/AAPL
```

**Response schema**

```jsonc
{
  "symbol": "AAPL",
  "quote_type": "EQUITY",
  "as_of": "2026-03-06T12:00:00Z",
  "price": {
    "price": 213.49,
    "currency": "USD",
    "change": 2.49,
    "change_pct": 1.18,
    "previous_close": 211.00,
    "open": 213.00,
    "day_high": 214.10,
    "day_low": 212.50,
    "volume": 45678900,
    "avg_volume_3m": 56789000,
    "market_cap": 3280000000000,
    "bid": 213.48,
    "ask": 213.50,
    "week_52_high": 237.23,
    "week_52_low": 164.08,
    "market_state": "REGULAR",       // REGULAR | PRE | POST | CLOSED
    "exchange": "NMS",
    "exchange_delay_minutes": 0
  },
  "company": {
    "name": "Apple Inc.",
    "long_name": "Apple Inc.",
    "sector": "Technology",
    "industry": "Consumer Electronics",
    "country": "United States",
    "website": "https://www.apple.com",
    "description": "Apple Inc. designs, manufactures …",
    "employees": 150000
  },
  "fundamentals": {
    "trailing_pe": 32.5,
    "forward_pe": 28.1,
    "beta": 1.24,
    "dividend_yield": 0.0045,
    "eps_trailing": 6.57,
    "eps_forward": 7.60,
    "book_value": 4.44,
    "price_to_book": 48.1,
    "enterprise_value": 3320000000000,
    "profit_margins": 0.261,
    "shares_outstanding": 15365000000
  }
}
```

---

### `GET /stock/{symbol}/history`

Returns historical OHLCV (open, high, low, close, volume) bars for a ticker symbol.

| Query param | Default | Allowed values |
|---|---|---|
| `period` | `1mo` | `1d` `5d` `1mo` `3mo` `6mo` `1y` `2y` `5y` `10y` `ytd` `max` |
| `interval` | `1d` | `1m` `2m` `5m` `15m` `30m` `60m` `90m` `1h` `1d` `5d` `1wk` `1mo` `3mo` |

Intraday intervals return full UTC ISO 8601 timestamps; daily and longer intervals return date-only strings.

**Example**

```bash
# Last month of daily bars
curl "http://localhost:8000/stock/AAPL/history?period=1mo&interval=1d"

# Today's 5-minute bars
curl "http://localhost:8000/stock/AAPL/history?period=1d&interval=5m"
```

**Response schema**

```jsonc
{
  "symbol": "AAPL",
  "period": "1mo",
  "interval": "1d",
  "as_of": "2026-05-07T14:00:00Z",
  "data": [
    { "date": "2026-04-07", "open": 250.1, "high": 255.3, "low": 249.0, "close": 253.5, "volume": 61200000 },
    { "date": "2026-04-08", "open": 254.0, "high": 258.9, "low": 252.1, "close": 257.4, "volume": 48900000 }
    // …
  ]
}
```

---

### `GET /health`

Liveness probe — returns `{"status": "ok"}` with HTTP 200.  Used by the Docker `HEALTHCHECK` and Kubernetes readiness probes.

---

## How It Works

Yahoo Finance's internal JSON APIs require Chrome-matching TLS fingerprints
(JA3/JA4).  Standard Python HTTP libraries (`requests`, `httpx`) are blocked at
the TLS layer.  This project uses
[**curl_cffi**](https://github.com/yifeikong/curl_cffi) — a Python binding
to `libcurl` compiled with BoringSSL — to replay Chrome's exact TLS ClientHello.

Auth flow on startup:

1. `GET https://fc.yahoo.com` — Yahoo sets a session cookie (`A3`).
2. `GET https://query1.finance.yahoo.com/v1/test/getcrumb` — returns a crumb
   token that is appended to every subsequent API call.

The session is re-used across requests and refreshed automatically when the
1-hour TTL expires or Yahoo returns HTTP 401.

---

## Configuration

All configuration is done through environment variables:

| Variable | Default | Description |
|---|---|---|
| `LOG_LEVEL` | `INFO` | Python logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |
| `CORS_ORIGINS` | `*` | Comma-separated list of allowed origins, or `*` for all |

```bash
docker run -p 8000:8000 \
  -e LOG_LEVEL=DEBUG \
  -e CORS_ORIGINS="https://myapp.example.com" \
  ghcr.io/JakePeralta7/finance-api:latest
```

---

## Project Structure

```
app/
├── main.py                  # FastAPI app, middleware, lifecycle hooks
├── routers/
│   └── stock.py             # Route definitions and input validation
├── models/
│   └── responses.py         # Pydantic response models
└── services/
    ├── yahoo_client.py      # Yahoo Finance fetch + normalisation logic
    └── yahoo_session.py     # Persistent curl_cffi session with auto re-auth
```
