"""Serve one-week-ahead SKU demand from eight completed weeks of sales."""

from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import Depends, FastAPI, Request
import joblib
import numpy as np
import pandas as pd
from pydantic import BaseModel, Field, field_validator

from features import HISTORY_WEEKS, WEEK, features_for_week
from train import MODEL_PATH


NonNegative = Annotated[float, Field(ge=0, allow_inf_nan=False, strict=True)]


class SalesSeries(BaseModel):
    sku: str = Field(min_length=1, pattern=r"\S")
    weekly_units: list[NonNegative] = Field(min_length=HISTORY_WEEKS, max_length=HISTORY_WEEKS)
    avg_price: NonNegative


class ForecastRequest(BaseModel):
    series: list[SalesSeries] = Field(min_length=1)

    @field_validator("series")
    @classmethod
    def unique_skus(cls, series: list[SalesSeries]) -> list[SalesSeries]:
        if len({item.sku for item in series}) != len(series):
            raise ValueError("Each SKU must appear once per request")
        return series


class Forecast(BaseModel):
    sku: str
    forecast_units: NonNegative


class ForecastResponse(BaseModel):
    forecasts: list[Forecast]


def forecast_monday() -> pd.Timestamp:
    today = datetime.now(UTC).date()
    return pd.Timestamp(today - timedelta(days=today.weekday()))


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.model = joblib.load(MODEL_PATH)
    yield


app = FastAPI(title="Shelfwise forecaster", lifespan=lifespan)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/forecast")
def forecast(payload: ForecastRequest, request: Request,
             target: Annotated[pd.Timestamp, Depends(forecast_monday)]) -> ForecastResponse:
    weeks = pd.date_range(end=target - WEEK, periods=HISTORY_WEEKS, freq="W-MON")
    history = pd.DataFrame.from_records(
        [(item.sku, week, units, item.avg_price)
         for item in payload.series for week, units in zip(weeks, item.weekly_units, strict=True)],
        columns=["stock_code", "week_start", "units", "avg_price"],
    )
    skus = [item.sku for item in payload.series]
    features = features_for_week(history, target).loc[skus]
    predictions = np.maximum(request.app.state.model.predict(features), 0)
    return ForecastResponse(forecasts=[
        Forecast(sku=sku, forecast_units=value)
        for sku, value in zip(skus, predictions, strict=True)
    ])
