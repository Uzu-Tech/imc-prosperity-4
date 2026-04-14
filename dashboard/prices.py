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

def fill_matrices_vectorized(vol_matrix, df, side, price_to_idx, time_to_idx):
    sign = 1 if side == "bid" else -1
    time_indices = np.array([time_to_idx[t] for t in df["timestamp"].to_list()])

    for level in (1, 2, 3):
        prices  = df[f"{side}_price_{level}"].to_list()
        volumes = df[f"{side}_volume_{level}"].to_list()

        mask = np.array([p is not None and v is not None for p, v in zip(prices, volumes)])
        if not mask.any():
            continue

        p_idx = np.array([price_to_idx[p] for p, m in zip(prices, mask) if m])
        t_idx = time_indices[mask]
        vols  = np.array([v for v, m in zip(volumes, mask) if m], dtype=float)

        np.add.at(vol_matrix, (p_idx, t_idx), sign * vols)


def process_prices(prices_df: pl.DataFrame):
    timestamps = prices_df.get_column('timestamp').to_list()

    price_min, price_max = get_min_max_price(prices_df)
    price_range = np.arange(price_min, price_max + 1)

    price_to_idx = {p: i for i, p in enumerate(price_range)}
    time_to_idx  = {t: i for i, t in enumerate(timestamps)}

    n_prices = len(price_range)
    n_times  = len(timestamps)

    vol_matrix = np.zeros((n_prices, n_times), dtype=float)

    for side in ('bid', 'ask'):
        fill_matrices_vectorized(vol_matrix, prices_df, side, price_to_idx, time_to_idx)

    # Save raw volumes before normalizing
    raw_vol_matrix = np.abs(vol_matrix.copy())

    bid_max = vol_matrix[vol_matrix > 0].max() if (vol_matrix > 0).any() else 1
    ask_max = abs(vol_matrix[vol_matrix < 0].min()) if (vol_matrix < 0).any() else 1
    vol_matrix[vol_matrix > 0] /= bid_max
    vol_matrix[vol_matrix < 0] /= ask_max

    vol_matrix = np.where(vol_matrix == 0, np.nan, vol_matrix)
    raw_vol_matrix = np.where(raw_vol_matrix == 0, np.nan, raw_vol_matrix)
    return vol_matrix, raw_vol_matrix