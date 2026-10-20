"""Stablecoin Tokenized 'Vending Machine' API Paywall ($0.05 'printing prices' per query)."""

from __future__ import annotations

import hashlib
import hmac
import time
import uuid
from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional


DEFAULT_PRICE_PER_QUERY_USD: float = 0.05


class InsufficientBalanceError(Exception):
    """Raised when a wallet does not have enough balance/tokens for a metered query."""


@dataclass
class WalletAccount:
    """Represents a client wallet in the Stablecoin Vending Machine Paywall."""

    wallet_id: str
    balance_usd: float = 0.0
    tokens_balance: int = 0
    total_minted_usd: float = 0.0
    queries_executed: int = 0
    stablecoin: str = "USDC"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class QueryReceipt:
    """Cryptographic HMAC-SHA256 receipt issued for each metered GraphRAG query."""

    receipt_id: str
    wallet_id: str
    query_hash: str
    cost_usd: float
    tokens_deducted: int
    remaining_balance_usd: float
    remaining_tokens: int
    timestamp: int
    signature: str
    pricing_tier: str = "printing_prices_$0.05"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class VendingMachinePaywall:
    """Manages client stablecoin wallets, token minting, $0.05 per-query metering, and HMAC-SHA256 receipts."""

    def __init__(
        self,
        price_per_query_usd: float = DEFAULT_PRICE_PER_QUERY_USD,
        secret_key: str = "vault-graphrag-vending-secret-key-2026",
    ) -> None:
        if price_per_query_usd <= 0:
            raise ValueError("price_per_query_usd must be positive")
        self.price_per_query_usd = round(price_per_query_usd, 4)
        self._secret_key = secret_key.encode("utf-8")
        self.wallets: Dict[str, WalletAccount] = {}
        self.receipts: List[QueryReceipt] = []

    def _compute_signature(
        self,
        receipt_id: str,
        wallet_id: str,
        query_hash: str,
        cost_usd: float,
        remaining_balance_usd: float,
        timestamp: int,
    ) -> str:
        payload = (
            f"{receipt_id}:{wallet_id}:{query_hash}:"
            f"{cost_usd:.4f}:{remaining_balance_usd:.4f}:{timestamp}"
        ).encode("utf-8")
        return hmac.new(self._secret_key, payload, hashlib.sha256).hexdigest()

    def mint_tokens(
        self, wallet_id: str, usd_amount: float, stablecoin: str = "USDC"
    ) -> Dict[str, Any]:
        """Mint query tokens into `wallet_id` from a stablecoin deposit (`$0.05` = 1 query token)."""
        if usd_amount <= 0:
            raise ValueError("usd_amount must be greater than 0")

        wallet = self.wallets.get(wallet_id)
        if wallet is None:
            wallet = WalletAccount(wallet_id=wallet_id, stablecoin=stablecoin)
            self.wallets[wallet_id] = wallet

        new_balance = round(wallet.balance_usd + usd_amount, 4)
        wallet.balance_usd = new_balance
        wallet.total_minted_usd = round(wallet.total_minted_usd + usd_amount, 4)
        wallet.tokens_balance = int(
            round(wallet.balance_usd / self.price_per_query_usd)
        )
        wallet.stablecoin = stablecoin

        minted_tokens = int(round(usd_amount / self.price_per_query_usd))
        return {
            "wallet_id": wallet.wallet_id,
            "stablecoin": wallet.stablecoin,
            "deposited_usd": round(usd_amount, 4),
            "minted_tokens": minted_tokens,
            "price_per_query_usd": self.price_per_query_usd,
            "balance_usd": wallet.balance_usd,
            "tokens_balance": wallet.tokens_balance,
        }

    def get_wallet(self, wallet_id: str) -> Dict[str, Any]:
        """Return wallet details or an empty uninitialized wallet representation."""
        wallet = self.wallets.get(wallet_id)
        if wallet is None:
            return WalletAccount(wallet_id=wallet_id).to_dict()
        return wallet.to_dict()

    def meter_query(
        self,
        wallet_id: str,
        query_text: str,
        cost_usd: Optional[float] = None,
    ) -> QueryReceipt:
        """Deduct `$0.05` (or custom `cost_usd`) from `wallet_id` and return a signed `QueryReceipt`."""
        charge = round(
            cost_usd if cost_usd is not None else self.price_per_query_usd, 4
        )
        wallet = self.wallets.get(wallet_id)
        if wallet is None or round(wallet.balance_usd, 4) < charge:
            available = 0.0 if wallet is None else wallet.balance_usd
            raise InsufficientBalanceError(
                f"Wallet '{wallet_id}' has insufficient balance (${available:.2f} USD) "
                f"for query cost ${charge:.2f} USD ('printing prices'). Please mint tokens."
            )

        wallet.balance_usd = round(wallet.balance_usd - charge, 4)
        tokens_deducted = max(1, int(round(charge / self.price_per_query_usd)))
        wallet.tokens_balance = int(
            round(wallet.balance_usd / self.price_per_query_usd)
        )
        wallet.queries_executed += 1

        receipt_id = f"rcpt-{uuid.uuid4().hex[:12]}"
        query_hash = hashlib.sha256(query_text.encode("utf-8")).hexdigest()
        timestamp = int(time.time())

        signature = self._compute_signature(
            receipt_id=receipt_id,
            wallet_id=wallet_id,
            query_hash=query_hash,
            cost_usd=charge,
            remaining_balance_usd=wallet.balance_usd,
            timestamp=timestamp,
        )

        receipt = QueryReceipt(
            receipt_id=receipt_id,
            wallet_id=wallet_id,
            query_hash=query_hash,
            cost_usd=charge,
            tokens_deducted=tokens_deducted,
            remaining_balance_usd=wallet.balance_usd,
            remaining_tokens=wallet.tokens_balance,
            timestamp=timestamp,
            signature=signature,
        )
        self.receipts.append(receipt)
        return receipt

    def verify_receipt(self, receipt: QueryReceipt | Dict[str, Any]) -> bool:
        """Verify the HMAC-SHA256 cryptographic signature of a QueryReceipt."""
        data = receipt.to_dict() if isinstance(receipt, QueryReceipt) else receipt
        expected = self._compute_signature(
            receipt_id=str(data["receipt_id"]),
            wallet_id=str(data["wallet_id"]),
            query_hash=str(data["query_hash"]),
            cost_usd=float(data["cost_usd"]),
            remaining_balance_usd=float(data["remaining_balance_usd"]),
            timestamp=int(data["timestamp"]),
        )
        return hmac.compare_digest(expected, str(data["signature"]))
