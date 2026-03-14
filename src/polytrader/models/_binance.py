import msgspec

from ._helpers import StrictStruct


class BinanceAggTrade(StrictStruct):
    """Aggregate trade data"""

    event: str = msgspec.field(name="e")
    event_time: int = msgspec.field(name="E")
    symbol: str = msgspec.field(name="s")
    agg_trade_id: int = msgspec.field(name="a")
    price: float = msgspec.field(name="p")
    quantity: float = msgspec.field(name="q")
    first_trade_id: int = msgspec.field(name="f")
    last_trade_id: int = msgspec.field(name="l")
    trade_time: int = msgspec.field(name="T")
    is_buyer_maker: bool = msgspec.field(name="m")
    is_best_match: bool = msgspec.field(name="M")

    @property
    def quote_qty(self) -> float:
        return self.price * self.quantity

    @property
    def is_taker_buy(self) -> bool:
        return not self.is_buyer_maker


class BinanceKline(StrictStruct):
    """Kline/Candlestick data"""

    open_time: int = msgspec.field(name="t")
    close_time: int = msgspec.field(name="T")
    symbol: str = msgspec.field(name="s")
    interval: str = msgspec.field(name="i")
    first_trade_id: int = msgspec.field(name="f")
    last_trade_id: int = msgspec.field(name="L")
    open: float = msgspec.field(name="o")
    close: float = msgspec.field(name="c")
    high: float = msgspec.field(name="h")
    low: float = msgspec.field(name="l")
    volume: float = msgspec.field(name="v")
    num_trades: int = msgspec.field(name="n")
    is_closed: bool = msgspec.field(name="x")
    quote_volume: float = msgspec.field(name="q")
    taker_buy_base_volume: float = msgspec.field(name="V")
    taker_buy_quote_volume: float = msgspec.field(name="Q")
    ignore_quote_asset_volume: str = msgspec.field(name="B")

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


class BinanceKlineEvent(StrictStruct):
    """Kline stream event wrapper"""

    event: str = msgspec.field(name="e")
    event_time: int = msgspec.field(name="E")
    symbol: str = msgspec.field(name="s")
    kline: BinanceKline = msgspec.field(name="k")


class BinanceOrderBookLevel(StrictStruct):
    """Single orderbook level"""

    price: float
    quantity: float


class BinanceDepthUpdate(StrictStruct):
    """Orderbook depth update"""

    event: str = msgspec.field(name="e")
    event_time: int = msgspec.field(name="E")
    symbol: str = msgspec.field(name="s")
    first_update_id: int = msgspec.field(name="U")
    final_update_id: int = msgspec.field(name="u")
    bids: list[list[str]] = msgspec.field(name="b")
    asks: list[list[str]] = msgspec.field(name="a")

    @property
    def bid_levels(self) -> list[BinanceOrderBookLevel]:
        return [
            BinanceOrderBookLevel(price=float(b[0]), quantity=float(b[1]))
            for b in self.bids
        ]

    @property
    def ask_levels(self) -> list[BinanceOrderBookLevel]:
        return [
            BinanceOrderBookLevel(price=float(a[0]), quantity=float(a[1]))
            for a in self.asks
        ]

    @property
    def best_bid(self) -> float | None:
        return float(self.bids[0][0]) if self.bids else None

    @property
    def best_ask(self) -> float | None:
        return float(self.asks[0][0]) if self.asks else None

    @property
    def spread(self) -> float | None:
        if self.bids and self.asks:
            return float(self.asks[0][0]) - float(self.bids[0][0])
        return None
