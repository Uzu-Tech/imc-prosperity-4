import polars as pl
import polars.selectors as cs
import numpy as np
from scipy.stats import pearsonr
from scipy.signal import detrend as scipy_detrend
from statsmodels.stats.diagnostic import acorr_ljungbox
from statsmodels.tsa.stattools import adfuller

def calc_fair_price(prices_df: pl.DataFrame):
    prices_df = prices_df.with_columns(
        deep_bid=pl.min_horizontal(cs.starts_with("bid_price")),
        deep_ask=pl.max_horizontal(cs.starts_with("ask_price"))
    ).with_columns(
        fair_price=((pl.col("deep_ask") + pl.col("deep_bid")) / 2)
    )
    return prices_df


def autocorrelation_test(
    values: pl.Series | list[float] | np.ndarray,
    lag: int = 1,
) -> dict[str, float]:
    series = np.asarray(values, dtype=float)
    series = series[np.isfinite(series)]

    if lag < 1:
        raise ValueError("lag must be at least 1")

    if series.size <= lag + 1:
        raise ValueError("not enough observations for the requested lag")

    x = series[:-lag]
    y = series[lag:]
    autocorr, autocorr_pvalue = pearsonr(x, y)

    lb_result = acorr_ljungbox(series, lags=[lag], return_df=True)
    ljung_box_stat = float(lb_result["lb_stat"].iloc[0])
    ljung_box_pvalue = float(lb_result["lb_pvalue"].iloc[0])

    return {
        "lag": float(lag),
        "autocorrelation": float(autocorr), # type: ignore
        "autocorrelation_pvalue": float(autocorr_pvalue), # type: ignore
        "ljung_box_stat": ljung_box_stat,
        "ljung_box_pvalue": ljung_box_pvalue,
        "n_observations": float(series.size),
    }


def detrend_series(
    values: pl.Series | list[float] | np.ndarray,
    order: int = 1,
) -> np.ndarray:
    """Detrend a series using linear (order=1) or polynomial detrending."""
    series = np.asarray(values, dtype=float)
    series = series[np.isfinite(series)]
    return scipy_detrend(series, type="linear")


def adf_test(
    values: pl.Series | list[float] | np.ndarray,
) -> dict[str, float]:
    """
    Augmented Dickey-Fuller test for stationarity.
    H0: Series has a unit root (non-stationary)
    H1: Series is stationary
    """
    series = np.asarray(values, dtype=float)
    series = series[np.isfinite(series)]

    if series.size < 3:
        raise ValueError("not enough observations for ADF test")

    adf_result = adfuller(series, autolag="AIC")
    
    return {
        "test_statistic": float(adf_result[0]),
        "pvalue": float(adf_result[1]),
        "n_lags": int(adf_result[2]), # type:ignore
        "n_observations": int(adf_result[3]), # type:ignore
        "critical_values": {str(k): float(v) for k, v in adf_result[4].items()}, # type:ignore
        "ic_best": float(adf_result[5]), # type:ignore
    } # type:ignore