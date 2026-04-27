import os
from pathlib import Path
import re
import polars as pl
import os
from pathlib import Path
import sys
from dotenv import load_dotenv
import polars.selectors as cs

load_dotenv()
CSV_DIR = os.getenv("CSV_SOURCE")

if CSV_DIR is None:
    print(f"ERROR: Environment variable 'CSV_SOURCE' is not set in your .env file.")
    sys.exit(1)

CSV_DIR = Path(CSV_DIR)

if not CSV_DIR.exists():
    print(f"❌ ERROR: CSV directory '{CSV_DIR}' not found.")
    print("Please create the folder or check your project structure.")
    sys.exit(1)

if not CSV_DIR.is_dir():
    print(f"ERROR: '{CSV_DIR}' exists but is not a directory.")
    sys.exit(1)

csv_files = list(CSV_DIR.glob("*.csv"))

if not csv_files:
    print(f"ERROR: No .csv files found in '{CSV_DIR}'.")
    sys.exit(1)

def parse_filename(filename: str) -> tuple[str, int] | None:
    match = re.search(r"(prices|trades)_round_(\d+)_day_(-?\d+)\.csv", filename)
    if match:
        file_type = match.group(1)
        round_num = int(match.group(2))
        day       = int(match.group(3))
        return file_type, round_num, day # type: ignore
    
    return None

def load_all_csvs(csv_dir: Path) -> tuple[dict, dict]:
    all_prices = {}
    all_trades = {}

    for filename in sorted(os.listdir(csv_dir)):
        parsed = parse_filename(filename)
        if parsed is None:
            continue

        file_type, round_num, day = parsed # type: ignore
        key  = (round_num, day)
        path = CSV_DIR / filename # type: ignore

        if file_type == "prices":
            all_prices[key] = pl.read_csv(path, separator=";")
        elif file_type == "trades":
            all_trades[key] = pl.read_csv(path, separator=";")

    return all_prices, all_trades

all_prices, all_trades = load_all_csvs(CSV_DIR)
available_keys = sorted(all_prices.keys())

# ── Design Utilities ────

def get_day_dropdown_options() -> list[dict]:
    return [
        {"label": f"Round {r} — Day {d}", "value": f"{r}_{d}"}
        for r, d in available_keys
    ]

def parse_day_value(value: str) -> tuple[int, int]:
    parts = value.split("_")
    round_num = int(parts[0])
    day = int(parts[1])
    return round_num, day

def get_products(round_num: int, day: int) -> list[str]:
    df = all_prices.get((round_num, day))
    if df is None:
        return []
    return df["product"].unique().sort().to_list()

def get_marks(round_num: int, day: int) -> list[str]:
    df = all_trades.get((round_num, day))
    if df is None:
        return []

    return ['ALL', ] + list(set(df["buyer"].to_list()) | set(df["seller"].to_list()))

def get_default_day_value() -> str:
    r, d = available_keys[0]
    return f"{r}_{d}"

# ── Data accessors ────

def get_prices_df(round_num: int, day: int, product: str) -> pl.DataFrame:
    df = all_prices.get((round_num, day), pl.DataFrame())
    prices_df = df.filter(pl.col("product") == product)
    prices_df = prices_df.with_columns(
        cs.starts_with("bid", "ask").cast(pl.Float64, strict=False)
    )
    return prices_df

def get_trades_df(round_num: int, day: int, product: str) -> pl.DataFrame:
    df = all_trades.get((round_num, day), pl.DataFrame())
    if df.is_empty():
        return df
    return df.filter(pl.col("symbol") == product)

def get_timestamps(round_num: int, day: int, product: str) -> list:
    return (
        get_prices_df(round_num, day, product)
        .get_column("timestamp")
        .sort()
        .to_list()
    )

def get_max_qty(round_num: int, day: int, product: str) -> int:
    df = get_trades_df(round_num, day, product)
    if df.is_empty():
        return 100
    return int(df["quantity"].max()) # type: ignore
