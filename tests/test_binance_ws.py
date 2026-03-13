"""Tests for Binance WebSocket message parsing.

To capture fresh data from the live WebSocket::

    uv run pytest tests/test_binance_ws.py::test_capture_binance_ws -s --no-header
"""

import asyncio
import contextlib
import json
from pathlib import Path

import pytest

from polytrader.binance import BinanceWebSocket
from polytrader.models import (
    BinanceAggTrade,
    BinanceDepthUpdate,
    BinanceKline,
    BinanceKlineEvent,
    BinanceOrderBookLevel,
)

FIXTURE_DIR = Path(__file__).parent / "fixtures"
BINANCE_FIXTURE = FIXTURE_DIR / "binance_ws_messages.jsonl"


@pytest.mark.skip(
    reason="Live capture -- run explicitly with -k test_capture_binance_ws"
)
async def test_capture_binance_ws() -> None:
    """Connect to Binance WS, subscribe to aggTrade/kline/depth for BTCUSDT, capture 15s."""
    ws = BinanceWebSocket()
    messages: list[dict] = []

    _orig_parse = ws._parse_message

    def _capture_parse(data: dict) -> tuple:
        messages.append(data)
        return _orig_parse(data)

    ws._parse_message = _capture_parse  # type: ignore[method-assign]

    await ws.connect()
    await ws.subscribe_agg_trade("BTCUSDT", lambda _: None)
    await ws.subscribe_kline("BTCUSDT", "1m", lambda _: None)
    await ws.subscribe_depth("BTCUSDT", lambda _: None)
    task = asyncio.create_task(ws.run())

    await asyncio.sleep(15)

    ws._running = False
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task

    assert messages, "No Binance WS messages received"
    FIXTURE_DIR.mkdir(exist_ok=True)
    with open(BINANCE_FIXTURE, "w") as f:
        for msg in messages:
            f.write(json.dumps(msg) + "\n")


async def test_binance_ws_parsing() -> None:
    """Replay fixture data and validate parsing + dispatch."""
    with open(BINANCE_FIXTURE) as f:
        messages = [json.loads(line) for line in f if line.strip()]

    event_types_seen: set[str] = set()
    for msg in messages:
        event_type = msg.get("e", "")
        event_types_seen.add(event_type)

        if event_type == "aggTrade":
            trade = BinanceAggTrade.from_dict(msg)
            assert trade.symbol != ""
            assert trade.price > 0
            assert trade.quantity > 0
            assert isinstance(trade.price, float)
            assert isinstance(trade.quantity, float)
            assert trade.quote_qty == trade.price * trade.quantity
            assert isinstance(trade.is_buyer_maker, bool)
            assert trade.is_taker_buy == (not trade.is_buyer_maker)

        elif event_type == "kline":
            event = BinanceKlineEvent.from_dict(msg)
            kline = event.kline
            assert isinstance(kline, BinanceKline)
            assert kline.symbol != ""
            assert kline.interval != ""
            assert isinstance(kline.open, float)
            assert isinstance(kline.close, float)
            assert isinstance(kline.high, float)
            assert isinstance(kline.low, float)
            assert isinstance(kline.volume, float)
            assert kline.high >= kline.low
            assert isinstance(kline.is_closed, bool)
            assert isinstance(kline.is_bullish, bool)
            assert 0 <= kline.taker_buy_ratio <= 1

        elif event_type == "depthUpdate":
            depth = BinanceDepthUpdate.from_dict(msg)
            assert depth.symbol != ""
            assert depth.first_update_id > 0
            assert depth.final_update_id >= depth.first_update_id
            assert isinstance(depth.bids, list)
            assert isinstance(depth.asks, list)
            for level in depth.bid_levels:
                assert isinstance(level, BinanceOrderBookLevel)
                assert isinstance(level.price, float)
                assert isinstance(level.quantity, float)
            for level in depth.ask_levels:
                assert isinstance(level, BinanceOrderBookLevel)
                assert isinstance(level.price, float)
                assert isinstance(level.quantity, float)

    assert "aggTrade" in event_types_seen, (
        f"No aggTrade events, got: {event_types_seen}"
    )
    assert "kline" in event_types_seen, f"No kline events, got: {event_types_seen}"
    assert "depthUpdate" in event_types_seen, (
        f"No depthUpdate events, got: {event_types_seen}"
    )

    # Verify WS handler dispatches events
    ws = BinanceWebSocket()
    received: list = []
    for msg in messages:
        stream, model = ws._parse_message(msg)
        if stream and model:
            ws._callbacks.setdefault(stream, []).append(received.append)
            await ws._dispatch_callbacks(stream, model)
    assert len(received) > 0
