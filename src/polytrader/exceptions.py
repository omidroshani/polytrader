"""Custom exception hierarchy for polytrader."""


class PolytraderError(Exception):
    """Base exception for all polytrader errors."""


class AuthenticationError(PolytraderError):
    """Authentication or credential error."""


class OrderError(PolytraderError):
    """Order placement, update, or cancellation error."""


class WebSocketError(PolytraderError):
    """WebSocket connection or messaging error."""


class RPCError(PolytraderError, RuntimeError):
    """On-chain RPC call error.

    Inherits from RuntimeError for backward compatibility with existing
    ``except RuntimeError`` handlers.
    """


class TransactionTimeoutError(RPCError, TimeoutError):
    """Transaction confirmation timed out.

    Inherits from TimeoutError for backward compatibility.
    """
