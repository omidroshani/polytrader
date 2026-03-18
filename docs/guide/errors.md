# Error Handling

PolyTrader uses a hierarchy of exceptions for different error types.

## Exception Hierarchy

```
PolytraderError              # Base exception
├── AuthenticationError      # Credential or auth failures
├── OrderError               # Order placement/cancellation failures
├── WebSocketError           # WebSocket connection issues
└── RPCError                 # On-chain RPC call failures
    └── TransactionTimeoutError  # Transaction confirmation timeout
```

## Handling Errors

```python
from polytrader import (
    PolytraderError,
    AuthenticationError,
    OrderError,
    WebSocketError,
    RPCError,
    TransactionTimeoutError,
)

# Catch specific errors
try:
    result = trader.create_order(
        token_id=token_id,
        side=OrderSide.BUY,
        price=Decimal("0.50"),
        size=Decimal("10"),
    )
except OrderError as e:
    print(f"Order failed: {e}")

# Catch authentication issues
try:
    auth = trader.get_auth()
except AuthenticationError as e:
    print(f"Auth failed: {e}")

# Catch on-chain errors
try:
    tx_hash = trader.approve_all()
except TransactionTimeoutError as e:
    print(f"Transaction timed out: {e}")
except RPCError as e:
    print(f"RPC error: {e}")

# Catch all polytrader errors
try:
    # ... any operation
    pass
except PolytraderError as e:
    print(f"PolyTrader error: {e}")
```

!!! tip
    `RPCError` also inherits from `RuntimeError` and `TransactionTimeoutError` also inherits from `TimeoutError`, so they can be caught with standard Python exception types as well.
