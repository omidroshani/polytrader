"""Tests for order lifecycle: create -> get -> cancel.

Record cassettes: uv run pytest tests/test_orders.py --record-mode=rewrite
"""

import time
from decimal import Decimal

import pytest
from freezegun import freeze_time
from py_clob_client.exceptions import PolyApiException

from polytrader import OrderResult, PolymarketOrder, PolyTrader
from polytrader.models import (
    Coin,
    OrderResultStatus,
    OrderSide,
    OrderStatus,
    PolymarketOrderType,
    Timeframe,
    TradeStatus,
)
from polytrader.rpc import wait_for_tx


def _assert_order_result(result: OrderResult) -> None:
    """Common assertions for a successful order result."""
    assert result.success is True
    assert result.order_id != ""
    assert isinstance(result.status, OrderResultStatus)
    assert result.error_msg == ""


def _assert_live_order(
    order: PolymarketOrder,
    *,
    side: OrderSide,
    price: Decimal,
    size: Decimal,
    order_type: PolymarketOrderType,
    token_id: str,
) -> None:
    """Assert fetched order matches what was placed."""
    assert isinstance(order, PolymarketOrder)
    assert order.side == side
    assert order.price == price
    assert order.original_size == size
    assert order.order_type == order_type
    assert order.status == OrderStatus.LIVE
    assert order.asset_id == token_id
    assert order.id != ""
    assert order.market != ""
    assert order.owner != ""
    assert order.maker_address != ""


@pytest.mark.vcr()
@freeze_time("2026-03-12 18:10:00+00:00")
async def test_gtc_order(trader: PolyTrader) -> None:
    """GTC limit order: create, get, cancel."""
    market = await trader.get_current_updown_market(Coin.BTC, Timeframe.M5)
    size = Decimal(str(market.order_min_size))
    tick_size = str(market.order_price_min_tick_size)

    result = trader.create_order(
        token_id=market.up_token_id,
        side=OrderSide.BUY,
        price=Decimal("0.10"),
        size=size,
        tick_size=tick_size,
        neg_risk=market.neg_risk,
        order_type=PolymarketOrderType.GTC,
    )
    _assert_order_result(result)
    assert result.status == OrderResultStatus.LIVE

    order = trader.get_order(result.order_id)
    _assert_live_order(
        order,
        side=OrderSide.BUY,
        price=Decimal("0.10"),
        size=size,
        order_type=PolymarketOrderType.GTC,
        token_id=market.up_token_id,
    )

    assert trader.cancel_order(result.order_id) is True


@pytest.mark.vcr()
@freeze_time("2026-03-12 18:10:00+00:00")
async def test_gtd_order(trader: PolyTrader) -> None:
    """GTD limit order: create with expiration, get, cancel."""
    market = await trader.get_current_updown_market(Coin.BTC, Timeframe.M5)
    size = Decimal(str(market.order_min_size))
    tick_size = str(market.order_price_min_tick_size)
    # Far-future expiration so it works on both recording and replay
    # 2030-01-01 00:00:00 UTC
    expiration = 1893456000

    result = trader.create_order(
        token_id=market.up_token_id,
        side=OrderSide.BUY,
        price=Decimal("0.10"),
        size=size,
        tick_size=tick_size,
        neg_risk=market.neg_risk,
        order_type=PolymarketOrderType.GTD,
        expiration=expiration,
    )
    _assert_order_result(result)
    assert result.status == OrderResultStatus.LIVE

    order = trader.get_order(result.order_id)
    _assert_live_order(
        order,
        side=OrderSide.BUY,
        price=Decimal("0.10"),
        size=size,
        order_type=PolymarketOrderType.GTD,
        token_id=market.up_token_id,
    )
    assert order.expiration is not None
    assert order.expiration > 0

    assert trader.cancel_order(result.order_id) is True


@pytest.mark.vcr()
@freeze_time("2026-03-12 18:10:00+00:00")
async def test_fok_order(trader: PolyTrader) -> None:
    """FOK market order: at unreachable price, should not fill."""
    market = await trader.get_current_updown_market(Coin.BTC, Timeframe.M5)
    size = Decimal(str(market.order_min_size))
    tick_size = str(market.order_price_min_tick_size)

    # BUY at 0.01 -- no seller will match, FOK rejects with 400
    with pytest.raises(PolyApiException):
        trader.create_order(
            token_id=market.up_token_id,
            side=OrderSide.BUY,
            price=Decimal("0.01"),
            size=size,
            tick_size=tick_size,
            neg_risk=market.neg_risk,
            order_type=PolymarketOrderType.FOK,
        )


@pytest.mark.vcr()
@freeze_time("2026-03-12 18:10:00+00:00")
async def test_fak_order(trader: PolyTrader) -> None:
    """FAK market order: partial fill allowed, rest cancelled."""
    market = await trader.get_current_updown_market(Coin.BTC, Timeframe.M5)
    size = Decimal(str(market.order_min_size))
    tick_size = str(market.order_price_min_tick_size)

    # BUY at 0.01 -- no liquidity, FAK rejects with 400
    with pytest.raises(PolyApiException):
        trader.create_order(
            token_id=market.up_token_id,
            side=OrderSide.BUY,
            price=Decimal("0.01"),
            size=size,
            tick_size=tick_size,
            neg_risk=market.neg_risk,
            order_type=PolymarketOrderType.FAK,
        )


