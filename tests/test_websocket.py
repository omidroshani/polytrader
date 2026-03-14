"""Tests for WebSocket message parsing.

To capture fresh data from the live WebSocket::

    uv run pytest tests/test_websocket.py::test_capture_user_ws -s --no-header
    uv run pytest tests/test_websocket.py::test_capture_market_ws -s --no-header
"""

import asyncio
import contextlib
import json
from decimal import Decimal
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from polytrader.models import (
    BestBidAsk,
    Book,
    Coin,
    LastTradePrice,
    MakerOrder,
    OrderBookLevel,
    OrderSide,
    PolymarketOrderType,
    PriceChange,
    PriceChangeItem,
    Timeframe,
    TradeStatus,
    UserOrder,
    UserTrade,
)
from polytrader.websocket import PolymarketMarketWebSocket, PolymarketUserWebSocket

FIXTURE_DIR = Path(__file__).parent / "fixtures"
USER_FIXTURE = FIXTURE_DIR / "user_ws_messages.jsonl"
MARKET_FIXTURE = FIXTURE_DIR / "market_ws_messages.jsonl"


@pytest.mark.skip(reason="Live capture -- run explicitly with -k test_capture_user_ws")
async def test_capture_user_ws(trader) -> None:
    """Connect to user WS, place orders, capture events for 10s."""
    market = await trader.get_current_updown_market(Coin.BTC, Timeframe.M5)
    auth = trader.get_auth()

    ws = PolymarketUserWebSocket(auth)
    messages: list[dict] = []
    _orig = ws._handle_message

    async def _capture(data: dict) -> None:
        messages.append(data)
        await _orig(data)

    ws._handle_message = _capture  # type: ignore[method-assign]

    await ws.connect()
    await ws.subscribe([market.condition_id], lambda _: None)
    task = asyncio.create_task(ws.run())
    await asyncio.sleep(2)

    ob = trader.get_orderbook(market.up_token_id)
    tick = str(market.order_price_min_tick_size)

    # 1. GTC post-only at best bid -> order PLACEMENT event
    assert ob.bids, "No bids in orderbook"
    best_bid = Decimal(ob.bids[0].price)
    gtc_result = trader.create_order(
        token_id=market.up_token_id,
        side=OrderSide.BUY,
        price=best_bid,
        size=market.order_min_size,
        order_type=PolymarketOrderType.GTC,
        tick_size=tick,
        neg_risk=market.neg_risk,
        post_only=True,
    )

    # 2. FAK at best ask -> trade MATCHED/MINED events
    assert ob.asks, "No asks in orderbook"
    best_ask = Decimal(ob.asks[0].price)
    with contextlib.suppress(Exception):
        trader.create_order(
            token_id=market.up_token_id,
            side=OrderSide.BUY,
            price=best_ask,
            size=market.order_min_size,
            order_type=PolymarketOrderType.FAK,
            tick_size=tick,
            neg_risk=market.neg_risk,
        )

    await asyncio.sleep(5)

    # Cancel the resting GTC order
    with contextlib.suppress(Exception):
        trader.cancel_order(gtc_result.order_id)

    await asyncio.sleep(5)

    ws._running = False
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task

    assert messages, "No WS messages received"
    FIXTURE_DIR.mkdir(exist_ok=True)
    with open(USER_FIXTURE, "w") as f:
        for msg in messages:
            f.write(json.dumps(msg) + "\n")


@pytest.mark.skip(
    reason="Live capture -- run explicitly with -k test_capture_market_ws"
)
async def test_capture_market_ws(trader) -> None:
    """Connect to market WS, collect book/price/trade events for 15s."""
    market = await trader.get_current_updown_market(Coin.BTC, Timeframe.M5)

    ws = PolymarketMarketWebSocket()
    messages: list[dict] = []
    _orig = ws._handle_message

    async def _capture(data: dict) -> None:
        messages.append(data)
        await _orig(data)

    ws._handle_message = _capture  # type: ignore[method-assign]

    await ws.connect()
    await ws.subscribe([market.up_token_id], lambda _: None)
    task = asyncio.create_task(ws.run())

    await asyncio.sleep(15)

    ws._running = False
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task

    assert messages, "No market WS messages received"
    FIXTURE_DIR.mkdir(exist_ok=True)
    with open(MARKET_FIXTURE, "w") as f:
        for msg in messages:
            f.write(json.dumps(msg) + "\n")


