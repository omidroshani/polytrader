from decimal import Decimal

from ._enums import OrderSide, OrderStatus, PolymarketOrderType, TraderSide, TradeStatus
from ._helpers import ZERO, StrictStruct, crypto_fee


class MakerOrder(StrictStruct):
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


class PolymarketOrder(StrictStruct):
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
    order_type: PolymarketOrderType = PolymarketOrderType.GTC
    created_at: int | None = None
    expiration: int | None = None
    associate_trades: list[str] | None = None

    @property
    def size_remaining(self) -> Decimal:
        return self.original_size - self.size_matched

    @property
    def fill_ratio(self) -> Decimal:
        return (
            self.size_matched / self.original_size if self.original_size > 0 else ZERO
        )


class UserOrder(PolymarketOrder):
    """Order event from the User WebSocket channel.

    Inherits all fields from PolymarketOrder and adds WS event metadata.
    """

    event_type: str = ""
    type: str = ""  # PLACEMENT, UPDATE, CANCELLATION
    timestamp: int = 0
    order_owner: str = ""


class PolymarketTrade(StrictStruct):
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
    trader_side: TraderSide = TraderSide.TAKER
    maker_orders: list[MakerOrder] = []

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
            return self.size - fee / self.price if self.price > 0 else self.size
        return self.size * self.price - fee


class UserTrade(PolymarketTrade):
    """Trade event from the User WebSocket channel.

    Inherits all fields from PolymarketTrade and adds WS event metadata.
    """

    event_type: str = ""
    type: str = ""
    timestamp: int = 0
    trade_owner: str | None = None
