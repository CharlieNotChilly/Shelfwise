# Shelfwise Design

## Problem

Small merchants run out of stock on their best sellers because they reorder by gut feel. Shelfwise forecasts weekly demand per product and warns the merchant, inside the Shopify admin, before a product runs out.

## Repository layout

```
web/            Rails app from the Shopify Ruby template (backend + React/Polaris frontend)
forecaster/     Python: data cleaning, backtest, model training, FastAPI prediction service
seed/           Scripts that create products and 1,000 real UCI orders in the dev store
results/        Backtest, seed, sync, and demo evidence
docs/           SPEC, DESIGN, PLAN
```

## Architecture

```
                 ┌──────────────── Shopify dev store ────────────────┐
                 │ products, inventory, 1,000 seeded orders          │
                 └───────▲───────────────┬───────────────┬──────────┘
        bulkOperationRunQuery   orders/create webhook   App Bridge (embedded UI)
                         │               │               │
┌────────────────────────┴───────────────▼───────────────┴──────────┐
│ Rails (web/)                                                       │
│  ShopifyGraphql client (cost-aware)   Background jobs:             │
│                                        BulkSyncJob, OrderWebhookJob│
│                                        ForecastJob                 │
│  DB: products, order_lines, weekly_sales, forecasts                │
│  React + Polaris page: Stockout risk table + banner                │
└────────────────────────────────┬──────────────────────────────────┘
                                 │ POST /forecast (weekly series)
                     ┌───────────▼────────────┐
                     │ forecaster (FastAPI)    │  model.joblib trained
                     │ LightGBM global model   │  offline on UCI data
                     └─────────────────────────┘
```

## Data: UCI Online Retail II

Columns: `Invoice`, `StockCode`, `Description`, `Quantity`, `InvoiceDate`, `Price`, `Customer ID`, `Country`. Two sheets: 2009–2010 and 2010–2011.

**Cleaning rules (unit-tested):**
1. Drop cancellations: `Invoice` starting with `C`.
2. Drop rows with `Quantity <= 0` or `Price <= 0`.
3. Drop non-product codes: `StockCode` values that don't start with a digit (e.g., `POST`, `DOT`, `M`, `BANK CHARGES`, `AMAZONFEE`, `C2`, `D`, `S`, `PADS`).
4. Drop rows with a missing `Description`.
5. Aggregate to **weekly units per StockCode**, weeks starting Monday; fill missing weeks with 0.

## Backtest

- **Training period:** weeks before 2010-12-06. **Test window:** 52 weeks starting 2010-12-06.
- **SKU selection:** top 500 StockCodes by units sold in the training period only.
- **Rolling origin:** for each test week `t`, train on weeks `< t` and predict week `t`. Retrain at the start of each month to keep run time reasonable.
- **Features** (all from weeks before `t`): lags 1, 2, 3, 4, 8; rolling mean and std over 4 and 8 weeks; week of year; month; average price over the last 4 weeks; weeks since last sale. Lags stop at 8 weeks so the same model works on the store's 8 weeks of history.
- **Baseline:** mean of the previous 4 weeks.
- **Metric:** WAPE = Σ|actual − forecast| ÷ Σ actual over all (SKU, week) pairs. Report baseline and model on identical pairs.
- **Leakage guard:** a test that builds features for a given week and asserts every source row is from an earlier week.

## Store seeding

1. Pick **50 demo SKUs** from the top 500 (highest volume, distinct products).
2. Create one product per SKU (`productCreate`, SKU = StockCode, title = Description, price from UCI), with inventory set so a few products are close to running out.
3. Take the first **1,000 real UCI invoices** (chronologically) that contain at least one demo SKU, keep only demo-SKU line items, and shift all dates by a fixed offset into the **last 8 weeks**. Shopify only returns orders from the last 60 days without the special `read_all_orders` access.
4. Create each order with `orderCreate`, setting `processedAt` to the shifted date. Development stores allow **5 new orders per minute**, so the script sleeps 12+ seconds between orders (about 3.5 hours total), logs progress, and resumes where it left off.
5. Write `results/seed/seed_log.csv`: UCI invoice number → Shopify order ID → processedAt.

## Sync

- **Cost-aware client:** every GraphQL call reads `extensions.cost.throttleStatus` (`currentlyAvailable`, `restoreRate`). If the next query's cost exceeds what's available, wait `(cost − available) ÷ restoreRate` seconds. On a `THROTTLED` error, retry with exponential backoff and jitter. Log every wait and retry.
- **Initial sync:** `BulkSyncJob` starts `bulkOperationRunQuery` for orders with line items (SKU, quantity, processedAt), polls until finished (or reacts to the `bulk_operations/finish` webhook), downloads the JSONL file, and upserts `order_lines` keyed by Shopify line-item ID.
- **Incremental:** `orders/create` webhook → `OrderWebhookJob` upserts the same way, so duplicate deliveries are harmless.
- After syncing, rebuild `weekly_sales` and enqueue `ForecastJob`.

## Forecasting in the app

- `ForecastJob` sends each product's weekly sales series (last 8 weeks) to the forecaster's `POST /forecast`, which returns next-week demand from the trained model.
- `days_until_stockout = on_hand ÷ (forecast_weekly ÷ 7)`; products under the threshold (default 14 days) are flagged.
- The Polaris page shows an `IndexTable` (product, SKU, on hand, forecast/week, days left, status badge) and a `Banner` summarizing at-risk products.

## Data model (Rails)

| Table | Key columns |
|---|---|
| `products` | `shopify_variant_id`, `sku`, `title`, `on_hand` |
| `order_lines` | `shopify_line_item_id` (unique), `shopify_order_id`, `sku`, `quantity`, `processed_at` |
| `weekly_sales` | `sku`, `week_start`, `units` |
| `forecasts` | `sku`, `week_start`, `forecast_units`, `days_until_stockout`, `at_risk`, `computed_at` |

## Key decisions (be ready to defend these)

1. **Global gradient-boosted model, not one model per SKU.** Most SKUs have sparse, noisy history; a global model learns shared patterns across products.
2. **WAPE, not MAPE.** Many SKU-weeks sell zero units, and MAPE divides by actual sales.
3. **Rolling-origin backtest.** It mimics real use: each forecast only sees the past.
4. **Bulk operations for the initial sync.** One asynchronous job instead of paging thousands of orders through rate-limited queries.
5. **Separate Python forecaster.** Python has the better ML tooling; Rails stays the Shopify-facing app.
6. **8-week feature window.** Matches the 60-day order window and the seeded history.

## Interview questions

1. How did you prevent future data from leaking into the backtest?
2. Why WAPE? Where does the model still fail (intermittent demand, new products)?
3. How does the client stay within Shopify's cost-based rate limit?
4. What happens if a webhook is delivered twice, or not at all?
5. Why bulk operations instead of paginated queries?
6. How would this work for a store with 100K SKUs?
