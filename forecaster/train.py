"""Fit the serving model with python forecaster/train.py."""

from pathlib import Path
from tempfile import TemporaryDirectory

import joblib
import pandas as pd

from backtest import SKU_COUNT, TEST_WEEKS, demand_model, select_skus, training_panel
from data_prep import WEEKLY_SALES
from features import WEEK


MODEL_PATH = Path(__file__).resolve().parent / "models" / "model.joblib"
TRAIN_BEFORE = pd.Timestamp("2011-12-05")


def train(weekly: pd.DataFrame, output: Path = MODEL_PATH) -> None:
    skus = select_skus(weekly, TEST_WEEKS[0], SKU_COUNT)
    features, actuals = training_panel(weekly, skus, TRAIN_BEFORE - WEEK)
    model = demand_model().fit(features, actuals)
    output.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=output.parent) as temporary:
        pending = Path(temporary) / output.name
        joblib.dump(model, pending, compress=3)
        pending.replace(output)


if __name__ == "__main__":
    train(pd.read_parquet(WEEKLY_SALES))
