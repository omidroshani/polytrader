# PolyTrader

A Python trading client for [Polymarket](https://polymarket.com) — the world's largest prediction market.

---

## Features

- **Order Management** — Create limit (GTC/GTD) and market (FOK/FAK) orders, cancel single or all orders
- **Real-time WebSocket** — Market data, user events, and Binance streams with typed callbacks
- **Typed Models** — All data parsed into typed structs with `Decimal` prices and enum statuses
- **Position & Balance Tracking** — Query positions, USDC balance, and conditional token balances
- **On-chain Operations** — Approve tokens and collateral for trading, with optional builder/relayer support
- **Binance Integration** — Subscribe to aggTrade, kline, and depth streams

## Quick Example

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

# Cancel all orders
trader.cancel_all_orders()
```

## Next Steps

- [Getting Started](getting-started.md) — Installation and setup
- [Trading Client Guide](guide/client.md) — Orders, positions, and balances
- [WebSockets Guide](guide/websockets.md) — Real-time market and user data
- [API Reference](reference/) — Full API documentation
