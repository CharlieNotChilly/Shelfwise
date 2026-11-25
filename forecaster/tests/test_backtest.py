import numpy as np
import pandas as pd
import pytest

import backtest
from features import WEEK, features_for_week


@pytest.fixture
def weekly():
    weeks = pd.date_range("2010-09-06", "2011-01-17", freq="W-MON")
    index = pd.MultiIndex.from_product([weeks, ["A", "B", "C"]], names=["week_start", "stock_code"])
    sales = index.to_frame(index=False)
    sales["units"] = sales["stock_code"].map({"A": 4, "B": 3, "C": 2})
    sales["avg_price"] = 1.50
    return sales


def test_s22_selection_ignores_test_sales_and_breaks_ties_by_code(weekly):
    cutoff = backtest.TEST_WEEKS[0]
    weekly.loc[weekly["stock_code"] == "C", "units"] = 3
    weekly.loc[(weekly["week_start"] >= cutoff) & (weekly["stock_code"] == "C"), "units"] = 100000
    assert list(backtest.select_skus(weekly.sample(frac=1, random_state=9), cutoff, 2)) == ["A", "B"]


def test_s23_features_use_the_eight_completed_weeks(weekly):
    target = pd.Timestamp("2011-01-03")
    history = weekly.loc[weekly["week_start"].between(target - 8 * WEEK, target - WEEK)].copy()
    a = history["stock_code"] == "A"
    demand = [1, 2, 3, 4, 5, 6, 0, 0]
    history.loc[a, "units"] = demand
    history.loc[a, "avg_price"] = [1, 2, 3, 4, 5, 9, 0, 0]
    history.loc[~a, "units"] = 0
    features = features_for_week(history.sample(frac=1, random_state=3), target)
    assert features.loc["A"].to_dict() == pytest.approx({
        "lag_1": 0, "lag_2": 0, "lag_3": 6, "lag_4": 5, "lag_8": 1,
        "mean_4": np.mean(demand[-4:]), "std_4": np.std(demand[-4:], ddof=1),
        "mean_8": np.mean(demand), "std_8": np.std(demand, ddof=1),
        "avg_price_4": 7, "weeks_since_sale": 3, "week_of_year": 1, "month": 1,
    })
    assert features.loc["B", "weeks_since_sale"] == 9
    assert pd.isna(features.loc["B", "avg_price_4"])
    with pytest.raises(ValueError, match="completed weeks"):
        features_for_week(pd.concat([history, weekly.loc[weekly["week_start"] == target]]), target)


def test_s23_rolling_origin_observes_actual_feature_and_training_dates(weekly, monkeypatch):
    weeks = backtest.TEST_WEEKS[:7]
    origins = []
    original_features = backtest.features_for_week
    def audited_features(history, target):
        assert history["week_start"].lt(target).all()
        assert history["week_start"].min() == target - 8 * WEEK
        origins.append(target)
        return original_features(history, target)

    training_ends = []
    class AuditedRegressor:
        def __init__(self, **settings):
            pass

        def fit(self, features, labels):
            assert features.index.equals(labels.index)
            self.last_week = labels.index.get_level_values("week_start").max()
            training_ends.append(self.last_week)

        def predict(self, features):
            assert (features.index.get_level_values("week_start") > self.last_week).all()
            return np.zeros(len(features))

    monkeypatch.setattr(backtest, "features_for_week", audited_features)
    monkeypatch.setattr(backtest, "LGBMRegressor", AuditedRegressor)
    predictions = backtest.run_backtest(weekly, weeks, 2)
    assert origins[-len(weeks):] == list(weeks)
    assert training_ends == [pd.Timestamp("2010-11-29"), pd.Timestamp("2010-12-27")]
    assert predictions.groupby("week_start").size().to_dict() == dict.fromkeys(weeks, 2)
    assert predictions["baseline"].tolist() == [4, 3] * len(weeks)


def test_s24_wape_pools_absolute_errors_including_zero_demand_weeks():
    actual = pd.Series([0, 2, 8])
    assert backtest.wape(actual, pd.Series([3, 1, 9])) == 0.5
    with pytest.raises(ValueError, match="positive total"):
        backtest.wape(pd.Series([0]), pd.Series([1]))


def test_s24_s25_summary_requires_complete_paired_predictions(tmp_path):
    index = pd.MultiIndex.from_product(
        [backtest.TEST_WEEKS, range(500)], names=["week_start", "stock_code"]
    )
    predictions = index.to_frame(index=False).assign(actual=4, baseline=3, model=6)
    backtest.write_results(predictions, tmp_path)
    pd.testing.assert_frame_equal(pd.read_parquet(tmp_path / "predictions.parquet"), predictions)
    summary = (tmp_path / "summary.md").read_text()
    for value in ["SKUs evaluated: 500", "Test weeks: 52", "26000", "25.0%", "50.0%", "-100.0%"]:
        assert value in summary
    predictions.iloc[-1] = predictions.iloc[0]
    with pytest.raises(ValueError, match="500 SKUs and 52 weeks"):
        backtest.write_results(predictions, tmp_path)
