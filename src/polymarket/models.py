from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, cast

from py_clob_client.clob_types import OrderType as ClobOrderType

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


# ============================================================================
# Helpers
# ============================================================================


def _float(v: Any) -> float:
    return float(v) if isinstance(v, str) else v


def _float_or_none(v: Any) -> float | None:
    if v is None:
        return None
    return float(v) if isinstance(v, str) else v


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

    price: float
    size: float

    def __post_init__(self) -> None:
        self.price = _float(self.price)
        self.size = _float(self.size)


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

    def __post_init__(self) -> None:
        self.timestamp = _int(self.timestamp)
        self.bids = [
            b if isinstance(b, OrderBookLevel) else OrderBookLevel(**b)
            for b in self.bids
        ]
        self.asks = [
            a if isinstance(a, OrderBookLevel) else OrderBookLevel(**a)
            for a in self.asks
        ]

    @property
    def best_bid(self) -> float | None:
        return self.bids[0].price if self.bids else None

    @property
    def best_ask(self) -> float | None:
        return self.asks[0].price if self.asks else None

    @property
    def spread(self) -> float | None:
        if self.best_bid and self.best_ask:
            return self.best_ask - self.best_bid
        return None

    @property
    def mid_price(self) -> float | None:
        if self.best_bid and self.best_ask:
            return (self.best_bid + self.best_ask) / 2
        return None


@dataclass
class PriceChangeItem:
    """Single price change item"""

    asset_id: str
    price: float
    size: float
    side: OrderSide
    hash: str
    best_bid: float | None = None
    best_ask: float | None = None

    def __post_init__(self) -> None:
        self.price = _float(self.price)
        self.size = _float(self.size)
        self.best_bid = _float_or_none(self.best_bid)
        self.best_ask = _float_or_none(self.best_ask)


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
    old_tick_size: float
    new_tick_size: float
    timestamp: int

    def __post_init__(self) -> None:
        self.old_tick_size = _float(self.old_tick_size)
        self.new_tick_size = _float(self.new_tick_size)
        self.timestamp = _int(self.timestamp)


@dataclass
class LastTradePrice:
    """Trade execution event"""

    event_type: str
    asset_id: str
    market: str
    price: float
    size: float
    side: OrderSide
    fee_rate_bps: int
    timestamp: int

    def __post_init__(self) -> None:
        self.price = _float(self.price)
        self.size = _float(self.size)
        self.fee_rate_bps = _int(self.fee_rate_bps)
        self.timestamp = _int(self.timestamp)

    @property
    def quote_value(self) -> float:
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
    best_bid: float
    best_ask: float
    spread: float
    timestamp: int

    def __post_init__(self) -> None:
        self.best_bid = _float(self.best_bid)
        self.best_ask = _float(self.best_ask)
        self.spread = _float(self.spread)
        self.timestamp = _int(self.timestamp)

    @property
    def mid_price(self) -> float:
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

    asset_id: str
    matched_amount: float
    order_id: str
    outcome: Outcome
    owner: str
    price: float

    def __post_init__(self) -> None:
        self.matched_amount = _float(self.matched_amount)
        self.price = _float(self.price)


@dataclass
class UserTrade:
    """User trade event"""

    event_type: str
    id: str
    asset_id: str
    market: str
    price: float
    size: float
    side: OrderSide
    outcome: Outcome
    status: TradeStatus
    owner: str
    type: str  # "TRADE"
    timestamp: int
    trade_owner: str | None = None
    taker_order_id: str | None = None
    maker_orders: list[MakerOrder] = field(default_factory=list)
    matchtime: int | None = None
    last_update: int | None = None

    def __post_init__(self) -> None:
        self.price = _float(self.price)
        self.size = _float(self.size)
        self.timestamp = _int(self.timestamp)
        self.matchtime = _int_or_none(self.matchtime)
        self.last_update = _int_or_none(self.last_update)
        self.maker_orders = [
            mo if isinstance(mo, MakerOrder) else MakerOrder(**mo)
            for mo in self.maker_orders
        ]

    @property
    def quote_value(self) -> float:
        return self.price * self.size

    @property
    def is_terminal(self) -> bool:
        return self.status in (TradeStatus.CONFIRMED, TradeStatus.FAILED)


@dataclass
class UserOrder:
    """User order event"""

    event_type: str
    id: str
    asset_id: str
    market: str
    price: float
    side: OrderSide
    outcome: Outcome
    original_size: float
    size_matched: float
    owner: str
    order_owner: str
    timestamp: int
    type: OrderType  # PLACEMENT, UPDATE, CANCELLATION
    associate_trades: list[str] | None = None

    def __post_init__(self) -> None:
        self.price = _float(self.price)
        self.original_size = _float(self.original_size)
        self.size_matched = _float(self.size_matched)
        self.timestamp = _int(self.timestamp)

    @property
    def size_remaining(self) -> float:
        return self.original_size - self.size_matched

    @property
    def fill_ratio(self) -> float:
        return self.size_matched / self.original_size if self.original_size > 0 else 0.0


# ============================================================================
# Client Response Models
# ============================================================================


@dataclass
class BtcMarketToken:
    """Token info for a BTC Up/Down market outcome"""

    token_id: str
    outcome: Outcome
    price: float | None = None


@dataclass
class TokenIdPair:
    """Up/Down token ID pair for a market"""

    up: str = ""
    down: str = ""


@dataclass
class BtcMarket:
    """BTC Up/Down market info from Gamma API"""

    condition_id: str
    question_id: str
    slug: str
    title: str
    up_token_id: str
    down_token_id: str
    end_date: str
    active: bool
    closed: bool


@dataclass
class PolymarketPosition:
    """User position in a market"""

    asset_id: str
    condition_id: str
    outcome: Outcome
    size: float
    avg_price: float
    cur_price: float
    initial_value: float
    current_value: float
    pnl: float
    realized_pnl: float

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PolymarketPosition":
        return cls(
            asset_id=data.get("asset", ""),
            condition_id=data.get("conditionId", ""),
            outcome=Outcome(data.get("outcome", "YES")),
            size=float(data.get("size", 0)),
            avg_price=float(data.get("avgPrice", 0)),
            cur_price=float(data.get("curPrice", 0)),
            initial_value=float(data.get("initialValue", 0)),
            current_value=float(data.get("currentValue", 0)),
            pnl=float(data.get("pnl", 0)),
            realized_pnl=float(data.get("realizedPnl", 0)),
        )


@dataclass
class PolymarketOrder:
    """Order info from CLOB"""

    id: str
    asset_id: str
    market: str
    side: OrderSide
    price: float
    original_size: float
    size_matched: float
    status: str
    created_at: int | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PolymarketOrder":
        return cls(
            id=data.get("id", ""),
            asset_id=data.get("asset_id", ""),
            market=data.get("market", ""),
            side=OrderSide(data.get("side", "BUY")),
            price=float(data.get("price", 0)),
            original_size=float(data.get("original_size", 0)),
            size_matched=float(data.get("size_matched", 0)),
            status=data.get("status", ""),
            created_at=data.get("created_at"),
        )

    @property
    def size_remaining(self) -> float:
        return self.original_size - self.size_matched


@dataclass
class OrderResult:
    """Result of order creation"""

    success: bool
    order_id: str | None = None
    error_msg: str | None = None
    status: str | None = None


@dataclass
class Balance:
    """USDC balance and allowance"""

    balance: float
    allowance: float

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Balance":
        return cls(
            balance=float(data.get("balance", 0)),
            allowance=float(data.get("allowance", 0)),
        )


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
