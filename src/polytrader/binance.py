import logging
import uuid
from collections.abc import Callable
from typing import Any

import orjson

from .models import (
    BinanceAggTrade,
    BinanceDepthUpdate,
    BinanceKline,
    BinanceKlineEvent,
    BinanceStreamType,
)
from .websocket import BaseWebSocket

logger = logging.getLogger(__name__)


class BinanceWebSocket(BaseWebSocket):
    """Async WebSocket manager for Binance streams."""

    BASE_URL = "wss://stream.binance.com:9443/ws"
    LOG_TAG = "BINANCE_WS"

    async def subscribe_agg_trade(
        self, symbol: str, callback: Callable[[BinanceAggTrade], None]
    ) -> None:
        """Subscribe to aggregate trade stream."""
        stream = self._stream_name(symbol, BinanceStreamType.AGG_TRADE)
        await self._subscribe(stream, callback)

    async def subscribe_kline(
        self, symbol: str, interval: str, callback: Callable[[BinanceKline], None]
    ) -> None:
        """Subscribe to kline stream."""
        stream = self._stream_name(symbol, BinanceStreamType.KLINE, interval)
        await self._subscribe(stream, callback)

    async def subscribe_depth(
        self, symbol: str, callback: Callable[[BinanceDepthUpdate], None]
    ) -> None:
        """Subscribe to orderbook depth stream."""
        stream = self._stream_name(symbol, BinanceStreamType.DEPTH)
        await self._subscribe(stream, callback)

    # -- Hooks --

    async def _do_ping(self) -> None:
        assert self._ws is not None
        await self._ws.ping()

    def _filter_message(self, msg: str) -> dict[str, Any] | None:
        if not msg or not msg.startswith("{"):
            return None
        data: dict[str, Any] = orjson.loads(msg)
        # Skip subscription confirmations
        if "result" in data or "id" in data:
            return None
        return data

    async def _handle_message(self, data: dict[str, Any]) -> None:
        stream, model = self._parse_message(data)
        if stream and model:
            await self._dispatch_callbacks(stream, model)

    async def _resubscribe(self) -> None:
        if self._subscriptions:
            await self._send_subscribe_request(list(self._subscriptions))

    # -- Internal --

    def _stream_name(
        self,
        symbol: str,
        stream_type: BinanceStreamType,
        interval: str | None = None,
    ) -> str:
        symbol = symbol.lower()
        if stream_type == BinanceStreamType.KLINE:
            return f"{symbol}@kline_{interval}"
        elif stream_type == BinanceStreamType.DEPTH:
            return f"{symbol}@depth@100ms"
        else:
            return f"{symbol}@{stream_type.value}"

    async def _subscribe(self, stream: str, callback: Callable[..., Any]) -> None:
        async with self._lock:
            if stream not in self._subscriptions:
                await self._send_subscribe_request([stream])
                self._subscriptions.add(stream)
            self._register_callback(stream, callback)
        logger.info("[%s] Subscribed to %s", self.LOG_TAG, stream)

    async def _send_subscribe_request(
        self, streams: list[str], subscribe: bool = True
    ) -> None:
        await self._send_json(
            {
                "method": "SUBSCRIBE" if subscribe else "UNSUBSCRIBE",
                "params": streams,
                "id": str(uuid.uuid4())[:8],
            }
        )

    def _parse_message(self, data: dict[str, Any]) -> tuple[str, Any | None]:
        event_type = data.get("e")

        if event_type == "aggTrade":
            symbol = data.get("s", "").lower()
            return f"{symbol}@aggTrade", BinanceAggTrade.from_dict(data)

        elif event_type == "kline":
            symbol = data.get("s", "").lower()
            interval = data.get("k", {}).get("i", "1m")
            event = BinanceKlineEvent.from_dict(data)
            return f"{symbol}@kline_{interval}", event.kline

        elif event_type == "depthUpdate":
            symbol = data.get("s", "").lower()
            return f"{symbol}@depth@100ms", BinanceDepthUpdate.from_dict(data)

        return "", None
