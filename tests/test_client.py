from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import patch

import pytest

from polytrader import Balance, PolyTrader
from polytrader.models import Coin, Timeframe, UpDownMarket


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
