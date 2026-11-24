# Shelfwise Build Plan

Work **one phase at a time**. Give the AI the phase prompt, check the "done when" line yourself, commit, then move on. Spec IDs (S1.1, S2.3, …) refer to [SPEC.md](SPEC.md).

| # | Phase | Done when | Covers |
|---|---|---|---|
| 0 | Machine, accounts, and data | Every tool in the Phase 0 table reports a version; Shopify Partner account and dev store exist; UCI dataset downloaded | — |
| 1 | Data cleaning (Python) | Weekly sales table built; cleaning tests pass | S2.1 |
| 2 | Backtest | Baseline and model WAPE on 500 SKUs × 52 weeks; leakage test passes; summary saved | S2.2–S2.5 |
| 3 | Model + forecaster service | `model.joblib` trained; FastAPI `POST /forecast` returns predictions; tests pass | S1.5 |
| 4 | Scaffold the Shopify app | Ruby template app installs and opens embedded in the dev store admin | S1.1 |
| 5 | Cost-aware GraphQL client | Client waits on low capacity and retries `THROTTLED`; tests pass | S3.3 |
| 6 | Seed the store | 50 products created; 1,000 real UCI orders created at ≤5/min; `seed_log.csv` saved | S1.2 |
| 7 | Sync | Bulk-operation sync + `orders/create` webhook in background jobs; sync log shows no throttling errors | S3.1, S3.2, S3.4, S3.5 |
| 8 | Forecasts and alerts UI | `ForecastJob` + Polaris table and banner show days until stockout | S1.3, S1.4 |
| 9 | Tests, CI, write-up | CI runs Ruby and Python tests; README results filled from `results/`; screenshots and 60-second demo | — |

The **backtest (phases 1–2) needs no Shopify account**, so it's a good place to start. At the end of phase 8, the early-stage bullets are true; with phase 2's results, all three bullets can be filled.

---

## Phase prompts

Start every session with: *"Read AGENTS.md, docs/SPEC.md, and docs/DESIGN.md first. We are on phase N."*

### Phase 0: Machine, accounts, and data (manual, once)

Build on your **personal** computer and personal GitHub account.

| Tool | Why | Check |
|---|---|---|
| Git | Version control | `git --version` |
| Python 3.12 | Data cleaning, backtest, model, forecaster service | `python3 --version` |
| Ruby 3.3+ and Bundler | The Rails app from the Shopify Ruby template | `ruby -v`, `bundle -v` |
| Node.js 20+ (LTS) | The template's React + Polaris frontend and Shopify CLI | `node -v` |
| Shopify CLI (latest) | Scaffolding, `shopify app dev`, installing on the dev store | `shopify version` |
| Claude Code or Codex CLI | Writing the code phase by phase | `claude --version` / `codex --version` |

On Windows, run everything inside WSL2 (Ubuntu) and keep the repo in the Linux file system (for example `~/code/Shelfwise`), not under `/mnt/c`.

Then:
1. `git clone https://github.com/CharlieNotChilly/Shelfwise.git` and `cd Shelfwise`.
2. Create a Shopify Partner account and a development store (`shopify store create dev` or the Partner Dashboard).
3. Install the Shopify AI Toolkit for your assistant:
   - Claude Code: `claude plugin install shopify-ai-toolkit@claude-plugins-official`
   - Codex: `codex plugin add shopify@openai-curated`
4. Download `online_retail_II.xlsx` from the UCI Machine Learning Repository into `forecaster/data/raw/`, and add `forecaster/data/` and `forecaster/models/*.joblib` to `.gitignore` (create it if needed) so the raw dataset and model files are never committed.

### Phase 1: Data cleaning
```
In forecaster/, set up a Python 3.12 project (pyproject.toml or
requirements.txt) with pandas, openpyxl, lightgbm, scikit-learn, joblib,
fastapi, uvicorn, pytest. Write forecaster/data_prep.py that loads both
sheets of data/raw/online_retail_II.xlsx, applies the cleaning rules in
docs/DESIGN.md, and writes data/processed/weekly_sales.parquet with columns
stock_code, week_start (Monday), units, avg_price, filling missing weeks
with 0. Add pytest tests for each cleaning rule using small hand-made
DataFrames.
```

### Phase 2: Backtest
```
Write forecaster/features.py (features from docs/DESIGN.md, computed only
from weeks before the target week) and forecaster/backtest.py:
- select the top 500 stock codes by units in the training period only
  (weeks before 2010-12-06)
- for each of the 52 test weeks starting 2010-12-06, forecast that week's
  units for every selected SKU with (a) the 4-week moving average and (b) a
  LightGBM global model retrained at the start of each month on all weeks
  before the forecast week
- compute WAPE for both on identical (SKU, week) pairs
- write results/backtest/summary.md (SKU count, week count, baseline WAPE,
  model WAPE, relative improvement) and results/backtest/predictions.parquet
Add a leakage test asserting that features for week t use only rows with
week_start < t, and a test that SKU selection ignores test-window data.
```
Check: summary shows exactly 500 SKUs and 52 weeks. If the model doesn't beat the baseline, stop and report it; don't tune on the test window.

