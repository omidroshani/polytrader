import asyncio
import contextlib
import inspect
import json
import logging
import uuid
from collections.abc import Callable
from typing import Any

import websockets
from websockets import ConnectionClosed
from websockets.asyncio.client import ClientConnection

from .models import (
    BinanceAggTrade,
    BinanceDepthUpdate,
    BinanceKline,
    BinanceKlineEvent,
    BinanceStreamType,
)

logger = logging.getLogger(__name__)


class BinanceWebSocket:
    """Async WebSocket manager for Binance streams"""

    BASE_URL = "wss://stream.binance.com:9443/ws"
    PING_INTERVAL = 10  # seconds

    def __init__(self) -> None:
        self._ws: ClientConnection | None = None
        self._subscriptions: set[str] = set()
        self._callbacks: dict[str, list[Callable[..., Any]]] = {}
        self._running = False
        self._lock = asyncio.Lock()
        self._ping_task: asyncio.Task[None] | None = None

    async def connect(self) -> None:
        """Connect to Binance WebSocket"""
        await self._close_ws()
        self._ws = await websockets.connect(self.BASE_URL)
        self._running = True
        logger.info("[BINANCE_WS] Connected")

    async def disconnect(self) -> None:
        """Disconnect from WebSocket"""
        self._running = False
        await self._stop_ping()
        await self._close_ws()
        logger.info("[BINANCE_WS] Disconnected")

    async def subscribe_agg_trade(
        self, symbol: str, callback: Callable[[BinanceAggTrade], None]
    ) -> None:
        """Subscribe to aggregate trade stream"""
        stream = self._stream_name(symbol, BinanceStreamType.AGG_TRADE)
        await self._subscribe(stream, callback)

    async def subscribe_kline(
        self, symbol: str, interval: str, callback: Callable[[BinanceKline], None]
    ) -> None:
        """Subscribe to kline stream"""
        stream = self._stream_name(symbol, BinanceStreamType.KLINE, interval)
        await self._subscribe(stream, callback)

    async def subscribe_depth(
        self, symbol: str, callback: Callable[[BinanceDepthUpdate], None]
    ) -> None:
        """Subscribe to orderbook depth stream"""
        stream = self._stream_name(symbol, BinanceStreamType.DEPTH)
        await self._subscribe(stream, callback)

    async def run(self) -> None:
        """Main loop to receive and process messages"""
        try:
            if not self._ws:
                await self.connect()

            self._ping_task = asyncio.create_task(self._send_ping())

            while self._running:
                try:
                    if not self._ws:
                        await self._reconnect()
                        continue

                    raw_msg = await asyncio.wait_for(self._ws.recv(), timeout=30)
                    msg = (
                        raw_msg.decode("utf-8")
                        if isinstance(raw_msg, bytes)
                        else raw_msg
                    )

                    if not msg or not msg.startswith("{"):
                        continue

                    data = json.loads(msg)

                    # Skip subscription confirmations
                    if "result" in data or "id" in data:
                        continue

                    stream, model = self._parse_message(data)
                    if stream and model:
                        await self._dispatch_callbacks(stream, model)

                except TimeoutError:
                    logger.debug("[BINANCE_WS] Timeout, waiting...")
                except ConnectionClosed:
                    logger.warning("[BINANCE_WS] Connection closed, reconnecting...")
                    await self._close_ws()
                    await asyncio.sleep(1)
                except Exception as e:
                    logger.error(f"[BINANCE_WS] Error: {e}")
                    await asyncio.sleep(1)
        finally:
            await self.disconnect()

    async def _close_ws(self) -> None:
        if self._ws is not None:
            with contextlib.suppress(Exception):
                await self._ws.close()
            self._ws = None

    async def _stop_ping(self) -> None:
        if self._ping_task:
            self._ping_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._ping_task
            self._ping_task = None

    async def _send_ping(self) -> None:
        while self._running:
            try:
                await asyncio.sleep(self.PING_INTERVAL)
                if self._ws and self._running:
                    await self._ws.ping()
            except asyncio.CancelledError:
                return
            except Exception as e:
                logger.error(f"[BINANCE_WS] Ping error: {e}")
                break

    async def _reconnect(self) -> None:
        await self.connect()
        if self._subscriptions:
            await self._send_subscribe(list(self._subscriptions))

    def _stream_name(
        self,
        symbol: str,
        stream_type: BinanceStreamType,
        interval: str | None = None,
    ) -> str:
        """Generate stream name"""
        symbol = symbol.lower()
        if stream_type == BinanceStreamType.KLINE:
            return f"{symbol}@kline_{interval}"
        elif stream_type == BinanceStreamType.DEPTH:
            return f"{symbol}@depth@100ms"
        else:
            return f"{symbol}@{stream_type.value}"

    async def _subscribe(self, stream: str, callback: Callable[..., Any]) -> None:
        """Subscribe to a stream with a callback"""
        async with self._lock:
            if stream not in self._subscriptions:
                await self._send_subscribe([stream])
                self._subscriptions.add(stream)
            self._callbacks.setdefault(stream, []).append(callback)
        logger.info(f"[BINANCE_WS] Subscribed to {stream}")

    async def _send_subscribe(self, streams: list[str], subscribe: bool = True) -> None:
        """Send subscribe/unsubscribe request"""
        if not self._ws:
            raise RuntimeError("WebSocket not connected")
        request = {
            "method": "SUBSCRIBE" if subscribe else "UNSUBSCRIBE",
            "params": streams,
            "id": str(uuid.uuid4())[:8],
        }
        await self._ws.send(json.dumps(request))

    def _parse_message(self, data: dict[str, Any]) -> tuple[str, Any | None]:
        """Parse incoming message and return (stream_name, parsed_model)"""
        event_type = data.get("e")

        if event_type == "aggTrade":
            symbol = data.get("s", "").lower()
            stream = f"{symbol}@aggTrade"
            return stream, BinanceAggTrade.from_dict(data)

        elif event_type == "kline":
            symbol = data.get("s", "").lower()
            kline_data = data.get("k", {})
            interval = kline_data.get("i", "1m")
            stream = f"{symbol}@kline_{interval}"
            event = BinanceKlineEvent.from_dict(data)
            return stream, event.kline

        elif event_type == "depthUpdate":
            symbol = data.get("s", "").lower()
            stream = f"{symbol}@depth@100ms"
            return stream, BinanceDepthUpdate.from_dict(data)

        return "", None

    async def _dispatch_callbacks(self, key: str, model: Any) -> None:
        for cb in self._callbacks.get(key, []):
            try:
                if inspect.iscoroutinefunction(cb):
                    await cb(model)
                else:
                    cb(model)
            except Exception as e:
                logger.error(f"[BINANCE_WS] Callback error: {e}")