@pytest.mark.vcr()
@freeze_time("2026-03-12 18:10:00+00:00")
async def test_market_order(trader: PolyTrader) -> None:
    """MARKET pseudo-type: converted to FOK with aggressive price."""
    market = await trader.get_current_updown_market(Coin.BTC, Timeframe.M5)
    size = Decimal(str(market.order_min_size))
    tick_size = str(market.order_price_min_tick_size)

    result = trader.create_order(
        token_id=market.up_token_id,
        side=OrderSide.BUY,
        price=Decimal("0.99"),
        size=size,
        tick_size=tick_size,
        neg_risk=market.neg_risk,
        order_type=PolymarketOrderType.MARKET,
    )

    assert isinstance(result, OrderResult)
    assert isinstance(result.status, OrderResultStatus)
    assert result.success is True


@pytest.mark.vcr()
@freeze_time("2026-03-12 18:10:00+00:00")
async def test_get_order(trader: PolyTrader) -> None:
    """Test get_order returns correct order details."""
    market = await trader.get_current_updown_market(Coin.BTC, Timeframe.M5)
    size = Decimal(str(market.order_min_size))
    tick_size = str(market.order_price_min_tick_size)

    result = trader.create_order(
        token_id=market.up_token_id,
        side=OrderSide.BUY,
        price=Decimal("0.10"),
        size=size,
        tick_size=tick_size,
        neg_risk=market.neg_risk,
        order_type=PolymarketOrderType.GTC,
    )
    _assert_order_result(result)

    order = trader.get_order(result.order_id)
    assert order.id == result.order_id
    assert order.side == OrderSide.BUY
    assert order.price == Decimal("0.10")
    assert order.original_size == size
    assert order.size_matched == Decimal("0")
    assert order.status == OrderStatus.LIVE
    assert order.asset_id == market.up_token_id

    assert trader.cancel_order(result.order_id) is True


@pytest.mark.vcr()
@freeze_time("2026-03-12 21:15:00+00:00")
async def test_fak_order_lifecycle(trader: PolyTrader) -> None:
    """FAK lifecycle: buy (fill), verify trade confirmed, check positions."""
    market = await trader.get_current_updown_market(Coin.BTC, Timeframe.M5)
    tick_size = str(market.order_price_min_tick_size)

    # 1. FAK BUY -- aggressive price to sweep available liquidity
    buy_size = Decimal(str(market.order_min_size))
    buy_result = trader.create_order(
        token_id=market.up_token_id,
        side=OrderSide.BUY,
        price=Decimal("0.99"),
        size=buy_size,
        tick_size=tick_size,
        neg_risk=market.neg_risk,
        order_type=PolymarketOrderType.FAK,
    )
    assert buy_result.success is True
    assert buy_result.status == OrderResultStatus.MATCHED
    assert buy_result.making_amount > 0  # USDC spent
    assert buy_result.taking_amount > 0  # shares received
    assert len(buy_result.transaction_hashes) > 0

    # 2. Wait for trade to be confirmed on-chain
    tx_hash = buy_result.transaction_hashes[0]
    for _ in range(30):
        trades = trader.get_trades(asset_id=market.up_token_id)
        trade = next((t for t in trades if t.transaction_hash == tx_hash), None)
        if trade and trade.status == TradeStatus.CONFIRMED:
            break
        time.sleep(1)
    else:
        pytest.fail(f"Trade for tx {tx_hash} did not confirm within 30s")

    assert trade.side == OrderSide.BUY
    assert trade.price > 0
    assert trade.size > 0

    # 3. Compute net shares from trade using crypto fee formula
    sell_size = trade.net_size
    assert sell_size > 0

    # 4. Approve conditional token on-chain if needed
    if not trader.ensure_can_sell(market.up_token_id, sell_size, market.neg_risk):
        tx_hash = trader.approve_token(market.neg_risk)
        wait_for_tx(tx_hash)
        trader.refresh_token_allowance(market.up_token_id)

    # 5. Try to SELL more shares than we own -> expect error
    with pytest.raises(PolyApiException):
        trader.create_order(
            token_id=market.up_token_id,
            side=OrderSide.SELL,
            price=Decimal("0.01"),
            size=sell_size + Decimal("10"),
            tick_size=tick_size,
            neg_risk=market.neg_risk,
            order_type=PolymarketOrderType.FAK,
        )

    # 6. FAK SELL using net shares from trade (no get_token_balance needed)
    # FAK may fail with "no match" if the market expired or has no bids --
    # that's acceptable. The key assertion is that it doesn't fail with
    # "not enough balance / allowance".
    try:
        sell_result = trader.create_order(
            token_id=market.up_token_id,
            side=OrderSide.SELL,
            price=Decimal("0.01"),
            size=sell_size,
            tick_size=tick_size,
            neg_risk=market.neg_risk,
            order_type=PolymarketOrderType.FAK,
        )
        assert sell_result.success is True
        assert sell_result.status == OrderResultStatus.MATCHED
    except PolyApiException as e:
        # "no orders found to match" is OK (no liquidity / market expired)
        assert "not enough balance" not in str(e).lower(), (
            f"Balance/allowance issue: {e}"
        )


@pytest.mark.vcr()
@freeze_time("2026-03-12 18:10:00+00:00")
async def test_cancel_order(trader: PolyTrader) -> None:
    """Test cancel_order removes an order."""
    market = await trader.get_current_updown_market(Coin.BTC, Timeframe.M5)
    size = Decimal(str(market.order_min_size))
    tick_size = str(market.order_price_min_tick_size)

    result = trader.create_order(
        token_id=market.up_token_id,
        side=OrderSide.BUY,
        price=Decimal("0.10"),
        size=size,
        tick_size=tick_size,
        neg_risk=market.neg_risk,
        order_type=PolymarketOrderType.GTC,
    )
    _assert_order_result(result)

    assert trader.cancel_order(result.order_id) is True

    # Verify order is no longer LIVE
    order = trader.get_order(result.order_id)
    assert order.status == OrderStatus.CANCELED
