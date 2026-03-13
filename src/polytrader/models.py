from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any, cast

from py_clob_client.clob_types import OrderType as ClobOrderType

from polytrader.constants import CRYPTO_FEE_EXPONENT, CRYPTO_FEE_RATE

# ============================================================================
# Enums
# ============================================================================


class MarketEventType(StrEnum):
    BOOK = "book"
    PRICE_CHANGE = "price_change"
    TICK_SIZE_CHANGE = "tick_size_change"
    LAST_TRADE_PRICE = "last_trade_price"
    BEST_BID_ASK = "best_bid_ask"
    NEW_MARKET = "new_market"
    MARKET_RESOLVED = "market_resolved"


class UserEventType(StrEnum):
    TRADE = "trade"
    ORDER = "order"


class TradeStatus(StrEnum):
    MATCHED = "MATCHED"
    MINED = "MINED"
    CONFIRMED = "CONFIRMED"
    RETRYING = "RETRYING"
    FAILED = "FAILED"


class OrderType(StrEnum):
    PLACEMENT = "PLACEMENT"
    UPDATE = "UPDATE"
    CANCELLATION = "CANCELLATION"


class Outcome(StrEnum):
    YES = "YES"
    NO = "NO"
    UP = "Up"
    DOWN = "Down"


class OrderSide(StrEnum):
    BUY = "BUY"
    SELL = "SELL"


class TraderSide(StrEnum):
    TAKER = "TAKER"
    MAKER = "MAKER"


class Coin(StrEnum):
    BTC = "btc"
    ETH = "eth"
    SOL = "sol"
    XRP = "xrp"


class Timeframe(StrEnum):
    M5 = "5m"
    M15 = "15m"


class OrderStatus(StrEnum):
    LIVE = "LIVE"
    MATCHED = "MATCHED"
    CANCELED = "CANCELED"
    CANCELED_MARKET_RESOLVED = "CANCELED_MARKET_RESOLVED"
    INVALID = "INVALID"
    DELAYED = "DELAYED"


class PolymarketOrderType(StrEnum):
    GTC = "GTC"  # Good Till Cancelled
    GTD = "GTD"  # Good Till Date
    FOK = "FOK"  # Fill Or Kill
    FAK = "FAK"  # Fill And Kill (partial fills allowed, rest cancelled)
    MARKET = "MARKET"  # Market order (immediate execution at best price)

    def to_clob_order_type(self) -> ClobOrderType:
        """Convert to py_clob_client OrderType"""
        return ORDER_TYPE_MAP[self]


# Mapping from our order types to py_clob_client OrderType
ORDER_TYPE_MAP: dict[PolymarketOrderType, ClobOrderType] = {
    PolymarketOrderType.GTC: cast(ClobOrderType, ClobOrderType.GTC),
    PolymarketOrderType.GTD: cast(ClobOrderType, ClobOrderType.GTD),
    PolymarketOrderType.FOK: cast(ClobOrderType, ClobOrderType.FOK),
    PolymarketOrderType.FAK: cast(ClobOrderType, ClobOrderType.FAK),
}

ZERO = Decimal("0")


# ============================================================================
# Helpers
# ============================================================================


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


# ============================================================================
# Market Channel Models
# ============================================================================


@dataclass
class OrderBookLevel:
    """Single orderbook level"""

    price: Decimal
    size: Decimal

    def __post_init__(self) -> None:
        self.price = _decimal(self.price)
        self.size = _decimal(self.size)


@dataclass
class Book:
    """Full orderbook snapshot"""

    event_type: str
    asset_id: str
    market: str
    timestamp: int
    hash: str
    bids: list[OrderBookLevel]
    asks: list[OrderBookLevel]
    tick_size: Decimal | None = None
    last_trade_price: Decimal | None = None

    def __post_init__(self) -> None:
        self.timestamp = _int(self.timestamp)
        self.tick_size = _decimal_or_none(self.tick_size)
        self.last_trade_price = _decimal_or_none(self.last_trade_price)
        self.bids = [
            b if isinstance(b, OrderBookLevel) else OrderBookLevel(**b)
            for b in self.bids
        ]
        self.asks = [
            a if isinstance(a, OrderBookLevel) else OrderBookLevel(**a)
            for a in self.asks
        ]

    @property
    def best_bid(self) -> Decimal | None:
        return self.bids[0].price if self.bids else None

    @property
    def best_ask(self) -> Decimal | None:
        return self.asks[0].price if self.asks else None

    @property
    def spread(self) -> Decimal | None:
        if self.best_bid and self.best_ask:
            return self.best_ask - self.best_bid
        return None

    @property
    def mid_price(self) -> Decimal | None:
        if self.best_bid and self.best_ask:
            return (self.best_bid + self.best_ask) / 2
        return None


@dataclass
class PriceChangeItem:
    """Single price change item"""

    asset_id: str
    price: Decimal
    size: Decimal
    side: OrderSide
    hash: str
    best_bid: Decimal | None = None
    best_ask: Decimal | None = None

    def __post_init__(self) -> None:
        self.price = _decimal(self.price)
        self.size = _decimal(self.size)
        self.best_bid = _decimal_or_none(self.best_bid)
        self.best_ask = _decimal_or_none(self.best_ask)


