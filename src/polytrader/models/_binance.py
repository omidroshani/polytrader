from dataclasses import dataclass, field
from typing import Any

from ._helpers import _float


@dataclass(slots=True)
class BinanceAggTrade:
    """Aggregate trade data"""

    event: str
    event_time: int
    symbol: str
    agg_trade_id: int
    price: float
    quantity: float
    first_trade_id: int
    last_trade_id: int
    trade_time: int
    is_buyer_maker: bool

    def __post_init__(self) -> None:
        self.price = _float(self.price)
        self.quantity = _float(self.quantity)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BinanceAggTrade":
        return cls(
            event=data["e"],
            event_time=data["E"],
            symbol=data["s"],
            agg_trade_id=data["a"],
            price=data["p"],
            quantity=data["q"],
            first_trade_id=data["f"],
            last_trade_id=data["l"],
            trade_time=data["T"],
            is_buyer_maker=data["m"],
        )

    @property
    def quote_qty(self) -> float:
        return self.price * self.quantity

    @property
    def is_taker_buy(self) -> bool:
        return not self.is_buyer_maker


@dataclass(slots=True)
class BinanceKline:
    """Kline/Candlestick data"""

    open_time: int
    close_time: int
    symbol: str
    interval: str
    first_trade_id: int
    last_trade_id: int
    open: float
    close: float
    high: float
    low: float
    volume: float
    num_trades: int
    is_closed: bool
    quote_volume: float
    taker_buy_base_volume: float
    taker_buy_quote_volume: float

    def __post_init__(self) -> None:
        self.open = _float(self.open)
        self.close = _float(self.close)
        self.high = _float(self.high)
        self.low = _float(self.low)
        self.volume = _float(self.volume)
        self.quote_volume = _float(self.quote_volume)
        self.taker_buy_base_volume = _float(self.taker_buy_base_volume)
        self.taker_buy_quote_volume = _float(self.taker_buy_quote_volume)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BinanceKline":
        return cls(
            open_time=data["t"],
            close_time=data["T"],
            symbol=data["s"],
            interval=data["i"],
            first_trade_id=data["f"],
            last_trade_id=data["L"],
            open=data["o"],
            close=data["c"],
            high=data["h"],
            low=data["l"],
            volume=data["v"],
            num_trades=data["n"],
            is_closed=data["x"],
            quote_volume=data["q"],
            taker_buy_base_volume=data["V"],
            taker_buy_quote_volume=data["Q"],
        )

    @property
    def taker_buy_ratio(self) -> float:
        return (
            self.taker_buy_quote_volume / self.quote_volume
            if self.quote_volume > 0
            else 0.5
        )

    @property
    def is_bullish(self) -> bool:
        return self.close > self.open


@dataclass(slots=True)
class BinanceKlineEvent:
    """Kline stream event wrapper"""

    event: str
    event_time: int
    symbol: str
    kline: BinanceKline

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BinanceKlineEvent":
        return cls(
            event=data["e"],
            event_time=data["E"],
            symbol=data["s"],
            kline=BinanceKline.from_dict(data["k"]),
        )


@dataclass(slots=True)
class BinanceOrderBookLevel:
    """Single orderbook level"""

    price: float
    quantity: float

    def __post_init__(self) -> None:
        self.price = _float(self.price)
        self.quantity = _float(self.quantity)


@dataclass(slots=True)
class BinanceDepthUpdate:
    """Orderbook depth update"""

    event: str
    event_time: int
    symbol: str
    first_update_id: int
    final_update_id: int
    bids: list[list[str]]
    asks: list[list[str]]
    bid_levels: list[BinanceOrderBookLevel] = field(default_factory=list)
    ask_levels: list[BinanceOrderBookLevel] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BinanceDepthUpdate":
        raw_bids = data["b"]
        raw_asks = data["a"]
        return cls(
            event=data["e"],
            event_time=data["E"],
            symbol=data["s"],
            first_update_id=data["U"],
            final_update_id=data["u"],
            bids=raw_bids,
            asks=raw_asks,
            bid_levels=[
                BinanceOrderBookLevel(price=float(b[0]), quantity=float(b[1]))
                for b in raw_bids
            ],
            ask_levels=[
                BinanceOrderBookLevel(price=float(a[0]), quantity=float(a[1]))
                for a in raw_asks
            ],
        )

    @property
    def best_bid(self) -> float | None:
        return self.bid_levels[0].price if self.bid_levels else None

    @property
    def best_ask(self) -> float | None:
        return self.ask_levels[0].price if self.ask_levels else None

    @property
    def spread(self) -> float | None:
        if self.bid_levels and self.ask_levels:
            return self.ask_levels[0].price - self.bid_levels[0].price
        return None
