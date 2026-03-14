from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any

from ._enums import Coin, OrderResultStatus, Outcome, Timeframe


@dataclass(slots=True)
class UpDownMarketToken:
    """Token info for an Up/Down market outcome"""

    token_id: str
    outcome: Outcome
    price: Decimal | None = None


@dataclass(slots=True)
class TokenIdPair:
    """Up/Down token ID pair for a market"""

    up: str = ""
    down: str = ""


@dataclass(slots=True)
class UpDownMarket:
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


@dataclass(slots=True)
class PolymarketPosition:
    """User position in a market"""

    proxy_wallet: str
    asset_id: str
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

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PolymarketPosition":
        return cls(
            proxy_wallet=data.get("proxyWallet", ""),
            asset_id=data.get("asset", ""),
            condition_id=data.get("conditionId", ""),
            outcome=data.get("outcome", ""),
            size=Decimal(str(data.get("size", 0))),
            avg_price=Decimal(str(data.get("avgPrice", 0))),
            cur_price=Decimal(str(data.get("curPrice", 0))),
            initial_value=Decimal(str(data.get("initialValue", 0))),
            current_value=Decimal(str(data.get("currentValue", 0))),
            cash_pnl=Decimal(str(data.get("cashPnl", 0))),
            percent_pnl=Decimal(str(data.get("percentPnl", 0))),
            total_bought=Decimal(str(data.get("totalBought", 0))),
            realized_pnl=Decimal(str(data.get("realizedPnl", 0))),
            percent_realized_pnl=Decimal(str(data.get("percentRealizedPnl", 0))),
            redeemable=data.get("redeemable", False),
            mergeable=data.get("mergeable", False),
            title=data.get("title", ""),
            slug=data.get("slug", ""),
            icon=data.get("icon", ""),
            event_slug=data.get("eventSlug", ""),
            outcome_index=data.get("outcomeIndex", 0),
            opposite_outcome=data.get("oppositeOutcome", ""),
            opposite_asset=data.get("oppositeAsset", ""),
            end_date=data.get("endDate", ""),
            negative_risk=data.get("negativeRisk", False),
        )


@dataclass(slots=True)
class OrderResult:
    """Result of order creation (SendOrderResponse)"""

    success: bool
    order_id: str
    status: OrderResultStatus
    making_amount: Decimal = Decimal("0")
    taking_amount: Decimal = Decimal("0")
    error_msg: str = ""
    transaction_hashes: list[str] = field(default_factory=list)
    trade_ids: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "OrderResult":
        return cls(
            success=data.get("success", False),
            order_id=data.get("orderID", ""),
            status=OrderResultStatus(data.get("status", "live")),
            making_amount=Decimal(str(data.get("makingAmount", 0) or 0)),
            taking_amount=Decimal(str(data.get("takingAmount", 0) or 0)),
            error_msg=data.get("errorMsg", ""),
            transaction_hashes=data.get("transactionsHashes", []),
            trade_ids=data.get("tradeIDs", []),
        )


@dataclass(slots=True)
class Balance:
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
