# Binance Integration

PolyTrader includes a Binance WebSocket client for subscribing to real-time market data streams. This is useful for building strategies that use Binance price data as signals.

## Aggregate Trades

```python
from polytrader import BinanceAggTrade

def on_trade(trade: BinanceAggTrade):
    print(f"{trade.symbol}: {trade.price} x {trade.quantity}")
    print(f"Quote qty: {trade.quote_qty}")
    print(f"Taker buy: {trade.is_taker_buy}")

await trader.binance_ws.connect()
await trader.binance_ws.subscribe_agg_trade("BTCUSDT", on_trade)
await trader.binance_ws.run()
```

## Kline (Candlestick) Data

```python
from polytrader import BinanceKline

def on_kline(kline: BinanceKline):
    print(f"O: {kline.open} H: {kline.high} L: {kline.low} C: {kline.close}")
    print(f"Volume: {kline.volume}")
    print(f"Closed: {kline.is_closed}")
    print(f"Bullish: {kline.is_bullish}")
    print(f"Taker buy ratio: {kline.taker_buy_ratio:.2%}")

await trader.binance_ws.connect()
await trader.binance_ws.subscribe_kline("BTCUSDT", "1m", on_kline)
await trader.binance_ws.run()
```

## Order Book Depth

```python
from polytrader import BinanceDepthUpdate

def on_depth(depth: BinanceDepthUpdate):
    print(f"Best bid: {depth.best_bid}")
    print(f"Best ask: {depth.best_ask}")
    print(f"Spread: {depth.spread}")

    for level in depth.bid_levels:
        print(f"  Bid: {level.price} x {level.quantity}")
    for level in depth.ask_levels:
        print(f"  Ask: {level.price} x {level.quantity}")

await trader.binance_ws.connect()
await trader.binance_ws.subscribe_depth("BTCUSDT", on_depth)
await trader.binance_ws.run()
```

## Multiple Streams

You can subscribe to multiple streams on the same connection:

```python
await trader.binance_ws.connect()
await trader.binance_ws.subscribe_agg_trade("BTCUSDT", on_trade)
await trader.binance_ws.subscribe_kline("BTCUSDT", "1m", on_kline)
await trader.binance_ws.subscribe_kline("ETHUSDT", "5m", on_kline)
await trader.binance_ws.subscribe_depth("BTCUSDT", on_depth)
await trader.binance_ws.run()
```

## Standalone Usage

The Binance WebSocket can also be used independently:

```python
from polytrader import BinanceWebSocket

async with BinanceWebSocket() as ws:
    await ws.subscribe_agg_trade("BTCUSDT", on_trade)
    await ws.run()
```
