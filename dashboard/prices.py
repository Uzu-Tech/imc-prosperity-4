import polars as pl
import numpy as np
import polars.selectors as cs

def calc_fair_price(prices_df):
    prices_df = prices_df.with_columns(
        deep_bid=pl.min_horizontal(cs.starts_with("bid_price")),
        deep_ask=pl.max_horizontal(cs.starts_with("ask_price")),
    )
    prices_df = prices_df.with_columns(
        fair_price=((pl.col('deep_bid') + pl.col('deep_ask')) / 2)
    )
    return prices_df

def get_min_max_price(prices_df):
    price_min = prices_df.select(cs.starts_with("bid_price")).min().min_horizontal().item()
    price_max = prices_df.select(cs.starts_with("ask_price")).max().max_horizontal().item()
    return price_min, price_max

def fill_matrices(vol_matrix, df, side, p_map_keys, p_map_vals, time_indices):
    sign = 1 if side == "bid" else -1
    
    for level in (1, 2, 3):
        p_col = f"{side}_price_{level}"
        v_col = f"{side}_volume_{level}"

        if p_col not in df.columns:
            continue

        subset = df.select([
            pl.col(p_col).alias("p"),
            pl.col(v_col).alias("v"),
            pl.lit(time_indices).alias("t_idx")
        ]).drop_nulls()

        if subset.is_empty():
            continue

        p_raw = subset["p"].to_numpy()
        # FIX: Cast before converting to numpy
        vols  = subset["v"].cast(pl.Float64).to_numpy()
        t_idx = subset["t_idx"].to_numpy()

        # Map prices to indices
        p_idx = p_map_vals[np.searchsorted(p_map_keys, p_raw)].astype(int)

        # Apply to matrix
        np.add.at(vol_matrix, (p_idx, t_idx), sign * vols)

def process_prices(prices_df: pl.DataFrame):
    # 1. Vectorized Time Mapping
    # Instead of a dict, use the inherent index of the sorted timestamp column
    n_times = prices_df.height
    time_indices = np.arange(n_times) 

    # 2. Vectorized Price Mapping Setup
    price_min, price_max = get_min_max_price(prices_df)
    price_range = np.arange(price_min, price_max + 1)
    
    # These arrays act as our 'vectorized dictionary'
    p_map_keys = price_range
    p_map_vals = np.arange(len(price_range))

    n_prices = len(price_range)
    vol_matrix = np.zeros((n_prices, n_times), dtype=float)

    # 3. Fill Matrix
    for side in ('bid', 'ask'):
        fill_matrices(vol_matrix, prices_df, side, p_map_keys, p_map_vals, time_indices)

    # 4. Vectorized Normalization (using NumPy views to avoid large copies)
    raw_vol_matrix = np.abs(vol_matrix) # Copy only once

    # Masking for normalization to avoid 'max of empty' or divide by zero warnings
    bids_mask = vol_matrix > 0
    asks_mask = vol_matrix < 0

    if bids_mask.any():
        vol_matrix[bids_mask] /= vol_matrix[bids_mask].max()
    
    if asks_mask.any():
        # Using abs() on the min to get the scalar divisor
        vol_matrix[asks_mask] /= np.abs(vol_matrix[asks_mask].min())

    # 5. Final NaN handling
    vol_matrix[vol_matrix == 0] = np.nan
    raw_vol_matrix[raw_vol_matrix == 0] = np.nan
    
    return vol_matrix, raw_vol_matrix