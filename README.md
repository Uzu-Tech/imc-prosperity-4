# IMC Prosperity 4 - Simulation Dashboard

A comprehensive dashboard and strategy development environment for the IMC Prosperity 4 challenge. This project integrates a high-performance Rust-based backtester via submodules and a React-based visualizer.

## Prerequisites

Before starting, ensure you have the following installed on your system:

**-** ****Python & [****uv****](****https://docs.astral.sh/uv/****):**** You'll need to install uv which is the package manage used. You can install it by copying and pasting this into your terminal:

**Windows (PowerShell):**

```powershell
-c "irm [https://astral.sh/uv/install.ps1](https://astral.sh/uv/install.ps1) | iex"
```

**Mac Os\Linux:**

```bash
curl -LsSf [https://astral.sh/uv/install.sh](https://astral.sh/uv/install.sh) | sh
```

## Setup Instructions

### 1. Clone the Repository

Clone the repository to get it on your system. If you want the folder in a specific place then open your terminal in that folder by right clicking in the files app and pressing open in terminal. Then copy these two commands.

```powershell
git clone --recursive https://github.com/Uzu-Tech/imc-prosperity-4
cd imc-prosperity-4
```

This will create a folder called imc-prosperity-4, which contains all the code, and put inside the folder. Now you can open vscode using if on windows, or just open the folder normally in vscode

**Windows (PowerShell):**

```powershell
code .
```

### 2. Create the Virtual Environment

Run this command to create the virtual environment and download and the required libraries.

```powershell
uv sync
```

## How to run the dashboard

First of all make sure you download all the csv files from the IMC website and put it in a folder called `csv-files`.
Afterwards to view the historical data in the csv files just run the historical_view.py script:

```powershell
python historical_view.py
```

If you want to view the logs from the simulation on the IMC website, place your .log file into a folder called `imc-log-files`. Then run this script to see the logs

```powershell
python simulation_view.py
```

## Trading bot — architecture & usage

### Overview

The bot is structured around three layers: a shared **`Logger`**, a **`BaseTrader`** that handles all per-tick state, and strategy subclasses that override **`get_orders()`** to implement trading logic. At runtime, **`Trader.run()`** iterates over every product registered in the **`TRADERS`** dict and dispatches to the appropriate strategy class.

---

### How `BaseTrader` works

Every strategy subclass gets a fully prepared snapshot of market state in its `__init__`. You never need to parse the raw `TradingState` yourself — `BaseTrader` does that for you.

**What it computes on construction:**


| Attribute                                  | Description                                                      |
| -------------------------------------------- | ------------------------------------------------------------------ |
| `self.bids` / `self.asks`                  | Order book dicts`{price: quantity}`, sorted best-first           |
| `self.best_bid` / `self.best_ask`          | Top of book prices                                               |
| `self.mid`                                 | Midpoint between best bid and ask                                |
| `self.spread`                              | `best_ask - best_bid`                                            |
| `self.deep_bid` / `self.deep_ask`          | Worst prices in the book (outermost levels)                      |
| `self.fair_price`                          | Midpoint of the deep bid/ask — a rougher estimate of true value |
| `self.position`                            | Current position in this product                                 |
| `self.buy_capacity` / `self.sell_capacity` | How much more you can buy or sell before hitting position limits |
| `self.saved_data`                          | Persistent dict loaded from`traderData` (survives across ticks)  |

**Placing orders:**

Don't append to `self.orders` directly. Use the helpers — they automatically enforce position limits and update remaining capacity:

```python
# places a limit buy; capped at buy_capacity self.sell(price, max_quantity)
self.buy(price, max_quantity)
# places a limit sell; capped at sell_capacity
self.sell(price, max_quantity)
```

For sweeping the order book (market orders):

```python
# walks asks up to a price/qty cap self.market_sell(min_price=..., max_quantity=...)
self.market_buy(max_price=..., max_quantity=...)
# walks bids down to a price/qty cap
self.market_sell(min_price=..., max_quantity=...) 
```

---

### How to add or change a strategy

Step 1 — Subclass `BaseTrader` and override `get_orders()`:

```python
class MeanReversionTrader(BaseTrader):   
    def get_orders(self):       
        if self.fair_price is None:           
            return {self.product: self.orders}
        if self.best_ask < self.fair_price: # Buy if price is below fair value     
            self.market_buy(max_price=self.fair_price - 2, max_quantity=20)  
        if self.best_bid > self.fair_price: # Sell if price is above fair value         
            self.market_sell(min_price=self.fair_price + 2, max_quantity=20)    
      
        return {self.product: self.orders}
```

Step 2 — Register the product and strategy in `TRADERS` (near the bottom of the file):

```python
TRADERS = {
    "ASH_COATED_OSMIUM": PureMarketMaker, 
    "INTARIAN_PEPPER_ROOT": MeanReversionTrader # changed this from PureMarketMaker
}
```

That's it, you can upload the trader.py file to website when you've finished your strategy.

---

### Persisting state across ticks

`self.saved_data` is a dict loaded from `traderData` at the start of each tick, scoped to the product. To write values that survive to the next tick, return them from `get_orders()` — or better, collect them somewhere your `Trader` class can serialize back into `traderData`. This is useful for things like rolling averages or momentum signals.

---

### Position limits

The `POSITION_LIMITS` dict at the top of the file must include every product you trade. If a product is missing, `BaseTrader` logs an error and sets `pos_limit = 0`, which prevents all orders from being placed.

```
python POSITION_LIMITS = {
    'ASH_COATED_OSMIUM': 80, 
    'INTARIAN_PEPPER_ROOT': 80
}
```

---

### Logging

The `Logger` is passed into every trader automatically. Inside `get_orders()` you can log any value with:

```python
self.logger.log("KEY", value)  # value can be a string, int, float, dict, or list
```

Common things to log from a strategy:

```python
self.logger.log("SPREAD", self.spread)
self.logger.log("SIGNAL", {"momentum": 0.4, "z_score": -1.2})
```

Orders are logged automatically by `Trader.run()` after `get_orders()` returns, so you don't need to log those yourself.

To log an error (appends to an `ERRORS` list in the output):

```python
self.logger.log_error("Something went wrong")
```
