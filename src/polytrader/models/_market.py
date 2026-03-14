from dataclasses import dataclass
from decimal import Decimal

from ._enums import OrderSide
from ._helpers import _decimal, _decimal_or_none, _int


@dataclass(slots=True)
class OrderBookLevel:
    """Single orderbook level"""

    price: Decimal
    size: Decimal

    def __post_init__(self) -> None:
        self.price = _decimal(self.price)
        self.size = _decimal(self.size)


@dataclass(slots=True)
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


@dataclass(slots=True)
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


@dataclass(slots=True)
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


@dataclass(slots=True)
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


@dataclass(slots=True)
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


@dataclass(slots=True)
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


@dataclass(slots=True)
class EventMessage:
    """Event message embedded in new_market/market_resolved"""

    id: str
    ticker: str
    slug: str
    title: str
    description: str


@dataclass(slots=True)
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


@dataclass(slots=True)
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
