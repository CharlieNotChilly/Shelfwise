import joblib
import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient
from lightgbm import LGBMRegressor

import service
import train
from backtest import TEST_WEEKS, demand_model, training_panel
from features import WEEK, features_for_week


@pytest.fixture
def client():
    with TestClient(service.app) as api:
        yield api


@pytest.fixture
def series():
    return [
        {"sku": "Z", "weekly_units": [0, 0, 0, 2, 9, 0, 12, 3], "avg_price": 2.75},
        {"sku": "A", "weekly_units": [0] * 8, "avg_price": 0},
        {"sku": "B", "weekly_units": [140] * 8, "avg_price": 4.50},
    ]


def test_s15_health_after_loading_fitted_model(client):
    assert client.get("/health").json() == {"status": "ok"}
    assert isinstance(service.app.state.model, LGBMRegressor)
    assert service.app.state.model.booster_.num_trees() > 0


def test_s15_forecast_matches_saved_model_on_offline_features(client, series, monkeypatch):
    target = pd.Timestamp("2026-01-05")
    monkeypatch.setitem(service.app.dependency_overrides, service.forecast_monday, lambda: target)
    weeks = pd.date_range("2025-11-10", "2025-12-29", freq="W-MON")
    history = pd.concat([
        pd.DataFrame({
            "stock_code": item["sku"], "week_start": weeks, "units": item["weekly_units"],
            "avg_price": item["avg_price"],
        }) for item in series
    ])
    # Distinct prior selling prices for Z average to the scalar sent by the client.
    history.loc[history["stock_code"] == "Z", "avg_price"] = [0, 0, 0, 8, 2, 0, 3, 3.25]
    features = features_for_week(history, target)
    model = joblib.load(train.MODEL_PATH)
    expected = pd.Series(np.maximum(0, model.predict(features)), index=features.index)
    response = client.post("/forecast", json={"series": series})
    assert response.status_code == 200, response.text
    assert response.json() == {"forecasts": [
        {"sku": item["sku"], "forecast_units": expected[item["sku"]]} for item in series
    ]}


@pytest.mark.parametrize("change", [
    {"weekly_units": [1] * 7}, {"weekly_units": [1] * 9},
    {"weekly_units": [-1] * 8}, {"avg_price": -1}, {"sku": " "},
])
def test_s15_invalid_series(client, series, change):
    assert client.post("/forecast", json={"series": [{**series[0], **change}]}).status_code == 422


def test_s15_duplicate_sku(client, series):
    assert client.post("/forecast", json={"series": [series[0], series[0]]}).status_code == 422


def test_s15_final_fit_preserves_original_sku_selection_and_training_cutoff(tmp_path, monkeypatch):
    weeks = pd.date_range("2010-09-06", train.TRAIN_BEFORE + WEEK, freq="W-MON")
    panel = pd.MultiIndex.from_product([weeks, ["A", "B"]], names=["week_start", "stock_code"])
    weekly = panel.to_frame(index=False)
    weekly["units"] = weekly["week_start"].dt.isocalendar().week.astype(int)
    weekly["avg_price"] = 2.0
    is_b = weekly["stock_code"] == "B"
    weekly.loc[is_b & (weekly["week_start"] < TEST_WEEKS[0]), "units"] = 1
    weekly.loc[is_b & (weekly["week_start"] >= TEST_WEEKS[0]), "units"] = 100000
    weekly.loc[weekly["week_start"] >= train.TRAIN_BEFORE, "units"] = 999999

    monkeypatch.setattr(train, "SKU_COUNT", 1)
    path = tmp_path / "models" / "model.joblib"
    train.train(weekly, path)
    features, actuals = training_panel(weekly, pd.Index(["A"]), pd.Timestamp("2011-11-28"))
    reference = demand_model().fit(features, actuals)
    assert joblib.load(path).booster_.model_to_string() == reference.booster_.model_to_string()
