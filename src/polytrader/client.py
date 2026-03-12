import json
import logging
from datetime import UTC, datetime
from typing import Any, cast

import httpx
from eth_account import Account
from py_clob_client.client import ApiCreds, ClobClient, OrderBookSummary
from py_clob_client.clob_types import (
    AssetType,
    BalanceAllowanceParams,
    OpenOrderParams,
    OrderArgs,
    TradeParams,
)

from polytrader.constants import CHAIN_ID, CLOB_HOST, DATA_API_HOST, GAMMA_API_HOST
from polytrader.models import (
    Balance,
    BtcMarket,
    OrderResult,
    OrderSide,
    PolymarketAuth,
    PolymarketOrder,
    PolymarketOrderType,
    PolymarketPosition,
    TokenIdPair,
)

logger = logging.getLogger(__name__)


class PolyTrader:
    """Polymarket client for API credential management and WebSocket connections"""

    def __init__(
        self,
        private_key: str,
        funder: str,
        signature_type: int,
    ) -> None:
        self._private_key = private_key
        self.funder: str = funder
        self._signature_type: int = signature_type
        self._clob_client: ClobClient | None = None
        self._auth: PolymarketAuth | None = None
        self._http = httpx.AsyncClient(timeout=10.0)

    @property
    def private_key(self) -> str:
        """Get private key without 0x prefix"""
        pk = self._private_key
        return pk[2:] if pk.startswith("0x") else pk

    @property
    def wallet_address(self) -> str:
        """Get wallet address (MetaMask) from private key"""
        address = Account.from_key(self._private_key).address
        if not isinstance(address, str):
            raise ValueError("Invalid private key")
        return address

    def _get_clob_client(self) -> ClobClient:
        """Get or create CLOB client"""
        if self._clob_client is None:
            self._clob_client = ClobClient(
                CLOB_HOST,
                key=self.private_key,
                chain_id=CHAIN_ID,
                signature_type=self._signature_type,
                funder=self.funder,
            )
        return self._clob_client

    def _get_authenticated_client(self) -> ClobClient:
        """Get CLOB client with API credentials set (cached)"""
        client = self._get_clob_client()
        if client.creds is None:
            auth = self.get_auth()
            client.set_api_creds(
                ApiCreds(
                    api_key=auth.api_key,
                    api_secret=auth.secret,
                    api_passphrase=auth.passphrase,
                )
            )
        return client

    def _derive_credentials(self) -> None:
        """Derive API credentials and funder from private key"""
        client = self._get_clob_client()
        resp: ApiCreds = client.derive_api_key()

        self._auth = PolymarketAuth(
            api_key=resp.api_key,
            secret=resp.api_secret,
            passphrase=resp.api_passphrase,
        )

        logger.info(f"[POLYMARKET] Credentials derived, funder: {self.funder}")

    def get_auth(self) -> PolymarketAuth:
        """Get API credentials (cached)"""
        if self._auth is None:
            self._derive_credentials()
        if self._auth is None:
            raise RuntimeError("Failed to derive credentials")
        return self._auth

    # ========================================================================
    # Market Data
    # ========================================================================

    @staticmethod
    def _parse_token_ids(market_data: dict[str, Any]) -> TokenIdPair:
        """Extract up/down token IDs from market data"""
        token_ids_raw = market_data.get("clobTokenIds", "[]")
        outcomes_raw = market_data.get("outcomes", "[]")

        token_ids = (
            json.loads(token_ids_raw)
            if isinstance(token_ids_raw, str)
            else token_ids_raw
        )
        outcomes = (
            json.loads(outcomes_raw) if isinstance(outcomes_raw, str) else outcomes_raw
        )

        outcome_map: dict[str, str] = {}
        for i, outcome in enumerate(outcomes):
            if i < len(token_ids):
                outcome_map[outcome.lower()] = token_ids[i]

        return TokenIdPair(
            up=outcome_map.get("up", ""), down=outcome_map.get("down", "")
        )

    async def get_btc_market(self, slug: str) -> BtcMarket | None:
        """
        Get BTC Up/Down market info by slug.

        Args:
            slug: Market slug (e.g., "btc-updown-5m-1772871600")

        Returns:
            BtcMarket with token IDs for Up and Down outcomes, or None if not found
        """
        url = f"{GAMMA_API_HOST}/markets?slug={slug}"
        try:
            resp = await self._http.get(url)
            resp.raise_for_status()
            data = resp.json()

            if not data:
                logger.warning(f"[POLYMARKET] No market found for slug: {slug}")
                return None

            market_data = data[0] if isinstance(data, list) else data
            tokens = self._parse_token_ids(market_data)

            return BtcMarket(
                condition_id=market_data.get("conditionId", ""),
                question_id=market_data.get("questionID", ""),
                slug=market_data.get("slug", slug),
                title=market_data.get("question", ""),
                up_token_id=tokens.up,
                down_token_id=tokens.down,
                end_date=market_data.get("endDate", ""),
                active=market_data.get("active", False),
                closed=market_data.get("closed", False),
            )

        except httpx.HTTPError as e:
            logger.error(f"[POLYMARKET] Failed to fetch market: {e}")
            return None

    async def get_btc_market_by_timestamp(self, timestamp: int) -> BtcMarket | None:
        """Get BTC Up/Down 5-minute market by Unix timestamp."""
        slug = f"btc-updown-5m-{timestamp}"
        return await self.get_btc_market(slug)

    async def get_current_btc_market(self) -> BtcMarket | None:
        """Get current BTC Up/Down 5-minute market."""
        now = datetime.now(UTC)
        rounded_ts = (int(now.timestamp()) // 300) * 300
        return await self.get_btc_market_by_timestamp(rounded_ts)

    # ========================================================================
    # Order Management
    # ========================================================================

    def create_order(
        self,
        token_id: str,
        side: OrderSide,
        price: float,
        size: float,
        order_type: PolymarketOrderType = PolymarketOrderType.GTC,
        post_only: bool = False,
    ) -> OrderResult:
        """
        Create and post an order.

        Args:
            token_id: The token ID (asset ID) to trade
            side: BUY or SELL
            price: Price (0.01 to 0.99 for binary markets). Ignored for MARKET orders.
            size: Number of shares
            order_type: GTC, GTD, FOK, FAK, or MARKET
            post_only: If True, order will be rejected if it would match immediately

        Returns:
            OrderResult with success status and order ID
        """
        client = self._get_authenticated_client()

        try:
            # Handle MARKET orders: use aggressive price with FOK
            actual_order_type = order_type
            actual_price = price

            if order_type == PolymarketOrderType.MARKET:
                actual_price = 0.99 if side == OrderSide.BUY else 0.01
                actual_order_type = PolymarketOrderType.FOK
                logger.debug(f"[POLYMARKET] MARKET order -> FOK at {actual_price}")

            order_args = OrderArgs(
                token_id=token_id,
                price=actual_price,
                size=size,
                side=side.value,
            )

            signed_order = client.create_order(order_args)
            resp = client.post_order(
                signed_order,
                orderType=actual_order_type.to_clob_order_type(),
                post_only=(
                    post_only if order_type != PolymarketOrderType.MARKET else False
                ),
            )

            order_id = resp.get("orderID") or resp.get("order_id")
            status = resp.get("status", "UNKNOWN")

            logger.info(
                f"[POLYMARKET] Order created: {side.value} {size}@{actual_price} "
                f"type={order_type.value} id={order_id}"
            )

            return OrderResult(
                success=True,
                order_id=order_id,
                status=status,
            )

        except Exception as e:
            logger.exception(f"[POLYMARKET] Failed to create order: {e}")
            return OrderResult(
                success=False,
                error_msg=f"{type(e).__name__}: {e}",
            )

    @staticmethod
    def _extract_cancelled(resp: dict[str, Any]) -> list[str]:
        """Extract cancelled order IDs from API response (handles both spellings)"""
        result = resp.get("canceled", resp.get("cancelled", []))
        return result if isinstance(result, list) else []

    def cancel_order(self, order_id: str) -> bool:
        """Cancel a specific order."""
        client = self._get_authenticated_client()

        try:
            resp = client.cancel(order_id)
            cancelled = bool(
                self._extract_cancelled(resp)
                or resp.get("canceled", resp.get("cancelled", False))
            )
            if cancelled:
                logger.info(f"[POLYMARKET] Order cancelled: {order_id}")
            return cancelled
        except Exception as e:
            logger.error(f"[POLYMARKET] Failed to cancel order {order_id}: {e}")
            return False

    def cancel_all_orders(self) -> int:
        """Cancel all open orders."""
        client = self._get_authenticated_client()

        try:
            resp = client.cancel_all()
            cancelled_ids = self._extract_cancelled(resp)
            logger.info(f"[POLYMARKET] Cancelled {len(cancelled_ids)} orders")
            return len(cancelled_ids)
        except Exception as e:
            logger.error(f"[POLYMARKET] Failed to cancel all orders: {e}")
            return 0

    def cancel_orders_for_market(self, market_id: str) -> int:
        """Cancel all orders for a specific market."""
        client = self._get_authenticated_client()

        try:
            resp = client.cancel_market_orders(market_id)
            cancelled_ids = self._extract_cancelled(resp)
            logger.info(
                f"[POLYMARKET] Cancelled {len(cancelled_ids)} orders for market {market_id}"
            )
            return len(cancelled_ids)
        except Exception as e:
            logger.error(f"[POLYMARKET] Failed to cancel market orders: {e}")
            return 0

    # ========================================================================
    # Order/Position Queries
    # ========================================================================

    def get_orders(
        self,
        market_id: str | None = None,
        asset_id: str | None = None,
    ) -> list[PolymarketOrder]:
        """Get open orders, optionally filtered by market or asset."""
        client = self._get_authenticated_client()

        try:
            params = OpenOrderParams(market=market_id, asset_id=asset_id)
            resp = client.get_orders(params)
            return [PolymarketOrder.from_dict(d) for d in resp]
        except Exception as e:
            logger.error(f"[POLYMARKET] Failed to get orders: {e}")
            return []

    def get_trades(
        self,
        market_id: str | None = None,
        asset_id: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Get trade history."""
        client = self._get_authenticated_client()

        try:
            params = TradeParams(market=market_id, asset_id=asset_id)
            return client.get_trades(params)  # type: ignore[no-any-return]
        except Exception as e:
            logger.error(f"[POLYMARKET] Failed to get trades: {e}")
            return []

    async def get_positions(self) -> list[PolymarketPosition]:
        """Get current positions from the data API."""
        url = f"{DATA_API_HOST}/positions?user={self.funder}"
        try:
            resp = await self._http.get(url)
            resp.raise_for_status()
            data = resp.json()

            positions: list[PolymarketPosition] = []
            for pos_data in data:
                try:
                    positions.append(PolymarketPosition.from_dict(pos_data))
                except Exception as e:
                    logger.warning(f"[POLYMARKET] Failed to parse position: {e}")
            return positions

        except httpx.HTTPError as e:
            logger.error(f"[POLYMARKET] Failed to fetch positions: {e}")
            return []

    def get_balance(self) -> Balance:
        """Get USDC balance and allowance."""
        client = self._get_authenticated_client()

        try:
            params = BalanceAllowanceParams(
                asset_type=cast(AssetType, AssetType.COLLATERAL)
            )
            resp = cast(dict[str, Any], client.get_balance_allowance(params))
            return Balance.from_dict(resp)
        except Exception as e:
            logger.error(f"[POLYMARKET] Failed to get balance: {e}")
            return Balance(balance=0.0, allowance=0.0)

    def get_orderbook(self, token_id: str) -> OrderBookSummary:
        """Get orderbook for a token."""
        client = self._get_clob_client()
        return client.get_order_book(token_id)

    # ========================================================================
    # Token Approvals
    # ========================================================================

    def ensure_can_sell(self, token_id: str, size: float) -> bool:
        """
        Check if a sell order is possible, auto-approving token if needed.

        Returns:
            True if sell of given size is possible
        """
        client = self._get_authenticated_client()

        try:
            params = BalanceAllowanceParams(
                asset_type=cast(AssetType, AssetType.CONDITIONAL),
                token_id=token_id,
            )
            resp = cast(dict[str, Any], client.get_balance_allowance(params))
            balance = float(resp.get("balance", 0))
            allowance = float(resp.get("allowance", 0))
        except Exception as e:
            logger.error(f"[POLYMARKET] Sell check failed: {e}")
            return False

        if balance < size:
            logger.warning(
                f"[POLYMARKET] Insufficient token balance: {balance} < {size}"
            )
            return False

        if allowance < size:
            logger.info(
                f"[POLYMARKET] Allowance too low ({allowance}), approving token..."
            )
            if not self.approve_token(token_id):
                return False

        # Account for tokens locked in open sell orders
        open_orders = self.get_orders(asset_id=token_id)
        locked = sum(o.size_remaining for o in open_orders if o.side == OrderSide.SELL)
        available = balance - locked

        if available < size:
            logger.warning(
                f"[POLYMARKET] Available after open orders: {available} < {size}"
            )
            return False

        return True

    def approve_token(self, token_id: str) -> bool:
        """Approve a conditional token for trading (required before selling)."""
        client = self._get_authenticated_client()

        try:
            params = BalanceAllowanceParams(
                asset_type=cast(AssetType, AssetType.CONDITIONAL),
                token_id=token_id,
            )
            client.update_balance_allowance(params)
            logger.info(f"[POLYMARKET] Approved token: {token_id[:20]}...")
            return True
        except Exception as e:
            logger.error(f"[POLYMARKET] Failed to approve token: {e}")
            return False

    def approve_collateral(self) -> bool:
        """Approve USDC collateral for trading."""
        client = self._get_authenticated_client()

        try:
            params = BalanceAllowanceParams(
                asset_type=cast(AssetType, AssetType.COLLATERAL),
            )
            client.update_balance_allowance(params)
            logger.info("[POLYMARKET] Approved USDC collateral")
            return True
        except Exception as e:
            logger.error(f"[POLYMARKET] Failed to approve collateral: {e}")
            return False

    def approve_market_tokens(self, up_token_id: str, down_token_id: str) -> bool:
        """Approve both UP and DOWN tokens for a market."""
        up_ok = self.approve_token(up_token_id)
        down_ok = self.approve_token(down_token_id)
        return up_ok and down_ok
