# Shelfwise Spec (the contract)

This file turns each résumé bullet into acceptance criteria. **The code must satisfy every criterion before the matching bullet goes on a résumé.** If the code and this spec disagree, fix the code or change the bullet.

## Résumé bullets

```latex
\resumeProjectHeading
  {Shelfwise -- AI Inventory Forecasting for Shopify}{Ruby on Rails, Shopify GraphQL API, Polaris, Python}
\resumeItemListStart
  \resumeItem{Built an embedded \textbf{Shopify app} that forecasts per-SKU stockouts and alerts merchants in the admin, demoed on a dev store seeded with \textbf{1,000} real orders from the UCI Online Retail II dataset.}
  \resumeItem{Cut forecast error (WAPE) from \textbf{[A]\%} to \textbf{[B]\%} vs. a moving-average baseline with a gradient-boosted model, backtested on the top \textbf{500} SKUs over \textbf{12} months without future-data leakage.}
  \resumeItem{Synced store orders via GraphQL bulk operations and webhooks with cost-aware background jobs, staying within Shopify API rate limits.}
\resumeItemListEnd
```

`[A]` and `[B]` are **measured**, never chosen. Fill them only from `results/backtest/summary.md`. If the model does not beat the baseline, bullet 2 cannot say "cut"; rewrite it or improve the model.

**Early-stage version** (true once the bullet 1 and bullet 3 criteria pass):

```latex
\resumeItem{Built an embedded \textbf{Shopify app} that forecasts per-SKU stockouts and alerts merchants in the admin, demoed on a dev store seeded with \textbf{1,000} real orders from the UCI Online Retail II dataset.}
\resumeItem{Synced store orders via GraphQL bulk operations and webhooks with cost-aware background jobs, staying within Shopify API rate limits.}
```

## Fixed parameters (do not change without changing the bullets)

| Parameter | Value |
|---|---|
| Dataset | UCI Online Retail II (Dec 2009 – Dec 2011), cleaned as in DESIGN.md |
| Backtest SKUs | Top **500** SKUs by quantity sold **in the training period only** (before the test window) |
| Test window | **12 months** of weekly forecasts: weeks starting 2010-12-06 through 2011-11-28 |
| Forecast target | Units sold per SKU per week, one week ahead |
| Metric | **WAPE** = Σ\|actual − forecast\| ÷ Σ actual, over all (SKU, week) pairs in the test window |
| Baseline | 4-week moving average |
| Model | Gradient-boosted trees (LightGBM), one global model across SKUs |
| Seeded store orders | **1,000** real UCI invoices (limited to the demo SKUs), dates shifted into the last 8 weeks |
| Store stack | Shopify Ruby app template (Rails backend, React + Polaris frontend) |

## Bullet 1: embedded app with stockout alerts

| ID | Criterion | How it is verified |
|---|---|---|
| S1.1 | The app is built from the Shopify Ruby (Rails) template and runs embedded in the dev store's admin | Screenshot in `results/demo/` |
| S1.2 | The dev store contains **at least 1,000** orders created from real UCI invoices; each order's line items and quantities match its source invoice | `results/seed/seed_log.csv` maps every Shopify order ID to a UCI invoice number |
| S1.3 | For each product, the app shows on-hand inventory, forecast weekly demand, and estimated days until stockout | Screenshot; spec test for the calculation |
| S1.4 | Products under the alert threshold (default 14 days) are flagged in a Polaris table and summarized in a banner | Screenshot |
| S1.5 | Forecasts come from the trained gradient-boosted model, not a placeholder | The forecaster service loads `forecaster/models/model.joblib`; test |

## Bullet 2: backtest

| ID | Criterion | How it is verified |
|---|---|---|
| S2.1 | Cleaning rules in DESIGN.md are implemented and unit-tested | Tests |
| S2.2 | SKU selection uses only data before the test window | Code + test |
| S2.3 | Rolling-origin backtest: for each test week, the model is trained only on weeks before that week (retraining at least monthly is fine) and features use only data before the forecast week | Leakage test asserts every feature's source week < forecast week |
| S2.4 | WAPE is computed exactly as defined above for the baseline (`[A]`) and the model (`[B]`) on the same (SKU, week) pairs | `results/backtest/summary.md` |
| S2.5 | Exactly 500 SKUs and 52 test weeks are evaluated | Summary prints both counts |

## Bullet 3: sync

| ID | Criterion | How it is verified |
|---|---|---|
| S3.1 | Initial sync uses `bulkOperationRunQuery` and parses the JSONL result into the app database | Code + test with a fixture JSONL file |
| S3.2 | New orders arrive through the `orders/create` webhook and are upserted idempotently | Test; demo: create an order and see it appear |
| S3.3 | All GraphQL calls go through a client that reads `extensions.cost.throttleStatus` and waits when capacity is low, and retries `THROTTLED` errors with backoff | Code + test with a stubbed throttle response |
| S3.4 | Sync runs in background jobs, not in web requests | Code |
| S3.5 | A full seed + sync run completes with **zero** unhandled throttling errors | `results/sync/sync_log.txt` |

## Stack line

Only list technologies the repo actually uses: Ruby on Rails, Shopify GraphQL API, Polaris, Python. If you switch to a non-Rails template, change the stack line and bullet 1.
