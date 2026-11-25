# Shelfwise rolling-origin backtest

- SKUs evaluated: 500
- Test weeks: 52 (2010-12-06 through 2011-11-28)
- SKU-week pairs: 26000

| Method | WAPE |
|---|---:|
| 4-week moving average | 73.55310721989032% |
| Global LightGBM | 63.38833361079639% |

Relative WAPE improvement: 13.819638616633675%

Both methods use the same SKU-week pairs. The SKU ranking was fixed before the test window. LightGBM used absolute-error loss and refit on the first forecast Monday of each month. Every refit used only completed weeks. Model settings were fixed before scoring.
