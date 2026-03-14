import asyncio
import contextlib
import inspect
import logging
from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any

import msgspec.json
import websockets
from websockets import ConnectionClosed
from websockets.asyncio.client import ClientConnection

from polytrader.exceptions import WebSocketError
from polytrader.models import (
    BestBidAsk,
    Book,
    LastTradePrice,
    MarketResolved,
    NewMarket,
    PolymarketAuth,
    PriceChange,
    StrictStruct,
    TickSizeChange,
    UserOrder,
    UserTrade,
)

logger = logging.getLogger(__name__)


# ============================================================================
# Base WebSocket
# ============================================================================


class BaseWebSocket(ABC):
    """Shared async WebSocket manager with reconnection and ping support."""

    BASE_URL: str
    LOG_TAG: str
    PING_INTERVAL = 10  # seconds

    def __init__(self) -> None:
        self._ws: ClientConnection | None = None
        self._subscriptions: set[str] = set()
        self._callbacks: dict[str, list[tuple[Callable[..., Any], bool]]] = {}
        self._running = False
        self._lock = asyncio.Lock()
        self._ping_task: asyncio.Task[None] | None = None

    async def connect(self) -> None:
        await self._close_ws()
        self._ws = await websockets.connect(self.BASE_URL)
        self._running = True
        logger.info("[%s] Connected", self.LOG_TAG)

    async def disconnect(self) -> None:
        self._running = False
        await self._stop_ping()
        await self._close_ws()
        logger.info("[%s] Disconnected", self.LOG_TAG)

    async def __aenter__(self) -> "BaseWebSocket":
        await self.connect()
        return self

    async def __aexit__(self, *_exc: Any) -> None:
        await self.disconnect()

    async def run(self) -> None:
        """Main loop to receive and process messages."""
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
                    msg_bytes = (
                        raw_msg
                        if isinstance(raw_msg, bytes)
                        else raw_msg.encode("utf-8")
                    )

                    data = self._filter_message(msg_bytes)
                    if data is not None:
                        await self._handle_message(data)

                except TimeoutError:
                    logger.debug("[%s] Timeout", self.LOG_TAG)
                except ConnectionClosed:
                    logger.warning(
                        "[%s] Connection closed, reconnecting...", self.LOG_TAG
                    )
                    await self._close_ws()
                    await asyncio.sleep(1)
                except Exception as e:
                    logger.error("[%s] Error: %s", self.LOG_TAG, e)
                    await asyncio.sleep(1)
        finally:
            await self.disconnect()

    # -- Internal helpers --

    async def _stop_ping(self) -> None:
        if self._ping_task:
            self._ping_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._ping_task
            self._ping_task = None

    async def _close_ws(self) -> None:
        if self._ws is not None:
            with contextlib.suppress(Exception):
                await self._ws.close()
            self._ws = None

    async def _reconnect(self) -> None:
        await self.connect()
        await self._resubscribe()

    async def _send_json(self, data: dict[str, Any]) -> None:
        if not self._ws:
            raise WebSocketError("WebSocket not connected")
        await self._ws.send(msgspec.json.encode(data))

    async def _send_ping(self) -> None:
        while self._running:
            try:
                await asyncio.sleep(self.PING_INTERVAL)
                if self._ws and self._running:
                    await self._do_ping()
            except asyncio.CancelledError:
                return
            except Exception as e:
                logger.error("[%s] Ping error: %s", self.LOG_TAG, e)
                break

    async def _dispatch_callbacks(self, key: str, model: Any) -> None:
        for cb, is_async in self._callbacks.get(key, []):
            try:
                if is_async:
                    await cb(model)
                else:
                    cb(model)
            except Exception as e:
                logger.error("[%s] Callback error: %s", self.LOG_TAG, e)

    async def _dispatch_all_callbacks(self, model: Any) -> None:
        """Dispatch to all registered callbacks regardless of key."""
        for key in self._callbacks:
            await self._dispatch_callbacks(key, model)

    def _register_callback(self, key: str, callback: Callable[..., Any]) -> None:
        """Register a callback with cached async status."""
        self._callbacks.setdefault(key, []).append(
            (callback, inspect.iscoroutinefunction(callback))
        )

    # -- Abstract hooks --

    @abstractmethod
    async def _do_ping(self) -> None:
        """Send a ping (protocol differs per exchange)."""
        ...

    @abstractmethod
    def _filter_message(self, msg: bytes) -> dict[str, Any] | None:
        """Filter and parse raw message. Return parsed dict or None to skip."""
        ...

    @abstractmethod
    async def _handle_message(self, data: dict[str, Any]) -> None:
        """Handle a parsed message dict."""
        ...

    @abstractmethod
    async def _resubscribe(self) -> None:
        """Re-subscribe after reconnection."""
        ...


# ============================================================================
# Polymarket WebSocket
# ============================================================================


