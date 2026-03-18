# Trading Client

The `PolyTrader` class is the main entry point for interacting with Polymarket.

## Markets

### Get Up/Down Markets

```python
from polytrader import Coin, Timeframe

# Get the current active market
market = await trader.get_current_updown_market(Coin.BTC, Timeframe.M5)

print(f"Title: {market.title}")
print(f"Up token: {market.up_token_id}")
print(f"Down token: {market.down_token_id}")
print(f"Best bid: {market.best_bid}")
print(f"Best ask: {market.best_ask}")
print(f"Spread: {market.spread}")
```

You can also fetch a market for a specific timestamp:

```python
market = await trader.get_updown_market(
    Coin.ETH,
    Timeframe.M15,
    timestamp=1710000000,
)
```

### Order Book

```python
orderbook = trader.get_orderbook(token_id=market.up_token_id)

for level in orderbook.bids:
    print(f"Bid: {level.price} x {level.size}")
for level in orderbook.asks:
    print(f"Ask: {level.price} x {level.size}")
```

## Orders

### Place Orders

```python
from decimal import Decimal
from polytrader import OrderSide, PolymarketOrderType

# Limit order (Good Till Cancelled)
result = trader.create_order(
    token_id=market.up_token_id,
    side=OrderSide.BUY,
    price=Decimal("0.50"),
    size=Decimal("10"),
)

print(f"Order ID: {result.order_id}")
print(f"Status: {result.status}")
```

#### Order Types

```python
# Good Till Date — expires at a specific timestamp
result = trader.create_order(
    token_id=market.up_token_id,
    side=OrderSide.BUY,
    price=Decimal("0.50"),
    size=Decimal("10"),
    order_type=PolymarketOrderType.GTD,
    expiration=1710000000,
)

# Fill Or Kill — must fill entirely or cancel
result = trader.create_order(
    token_id=market.up_token_id,
    side=OrderSide.BUY,
    price=Decimal("0.50"),
    size=Decimal("10"),
    order_type=PolymarketOrderType.FOK,
)

# Market order (uses FOK internally)
result = trader.create_order(
    token_id=market.up_token_id,
    side=OrderSide.BUY,
    price=Decimal("0.99"),
    size=Decimal("10"),
    order_type=PolymarketOrderType.MARKET,
)

# Post-only order — rejected if it would match immediately
result = trader.create_order(
    token_id=market.up_token_id,
    side=OrderSide.BUY,
    price=Decimal("0.45"),
    size=Decimal("10"),
    post_only=True,
)
```

### Cancel Orders

```python
# Cancel a single order
success = trader.cancel_order(order_id="order-id-here")

# Cancel all open orders
cancelled_count = trader.cancel_all_orders()

# Cancel orders for a specific market
cancelled_count = trader.cancel_orders_for_market(market_id="condition-id")
```

### Query Orders and Trades

```python
# Get a specific order
order = trader.get_order(order_id="order-id-here")
print(f"Status: {order.status}")
print(f"Filled: {order.fill_ratio:.0%}")
print(f"Remaining: {order.size_remaining}")

# Get all open orders
orders = trader.get_orders()

# Filter by market or asset
orders = trader.get_orders(market_id="condition-id")
orders = trader.get_orders(asset_id="token-id")

# Get trade history
trades = trader.get_trades()
trades = trader.get_trades(market_id="condition-id")
```

## Positions & Balances

```python
# USDC balance
balance = trader.get_balance()
print(f"Balance: {balance.balance}")
print(f"Allowance: {balance.allowance}")

# Conditional token balance
token_balance = trader.get_token_balance(token_id=market.up_token_id)

# All positions
positions = await trader.get_positions()
for pos in positions:
    print(f"{pos.title} {pos.outcome}: {pos.size} @ {pos.avg_price}")
    print(f"  PnL: {pos.cash_pnl} ({pos.percent_pnl:.2%})")
```

### Pre-trade Checks

```python
# Check if you can sell a token (have enough balance + allowance)
can_sell = trader.ensure_can_sell(
    token_id=market.up_token_id,
    size=Decimal("5"),
    neg_risk=False,
)

# Refresh allowances if needed
trader.refresh_collateral_allowance()
trader.refresh_token_allowance(token_id=market.up_token_id)
```

## Async Context Manager

```python
async with PolyTrader(
    private_key="0x...",
    funder="0x...",
    signature_type=0,
) as trader:
    market = await trader.get_current_updown_market(Coin.BTC, Timeframe.M5)
    # ... trade ...
# Automatically closes connections
```