@dataclass
class PriceChange:
    """Price level updates"""

    event_type: str
    market: str
    timestamp: int
    price_changes: list[PriceChangeItem]

    def __post_init__(self) -> None:
        self.timestamp = _int(self.timestamp)
        self.price_changes = [
            pc if isinstance(pc, PriceChangeItem) else PriceChangeItem(**pc)
            for pc in self.price_changes
        ]


@dataclass
class TickSizeChange:
    """Tick size change event"""

    event_type: str
    asset_id: str
    market: str
    old_tick_size: Decimal
    new_tick_size: Decimal
    timestamp: int

    def __post_init__(self) -> None:
        self.old_tick_size = _decimal(self.old_tick_size)
        self.new_tick_size = _decimal(self.new_tick_size)
        self.timestamp = _int(self.timestamp)


@dataclass
class LastTradePrice:
    """Trade execution event"""

    event_type: str
    asset_id: str
    market: str
    price: Decimal
    size: Decimal
    side: OrderSide
    fee_rate_bps: int
    timestamp: int
    transaction_hash: str = ""

    def __post_init__(self) -> None:
        self.price = _decimal(self.price)
        self.size = _decimal(self.size)
        self.side = OrderSide(self.side)
        self.fee_rate_bps = _int(self.fee_rate_bps)
        self.timestamp = _int(self.timestamp)

    @property
    def quote_value(self) -> Decimal:
        return self.price * self.size

    @property
    def is_buy(self) -> bool:
        return self.side == OrderSide.BUY


@dataclass
class BestBidAsk:
    """Best bid/ask update"""

    event_type: str
    market: str
    asset_id: str
    best_bid: Decimal
    best_ask: Decimal
    spread: Decimal
    timestamp: int

    def __post_init__(self) -> None:
        self.best_bid = _decimal(self.best_bid)
        self.best_ask = _decimal(self.best_ask)
        self.spread = _decimal(self.spread)
        self.timestamp = _int(self.timestamp)

    @property
    def mid_price(self) -> Decimal:
        return (self.best_bid + self.best_ask) / 2


@dataclass
class EventMessage:
    """Event message embedded in new_market/market_resolved"""

    id: str
    ticker: str
    slug: str
    title: str
    description: str


@dataclass
class NewMarket:
    """New market created event"""

    event_type: str
    id: str
    question: str
    market: str
    slug: str
    description: str
    assets_ids: list[str]
    outcomes: list[str]
    event_message: EventMessage
    timestamp: int

    def __post_init__(self) -> None:
        self.timestamp = _int(self.timestamp)
        if isinstance(self.event_message, dict):
            self.event_message = EventMessage(**self.event_message)


@dataclass
class MarketResolved:
    """Market resolution event"""

    event_type: str
    id: str
    question: str
    market: str
    slug: str
    description: str
    assets_ids: list[str]
    outcomes: list[str]
    winning_asset_id: str
    winning_outcome: str
    event_message: EventMessage
    timestamp: int

    def __post_init__(self) -> None:
        self.timestamp = _int(self.timestamp)
        if isinstance(self.event_message, dict):
            self.event_message = EventMessage(**self.event_message)


# ============================================================================
# User Channel Models
# ============================================================================


@dataclass
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


# ============================================================================
# Client Response Models
# ============================================================================


@dataclass
class UpDownMarketToken:
    """Token info for an Up/Down market outcome"""

    token_id: str
    outcome: Outcome
    price: Decimal | None = None


@dataclass
class TokenIdPair:
    """Up/Down token ID pair for a market"""

    up: str = ""
    down: str = ""


@dataclass
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


@dataclass
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


@dataclass
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


@dataclass
class UserOrder(PolymarketOrder):
    """Order event from the User WebSocket channel.

    Inherits all fields from PolymarketOrder and adds WS event metadata.
    """

    event_type: str = ""
    type: str = ""  # PLACEMENT, UPDATE, CANCELLATION
    timestamp: int = 0
    order_owner: str = ""

    def __post_init__(self) -> None:
        super().__post_init__()
        self.timestamp = _int(self.timestamp)


@dataclass
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


@dataclass
class UserTrade(PolymarketTrade):
    """Trade event from the User WebSocket channel.

    Inherits all fields from PolymarketTrade and adds WS event metadata.
    """

    event_type: str = ""
    type: str = ""
    timestamp: int = 0
    trade_owner: str | None = None

    def __post_init__(self) -> None:
        super().__post_init__()
        self.timestamp = _int(self.timestamp)


class OrderResultStatus(StrEnum):
    LIVE = "live"
    MATCHED = "matched"
    DELAYED = "delayed"
    UNMATCHED = "unmatched"


@dataclass
class OrderResult:
    """Result of order creation (SendOrderResponse)"""

    success: bool
    order_id: str
    status: OrderResultStatus
    making_amount: Decimal = ZERO
    taking_amount: Decimal = ZERO
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


@dataclass
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


# ============================================================================
# Auth Model
# ============================================================================


@dataclass
class PolymarketAuth:
    """Polymarket API authentication credentials"""

    api_key: str
    secret: str
    passphrase: str

    def to_auth_dict(self) -> dict[str, str]:
        """Convert to dict format for WebSocket auth"""
        return {
            "apiKey": self.api_key,
            "secret": self.secret,
            "passphrase": self.passphrase,
        }
