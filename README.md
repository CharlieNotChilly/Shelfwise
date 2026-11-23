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

_Filled in during phases 3–4._

## Project docs

- [docs/SPEC.md](docs/SPEC.md): acceptance criteria
- [docs/DESIGN.md](docs/DESIGN.md): architecture and decisions
- [docs/PLAN.md](docs/PLAN.md): build phases

## Data

UCI Online Retail II (Chen, 2019), UCI Machine Learning Repository. The raw dataset is not committed; download it as described in PLAN.md phase 0.
