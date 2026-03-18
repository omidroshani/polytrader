from decimal import Decimal

from ._enums import OrderSide
from ._helpers import StrictStruct


class OrderBookLevel(StrictStruct):
    """Single orderbook level"""

    price: Decimal
    size: Decimal


class Book(StrictStruct):
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

    @property
    def best_bid(self) -> Decimal | None:
        return self.bids[0].price if self.bids else None

    @property
    def best_ask(self) -> Decimal | None:
        return self.asks[0].price if self.asks else None

    @property
    def spread(self) -> Decimal | None:
        bid, ask = self.best_bid, self.best_ask
        if bid is not None and ask is not None:
            return ask - bid
        return None

    @property
    def mid_price(self) -> Decimal | None:
        bid, ask = self.best_bid, self.best_ask
        if bid is not None and ask is not None:
            return (bid + ask) / 2
        return None


class PriceChangeItem(StrictStruct):
    """Single price change item"""

    asset_id: str
    price: Decimal
    size: Decimal
    side: OrderSide
    hash: str
    best_bid: Decimal | None = None
    best_ask: Decimal | None = None


class PriceChange(StrictStruct):
    """Price level updates"""

    event_type: str
    market: str
    timestamp: int
    price_changes: list[PriceChangeItem]


class TickSizeChange(StrictStruct):
    """Tick size change event"""

    event_type: str
    asset_id: str
    market: str
    old_tick_size: Decimal
    new_tick_size: Decimal
    timestamp: int


class LastTradePrice(StrictStruct):
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

    @property
    def quote_value(self) -> Decimal:
        return self.price * self.size

    @property
    def is_buy(self) -> bool:
        return self.side == OrderSide.BUY


class BestBidAsk(StrictStruct):
    """Best bid/ask update"""

    event_type: str
    market: str
    asset_id: str
    best_bid: Decimal
    best_ask: Decimal
    spread: Decimal
    timestamp: int

    @property
    def mid_price(self) -> Decimal:
        return (self.best_bid + self.best_ask) / 2


class EventMessage(StrictStruct):
    """Event message embedded in new_market/market_resolved"""

    id: str
    ticker: str
    slug: str
    title: str
    description: str


class NewMarket(StrictStruct):
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
    tags: list[str] | None = None


class MarketResolved(StrictStruct):
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
