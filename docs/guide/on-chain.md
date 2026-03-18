# On-Chain Operations

PolyTrader supports on-chain token approvals required before trading on Polymarket.

## Token Approvals

Before placing orders, you must approve the Polymarket exchange contracts to spend your tokens.

### Approve All (Recommended)

```python
# Approve both conditional tokens and USDC collateral
tx_hashes = trader.approve_all()
print(f"Transaction hashes: {tx_hashes}")
```

### Individual Approvals

```python
# Approve conditional tokens
tx_hash = trader.approve_token(neg_risk=False)

# Approve for neg-risk markets
tx_hash = trader.approve_token(neg_risk=True)

# Approve USDC collateral
tx_hash = trader.approve_collateral(neg_risk=False)
```

## Waiting for Transactions

Use `wait_for_tx` to wait for a transaction to be confirmed on-chain:

```python
from polytrader.rpc import wait_for_tx

tx_hash = trader.approve_token()
receipt = await wait_for_tx(tx_hash, timeout=60)
print(f"Confirmed in block: {receipt['blockNumber']}")
```

!!! warning
    If the transaction is not confirmed within the timeout period, a `TransactionTimeoutError` is raised.

## Allowance Management

```python
# Check current balance and allowance
balance = trader.get_balance()
if balance.allowance == 0:
    trader.approve_collateral()

# Refresh allowances after approval
trader.refresh_collateral_allowance()
trader.refresh_token_allowance(token_id="your-token-id")

# Verify you can sell before placing a sell order
can_sell = trader.ensure_can_sell(
    token_id="your-token-id",
    size=Decimal("10"),
)
```
