from decimal import Decimal
from typing import Any

from polytrader.constants import CRYPTO_FEE_EXPONENT, CRYPTO_FEE_RATE

ZERO = Decimal("0")


def crypto_fee(size: Decimal, price: Decimal) -> Decimal:
    """Compute the trading fee for a crypto market in USDC.

    Formula: ``C * p * 0.25 * (p * (1 - p))^2``

    The fee peaks at ~1.56 % when *p* = 0.50 and drops toward 0 at the
    extremes (p -> 0 or p -> 1).
    """
    return size * price * CRYPTO_FEE_RATE * (price * (1 - price)) ** CRYPTO_FEE_EXPONENT


def _decimal(v: Any) -> Decimal:
    if isinstance(v, Decimal):
        return v
    return Decimal(str(v))


def _decimal_or_none(v: Any) -> Decimal | None:
    if v is None:
        return None
    if isinstance(v, Decimal):
        return v
    return Decimal(str(v))


def _int(v: Any) -> int:
    return int(v) if isinstance(v, str) else v


def _int_or_none(v: Any) -> int | None:
    if v is None:
        return None
    return int(v) if isinstance(v, str) else v


def _float(v: Any) -> float:
    return float(v) if isinstance(v, str) else v
