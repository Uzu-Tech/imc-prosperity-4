from pathlib import Path
import json
import polars as pl
import polars.selectors as cs
import io
import re
from dotenv import load_dotenv
import os
from pathlib import Path
import sys

load_dotenv()

USING_BACKTEST_LOGS = os.getenv("USE_BACKTEST_LOGS", "false").lower() == "true"

# Determine which source to use based on the boolean
if USING_BACKTEST_LOGS:
    source_key = "BACKTEST_LOG_SOURCE"
else:
    source_key = "IMC_LOG_SOURCE"

folder_name = os.getenv(source_key)

# 2. Safety Check: Was the environment variable even set?
if not folder_name:
    print(f"ERROR: Environment variable '{source_key}' is not set in your .env file.")
    sys.exit(1)

# 3. Path Validation
LOG_DIR = Path(folder_name)

# Check if folder exists
if not LOG_DIR.exists():
    print(f"ERROR: The directory '{LOG_DIR}' does not exist, double check your .env file")
    sys.exit(1)

# Check if it's actually a directory
if not LOG_DIR.is_dir():
    print(f"ERROR: '{LOG_DIR}' exists but is not a directory.")
    sys.exit(1)

# 4. Content Validation (Check for files)
# This looks for any file inside the folder
files = list(LOG_DIR.glob("*")) 
if not files:
    print(f"ERROR: The folder '{LOG_DIR}' is empty. No logs to load.")
    sys.exit(1)

