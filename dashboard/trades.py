import polars as pl
import numpy as np
import polars.selectors as cs

def process_trades(prices_df: pl.DataFrame, trades_df: pl.DataFrame):
    trades_df = trades_df.with_columns(pl.col("price").cast(pl.Int64))
    trades_df = trades_df.join(
        prices_df.select(["timestamp", "fair_price"]),
        on="timestamp",
        how="left"
    )

    trades_df = trades_df.with_columns(
        pl.when(pl.col("price") >= pl.col("fair_price"))
            .then(pl.lit("buy"))
        .when(pl.col("price") < pl.col("fair_price"))
            .then(pl.lit("sell"))
        .otherwise(pl.lit("unknown"))
        .alias("direction")
    )
    return trades_df

def get_max_qty(trades_df: pl.DataFrame, product: str):
    return trades_df.filter(pl.col('symbol') == product).get_column("quantity").max()