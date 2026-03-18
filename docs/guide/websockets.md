# WebSockets

PolyTrader provides real-time WebSocket connections for market data and user events.

## Market WebSocket

Subscribe to public market data for specific asset IDs.

```python
from polytrader import (
    Book, PriceChange, LastTradePrice,
    BestBidAsk, TickSizeChange, NewMarket, MarketResolved,
)

def on_market_event(event):
    match event:
        case Book():
            print(f"Order book update: {len(event.bids)} bids, {len(event.asks)} asks")
            print(f"Best bid: {event.best_bid}, Best ask: {event.best_ask}")
            print(f"Spread: {event.spread}, Mid: {event.mid_price}")
        case PriceChange():
            for change in event.price_changes:
                print(f"Price change: {change.side} {change.size} @ {change.price}")
        case LastTradePrice():
            print(f"Last trade: {event.size} @ {event.price} ({event.side})")
            print(f"Quote value: {event.quote_value}")
        case BestBidAsk():
            print(f"BBO: {event.best_bid} / {event.best_ask} (spread: {event.spread})")
        case TickSizeChange():
            print(f"Tick size: {event.old_tick_size} -> {event.new_tick_size}")
        case NewMarket():
            print(f"New market: {event.question}")
        case MarketResolved():
            print(f"Resolved: {event.question} -> {event.winning_outcome}")

await trader.market_ws.connect()
await trader.market_ws.subscribe([market.up_token_id], on_market_event)
await trader.market_ws.run()
```

## User WebSocket

Subscribe to authenticated user events (orders and trades) for specific market IDs.

```python
from polytrader import UserOrder, UserTrade

def on_user_event(event):
    match event:
        case UserOrder():
            print(f"Order {event.id}: {event.side} {event.original_size} @ {event.price}")
            print(f"Status: {event.status}, Filled: {event.fill_ratio:.0%}")
        case UserTrade():
            print(f"Trade {event.id}: {event.side} {event.size} @ {event.price}")
            print(f"Fee: {event.fee}, Net: {event.net_size}")
            print(f"Role: {event.trader_side}")

await trader.user_ws.connect()
await trader.user_ws.subscribe([market.condition_id], on_user_event)
await trader.user_ws.run()
```

## Managing Subscriptions

```python
# Subscribe to multiple assets/markets
await trader.market_ws.subscribe(
    [market.up_token_id, market.down_token_id],
    on_market_event,
)

# Unsubscribe
await trader.market_ws.unsubscribe([market.up_token_id])

# Disconnect
await trader.market_ws.disconnect()
```

## Connection Lifecycle

WebSockets support async context managers:

```python
async with trader.market_ws:
    await trader.market_ws.subscribe([token_id], callback)
    await trader.market_ws.run()
# Automatically disconnected
```

!!! note
    WebSocket connections automatically handle ping/pong keepalive messages every 10 seconds.
