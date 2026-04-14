import polars as pl

def format_log(logs_df: pl.DataFrame, timestamp, product):
    data = logs_df.filter(
        (pl.col('timestamp') == timestamp) & (pl.col("product") == product)
    ).to_dict()["log_dict"]

    if data.is_empty():
        return f"No data available for {product} at this timestamp."

    if len(data) > 1:
        return f"Error: Multiple logs created for the same timestamp and product"
    
    data = data[0]

    lines = [f"=== {product} LOGS ===", f"Timestamp: {timestamp}\n"]

    errors = data.get("ERRORS")
    if errors:
        errors_str = "\n".join(f"  - {message}" for message in errors)
        lines.append(f"Errors:\n{errors_str}\n")

    pos = data.get("POSITION", "N/A")
    lines.append(f"Position: {pos}\n")

    trade = data.get("MARKET_BUY")
    if trade:
        lines.append(f"Market Buy Order: {trade['quantity']} units @ avg {trade['avg_price']} "
                        f"(Best price: {trade.get('min_price')}, Slippage: {trade.get('slippage', '0')})")

    trade = data.get("MARKET_SELL")
    if trade:
        lines.append(f"Market Sell Order: {trade['quantity']} units @ avg {trade['avg_price']} "
                        f"(Best price: {trade.get('max_price')}, Slippage: {trade.get('slippage', '0')})")

    buys: list[dict] = data.get("BUY_ORDERS", [])
    sells = data.get("SELL_ORDERS", [])

    if buys:
        buys.sort(key=lambda o: o["price"], reverse=True)
        buy_str = "\n".join([f"  - {b['quantity']} @ {b['price']}" for b in buys])
        lines.append(f"All Buy Orders:\n{buy_str}\n")
    
    if sells:
        sells.sort(key=lambda o: o["price"], reverse=True)
        sell_str = ", ".join([f"  - {abs(s['quantity'])} @ {s['price']}" for s in sells])
        lines.append(f"All Sell Orders:\n{sell_str}\n")

    errors = data.get("ERRORS", [])
    if errors:
        lines.append(f"ERRORS: {', '.join(errors)}")

    return "\n".join(lines)