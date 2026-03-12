from decimal import Decimal

import pytest

from polytrader import Balance, PolyTrader


@pytest.mark.vcr()
def test_get_balance(trader: PolyTrader) -> None:
    """Test fetching USDC balance and allowance."""
    result = trader.get_balance()

    assert isinstance(result, Balance)
    assert isinstance(result.balance, Decimal)
    assert isinstance(result.allowance, Decimal)
    assert result.balance >= 0
    assert result.allowance >= 0
