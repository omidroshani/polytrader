"""Tests for WebSocket message parsing.

To capture fresh data from the live WebSocket::

    uv run pytest tests/test_websocket.py::test_capture_user_ws -s --no-header
"""

import asyncio
import contextlib
import json
from decimal import Decimal
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from polytrader.models import (
    Coin,
    MakerOrder,
    OrderSide,
    PolymarketOrderType,
    Timeframe,
    TradeStatus,
    UserOrder,
    UserTrade,
)
from polytrader.websocket import PolymarketUserWebSocket

FIXTURE_FILE = Path(__file__).parent / "fixtures" / "user_ws_messages.jsonl"


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
    FIXTURE_FILE.parent.mkdir(exist_ok=True)
    with open(FIXTURE_FILE, "w") as f:
        for msg in messages:
            f.write(json.dumps(msg) + "\n")


async def test_user_ws_parsing() -> None:
    """Replay fixture data and validate parsing + dispatch."""
    with open(FIXTURE_FILE) as f:
        messages = [json.loads(line) for line in f if line.strip()]

    for msg in messages:
        event_type = msg["event_type"]
        assert event_type in ("trade", "order")

        if event_type == "trade":
            event = UserTrade(**msg)
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
            order = UserOrder(**msg)
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
    ws._callbacks["any"] = [received.append]
    for msg in messages:
        await ws._handle_message(msg)
    assert len(received) == len(messages)