async def test_user_ws_parsing() -> None:
    """Replay fixture data and validate parsing + dispatch."""
    with open(USER_FIXTURE) as f:
        messages = [json.loads(line) for line in f if line.strip()]

    for msg in messages:
        event_type = msg["event_type"]
        assert event_type in ("trade", "order")

        if event_type == "trade":
            event = UserTrade.validate(msg)
            assert event.id != ""
            assert event.price > 0
            assert event.size > 0
            assert event.side in (OrderSide.BUY, OrderSide.SELL)
            assert event.status in (
                TradeStatus.MATCHED,
                TradeStatus.MINED,
                TradeStatus.CONFIRMED,
                TradeStatus.RETRYING,
            )
            assert isinstance(event.price, Decimal)
            assert isinstance(event.size, Decimal)
            assert event.quote_value == event.price * event.size
            for mo in event.maker_orders:
                assert isinstance(mo, MakerOrder)
                assert mo.matched_amount > 0
        else:
            order = UserOrder.validate(msg)
            assert order.id != ""
            assert order.price >= 0
            assert order.original_size > 0
            assert order.side in (OrderSide.BUY, OrderSide.SELL)
            assert isinstance(order.price, Decimal)
            assert isinstance(order.original_size, Decimal)

    # Verify WS handler dispatches all events
    auth = AsyncMock()
    auth.to_auth_dict.return_value = {}
    ws = PolymarketUserWebSocket(auth)
    received: list = []
    ws._callbacks["any"] = [(received.append, False)]
    for msg in messages:
        await ws._handle_message(msg)
    assert len(received) == len(messages)


async def test_market_ws_parsing() -> None:
    """Replay market fixture data and validate parsing + dispatch."""
    with open(MARKET_FIXTURE) as f:
        messages = [json.loads(line) for line in f if line.strip()]

    event_types_seen: set[str] = set()
    for msg in messages:
        event_type = msg["event_type"]
        event_types_seen.add(event_type)

        if event_type == "book":
            book = Book.validate(msg)
            assert book.asset_id != ""
            assert book.market != ""
            assert book.timestamp > 0
            assert isinstance(book.bids, list)
            assert isinstance(book.asks, list)
            for level in book.bids + book.asks:
                assert isinstance(level, OrderBookLevel)
                assert isinstance(level.price, Decimal)
                assert isinstance(level.size, Decimal)
            if book.bids and book.asks:
                assert book.spread is not None
                assert book.spread >= 0

        elif event_type == "price_change":
            pc = PriceChange.validate(msg)
            assert pc.market != ""
            assert pc.timestamp > 0
            assert len(pc.price_changes) > 0
            for item in pc.price_changes:
                assert isinstance(item, PriceChangeItem)
                assert isinstance(item.price, Decimal)
                assert isinstance(item.size, Decimal)
                assert item.side in (OrderSide.BUY, OrderSide.SELL)

        elif event_type == "last_trade_price":
            ltp = LastTradePrice.validate(msg)
            assert ltp.asset_id != ""
            assert isinstance(ltp.price, Decimal)
            assert isinstance(ltp.size, Decimal)
            assert ltp.price > 0
            assert ltp.size > 0
            assert ltp.side in (OrderSide.BUY, OrderSide.SELL)
            assert ltp.quote_value == ltp.price * ltp.size

        elif event_type == "best_bid_ask":
            bba = BestBidAsk.validate(msg)
            assert bba.asset_id != ""
            assert isinstance(bba.best_bid, Decimal)
            assert isinstance(bba.best_ask, Decimal)
            assert isinstance(bba.spread, Decimal)
            assert bba.best_ask >= bba.best_bid

    # Expect at least book and price_change from a 15s capture
    assert "book" in event_types_seen, f"No book events, got: {event_types_seen}"

    # Verify WS handler dispatches events
    ws = PolymarketMarketWebSocket()
    received: list = []
    # Register callback for all asset_ids and markets in fixture
    keys = set()
    for msg in messages:
        for key_field in ("asset_id", "market"):
            if key_field in msg:
                keys.add(msg[key_field])
    for key in keys:
        ws._callbacks[key] = [(received.append, False)]
    for msg in messages:
        await ws._handle_message(msg)
    assert len(received) > 0
