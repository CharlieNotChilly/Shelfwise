"""Weekly model inputs from the eight completed weeks before a forecast."""

import numpy as np
import pandas as pd


HISTORY_WEEKS = 8
WEEK = pd.Timedelta(weeks=1)


def features_for_week(history: pd.DataFrame, forecast_week: pd.Timestamp) -> pd.DataFrame:
    """Use one observed row per SKU and Monday in the eight-week history."""
    weeks = pd.date_range(end=forecast_week - WEEK, periods=HISTORY_WEEKS, freq="W-MON")
    if forecast_week.weekday() != 0 or not history["week_start"].isin(weeks).all():
        raise ValueError("Expected only completed weeks from the eight Mondays before the forecast")
    units = history.pivot(index="stock_code", columns="week_start", values="units").reindex(columns=weeks)
    if units.empty or units.isna().any().any():
        raise ValueError("Every SKU needs eight weekly observations, including zero-sales weeks")

    features = pd.DataFrame(index=units.index)
    for lag in (1, 2, 3, 4, 8):
        features[f"lag_{lag}"] = units.iloc[:, -lag]
    for window in (4, 8):
        previous = units.iloc[:, -window:]
        features[f"mean_{window}"] = previous.mean(axis=1)
        features[f"std_{window}"] = previous.std(axis=1)

    prices = history.pivot(index="stock_code", columns="week_start", values="avg_price")
    recent_prices = prices.reindex(columns=weeks[-4:])
    features["avg_price_4"] = recent_prices.where(units[weeks[-4:]] > 0).mean(axis=1)
    sold = units.to_numpy()[:, ::-1] > 0
    features["weeks_since_sale"] = np.where(sold.any(axis=1), sold.argmax(axis=1) + 1, HISTORY_WEEKS + 1)
    features["week_of_year"] = forecast_week.isocalendar().week
    features["month"] = forecast_week.month
    return features
