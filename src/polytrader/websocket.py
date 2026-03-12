import asyncio
import contextlib
import inspect
import json
import logging
from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any

import websockets
from websockets import ConnectionClosed
from websockets.asyncio.client import ClientConnection

from polytrader.models import (
    BestBidAsk,
    Book,
    LastTradePrice,
    MarketResolved,
    NewMarket,
    PolymarketAuth,
    PriceChange,
    TickSizeChange,
    UserOrder,
    UserTrade,
)

logger = logging.getLogger(__name__)


class BasePolymarketWebSocket(ABC):
    """Base WebSocket manager for Polymarket channels"""

    BASE_URL: str
    CHANNEL_NAME: str
    PING_INTERVAL = 10  # seconds

    def __init__(self) -> None:
        self._ws: ClientConnection | None = None
        self._subscriptions: set[str] = set()
        self._callbacks: dict[str, list[Callable[..., Any]]] = {}
        self._running = False
        self._lock = asyncio.Lock()
        self._ping_task: asyncio.Task[None] | None = None

    async def connect(self) -> None:
        """Connect to Polymarket WebSocket"""
        await self._close_ws()
        self._ws = await websockets.connect(self.BASE_URL)
        self._running = True
        logger.info(f"[POLYMARKET_WS] {self.CHANNEL_NAME} connected")

    async def disconnect(self) -> None:
        """Disconnect from WebSocket"""
        self._running = False
        await self._stop_ping()
        await self._close_ws()
        logger.info(f"[POLYMARKET_WS] {self.CHANNEL_NAME} disconnected")

    async def subscribe(
        self,
        ids: list[str],
        callback: Callable[..., Any],
    ) -> None:
        """Subscribe to events for given IDs"""
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
                self._callbacks.setdefault(id_, []).append(callback)

    async def unsubscribe(self, ids: list[str]) -> None:
        """Unsubscribe from IDs"""
        async with self._lock:
            existing = [i for i in ids if i in self._subscriptions]
            if not existing:
                return

            await self._send_dynamic_subscribe(existing, subscribe=False)
            for id_ in existing:
                self._subscriptions.discard(id_)
                self._callbacks.pop(id_, None)

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

                    if not msg or msg in ("PONG", "PING", ""):
                        continue

                    if not msg.startswith(("{", "[")):
                        if "INVALID" in msg:
                            logger.warning(
                                f"[POLYMARKET_WS] {self.CHANNEL_NAME} received: {msg}, reconnecting..."
                            )
                            await self._close_ws()
                            await asyncio.sleep(1)
                        else:
                            logger.debug(
                                f"[POLYMARKET_WS] {self.CHANNEL_NAME} non-JSON: {msg}"
                            )
                        continue

                    data = json.loads(msg)
                    messages = data if isinstance(data, list) else [data]
                    for item in messages:
                        await self._handle_message(item)

                except TimeoutError:
                    logger.debug(f"[POLYMARKET_WS] {self.CHANNEL_NAME} timeout")
                except ConnectionClosed:
                    logger.warning(
                        f"[POLYMARKET_WS] {self.CHANNEL_NAME} connection closed, reconnecting..."
                    )
                    await self._close_ws()
                    await asyncio.sleep(1)
                except Exception as e:
                    logger.error(f"[POLYMARKET_WS] {self.CHANNEL_NAME} error: {e}")
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
        if self._subscriptions:
            await self._send_subscribe(list(self._subscriptions))

    async def _send(self, data: dict[str, Any]) -> None:
        if not self._ws:
            raise RuntimeError("WebSocket not connected")
        await self._ws.send(json.dumps(data))

    async def _send_ping(self) -> None:
        while self._running:
            try:
                await asyncio.sleep(self.PING_INTERVAL)
                if self._ws and self._running:
                    await self._ws.send("PING")
            except asyncio.CancelledError:
                return
            except Exception as e:
                logger.error(f"[POLYMARKET_WS] {self.CHANNEL_NAME} ping error: {e}")
                break

    async def _dispatch_callbacks(self, key: str, model: Any) -> None:
        for cb in self._callbacks.get(key, []):
            try:
                if inspect.iscoroutinefunction(cb):
                    await cb(model)
                else:
                    cb(model)
            except Exception as e:
                logger.error(f"[POLYMARKET_WS] {self.CHANNEL_NAME} callback error: {e}")

    async def _dispatch_all_callbacks(self, model: Any) -> None:
        """Dispatch to all registered callbacks regardless of key"""
        for key in self._callbacks:
            await self._dispatch_callbacks(key, model)

    async def _handle_message(self, data: dict[str, Any]) -> None:
        key, model = self._parse_message(data)
        if key and model:
            await self._dispatch_callbacks(key, model)

    @abstractmethod
    async def _send_subscribe(self, ids: list[str]) -> None: ...

    @abstractmethod
    async def _send_dynamic_subscribe(
        self, ids: list[str], subscribe: bool
    ) -> None: ...

    @abstractmethod
    def _parse_message(self, data: dict[str, Any]) -> tuple[str, Any | None]: ...