### Phase 3: Model and forecaster service
```
Write forecaster/train.py that trains the final LightGBM model on all
weeks before 2011-12-05 for the top 500 SKUs, using the same features, and
saves models/model.joblib. Write forecaster/service.py, a FastAPI app with
POST /forecast taking {"series": [{"sku": str, "weekly_units": [8 numbers,
oldest first], "avg_price": float}]} and returning next-week forecasts per
SKU (non-negative). Add a GET /health. Add tests for both endpoints using
the saved model and a fixture. Add a Dockerfile.
```

### Phase 4: Scaffold the Shopify app
```
Scaffold the app with Shopify CLI using the Ruby template:
shopify app init --template=https://github.com/Shopify/shopify-app-template-ruby
Put it in web/. Configure access scopes: read_products, write_products,
read_inventory, write_inventory, read_orders, write_orders. Run
shopify app dev, install on the dev store, and confirm the app opens
embedded in the admin. Document the steps in the README.
```
Check: take a screenshot of the embedded app → `results/demo/`. If the Ruby template no longer works with current Shopify CLI, stop: switching templates changes the résumé stack line.

### Phase 5: Cost-aware GraphQL client
```
In web/, add app/services/shopify_graphql.rb wrapping the template's
GraphQL client. Before each call, if the last known currentlyAvailable is
below the query's expected cost, sleep (cost - available) / restoreRate
seconds. After each call, update throttle state from
extensions.cost.throttleStatus. On a THROTTLED error, retry up to 5 times
with exponential backoff and jitter. Log every wait and retry to
log/shopify_throttle.log. Add RSpec tests with stubbed responses for the
wait and retry paths.
```

### Phase 6: Seed the store
```
Write seed/ scripts (Ruby rake tasks in web/ are fine) that:
1. read the top-500 list and pick 50 demo SKUs (highest training volume,
   distinct descriptions)
2. create one product per SKU via productCreate (SKU = StockCode,
   title = Description, price from UCI) and set inventory quantities so
   about 10 products will be within 14 days of running out
3. take the first 1,000 real UCI invoices (chronological, cleaned) that
   contain at least one demo SKU, keep only demo-SKU line items, shift all
   dates by one fixed offset so they fall in the last 8 weeks, and create
   each with orderCreate setting processedAt; sleep at least 12 seconds
   between orders (dev stores allow 5 orders per minute)
4. be resumable (skip invoices already created) and append each result
   to results/seed/seed_log.csv: uci_invoice, shopify_order_id,
   processed_at, line_count
Use the cost-aware client for every call.
```
Check: `seed_log.csv` has 1,000 rows and the store's order count is at least 1,000. The order seeding takes about 3.5 hours, so run it overnight.

### Phase 7: Sync
```
Add BulkSyncJob: start bulkOperationRunQuery for orders with line items
(id, sku, quantity) and processedAt, poll currentBulkOperation until
COMPLETED, download the JSONL, and upsert order_lines keyed by line-item
ID. Register the orders/create webhook; OrderWebhookJob upserts the same
way (idempotent). After syncing, rebuild weekly_sales and enqueue
ForecastJob. All of this runs in background jobs. Add tests: JSONL fixture
parsing, idempotent upsert, webhook handling. Run a full sync and save the
log to results/sync/sync_log.txt.
```
Check: `order_lines` covers all 1,000 orders; the sync log shows no unhandled throttling errors.

### Phase 8: Forecasts and alerts UI
```
Add ForecastJob: for each product, build its last 8 weeks of units from
weekly_sales, call the forecaster's POST /forecast, read on-hand inventory,
compute days_until_stockout = on_hand / (forecast / 7), mark at_risk when
under the threshold (default 14, configurable), and save to forecasts.
Add an API endpoint returning forecasts, and a React page using Polaris:
an IndexTable (product, SKU, on hand, forecast per week, days left, status
Badge) and a Banner summarizing at-risk products. Add tests for the
calculation and the endpoint.
```
Check: screenshots of the table and banner → `results/demo/`.

### Phase 9: Tests, CI, write-up
Add GitHub Actions running RSpec and pytest. Fill the README results from `results/backtest/summary.md`, add the architecture diagram from DESIGN.md, screenshots, and a 60-second demo video. Then fill `[A]` and `[B]` in SPEC.md from the same summary.
