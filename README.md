# Shelfwise

An embedded Shopify app that forecasts weekly demand per product and warns merchants, inside the Shopify admin, before a product runs out of stock. Forecasts come from a gradient-boosted model backtested on real retail transactions from the UCI Online Retail II dataset.

**Stack:** Ruby on Rails (Shopify Ruby app template), Shopify GraphQL Admin API, Polaris, Python (pandas, LightGBM, FastAPI)

## Results

All numbers come from files in [`results/`](results/).

### Backtest: top 500 SKUs, 52 weekly forecasts (Dec 2010 – Nov 2011)

| Method | WAPE |
|---|---|
| 4-week moving average (baseline) | |
| Gradient-boosted model (LightGBM) | |

Relative improvement: **_%**

### Demo store

| Seeded orders (real UCI invoices) | Demo products | Unhandled throttling errors during seed + sync |
|---|---|---|
| | 50 | |

_Screenshots of the stockout table and banner go here._

## How it works

See [docs/DESIGN.md](docs/DESIGN.md) for the architecture, backtest method, seeding, sync, and design decisions.

## Running it

Build and start the forecaster from the repository root. The image includes the fitted model.

```sh
docker build -t shelfwise-forecaster forecaster
docker run --rm -p 127.0.0.1:8000:8000 shelfwise-forecaster
```

Check readiness and request a forecast in a second terminal.

```sh
curl -fsS http://127.0.0.1:8000/health
curl -fsS http://127.0.0.1:8000/forecast -H 'Content-Type: application/json' \
  -d '{"series":[{"sku":"DEMO","weekly_units":[0,2,1,0,4,0,3,1],"avg_price":2.75}]}'
```

Send the eight most recently completed Monday–Sunday weeks, oldest first. The service forecasts the week beginning on the current UTC week's Monday. Supply the mean of the selling weeks' average prices over the last four completed weeks. When none had sales, send zero and the service treats the price feature as missing. The response lists `sku` and non-negative `forecast_units` under `forecasts`, in request order.

To rebuild the model locally, install Python 3.12 and the OpenMP runtime (`libomp` on macOS). Place the UCI workbook as described in phase 0, then run from the repository root.

```sh
python3.12 -m venv forecaster/.venv
forecaster/.venv/bin/python -m pip install './forecaster[test]'
forecaster/.venv/bin/python forecaster/data_prep.py
forecaster/.venv/bin/python forecaster/train.py
forecaster/.venv/bin/python -m pytest -q
```

## Project docs

- [docs/SPEC.md](docs/SPEC.md): acceptance criteria
- [docs/DESIGN.md](docs/DESIGN.md): architecture and decisions
- [docs/PLAN.md](docs/PLAN.md): build phases

## Data

UCI Online Retail II (Chen, 2019), UCI Machine Learning Repository. The raw dataset is not committed; download it as described in PLAN.md phase 0.
