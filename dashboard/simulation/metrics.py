import polars as pl
import numpy as np
from typing import Optional
from loaders.log_loader import USING_BACKTEST_LOGS

def calc_metrics(
    own_takes  : pl.DataFrame,
    own_makes  : pl.DataFrame,
    prices_df  : pl.DataFrame,
    trades_df  : pl.DataFrame,
    timestamp_range: tuple,
) -> dict:
    start, end = timestamp_range

    prices_df = prices_df.filter(pl.col("timestamp").is_between(start, end))
    own_takes = own_takes.filter(pl.col("timestamp").is_between(start, end)) if not own_takes.is_empty() else own_takes
    own_makes = own_makes.filter(pl.col("timestamp").is_between(start, end)) if not own_makes.is_empty() else own_makes
    trades_df = trades_df.filter(pl.col("timestamp").is_between(start, end))

    making  = _calc_making_metrics(own_makes, prices_df, trades_df)
    taking  = _calc_taking_metrics(own_takes, prices_df)
    return {**making, **taking}


def _calc_making_metrics(own_makes: pl.DataFrame, prices_df: pl.DataFrame, trades_df: pl.DataFrame) -> dict:
    if own_makes.is_empty():
        return {
            "fill_prob"      : "-",
            "avg_spread"     : "-",
            "avg_make_size"  : "-",
            "avg_fill_size"  : "-",
            "quote_distance" : "-",
            "quote_rate"     : "-"
        }


    own_makes = own_makes.join(
        prices_df.select(["timestamp", "fair_price"]),
        on="timestamp", how='left'
    )

    own_makes = own_makes.with_columns(
        (pl.col("price") - pl.col("fair_price")).abs().alias("quote_dist")
    )

    bids = own_makes.filter(pl.col("order_type") == "bid")
    asks = own_makes.filter(pl.col("order_type") == "ask")

    spread = None
    if not bids.is_empty() and not asks.is_empty():
        spread_df = bids.join(
            asks.select(["timestamp", "price"]).rename({"price": "ask_price"}),
            on="timestamp", how="inner",
        ).with_columns(
            (pl.col("ask_price") - pl.col("price")).alias("spread")
        )
        spread = spread_df["spread"].mean() if not spread_df.is_empty() else None

    total_quotes = len(own_makes)
    quote_rate   = total_quotes / (len(prices_df.get_column("timestamp")) * 2) * 100 if total_quotes > 0 else 0

    filled_bids = trades_df.filter(pl.col('buyer') == 'SUBMISSION')
    filled_asks = trades_df.filter(pl.col('seller') == 'SUBMISSION')
    filled_quotes = trades_df.filter((pl.col('buyer') == 'SUBMISSION') | (pl.col('seller') == 'SUBMISSION'))
    if len(bids) and len(asks):
        fill_prob = np.mean([len(filled_bids) / len(bids) * 100, len(filled_asks) / len(asks) * 100])
    elif len(bids):
        fill_prob = len(filled_bids) / len(bids) * 100  
    elif len(asks):
        fill_prob = len(filled_asks) / len(asks) * 100
    else:
        fill_prob = 0
    
    avg_fill_size = filled_quotes.get_column('quantity').mean() if not filled_quotes.is_empty() else 0

    return {
        "fill_prob"      : f"{fill_prob:.1f}%",
        "avg_spread"     : f"{spread:.2f}" if spread is not None else "—",
        "avg_make_size"  : f"{own_makes['quantity'].mean():.1f}",
        "avg_fill_size"  : f"{avg_fill_size:.2f}",
        "quote_distance" : f"{own_makes['quote_dist'].mean():.2f}",
        "quote_rate"     : f"{quote_rate:.1f}%",
    }


def _calc_taking_metrics(own_takes: pl.DataFrame, prices_df: pl.DataFrame) -> dict:
    total_pnl  = int(prices_df["pnl_per_step"].sum())
    cum_pnl    = prices_df["profit_and_loss"]
    peak       = cum_pnl.cum_max()
    peak_val   = peak.max()
    max_dd     = (cum_pnl - peak).min()
    max_dd_pct = (max_dd / peak_val * 100) if peak_val is not None and max_dd is not None and peak_val != 0 else None # type: ignore

    pnl_per_step = prices_df["profit_and_loss"]
    std          = pnl_per_step.std()
    sharpe       = (pnl_per_step.mean() / std * np.sqrt(len(pnl_per_step))) if std and std > 0 else 0 # type: ignore

    if own_takes.is_empty() or prices_df.is_empty():
        return {
            "total_pnl"    : f"{total_pnl:+d}",
            "fill_quality" : "—",
            "num_takes"    : "—",
            "avg_take_size": "—",
            "sharpe"       : f"{sharpe:.2f}",
            "max_drawdown" : f"-{max_dd_pct:.1f}%" if max_dd_pct else "—",
        }

    fair_price_str = "inferred_fair_price" if not USING_BACKTEST_LOGS else "fair_price"

    own_takes = own_takes.join(
        prices_df.select(["timestamp", fair_price_str]),
        on="timestamp", how="left",
    )

    own_takes = own_takes.with_columns(
        pl.when(pl.col("order_type") == "buy")
          .then(pl.col(fair_price_str) - pl.col("price"))
          .otherwise(pl.col("price") - pl.col(fair_price_str))
          .alias("fill_quality"),
    )

    avg_fq       = own_takes["fill_quality"].mean()
    avg_take_size = own_takes["quantity"].mean()

    return {
        "total_pnl"    : f"{total_pnl:+d}",
        "fill_quality" : f"{avg_fq:+.2f}" if avg_fq is not None else "—",
        "num_takes"    : str(len(own_takes)),
        "avg_take_size": f"{avg_take_size:.2f}",
        "sharpe"       : f"{sharpe:.2f}",
        "max_drawdown" : f"{max_dd_pct:.1f}%" if max_dd_pct is not None else "—",
    }


def _empty_metrics() -> dict:
    return {k: "—" for k in [
        "fill_prob", "avg_spread", "avg_make_size", "num_makes",
        "quote_distance", "fill_rate", "total_pnl", "fill_quality",
        "avg_slippage", "num_takes", "sharpe", "max_drawdown",
    ]}