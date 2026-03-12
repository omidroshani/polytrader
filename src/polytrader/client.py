import json
import logging
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, cast

import httpx
from eth_account import Account
from py_clob_client.client import ApiCreds, ClobClient, OrderBookSummary
from py_clob_client.clob_types import (
    AssetType,
    BalanceAllowanceParams,
    MarketOrderArgs,
    OpenOrderParams,
    OrderArgs,
    PartialCreateOrderOptions,
    TradeParams,
)

from polytrader.constants import CHAIN_ID, CLOB_HOST, DATA_API_HOST, GAMMA_API_HOST
from polytrader.models import (
    ZERO,
    Balance,
    Coin,
    OrderResult,
    OrderSide,
    PolymarketAuth,
    PolymarketOrder,
    PolymarketOrderType,
    PolymarketPosition,
    PolymarketTrade,
    Timeframe,
    TokenIdPair,
    UpDownMarket,
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

    async def get_updown_market(
        self, coin: Coin, timeframe: Timeframe, timestamp: int
    ) -> UpDownMarket:
        """
        Get Up/Down market by coin, timeframe, and Unix timestamp.

        Args:
            coin: Coin enum (BTC, ETH, SOL, XRP)
            timeframe: Timeframe enum (M5, M15)
            timestamp: Unix timestamp for the market period

        Returns:
            UpDownMarket with token IDs for Up and Down outcomes

        Raises:
            ValueError: If no market found for the given parameters
            httpx.HTTPError: If the API request fails
        """
        slug = f"{coin}-updown-{timeframe}-{timestamp}"
        url = f"{GAMMA_API_HOST}/markets?slug={slug}"
        resp = await self._http.get(url)
        resp.raise_for_status()
        data = resp.json()

        if not data:
            raise ValueError(f"No market found for slug: {slug}")

        market_data = data[0] if isinstance(data, list) else data
        tokens = self._parse_token_ids(market_data)

        return UpDownMarket(
            coin=coin,
            timeframe=timeframe,
            condition_id=market_data.get("conditionId", ""),
            question_id=market_data.get("questionID", ""),
            slug=market_data.get("slug", slug),
            title=market_data.get("question", ""),
            up_token_id=tokens.up,
            down_token_id=tokens.down,
            end_date=datetime.fromisoformat(market_data["endDate"]),
            active=market_data.get("active", False),
            closed=market_data.get("closed", False),
            order_price_min_tick_size=Decimal(
                str(market_data.get("orderPriceMinTickSize", 0))
            ),
            order_min_size=Decimal(str(market_data.get("orderMinSize", 0))),
            neg_risk=market_data.get("negRisk", False),
            accepting_orders=market_data.get("acceptingOrders", False),
            best_bid=Decimal(str(market_data.get("bestBid", 0))),
            best_ask=Decimal(str(market_data.get("bestAsk", 0))),
            last_trade_price=Decimal(str(market_data.get("lastTradePrice", 0))),
            spread=Decimal(str(market_data.get("spread", 0))),
            maker_base_fee=int(market_data.get("makerBaseFee", 0)),
            taker_base_fee=int(market_data.get("takerBaseFee", 0)),
        )

    async def get_current_updown_market(
        self, coin: Coin, timeframe: Timeframe
    ) -> UpDownMarket:
        """Get current Up/Down market for a coin and timeframe."""
        now = datetime.now(UTC)
        interval = 300 if timeframe == Timeframe.M5 else 900
        rounded_ts = (int(now.timestamp()) // interval) * interval
        return await self.get_updown_market(coin, timeframe, rounded_ts)

    # ========================================================================
    # Order Management
    # ========================================================================

    def create_order(
        self,
        token_id: str,
        side: OrderSide,
        price: Decimal,
        size: Decimal,
        tick_size: str = "0.01",
        neg_risk: bool = False,
        order_type: PolymarketOrderType = PolymarketOrderType.GTC,
        expiration: int = 0,
        post_only: bool = False,
    ) -> OrderResult:
        """
        Create and post an order.

        For limit orders (GTC, GTD): specify price and size.
        For market orders (FOK, FAK): size is the dollar amount for BUY,
            or number of shares for SELL. Price acts as worst-price limit.
        For MARKET pseudo-type: converted to FOK with aggressive price.

        Args:
            token_id: The token ID (asset ID) to trade
            side: BUY or SELL
            price: Limit price (slippage protection for FOK/FAK)
            size: Shares for limit/SELL, dollar amount for FOK/FAK BUY
            tick_size: Market tick size ("0.1", "0.01", "0.001", "0.0001")
            neg_risk: Whether this is a negative risk market (3+ outcomes)
            order_type: GTC, GTD, FOK, FAK, or MARKET
            expiration: Unix timestamp for GTD orders (add 60s security buffer)
            post_only: Reject if order would match immediately (GTC/GTD only)
        """
        client = self._get_authenticated_client()
        options = PartialCreateOrderOptions(tick_size=tick_size, neg_risk=neg_risk)

        actual_order_type = order_type
        if order_type == PolymarketOrderType.MARKET:
            actual_order_type = PolymarketOrderType.FOK

        if actual_order_type in (PolymarketOrderType.FOK, PolymarketOrderType.FAK):
            # Market orders: use create_market_order
            market_price = price
            if order_type == PolymarketOrderType.MARKET:
                market_price = (
                    Decimal("0.99") if side == OrderSide.BUY else Decimal("0.01")
                )

            market_args = MarketOrderArgs(
                token_id=token_id,
                amount=float(size),
                side=side.value,
                price=float(market_price),
            )
            signed_order = client.create_market_order(market_args, options)
        else:
            # Limit orders: GTC or GTD
            order_args = OrderArgs(
                token_id=token_id,
                price=float(price),
                size=float(size),
                side=side.value,
                expiration=expiration,
            )
            signed_order = client.create_order(order_args, options)

        resp = client.post_order(
            signed_order,
            orderType=actual_order_type.to_clob_order_type(),
            post_only=post_only
            and actual_order_type
            in (
                PolymarketOrderType.GTC,
                PolymarketOrderType.GTD,
            ),
        )

        result = OrderResult.from_dict(resp)

        logger.info(
            "[POLYMARKET] Order %s: %s %s@%s type=%s id=%s",
            result.status.value,
            side.value,
            size,
            price,
            order_type.value,
            result.order_id,
        )

        return result

    @staticmethod
    def _extract_cancelled(resp: dict[str, Any]) -> list[str]:
        """Extract cancelled order IDs from API response (handles both spellings)"""
        result = resp.get("canceled", resp.get("cancelled", []))
        return result if isinstance(result, list) else []

    def cancel_order(self, order_id: str) -> bool:
        """Cancel a specific order."""
        client = self._get_authenticated_client()
        resp = client.cancel(order_id)
        cancelled = bool(
            self._extract_cancelled(resp)
            or resp.get("canceled", resp.get("cancelled", False))
        )
        if cancelled:
            logger.info(f"[POLYMARKET] Order cancelled: {order_id}")
        return cancelled

    def cancel_all_orders(self) -> int:
        """Cancel all open orders."""
        client = self._get_authenticated_client()
        resp = client.cancel_all()
        cancelled_ids = self._extract_cancelled(resp)
        logger.info(f"[POLYMARKET] Cancelled {len(cancelled_ids)} orders")
        return len(cancelled_ids)

    def cancel_orders_for_market(self, market_id: str) -> int:
        """Cancel all orders for a specific market."""
        client = self._get_authenticated_client()
        resp = client.cancel_market_orders(market_id)
        cancelled_ids = self._extract_cancelled(resp)
        logger.info(
            f"[POLYMARKET] Cancelled {len(cancelled_ids)} orders for market {market_id}"
        )
        return len(cancelled_ids)

    # ========================================================================
    # Order/Position Queries
    # ========================================================================

    def get_order(self, order_id: str) -> PolymarketOrder:
        """Get a single order by ID."""
        client = self._get_authenticated_client()
        resp = client.get_order(order_id)
        return PolymarketOrder.from_dict(resp)

    def get_orders(
        self,
        market_id: str | None = None,
        asset_id: str | None = None,
    ) -> list[PolymarketOrder]:
        """Get open orders, optionally filtered by market or asset."""
        client = self._get_authenticated_client()
        params = OpenOrderParams(market=market_id, asset_id=asset_id)
        resp = client.get_orders(params)
        return [PolymarketOrder.from_dict(d) for d in resp]

    def get_trades(
        self,
        market_id: str | None = None,
        asset_id: str | None = None,
    ) -> list[PolymarketTrade]:
        """Get trade history."""
        client = self._get_authenticated_client()
        params = TradeParams(market=market_id, asset_id=asset_id)
        resp = client.get_trades(params)
        return [PolymarketTrade.from_dict(d) for d in resp]

    async def get_positions(self) -> list[PolymarketPosition]:
        """Get current positions from the data API."""
        url = f"{DATA_API_HOST}/positions?user={self.funder}"
        resp = await self._http.get(url)
        resp.raise_for_status()
        data = resp.json()
        return [PolymarketPosition.from_dict(pos_data) for pos_data in data]

    def get_balance(self) -> Balance:
        """Get USDC balance and allowance."""
        client = self._get_authenticated_client()
        params = BalanceAllowanceParams(
            asset_type=cast(AssetType, AssetType.COLLATERAL)
        )
        resp = cast(dict[str, Any], client.get_balance_allowance(params))
        return Balance.from_dict(resp)

    def get_orderbook(self, token_id: str) -> OrderBookSummary:
        """Get orderbook for a token."""
        client = self._get_clob_client()
        return client.get_order_book(token_id)

    # ========================================================================
    # Token Approvals
    # ========================================================================

    def ensure_can_sell(self, token_id: str, size: Decimal) -> bool:
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
            balance = Decimal(str(resp.get("balance", 0)))
            allowance = Decimal(str(resp.get("allowance", 0)))
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
        locked = sum(
            (o.size_remaining for o in open_orders if o.side == OrderSide.SELL), ZERO
        )
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