def load_back_test_log(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        file_content = f.read()

    # 1. Split the file into its three core sections
    sandbox_logs_raw = ""
    activities_log_raw = ""
    trade_history_raw = "[]"

    if "Activities log:" in file_content:
        parts = file_content.split("Activities log:")
        sandbox_logs_raw = parts[0].replace("Sandbox logs:", "").strip()
        
        if "Trade History:" in parts[1]:
            sub_parts = parts[1].split("Trade History:")
            activities_log_raw = sub_parts[0].strip()
            trade_history_raw = sub_parts[1].strip()
        else:
            activities_log_raw = parts[1].strip()

    # 2. Parse Sandbox Logs
    # The backtester outputs adjacent JSON objects. We comma-separate them to create a valid JSON array.
    sandbox_logs_str = re.sub(r'}\s*{', '},{', sandbox_logs_raw)
    sandbox_logs_json = f"[{sandbox_logs_str}]"
    raw_logs = json.loads(sandbox_logs_json)

    # 3. Parse Activities Log (CSV)
    prices_df = pl.read_csv(
        io.BytesIO(activities_log_raw.encode('utf-8')), 
        separator=';'
    )

    # 4. Parse Trade History
    # Remove trailing commas
    trade_history_str = re.sub(r',\s*]', ']', trade_history_raw)
    trade_history_str = re.sub(r',\s*}', '}', trade_history_str)
    
    trades_list = json.loads(trade_history_str)
    trades_df = pl.DataFrame(trades_list).with_row_index()

    return prices_df, trades_df, raw_logs


def load_imc_log(file_path):
    with open(file_path, 'r') as f:
        data = json.load(f)
        
        orderbook_data_string = data.get("activitiesLog", "")
        trades_list = data.get("tradeHistory")
        
        prices_df = pl.read_csv(
            io.BytesIO(orderbook_data_string.encode('utf-8')), 
            separator=';'
        )

        trades_df = pl.DataFrame(trades_list).with_row_index()
        raw_logs = data.get("logs")
    
    return prices_df, trades_df, raw_logs

def load_log(file_path):
    if USING_BACKTEST_LOGS:
        prices_df, trades_df, raw_logs = load_back_test_log(file_path)
    else:
        prices_df, trades_df, raw_logs = load_imc_log(file_path)
    
    trades_df = trades_df.with_columns(pl.col("price").cast(pl.Int64))

    prices_df = prices_df.with_columns(
        pl.col("profit_and_loss").diff().alias("pnl_per_step").over("product")
    )


    own_trades = trades_df.filter(
        (pl.col('buyer') == "SUBMISSION") | (pl.col('seller') == "SUBMISSION")
    )
    own_takes = get_own_takes(own_trades, prices_df)

    trades_df = trades_df.join(own_takes.select("index"), on="index", how="anti").drop("index")
    own_takes = own_takes.drop("index")

    logs = parse_user_logs(raw_logs)

    prices_df = infer_fair_price(prices_df, own_trades, logs)
    own_makes = get_own_makes(logs, prices_df, own_takes)

    logs = logs.drop('buy_orders', 'sell_orders')

    return prices_df, trades_df, own_takes, own_makes, logs
    
def get_own_takes(own_trades: pl.DataFrame, prices_df: pl.DataFrame):
    own_trades = own_trades.rename({"symbol": "product"})
 
    combined = own_trades.join(
        prices_df.drop("mid_price", "profit_and_loss"),
        on=["timestamp", "product"],
        how="left"
    )

    is_buyer = pl.col("buyer") == "SUBMISSION"

    bid_cols = cs.starts_with("bid_price_")
    ask_cols = cs.starts_with("ask_price_")

    return (
        combined.filter(
            pl.when(is_buyer)
            .then(pl.any_horizontal(ask_cols == pl.col("price")))
            .otherwise(pl.any_horizontal(bid_cols == pl.col("price")))
        )
        .with_columns(
            order_type = pl.when(is_buyer).then(pl.lit("buy")).otherwise(pl.lit("sell"))
        )
        .drop(cs.starts_with("bid_", "ask_"), "buyer", "seller")
    )


def infer_fair_price(prices_df: pl.DataFrame, own_trades: pl.DataFrame, logs: pl.DataFrame):
    own_trades = own_trades.rename({"symbol": "product"})

    cash_flow = (
        own_trades
        .with_columns(
            pl.when(pl.col("buyer") == "SUBMISSION")
              .then(-pl.col("price") * pl.col("quantity"))
              .otherwise(pl.col("price") * pl.col("quantity"))
              .alias("cash_delta")
        )
        .group_by("timestamp", "product")
        .agg(pl.col("cash_delta").sum())
    )

    prices_df = prices_df.join(cash_flow, on=["timestamp", "product"], how="left").with_columns(
        pl.col("cash_delta").fill_null(0)
    ).sort("timestamp")

    prices_df = prices_df.with_columns(
        pl.col("cash_delta").cum_sum().shift().over("product").alias("cum_cash")
    )

    prices_df = prices_df.join(
        logs.select("timestamp", "product", "position"),
        on=("timestamp", "product"),
        how="left"
    )

    # Infer fair price where position is non-zero
    prices_df = prices_df.with_columns(
        pl.when(pl.col("position") != 0)
          .then((pl.col("profit_and_loss") - pl.col("cum_cash")) / pl.col("position"))
          .otherwise(None)
          .alias("inferred_fair_price")
    )

    # Forward fill across zero-position gaps
    prices_df = prices_df.with_columns(
        pl.col("inferred_fair_price").forward_fill().over("product")
    )

    return prices_df



def parse_user_logs(raw_logs: dict):
    lambda_logs = [json.loads(raw_log["lambdaLog"]) for raw_log in raw_logs]

    processed_rows = []
    for log_content in lambda_logs:
        ts = log_content["TIMESTAMP"]
        
        for product, product_data in log_content.items():
            if product != "TIMESTAMP":
                row = {"timestamp": ts, "product": product}

                for key in product_data:
                    row[key.lower()] = product_data[key]
                
                row["log_dict"] = product_data
                processed_rows.append(row)
    
    return pl.DataFrame(processed_rows)


def get_own_makes(logs: pl.DataFrame, prices_df: pl.DataFrame, own_takes: pl.DataFrame):
    logs = logs.drop('position', 'log_dict', strict=False)
    makes = []
    col_names = ("buy_orders", "sell_orders")
    sides = ("bid", "ask")
    side_thresholds = {
        side: get_side_thresholds(prices_df, side)
        for side in sides
    }

    for col_name, other_col_name, side in zip(col_names, reversed(col_names), sides):
        side_make = (
            logs
            .drop(other_col_name, strict=False)
            .filter(
                pl.col(col_name).is_not_null() &
                (pl.col(col_name).list.len() > 0)
            )
            .with_columns(pl.lit(side).alias("order_type"))
            .explode(col_name)
            .unnest(col_name)
            .with_columns(pl.col('quantity').abs())
        )

        threshold_col = "best_bid" if side == "bid" else "best_ask"
        side_make = (
            side_make
            .join(side_thresholds[side], on=["timestamp", "product"], how="left")
            .filter(
                (pl.col(threshold_col) < pl.col("price"))
                if side == "bid"
                else (pl.col(threshold_col) > pl.col("price"))
            )
            .drop(threshold_col)
        )

        if not own_takes.is_empty():
            takes_key = own_takes.rename({"product": "product"}).select(
                ["timestamp", "product", "price"]
            )
            side_make = side_make.join(
                takes_key,
                on=["timestamp", "product", "price"],
                how="anti",  # ← drop rows that match a take
            )

        makes.append(side_make)

    if not makes:
        return pl.DataFrame()

    return pl.concat(makes, how='vertical').sort('timestamp')


def get_side_thresholds(prices_df: pl.DataFrame, side: str) -> pl.DataFrame:
    price_columns = [
        column_name
        for column_name in prices_df.columns
        if column_name.startswith(f"{side}_price_")
    ]

    if side == "bid":
        return prices_df.select(
            pl.col("timestamp"),
            pl.col("product"),
            best_bid=pl.max_horizontal([pl.col(column_name) for column_name in price_columns]).over("product"),
        )

    return prices_df.select(
        pl.col("timestamp"),
        pl.col("product"),
        best_ask=pl.min_horizontal([pl.col(column_name) for column_name in price_columns]).over("product"),
    )


def load_all_logs(logs_dir: Path):
    all_prices = {}
    all_trades = {}
    all_own_takes = {}
    all_own_makes = {}
    all_logs = {}

    for file in sorted(logs_dir.iterdir()):
        (
            all_prices[file.stem], 
            all_trades[file.stem], 
            all_own_takes[file.stem], 
            all_own_makes[file.stem], 
            all_logs[file.stem]
        ) = load_log(file)

    return all_prices, all_trades, all_own_takes, all_own_makes, all_logs

# ── Design Utilities ────

def get_products(log_name: str) -> list[str]:
    df = all_prices.get(log_name)
    if df is None:
        return []
    return df["product"].unique().sort().to_list()

# ── Data accessors ────

def get_prices_df(log_name: str, product: str) -> pl.DataFrame:
    df = all_prices.get(log_name, pl.DataFrame())
    return df.filter(pl.col("product") == product)

def get_trades_df(log_name: str, product: str) -> pl.DataFrame:
    df = all_trades.get(log_name, pl.DataFrame())
    if df.is_empty():
        return df

    return df.filter(pl.col("symbol") == product)

def get_own_takes_df(log_name: str, product: str) -> pl.DataFrame:
    df = all_own_takes.get(log_name, pl.DataFrame())
    if df.is_empty():
        return df
    return df.filter(pl.col("product") == product)

def get_own_makes_df(log_name: str, product: str) -> pl.DataFrame:
    df = all_own_makes.get(log_name, pl.DataFrame())
    if df.is_empty():
        return df
    return df.filter(pl.col("product") == product)

def get_logs_df(log_name: str, product: str) -> pl.DataFrame:
    df = all_logs.get(log_name, pl.DataFrame())
    if df.is_empty():
        return df
    return df.filter(pl.col("product") == product)


def get_timestamps(log_name: str, product: str) -> list:
    return (
        get_prices_df(log_name, product)
        .get_column("timestamp")
        .sort()
        .to_list()
    )

def get_max_qty(log_name: str, product: str) -> int:
    bot_df  = get_trades_df(log_name, product)
    own_df  = get_own_takes_df(log_name, product)

    bot_max = int(bot_df["quantity"].max()) if not bot_df.is_empty() else 0 # type: ignore
    own_max = int(own_df["quantity"].max()) if not own_df.is_empty() else 0 # type: ignore

    return max(bot_max, own_max, 1)

all_prices, all_trades, all_own_takes, all_own_makes, all_logs = load_all_logs(LOG_DIR)
log_names = list(all_logs.keys())
