# PolyTrader

A Python trading client for [Polymarket](https://polymarket.com) — the world's largest prediction market.

## Features

- **Order management** — create limit (GTC/GTD) and market (FOK/FAK) orders, cancel single or all orders
- **Real-time WebSocket** — market data (order book, price changes, trades, best bid/ask), user events (order updates, trade confirmations), and Binance streams (aggTrade, kline, depth)
- **Typed models** — all API and WebSocket data parsed into Python dataclasses with proper types (Decimal prices, enum statuses)
- **Position & balance tracking** — query positions, USDC balance, and conditional token balances
- **On-chain operations** — approve tokens and collateral for trading, with optional builder/relayer support

## Installation

```bash
pip install polytrader
```

## Quick Start

```python
from decimal import Decimal
from polytrader import PolyTrader, OrderSide, Coin, Timeframe

trader = PolyTrader(
    private_key="0x...",
    funder="0x...",
    signature_type=0,
)

# Get current Up/Down market
market = await trader.get_current_updown_market(Coin.BTC, Timeframe.M5)

# Place a limit order
result = trader.create_order(
    token_id=market.up_token_id,
    side=OrderSide.BUY,
    price=Decimal("0.50"),
    size=Decimal("10"),
)

# Get open orders
orders = trader.get_orders()

# Cancel all orders
trader.cancel_all_orders()
```

## WebSocket

```python
# Market data (public)
await trader.market_ws.connect()
await trader.market_ws.subscribe([market.up_token_id], callback)
await trader.market_ws.run()

# User events (authenticated)
await trader.user_ws.connect()
await trader.user_ws.subscribe([market.condition_id], callback)
await trader.user_ws.run()
```

## Binance WebSocket

```python
from polytrader import BinanceAggTrade, BinanceKline

# Subscribe to Binance streams
await trader.binance_ws.connect()
await trader.binance_ws.subscribe_agg_trade("BTCUSDT", on_trade)
await trader.binance_ws.subscribe_kline("BTCUSDT", "1m", on_kline)
await trader.binance_ws.subscribe_depth("BTCUSDT", on_depth)
await trader.binance_ws.run()
```

## Requirements

- Python >= 3.11

## License

MIT
