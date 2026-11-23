# Results

Every number on the résumé and in the README must trace to a file here. Commit these files.

```
results/
  backtest/
    summary.md            SKU count, week count, baseline WAPE, model WAPE, improvement
    predictions.parquet   every (SKU, week): actual, baseline, model
  seed/
    seed_log.csv          uci_invoice, shopify_order_id, processed_at, line_count
  sync/
    sync_log.txt          bulk operation run + throttle waits/retries
  demo/
    *.png                 embedded app, stockout table, banner
```

## Where each résumé number comes from

| Résumé value | Source |
|---|---|
| 1,000 real orders | `seed/seed_log.csv` row count (and the store's order count) |
| `[A]%` baseline WAPE | `backtest/summary.md` |
| `[B]%` model WAPE | `backtest/summary.md` |
| 500 SKUs, 12 months | `backtest/summary.md` counts (500 SKUs, 52 weeks) |
| Within rate limits | `sync/sync_log.txt` shows no unhandled throttling errors |

Rules: don't edit result files by hand, don't delete failed runs, and re-run the full backtest after any model change.
