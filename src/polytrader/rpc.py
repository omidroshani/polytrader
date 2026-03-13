"""On-chain transaction helpers for Polygon.

Supports both direct EOA transactions and Gnosis Safe proxy wallets
(via Polymarket's Relayer service).
"""

import time
from dataclasses import dataclass
from typing import Any, cast

import httpx
from eth_abi import encode as abi_encode
from eth_account import Account
from eth_utils import keccak
from py_builder_relayer_client.client import RelayClient
from py_builder_relayer_client.models import OperationType, SafeTransaction
from py_builder_signing_sdk.config import BuilderConfig
from py_builder_signing_sdk.sdk_types import BuilderApiKeyCreds
from py_clob_client.config import get_contract_config

from polytrader.constants import CHAIN_ID, POLYGON_RPC, RELAYER_HOST

_SET_APPROVAL_FOR_ALL_SELECTOR = keccak(text="setApprovalForAll(address,bool)")[:4]
_ERC20_APPROVE_SELECTOR = keccak(text="approve(address,uint256)")[:4]
_MAX_UINT256 = 2**256 - 1


@dataclass
class BuilderCreds:
    """Builder API credentials for the Polymarket Relayer."""

    key: str
    secret: str
    passphrase: str


def approve_token(
    private_key: str,
    neg_risk: bool = False,
    funder: str | None = None,
    builder_creds: BuilderCreds | None = None,
) -> str:
    """Approve the CTF conditional tokens for the exchange via setApprovalForAll.

    One-time setup per exchange (neg_risk vs non-neg_risk).

    Returns:
        Transaction hash.
    """
    config = get_contract_config(CHAIN_ID, neg_risk)
    calldata = _SET_APPROVAL_FOR_ALL_SELECTOR + abi_encode(
        ["address", "bool"], [config.exchange, True]
    )
    return _send_tx(
        private_key, config.conditional_tokens, calldata, funder, builder_creds
    )


def approve_collateral(
    private_key: str,
    neg_risk: bool = False,
    funder: str | None = None,
    builder_creds: BuilderCreds | None = None,
) -> str:
    """Approve USDC for the exchange contract (required for buying).

    Sends an on-chain ERC20 approve transaction for max uint256.

    Returns:
        Transaction hash.
    """
    config = get_contract_config(CHAIN_ID, neg_risk)
    calldata = _ERC20_APPROVE_SELECTOR + abi_encode(
        ["address", "uint256"], [config.exchange, _MAX_UINT256]
    )
    return _send_tx(private_key, config.collateral, calldata, funder, builder_creds)


def approve_all(
    private_key: str,
    funder: str | None = None,
    builder_creds: BuilderCreds | None = None,
) -> list[str]:
    """Approve both exchanges (neg_risk + non-neg_risk) for tokens and USDC.

    Returns:
        List of transaction hashes.
    """
    hashes = []
    for neg_risk in (False, True):
        hashes.append(approve_token(private_key, neg_risk, funder, builder_creds))
        hashes.append(approve_collateral(private_key, neg_risk, funder, builder_creds))
    return hashes


def wait_for_tx(tx_hash: str, timeout: int = 60) -> dict[str, Any]:
    """Wait for a transaction to be mined and return the receipt."""
    with httpx.Client(timeout=30.0) as rpc:
        for _ in range(timeout):
            receipt = _rpc_call(rpc, "eth_getTransactionReceipt", [tx_hash])
            if receipt is not None:
                return cast(dict[str, Any], receipt)
            time.sleep(1)
    raise TimeoutError(f"Transaction {tx_hash} not mined within {timeout}s")


def _send_tx(
    private_key: str,
    to: str,
    data: bytes,
    funder: str | None = None,
    builder_creds: BuilderCreds | None = None,
) -> str:
    """Build, sign, and send a transaction on Polygon.

    If funder differs from EOA, sends via Polymarket's Relayer (gasless).
    """
    account = Account.from_key(private_key)
    eoa = account.address

    if funder and funder.lower() != eoa.lower():
        if builder_creds is None:
            raise ValueError(
                "builder_creds required for Safe proxy wallet transactions"
            )
        return _send_relayer_tx(private_key, builder_creds, to, data)

    with httpx.Client(timeout=30.0) as rpc:
        nonce = _rpc_call(rpc, "eth_getTransactionCount", [eoa, "latest"])
        gas_price = _rpc_call(rpc, "eth_gasPrice", [])

        tx = {
            "to": to,
            "data": data,
            "value": 0,
            "gas": 100_000,
            "gasPrice": int(gas_price, 16),
            "nonce": int(nonce, 16),
            "chainId": CHAIN_ID,
        }
        signed = account.sign_transaction(tx)
        raw_hex = "0x" + signed.raw_transaction.hex()
        tx_hash: str = _rpc_call(rpc, "eth_sendRawTransaction", [raw_hex])
    return tx_hash


def _send_relayer_tx(
    private_key: str, builder_creds: BuilderCreds, to: str, data: bytes
) -> str:
    """Execute a transaction through Polymarket's Relayer (gasless Safe tx)."""
    builder_config = BuilderConfig(
        local_builder_creds=BuilderApiKeyCreds(
            key=builder_creds.key,
            secret=builder_creds.secret,
            passphrase=builder_creds.passphrase,
        )
    )
    relay_client = RelayClient(
        relayer_url=RELAYER_HOST,
        chain_id=CHAIN_ID,
        private_key=private_key,
        builder_config=builder_config,
    )

    safe_tx = SafeTransaction(
        to=to,
        operation=OperationType.Call,
        data="0x" + data.hex(),
        value="0",
    )

    response = relay_client.execute([safe_tx], "Token approval")
    result = response.wait()
    if result is None:
        raise RuntimeError("Relayer transaction failed or timed out")
    tx_hash: str = result.get("transactionHash", response.transaction_hash)
    return tx_hash


def _rpc_call(client: httpx.Client, method: str, params: list) -> Any:
    """Make a JSON-RPC call to Polygon."""
    resp = client.post(
        POLYGON_RPC,
        json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params},
    )
    resp.raise_for_status()
    result = resp.json()
    if "error" in result:
        raise RuntimeError(f"RPC error: {result['error']}")
    return result["result"]
