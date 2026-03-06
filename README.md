# Finance-API

A containerised REST API proxy that retrieves financial data from Yahoo Finance
and returns it as clean, structured JSON.  No API key required.

[![Build and Push Docker Image](https://github.com/JakePeralta7/Finance-API/actions/workflows/docker-publish.yml/badge.svg)](https://github.com/JakePeralta7/Finance-API/actions/workflows/docker-publish.yml)

---

## Quick Start

```bash
# Pull and run the latest image from GitHub Container Registry
docker pull ghcr.io/eladlevi/finance-api:main
docker run -p 8000:8000 ghcr.io/eladlevi/finance-api:main
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

Returns current price quote, company profile, and key fundamental ratios.

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
    "market_state": "REGULAR",
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

### `GET /health`

Liveness probe — returns `{"status": "ok"}` with HTTP 200.

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
| `LOG_LEVEL` | `INFO` | Python logging level |
| `CORS_ORIGINS` | `*` | Comma-separated allowed origins, or `*` for all |

```bash
docker run -p 8000:8000 \
  -e LOG_LEVEL=DEBUG \
  -e CORS_ORIGINS="https://myapp.example.com" \
  ghcr.io/eladlevi/finance-api:main
```

---

## Docker Image

The image is built and published to GitHub Container Registry on every push to
`main` and on version tags (`v*.*.*`).

```bash
# Latest from main branch
docker pull ghcr.io/eladlevi/finance-api:main

# Specific release
docker pull ghcr.io/eladlevi/finance-api:1.0.0
```

Images are built for **linux/amd64** and **linux/arm64** (Apple Silicon / AWS Graviton).

---

## Project Structure

```
Finance-API/
├── .github/workflows/docker-publish.yml   # CI/CD → ghcr.io
├── app/
│   ├── main.py                            # FastAPI application
│   ├── routers/stock.py                   # GET /stock/{symbol}, GET /health
│   ├── services/
│   │   ├── yahoo_session.py               # curl_cffi session + auth lifecycle
│   │   └── yahoo_client.py                # Yahoo API calls + response normalisation
│   └── models/responses.py                # Pydantic response models
├── Dockerfile
├── requirements.txt
└── .gitignore
```

---

## Disclaimer

This project uses Yahoo Finance's **unofficial internal API**. It is intended
for personal and educational use only.  Yahoo Finance data is subject to
[Yahoo's Terms of Service](https://legal.yahoo.com/us/en/yahoo/terms/otos/index.html).
For production or commercial use, consider a licensed data provider such as
[Polygon.io](https://polygon.io), [Alpha Vantage](https://www.alphavantage.co),
or [Tiingo](https://www.tiingo.com).

---

## License

MIT © 2026 Elad Levi


