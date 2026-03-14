from __future__ import annotations

from decimal import Decimal
from typing import Any, Self

import msgspec

from polytrader.constants import CRYPTO_FEE_EXPONENT, CRYPTO_FEE_RATE

ZERO = Decimal("0")


class StrictStruct(msgspec.Struct, forbid_unknown_fields=True):
    """Base struct that rejects unknown fields."""

    @classmethod
    def validate(cls, data: dict[str, Any]) -> Self:
        """Convert a raw dict into a typed struct with automatic coercion."""
        return msgspec.convert(data, cls, strict=False)


def crypto_fee(size: Decimal, price: Decimal) -> Decimal:
    """Compute the trading fee for a crypto market in USDC.

    Formula: ``C * p * 0.25 * (p * (1 - p))^2``

    The fee peaks at ~1.56 % when *p* = 0.50 and drops toward 0 at the
    extremes (p -> 0 or p -> 1).
    """
    return size * price * CRYPTO_FEE_RATE * (price * (1 - price)) ** CRYPTO_FEE_EXPONENT
