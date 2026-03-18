# PolyTrader

[![PyPI version](https://img.shields.io/pypi/v/polytrader)](https://pypi.org/project/polytrader/)
[![Python](https://img.shields.io/pypi/pyversions/polytrader)](https://pypi.org/project/polytrader/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

A Python trading client for [Polymarket](https://polymarket.com) — the world's largest prediction market.

**[Documentation](https://omidroshani.github.io/polytrader/)**

## Features

- **Order Management** — Limit (GTC/GTD), market (FOK/FAK), and post-only orders with full cancel support
- **Real-time WebSocket** — Market data (order book, price changes, trades, BBO) and authenticated user events (order updates, trade confirmations)
- **Binance Integration** — aggTrade, kline, and depth streams for cross-market signals
- **Typed Models** — All data parsed into `msgspec.Struct` with `Decimal` prices and `StrEnum` statuses
- **Position & Balance Tracking** — Query positions, USDC balance, and conditional token balances
- **On-chain Operations** — Token and collateral approvals with optional builder/relayer support

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

# Cancel all orders
trader.cancel_all_orders()
```

```python
# Real-time market data
await trader.market_ws.connect()
await trader.market_ws.subscribe([market.up_token_id], callback)
await trader.market_ws.run()
```

See the [Getting Started](https://omidroshani.github.io/polytrader/getting-started/) guide for setup details and configuration options.

## Documentation

Full documentation is available at **[omidroshani.github.io/polytrader](https://omidroshani.github.io/polytrader/)**.

- [Getting Started](https://omidroshani.github.io/polytrader/getting-started/) — Installation, setup, and configuration
- [Trading Client](https://omidroshani.github.io/polytrader/guide/client/) — Orders, positions, and balances
- [WebSockets](https://omidroshani.github.io/polytrader/guide/websockets/) — Real-time market and user data
- [Binance Integration](https://omidroshani.github.io/polytrader/guide/binance/) — Binance streams
- [API Reference](https://omidroshani.github.io/polytrader/reference/) — Full API documentation

## Contributing

Contributions are welcome! To get started:

```bash
git clone https://github.com/omidroshani/polytrader.git
cd polytrader
uv sync --group dev --group docs
```

Run checks before submitting a PR:

```bash
make check    # mypy + ruff lint + ruff format
make test     # pytest
make security # bandit
```

## License

This project is licensed under the [MIT License](LICENSE).
