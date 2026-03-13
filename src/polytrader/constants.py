from decimal import Decimal

CLOB_HOST = "https://clob.polymarket.com"
GAMMA_API_HOST = "https://gamma-api.polymarket.com"
DATA_API_HOST = "https://data-api.polymarket.com"
CHAIN_ID = 137  # Polygon mainnet
POLYGON_RPC = "https://polygon-bor-rpc.publicnode.com"
RELAYER_HOST = "https://relayer-v2.polymarket.com"

# Conditional tokens and USDC on Polygon both use 6 decimals.
# The CLOB balance API returns raw values; create_order expects human-readable.
TOKEN_DECIMALS = Decimal("1000000")

# Crypto-market fee formula: fee = size * price * CRYPTO_FEE_RATE * (price * (1 - price))^CRYPTO_FEE_EXPONENT
CRYPTO_FEE_RATE = Decimal("0.25")
CRYPTO_FEE_EXPONENT = 2
