# Getting Started

## Installation

=== "pip"

    ```bash
    pip install polytrader
    ```

=== "uv"

    ```bash
    uv add polytrader
    ```

## Requirements

- Python >= 3.11

## Setup

### 1. Get Your Credentials

To trade on Polymarket you need:

- **Private key** — Your Ethereum wallet private key (hex string)
- **Funder address** — The wallet address that funds your trades
- **Signature type** — `0` for EOA wallets, `2` for Gnosis Safe proxy wallets

Optionally, for builder/relayer support:

- **Builder API key**, **secret**, and **passphrase** — Get these from [Polymarket](https://polymarket.com)

### 2. Environment Variables

Create a `.env` file in your project root:

```bash
POLYMARKET_PRIVATE_KEY=your_private_key_here
POLYMARKET_FUNDER=0xYourWalletAddress
POLYMARKET_SIGNATURE_TYPE=0
```

### 3. Initialize the Client

```python
import os
from polytrader import PolyTrader

trader = PolyTrader(
    private_key=os.environ["POLYMARKET_PRIVATE_KEY"],
    funder=os.environ["POLYMARKET_FUNDER"],
    signature_type=int(os.environ["POLYMARKET_SIGNATURE_TYPE"]),
)
```

With builder/relayer support:

```python
trader = PolyTrader(
    private_key=os.environ["POLYMARKET_PRIVATE_KEY"],
    funder=os.environ["POLYMARKET_FUNDER"],
    signature_type=int(os.environ["POLYMARKET_SIGNATURE_TYPE"]),
    builder_key=os.environ["POLY_BUILDER_API_KEY"],
    builder_secret=os.environ["POLY_BUILDER_SECRET"],
    builder_passphrase=os.environ["POLY_BUILDER_PASSPHRASE"],
)
```

### 4. Approve Tokens (First Time Only)

Before placing orders, you need to approve token spending on-chain:

```python
tx_hashes = trader.approve_all()
print(f"Approved: {tx_hashes}")
```

## Configuration

PolyTrader can be configured via environment variables:

| Variable | Default | Description |
|---|---|---|
| `POLYTRADER_CLOB_HOST` | `https://clob.polymarket.com` | CLOB API endpoint |
| `POLYTRADER_GAMMA_API_HOST` | `https://gamma-api.polymarket.com` | Gamma API endpoint |
| `POLYTRADER_DATA_API_HOST` | `https://data-api.polymarket.com` | Data API endpoint |
| `POLYTRADER_CHAIN_ID` | `137` | Polygon chain ID |
| `POLYTRADER_POLYGON_RPC` | `https://polygon-bor-rpc.publicnode.com` | Polygon RPC endpoint |
| `POLYTRADER_RELAYER_HOST` | `https://relayer-v2.polymarket.com` | Relayer endpoint |