class BasePolymarketWebSocket(BaseWebSocket, ABC):
    """Base WebSocket manager for Polymarket channels."""

    CHANNEL_NAME: str

    def __init__(self) -> None:
        super().__init__()
        self.LOG_TAG = f"POLYMARKET_WS:{self.CHANNEL_NAME}"

    async def subscribe(
        self,
        ids: list[str],
        callback: Callable[..., Any],
    ) -> None:
        """Subscribe to events for given IDs."""
        async with self._lock:
            new_ids = [i for i in ids if i not in self._subscriptions]
            if not new_ids:
                return

            if self._subscriptions:
                await self._send_dynamic_subscribe(new_ids, subscribe=True)
            else:
                await self._send_subscribe(new_ids)

            for id_ in new_ids:
                self._subscriptions.add(id_)
                self._register_callback(id_, callback)

    async def unsubscribe(self, ids: list[str]) -> None:
        """Unsubscribe from IDs."""
        async with self._lock:
            existing = [i for i in ids if i in self._subscriptions]
            if not existing:
                return

            await self._send_dynamic_subscribe(existing, subscribe=False)
            for id_ in existing:
                self._subscriptions.discard(id_)
                self._callbacks.pop(id_, None)

    async def _do_ping(self) -> None:
        assert self._ws is not None
        await self._ws.send("PING")

    _SKIP_MESSAGES = frozenset((b"PONG", b"PING", b""))

    def _filter_message(self, msg: bytes) -> dict[str, Any] | None:
        if not msg or msg in self._SKIP_MESSAGES:
            return None

        if not msg.startswith((b"{", b"[")):
            if b"INVALID" in msg:
                logger.warning("[%s] Received: %s, reconnecting...", self.LOG_TAG, msg)
            else:
                logger.debug("[%s] Non-JSON: %s", self.LOG_TAG, msg)
            return None

        result: dict[str, Any] = msgspec.json.decode(msg)
        return result

    async def _handle_message(self, data: dict[str, Any]) -> None:
        messages = data if isinstance(data, list) else [data]
        for item in messages:
            await self._handle_single(item)

    async def _handle_single(self, data: dict[str, Any]) -> None:
        key, model = self._parse_message(data)
        if key and model:
            await self._dispatch_callbacks(key, model)

    async def _resubscribe(self) -> None:
        if self._subscriptions:
            await self._send_subscribe(list(self._subscriptions))

    @abstractmethod
    async def _send_subscribe(self, ids: list[str]) -> None: ...

    @abstractmethod
    async def _send_dynamic_subscribe(
        self, ids: list[str], subscribe: bool
    ) -> None: ...

    @abstractmethod
    def _parse_message(self, data: dict[str, Any]) -> tuple[str, Any | None]: ...


# -- Event type to model/key mappings --

_MARKET_EVENT_PARSERS: dict[str, tuple[str, type[StrictStruct]]] = {
    "book": ("asset_id", Book),
    "price_change": ("market", PriceChange),
    "tick_size_change": ("asset_id", TickSizeChange),
    "last_trade_price": ("asset_id", LastTradePrice),
    "best_bid_ask": ("asset_id", BestBidAsk),
    "new_market": ("market", NewMarket),
    "market_resolved": ("market", MarketResolved),
}

_USER_EVENT_PARSERS: dict[str, type[StrictStruct]] = {
    "trade": UserTrade,
    "order": UserOrder,
}


class PolymarketMarketWebSocket(BasePolymarketWebSocket):
    """WebSocket manager for Polymarket Market channel (public)."""

    BASE_URL = "wss://ws-subscriptions-clob.polymarket.com/ws/market"
    CHANNEL_NAME = "Market"

    async def _send_subscribe(self, asset_ids: list[str]) -> None:
        await self._send_json(
            {
                "assets_ids": asset_ids,
                "type": "market",
                "custom_feature_enabled": True,
            }
        )
        logger.info("[%s] Subscribed to %d assets", self.LOG_TAG, len(asset_ids))

    async def _send_dynamic_subscribe(
        self, asset_ids: list[str], subscribe: bool = True
    ) -> None:
        request: dict[str, Any] = {
            "assets_ids": asset_ids,
            "operation": "subscribe" if subscribe else "unsubscribe",
        }
        if subscribe:
            request["custom_feature_enabled"] = True
        await self._send_json(request)
        action = "Subscribed to" if subscribe else "Unsubscribed from"
        logger.info("[%s] %s %d assets", self.LOG_TAG, action, len(asset_ids))

    def _parse_message(self, data: dict[str, Any]) -> tuple[str, Any | None]:
        event_type = data.get("event_type")
        parser = _MARKET_EVENT_PARSERS.get(event_type or "")
        if not parser:
            return "", None
        key_field, model_cls = parser
        return data.get(key_field, ""), model_cls.validate(data)

    async def _handle_single(self, data: dict[str, Any]) -> None:
        key, model = self._parse_message(data)
        if not key or not model:
            return

        await self._dispatch_callbacks(key, model)

        # For price_change, also dispatch to each affected asset_id
        if isinstance(model, PriceChange):
            for pc in model.price_changes:
                await self._dispatch_callbacks(pc.asset_id, model)


class PolymarketUserWebSocket(BasePolymarketWebSocket):
    """WebSocket manager for Polymarket User channel (authenticated)."""

    BASE_URL = "wss://ws-subscriptions-clob.polymarket.com/ws/user"
    CHANNEL_NAME = "User"

    def __init__(self, auth: PolymarketAuth) -> None:
        super().__init__()
        self._auth = auth

    async def _send_subscribe(self, market_ids: list[str]) -> None:
        await self._send_json(
            {
                "auth": self._auth.to_auth_dict(),
                "markets": market_ids,
                "type": "user",
            }
        )
        logger.info("[%s] Subscribed to %d markets", self.LOG_TAG, len(market_ids))

    async def _send_dynamic_subscribe(
        self, market_ids: list[str], subscribe: bool = True
    ) -> None:
        await self._send_json(
            {
                "markets": market_ids,
                "operation": "subscribe" if subscribe else "unsubscribe",
            }
        )

    def _parse_message(self, data: dict[str, Any]) -> tuple[str, StrictStruct | None]:
        event_type = data.get("event_type")
        model_cls = _USER_EVENT_PARSERS.get(event_type or "")
        if not model_cls:
            return "", None
        return data.get("market", ""), model_cls.validate(data)

    async def _handle_single(self, data: dict[str, Any]) -> None:
        _, model = self._parse_message(data)
        if model:
            await self._dispatch_all_callbacks(model)
