from enum import StrEnum

from py_clob_client.clob_types import OrderType as ClobOrderType


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
    PolymarketOrderType.GTC: ClobOrderType.GTC,
    PolymarketOrderType.GTD: ClobOrderType.GTD,
    PolymarketOrderType.FOK: ClobOrderType.FOK,
    PolymarketOrderType.FAK: ClobOrderType.FAK,
}


class OrderResultStatus(StrEnum):
    LIVE = "live"
    MATCHED = "matched"
    DELAYED = "delayed"
    UNMATCHED = "unmatched"


class BinanceStreamType(StrEnum):
    AGG_TRADE = "aggTrade"
    DEPTH = "depth"
    KLINE = "kline"
