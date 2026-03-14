from dataclasses import dataclass, field
from decimal import Decimal

from ._enums import OrderSide, OrderStatus, PolymarketOrderType, TraderSide, TradeStatus
from ._helpers import ZERO, _decimal, _int, _int_or_none, crypto_fee


@dataclass(slots=True)
class MakerOrder:
    """Maker order in a trade"""

    order_id: str
    owner: str
    asset_id: str
    matched_amount: Decimal
    price: Decimal
    outcome: str
    maker_address: str = ""
    fee_rate_bps: int = 0
    side: OrderSide = OrderSide.BUY
    outcome_index: int | None = None

    def __post_init__(self) -> None:
        self.matched_amount = _decimal(self.matched_amount)
        self.price = _decimal(self.price)
        self.fee_rate_bps = _int(self.fee_rate_bps)
        self.side = OrderSide(self.side)


@dataclass(slots=True)
class PolymarketOrder:
    """Order info from CLOB API or WebSocket."""

    id: str
    asset_id: str
    market: str
    side: OrderSide
    outcome: str
    price: Decimal
    original_size: Decimal
    size_matched: Decimal
    status: OrderStatus
    owner: str
    maker_address: str = ""
    order_type: PolymarketOrderType | str = ""
    created_at: int | None = None
    expiration: int | None = None
    associate_trades: list[str] | None = None

    def __post_init__(self) -> None:
        self.price = _decimal(self.price)
        self.original_size = _decimal(self.original_size)
        self.size_matched = _decimal(self.size_matched)
        self.status = OrderStatus(self.status)
        if self.order_type:
            self.order_type = PolymarketOrderType(self.order_type)
        self.side = OrderSide(self.side)
        self.created_at = _int_or_none(self.created_at)
        self.expiration = _int_or_none(self.expiration)

    @property
    def size_remaining(self) -> Decimal:
        return self.original_size - self.size_matched

    @property
    def fill_ratio(self) -> Decimal:
        return (
            self.size_matched / self.original_size if self.original_size > 0 else ZERO
        )


@dataclass(slots=True)
class UserOrder(PolymarketOrder):
    """Order event from the User WebSocket channel.

    Inherits all fields from PolymarketOrder and adds WS event metadata.
    """

    event_type: str = ""
    type: str = ""  # PLACEMENT, UPDATE, CANCELLATION
    timestamp: int = 0
    order_owner: str = ""

    def __post_init__(self) -> None:
        PolymarketOrder.__post_init__(self)
        self.timestamp = _int(self.timestamp)


@dataclass(slots=True)
class PolymarketTrade:
    """Trade info from CLOB API or WebSocket."""

    id: str
    market: str
    asset_id: str
    side: OrderSide
    size: Decimal
    price: Decimal
    status: TradeStatus
    outcome: str
    owner: str
    fee_rate_bps: int = 0
    taker_order_id: str = ""
    match_time: int = 0
    last_update: int = 0
    bucket_index: int = 0
    maker_address: str = ""
    transaction_hash: str = ""
    trader_side: TraderSide | str = ""
    maker_orders: list[MakerOrder] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.price = _decimal(self.price)
        self.size = _decimal(self.size)
        self.side = OrderSide(self.side)
        self.status = TradeStatus(self.status)
        if self.trader_side:
            self.trader_side = TraderSide(self.trader_side)
        self.fee_rate_bps = int(self.fee_rate_bps)
        self.match_time = int(self.match_time)
        self.last_update = int(self.last_update)
        self.maker_orders = [
            mo if isinstance(mo, MakerOrder) else MakerOrder(**mo)
            for mo in self.maker_orders
        ]

    @property
    def quote_value(self) -> Decimal:
        return self.price * self.size

    @property
    def is_terminal(self) -> bool:
        return self.status in (TradeStatus.CONFIRMED, TradeStatus.FAILED)

    @property
    def fee(self) -> Decimal:
        """Trading fee in USDC (crypto markets)."""
        return crypto_fee(self.size, self.price)

    @property
    def net_size(self) -> Decimal:
        """Net shares/USDC after fee deduction.

        BUY: net shares received (fee deducted in shares).
        SELL: net USDC received (fee deducted in USDC).
        """
        fee = self.fee
        if self.side == OrderSide.BUY:
            return self.size - fee / self.price if self.price else self.size
        return self.size * self.price - fee


@dataclass(slots=True)
class UserTrade(PolymarketTrade):
    """Trade event from the User WebSocket channel.

    Inherits all fields from PolymarketTrade and adds WS event metadata.
    """

    event_type: str = ""
    type: str = ""
    timestamp: int = 0
    trade_owner: str | None = None

    def __post_init__(self) -> None:
        PolymarketTrade.__post_init__(self)
        self.timestamp = _int(self.timestamp)
