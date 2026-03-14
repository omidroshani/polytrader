"""Polytrader data models."""

from ._auth import PolymarketAuth
from ._binance import (
    BinanceAggTrade,
    BinanceDepthUpdate,
    BinanceKline,
    BinanceKlineEvent,
    BinanceOrderBookLevel,
)
from ._client import (
    Balance,
    OrderResult,
    PolymarketPosition,
    TokenIdPair,
    UpDownMarket,
    UpDownMarketToken,
)
from ._enums import (
    BinanceStreamType,
    Coin,
    MarketEventType,
    OrderResultStatus,
    OrderSide,
    OrderStatus,
    OrderType,
    Outcome,
    PolymarketOrderType,
    Timeframe,
    TraderSide,
    TradeStatus,
    UserEventType,
)
from ._helpers import ZERO, StrictStruct, crypto_fee
from ._market import (
    BestBidAsk,
    Book,
    EventMessage,
    LastTradePrice,
    MarketResolved,
    NewMarket,
    OrderBookLevel,
    PriceChange,
    PriceChangeItem,
    TickSizeChange,
)
from ._user import (
    MakerOrder,
    PolymarketOrder,
    PolymarketTrade,
    UserOrder,
    UserTrade,
)

__all__ = [
    # Enums
    "BinanceStreamType",
    "Coin",
    "MarketEventType",
    "OrderResultStatus",
    "OrderSide",
    "OrderStatus",
    "OrderType",
    "Outcome",
    "PolymarketOrderType",
    "Timeframe",
    "TradeStatus",
    "TraderSide",
    "UserEventType",
    # Helpers
    "ZERO",
    "StrictStruct",
    "crypto_fee",
    # Auth
    "PolymarketAuth",
    # Market
    "BestBidAsk",
    "Book",
    "EventMessage",
    "LastTradePrice",
    "MarketResolved",
    "NewMarket",
    "OrderBookLevel",
    "PriceChange",
    "PriceChangeItem",
    "TickSizeChange",
    # User
    "MakerOrder",
    "PolymarketOrder",
    "PolymarketTrade",
    "UserOrder",
    "UserTrade",
    # Client
    "Balance",
    "OrderResult",
    "PolymarketPosition",
    "TokenIdPair",
    "UpDownMarket",
    "UpDownMarketToken",
    # Binance
    "BinanceAggTrade",
    "BinanceDepthUpdate",
    "BinanceKline",
    "BinanceKlineEvent",
    "BinanceOrderBookLevel",
]
