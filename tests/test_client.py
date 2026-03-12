from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import patch

import pytest

from polytrader import (
    Balance,
    PolymarketOrder,
    PolymarketPosition,
    PolymarketTrade,
    PolyTrader,
)
from polytrader.models import (
    Coin,
    MakerOrder,
    OrderSide,
    OrderStatus,
    PolymarketOrderType,
    Timeframe,
    TraderSide,
    TradeStatus,
    UpDownMarket,
)


@pytest.mark.vcr()
def test_get_balance(trader: PolyTrader) -> None:
    """Test fetching USDC balance and allowance."""
    result = trader.get_balance()

    assert isinstance(result, Balance)
    assert isinstance(result.balance, Decimal)
    assert isinstance(result.allowance, Decimal)
    assert result.balance >= 0
    assert result.allowance >= 0


def _assert_updown_market(result: UpDownMarket) -> None:
    """Common assertions for UpDownMarket fields."""
    assert result.coin == Coin.BTC
    assert result.timeframe == Timeframe.M5
    assert result.up_token_id != ""
    assert result.down_token_id != ""
    assert isinstance(result.end_date, datetime)
    assert result.order_price_min_tick_size > 0
    assert result.order_min_size > 0
    assert isinstance(result.neg_risk, bool)
    assert isinstance(result.accepting_orders, bool)
    assert isinstance(result.best_bid, Decimal)
    assert isinstance(result.best_ask, Decimal)
    assert isinstance(result.last_trade_price, Decimal)
    assert isinstance(result.spread, Decimal)
    assert result.maker_base_fee >= 0
    assert result.taker_base_fee >= 0


@pytest.mark.vcr()
async def test_get_updown_market(trader: PolyTrader) -> None:
    """Test fetching an Up/Down market by timestamp."""
    result = await trader.get_updown_market(Coin.BTC, Timeframe.M5, 1773313200)

    assert isinstance(result, UpDownMarket)
    assert result.slug == "btc-updown-5m-1773313200"
    _assert_updown_market(result)


@pytest.mark.vcr()
async def test_get_current_updown_market(trader: PolyTrader) -> None:
    """Test fetching the current Up/Down market."""
    frozen = datetime(2026, 3, 12, 11, 40, 0, tzinfo=UTC)
    with patch("polytrader.client.datetime") as mock_dt:
        mock_dt.now.return_value = frozen
        mock_dt.fromisoformat = datetime.fromisoformat
        result = await trader.get_current_updown_market(Coin.BTC, Timeframe.M5)

    assert isinstance(result, UpDownMarket)
    assert result.active is True
    _assert_updown_market(result)


@pytest.mark.vcr()
def test_get_orders(trader: PolyTrader) -> None:
    """Test fetching open orders."""
    result = trader.get_orders()

    assert isinstance(result, list)
    assert len(result) > 0
    for order in result:
        assert isinstance(order, PolymarketOrder)
        assert isinstance(order.price, Decimal)
        assert isinstance(order.original_size, Decimal)
        assert isinstance(order.size_matched, Decimal)
        assert isinstance(order.status, OrderStatus)
        assert isinstance(order.order_type, PolymarketOrderType)
        assert isinstance(order.side, OrderSide)
        assert order.outcome != ""
        assert order.id != ""
        assert order.market != ""
        assert order.asset_id != ""
        assert order.owner != ""
        assert order.maker_address != ""


@pytest.mark.vcr()
def test_get_trades(trader: PolyTrader) -> None:
    """Test fetching trade history."""
    result = trader.get_trades()

    assert isinstance(result, list)
    assert len(result) > 0
    for trade in result:
        assert isinstance(trade, PolymarketTrade)
        assert isinstance(trade.price, Decimal)
        assert isinstance(trade.size, Decimal)
        assert isinstance(trade.status, TradeStatus)
        assert isinstance(trade.side, OrderSide)
        assert isinstance(trade.trader_side, TraderSide)
        assert trade.id != ""
        assert trade.market != ""
        assert trade.asset_id != ""
        assert trade.outcome != ""
        assert trade.fee_rate_bps >= 0
        assert trade.match_time > 0
        assert trade.transaction_hash != ""
        for mo in trade.maker_orders:
            assert isinstance(mo, MakerOrder)
            assert isinstance(mo.matched_amount, Decimal)
            assert isinstance(mo.price, Decimal)
            assert isinstance(mo.side, OrderSide)
            assert mo.order_id != ""
            assert mo.outcome != ""


@pytest.mark.vcr()
async def test_get_positions(trader: PolyTrader) -> None:
    """Test fetching current positions."""
    result = await trader.get_positions()

    assert isinstance(result, list)
    assert len(result) > 0
    for pos in result:
        assert isinstance(pos, PolymarketPosition)
        assert isinstance(pos.size, Decimal)
        assert isinstance(pos.avg_price, Decimal)
        assert isinstance(pos.cash_pnl, Decimal)
        assert isinstance(pos.realized_pnl, Decimal)
        assert isinstance(pos.redeemable, bool)
        assert isinstance(pos.negative_risk, bool)
        assert pos.title != ""
        assert pos.slug != ""
        assert pos.end_date != ""
