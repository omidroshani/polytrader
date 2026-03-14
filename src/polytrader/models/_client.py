from datetime import datetime
from decimal import Decimal
from typing import Any

import msgspec

from ._enums import Coin, OrderResultStatus, Outcome, Timeframe
from ._helpers import StrictStruct


class UpDownMarketToken(StrictStruct):
    """Token info for an Up/Down market outcome"""

    token_id: str
    outcome: Outcome
    price: Decimal | None = None


class TokenIdPair(StrictStruct):
    """Up/Down token ID pair for a market"""

    up: str = ""
    down: str = ""


class UpDownMarket(StrictStruct):
    """Up/Down market info from Gamma API"""

    coin: Coin
    timeframe: Timeframe
    condition_id: str
    question_id: str
    slug: str
    title: str
    up_token_id: str
    down_token_id: str
    end_date: datetime
    active: bool
    closed: bool
    order_price_min_tick_size: Decimal
    order_min_size: Decimal
    neg_risk: bool
    accepting_orders: bool
    best_bid: Decimal
    best_ask: Decimal
    last_trade_price: Decimal
    spread: Decimal
    maker_base_fee: int
    taker_base_fee: int


class PolymarketPosition(StrictStruct, rename="camel"):
    """User position in a market"""

    proxy_wallet: str = msgspec.field(name="proxyWallet")
    asset_id: str = msgspec.field(name="asset")
    condition_id: str
    outcome: str
    size: Decimal
    avg_price: Decimal
    cur_price: Decimal
    initial_value: Decimal
    current_value: Decimal
    cash_pnl: Decimal
    percent_pnl: Decimal
    total_bought: Decimal
    realized_pnl: Decimal
    percent_realized_pnl: Decimal
    redeemable: bool
    mergeable: bool
    title: str
    slug: str
    icon: str
    event_slug: str
    outcome_index: int
    opposite_outcome: str
    opposite_asset: str
    end_date: str
    negative_risk: bool
    event_id: str = ""


class OrderResult(StrictStruct):
    """Result of order creation (SendOrderResponse)"""

    success: bool
    order_id: str = msgspec.field(name="orderID", default="")
    status: OrderResultStatus = OrderResultStatus.LIVE
    making_amount: Decimal = msgspec.field(name="makingAmount", default=Decimal("0"))
    taking_amount: Decimal = msgspec.field(name="takingAmount", default=Decimal("0"))
    error_msg: str = msgspec.field(name="errorMsg", default="")
    transaction_hashes: list[str] = msgspec.field(name="transactionsHashes", default=[])
    trade_ids: list[str] = msgspec.field(name="tradeIDs", default=[])

    @classmethod
    def validate(cls, data: dict[str, Any]) -> "OrderResult":
        """Handle empty-string amounts from the API."""
        cleaned = data.copy()
        for key in ("makingAmount", "takingAmount"):
            if cleaned.get(key) == "":
                cleaned[key] = "0"
        return msgspec.convert(cleaned, cls, strict=False)


class Balance(StrictStruct):
    """Balance and allowance (works for both USDC and conditional tokens).

    For USDC (collateral), the API returns ``{"balance": "...", "allowance": "..."}``.
    For conditional tokens, it returns ``{"balance": "...", "allowances": {"<exchange>": "..."}}``.
    The ``allowance`` field is the minimum across all exchange allowances (or the
    single ``allowance`` value for collateral).
    """

    balance: Decimal
    allowance: Decimal

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Balance":
        balance = Decimal(str(data.get("balance", 0)))

        # Collateral returns "allowance" (singular str)
        if "allowance" in data:
            allowance = Decimal(str(data["allowance"]))
        # Conditional tokens return "allowances" (dict of exchange → value)
        elif "allowances" in data:
            allowances_dict: dict[str, str] = data["allowances"]
            if allowances_dict:
                allowance = min(Decimal(str(v)) for v in allowances_dict.values())
            else:
                allowance = Decimal(0)
        else:
            allowance = Decimal(0)

        return cls(balance=balance, allowance=allowance)
