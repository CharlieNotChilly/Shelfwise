"""Run the official rolling-origin evaluation with python forecaster/backtest.py."""

from pathlib import Path

import numpy as np
import pandas as pd
from lightgbm import LGBMRegressor

from data_prep import WEEKLY_SALES
from features import HISTORY_WEEKS, WEEK, features_for_week


TEST_WEEKS = pd.date_range("2010-12-06", periods=52, freq="W-MON")
SKU_COUNT = 500
RESULTS = Path(__file__).resolve().parents[1] / "results" / "backtest"


def select_skus(weekly: pd.DataFrame, cutoff: pd.Timestamp, count: int) -> pd.Index:
    training = weekly.loc[weekly["week_start"] < cutoff]
    # groupby sorts stock codes, giving ties a stable, predeclared ordering.
    totals = training.groupby("stock_code", sort=True)["units"].sum()
    ranked = totals[totals > 0].sort_values(ascending=False, kind="stable")
    if len(ranked) < count:
        raise ValueError("Too few SKUs with sales before the test window")
    return ranked.index[:count]


def run_backtest(weekly: pd.DataFrame, weeks: pd.DatetimeIndex = TEST_WEEKS,
                 sku_count: int = SKU_COUNT) -> pd.DataFrame:
    skus = select_skus(weekly, weeks[0], sku_count)
    sales = weekly.loc[weekly["stock_code"].isin(skus) & (weekly["week_start"] <= weeks[-1])]
    by_week = sales.set_index("week_start").sort_index()
    first_target = by_week.index.min() + HISTORY_WEEKS * WEEK
    targets = pd.date_range(first_target, weeks[-1], freq="W-MON")
    feature_rows = {}
    for target in targets:
        history = by_week.loc[target - HISTORY_WEEKS * WEEK : target - WEEK].reset_index()
        feature_rows[target] = features_for_week(history, target)

    features = pd.concat(feature_rows, names=["week_start", "stock_code"])
    expected = pd.MultiIndex.from_product([targets, sorted(skus)], names=features.index.names)
    actuals = sales.set_index(["week_start", "stock_code"])["units"].reindex(expected)
    if not features.index.equals(expected) or actuals.isna().any():
        raise ValueError("Missing SKU-week observations in the backtest panel")

    month = None
    predictions = []
    origins = features.index.get_level_values("week_start")
    for target in weeks:
        if target.to_period("M") != month:
            month = target.to_period("M")
            training = origins < target
            model = LGBMRegressor(
                objective="regression_l1", n_estimators=100, learning_rate=0.1,
                num_leaves=31, random_state=42, n_jobs=1, verbosity=-1,
            )
            model.fit(features.loc[training], actuals.loc[training])

        current = features.xs(target, drop_level=False)
        predictions.append(pd.DataFrame({
            "actual": actuals.loc[current.index],
            "baseline": current["mean_4"],
            "model": np.maximum(model.predict(current), 0),
        }, index=current.index))
    return pd.concat(predictions).reset_index()


def wape(actual: pd.Series, forecast: pd.Series) -> float:
    total = actual.sum()
    if total <= 0:
        raise ValueError("WAPE requires positive total actual demand")
    return float((actual - forecast).abs().sum() / total)


def write_results(predictions: pd.DataFrame, output: Path) -> None:
    expected = pd.MultiIndex.from_product(
        [TEST_WEEKS, predictions["stock_code"].unique()], names=["week_start", "stock_code"]
    )
    measured = predictions.set_index(["week_start", "stock_code"])
    if (predictions["stock_code"].nunique() != SKU_COUNT
            or not measured.index.sort_values().equals(expected.sort_values())
            or not np.isfinite(measured[["actual", "baseline", "model"]]).all().all()):
        raise ValueError("Expected finite predictions and actuals on all 500 SKUs and 52 weeks")
    baseline = wape(measured["actual"], measured["baseline"])
    model = wape(measured["actual"], measured["model"])
    improvement = f"{100 * (baseline - model) / baseline}%" if baseline else "undefined (zero baseline WAPE)"
    output.mkdir(parents=True, exist_ok=True)
    predictions.to_parquet(output / "predictions.parquet", index=False)
    (output / "summary.md").write_text(
        "# Shelfwise rolling-origin backtest\n\n"
        f"- SKUs evaluated: {predictions['stock_code'].nunique()}\n"
        f"- Test weeks: {predictions['week_start'].nunique()} "
        f"({TEST_WEEKS[0].date()} through {TEST_WEEKS[-1].date()})\n"
        f"- SKU-week pairs: {len(predictions)}\n\n"
        "| Method | WAPE |\n|---|---:|\n"
        f"| 4-week moving average | {100 * baseline}% |\n"
        f"| Global LightGBM | {100 * model}% |\n\n"
        f"Relative WAPE improvement: {improvement}\n\n"
        "Both methods use the same SKU-week pairs. The SKU ranking was fixed before the test window. "
        "LightGBM used absolute-error loss and refit on the first forecast Monday of each month. "
        "Every refit used only completed weeks. Model settings were fixed before scoring.\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    write_results(run_backtest(pd.read_parquet(WEEKLY_SALES)), RESULTS)
