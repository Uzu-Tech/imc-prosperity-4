import polars as pl
import polars.selectors as cs

def calc_fair_price(prices_df: pl.DataFrame):
    prices_df = prices_df.with_columns(
        deep_bid=pl.min_horizontal(cs.starts_with("bid_price")),
        deep_ask=pl.max_horizontal(cs.starts_with("ask_price"))
    ).with_columns(
        fair_price=((pl.col("deep_ask") + pl.col("deep_bid")) / 2).forward_fill().ewm_mean(half_life=2)
    )
    return prices_df