# -- Event type to model/key mappings --

_MARKET_EVENT_PARSERS: dict[str, tuple[str, type]] = {
    "book": ("asset_id", Book),
    "price_change": ("market", PriceChange),
    "tick_size_change": ("asset_id", TickSizeChange),
    "last_trade_price": ("asset_id", LastTradePrice),
    "best_bid_ask": ("asset_id", BestBidAsk),
    "new_market": ("market", NewMarket),
    "market_resolved": ("market", MarketResolved),
}

_USER_EVENT_PARSERS: dict[str, type] = {
    "trade": UserTrade,
    "order": UserOrder,
}


class PolymarketMarketWebSocket(BasePolymarketWebSocket):
    """WebSocket manager for Polymarket Market channel (public)"""

    BASE_URL = "wss://ws-subscriptions-clob.polymarket.com/ws/market"
    CHANNEL_NAME = "Market"

    async def _send_subscribe(self, asset_ids: list[str]) -> None:
        await self._send(
            {
                "assets_ids": asset_ids,
                "type": "market",
                "custom_feature_enabled": True,
            }
        )
        logger.info(f"[POLYMARKET_WS] Subscribed to {len(asset_ids)} assets")

    async def _send_dynamic_subscribe(
        self, asset_ids: list[str], subscribe: bool = True
    ) -> None:
        request: dict[str, Any] = {
            "assets_ids": asset_ids,
            "operation": "subscribe" if subscribe else "unsubscribe",
        }
        if subscribe:
            request["custom_feature_enabled"] = True
        await self._send(request)
        action = "Subscribed to" if subscribe else "Unsubscribed from"
        logger.info(f"[POLYMARKET_WS] {action} {len(asset_ids)} assets")

    def _parse_message(self, data: dict[str, Any]) -> tuple[str, Any | None]:
        event_type = data.get("event_type")
        parser = _MARKET_EVENT_PARSERS.get(event_type or "")
        if not parser:
            return "", None
        key_field, model_cls = parser
        return data.get(key_field, ""), model_cls(**data)

    async def _handle_message(self, data: dict[str, Any]) -> None:
        key, model = self._parse_message(data)
        if not key or not model:
            return

        await self._dispatch_callbacks(key, model)

        # For price_change, also dispatch to each affected asset_id
        if isinstance(model, PriceChange):
            for pc in model.price_changes:
                await self._dispatch_callbacks(pc.asset_id, model)


class PolymarketUserWebSocket(BasePolymarketWebSocket):
    """WebSocket manager for Polymarket User channel (authenticated)"""

    BASE_URL = "wss://ws-subscriptions-clob.polymarket.com/ws/user"
    CHANNEL_NAME = "User"

    def __init__(self, auth: PolymarketAuth) -> None:
        super().__init__()
        self._auth = auth

    async def _send_subscribe(self, market_ids: list[str]) -> None:
        await self._send(
            {
                "auth": self._auth.to_auth_dict(),
                "markets": market_ids,
                "type": "user",
            }
        )
        logger.info(f"[POLYMARKET_WS] User subscribed to {len(market_ids)} markets")

    async def _send_dynamic_subscribe(
        self, market_ids: list[str], subscribe: bool = True
    ) -> None:
        await self._send(
            {
                "markets": market_ids,
                "operation": "subscribe" if subscribe else "unsubscribe",
            }
        )

    def _parse_message(
        self, data: dict[str, Any]
    ) -> tuple[str, UserTrade | UserOrder | None]:
        event_type = data.get("event_type")
        model_cls = _USER_EVENT_PARSERS.get(event_type or "")
        if not model_cls:
            return "", None
        return data.get("market", ""), model_cls(**data)

    async def _handle_message(self, data: dict[str, Any]) -> None:
        _, model = self._parse_message(data)
        if model:
            await self._dispatch_all_callbacks(model)
