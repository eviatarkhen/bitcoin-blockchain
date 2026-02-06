"""
Bitcoin Transaction Memory Pool (Mempool)
==========================================

The mempool (memory pool) is a holding area for unconfirmed transactions that
have been broadcast to the network but not yet included in a block. Every full
node maintains its own mempool.

Key concepts:

- **Transaction Relay**: When a node receives a valid transaction, it adds it
  to its mempool and relays it to connected peers. This is how transactions
  propagate across the network before being mined.

- **Fee-based Prioritization**: Miners select transactions from the mempool to
  include in blocks. Transactions with higher fee rates (satoshis per byte)
  are typically selected first, since miners are economically incentivized to
  maximize the total fees collected in each block.

- **Double-Spend Prevention**: The mempool rejects transactions that attempt
  to spend the same UTXO as an already-accepted mempool transaction. This is
  a first-seen policy -- the first valid transaction spending a particular
  output is accepted, and subsequent conflicting transactions are rejected.

- **Eviction**: In a real Bitcoin node, when the mempool grows beyond a
  configured size limit, the lowest fee-rate transactions are evicted. This
  implementation does not enforce a size limit but maintains the fee-rate
  ordering needed for such a policy.

This module implements a simplified mempool suitable for educational purposes
and local blockchain simulation.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.core.transaction import Transaction
    from src.core.utxo import UTXOSet
    from src.core.block import Block

logger = logging.getLogger(__name__)


class Mempool:
    """
    Transaction memory pool -- a staging area for unconfirmed transactions.

    The mempool holds transactions that have been validated and accepted but
    are not yet included in a block. It provides fee-rate-based ordering so
    that miners can select the most profitable transactions first.

    Attributes:
        transactions: Mapping from txid (hex string) to Transaction objects.
        _fee_index: List of (fee_rate, txid) tuples kept in descending
            fee-rate order for efficient retrieval of highest-fee transactions.
    """

    def __init__(self) -> None:
        """Initialize an empty mempool."""
        self.transactions: dict[str, Transaction] = {}
        self._fee_index: list[tuple[float, str]] = []

    def add_transaction(self, tx: "Transaction", utxo_set: "UTXOSet | None" = None) -> bool:
        """
        Attempt to add a transaction to the mempool.

        The transaction is accepted only if:
        1. It is not already in the mempool (no duplicate txids).
        2. It is not a coinbase transaction (coinbase txs are created by miners
           and appear only as the first transaction in a block).
        3. It does not double-spend any UTXO already consumed by another
           mempool transaction.

        If accepted, the transaction is inserted into both the transactions
        dict and the fee-rate index.

        Args:
            tx: The transaction to add.
            utxo_set: Optional UTXO set used to calculate the fee rate.
                      If not provided, the fee rate defaults to 0.

        Returns:
            True if the transaction was accepted, False otherwise.
        """
        txid = tx.txid

        # Reject if already in the mempool
        if txid in self.transactions:
            logger.debug("Transaction %s already in mempool", txid[:16])
            return False

        # Reject coinbase transactions -- they belong only in blocks
        if tx.is_coinbase():
            logger.debug("Rejecting coinbase transaction %s from mempool", txid[:16])
            return False

        # Reject double-spends against existing mempool transactions
        if self.is_double_spend(tx):
            logger.warning("Rejecting double-spend transaction %s", txid[:16])
            return False

        # Calculate fee rate for prioritization
        fee_rate = self._calculate_fee_rate(tx, utxo_set)

        # Add to the pool
        self.transactions[txid] = tx

        # Insert into the fee index maintaining descending order
        self._fee_index.append((fee_rate, txid))
        self._fee_index.sort(key=lambda entry: entry[0], reverse=True)

        logger.info("Added transaction %s to mempool (fee_rate=%.2f sat/byte)", txid[:16], fee_rate)
        return True

    def remove_transaction(self, txid: str) -> "Transaction | None":
        """
        Remove a transaction from the mempool by its txid.

        Args:
            txid: The transaction ID (hex string) to remove.

        Returns:
            The removed Transaction object, or None if not found.
        """
        tx = self.transactions.pop(txid, None)
        if tx is not None:
            self._fee_index = [(rate, tid) for rate, tid in self._fee_index if tid != txid]
            logger.debug("Removed transaction %s from mempool", txid[:16])
        return tx

    def get_transactions(self, limit: int | None = None) -> list["Transaction"]:
        """
        Retrieve transactions ordered by fee rate (highest first).

        This is the primary interface used by the mining module to select
        transactions for inclusion in a new block.

        Args:
            limit: Maximum number of transactions to return.  If None, all
                   transactions in the mempool are returned.

        Returns:
            List of Transaction objects sorted by descending fee rate.
        """
        ordered_txids = [txid for _, txid in self._fee_index]
        if limit is not None:
            ordered_txids = ordered_txids[:limit]
        return [self.transactions[txid] for txid in ordered_txids if txid in self.transactions]

    def get_transaction(self, txid: str) -> "Transaction | None":
        """
        Look up a single transaction by txid.

        Args:
            txid: The transaction ID (hex string).

        Returns:
            The Transaction if found, otherwise None.
        """
        return self.transactions.get(txid)

    def clear_confirmed(self, block: "Block") -> int:
        """
        Remove all transactions that were confirmed in a block.

        When a new block is added to the blockchain, any of its transactions
        that were sitting in the mempool should be removed since they are now
        confirmed on-chain.

        Args:
            block: The newly confirmed block.

        Returns:
            The number of transactions removed from the mempool.
        """
        removed_count = 0
        for tx in block.transactions:
            if tx.is_coinbase():
                continue
            if self.remove_transaction(tx.txid) is not None:
                removed_count += 1
        logger.info("Cleared %d confirmed transactions from mempool", removed_count)
        return removed_count

    def is_double_spend(self, tx: "Transaction") -> bool:
        """
        Check whether any input in *tx* spends the same UTXO as an existing
        mempool transaction.

        In Bitcoin, each UTXO can only be spent once. If two unconfirmed
        transactions try to spend the same UTXO, only the first one accepted
        into the mempool is considered valid (first-seen rule).

        Args:
            tx: The candidate transaction to check.

        Returns:
            True if a double-spend conflict is detected, False otherwise.
        """
        # Build a set of (prev_txid, prev_output_index) for all inputs in the
        # existing mempool transactions.
        spent_outputs: set[tuple[str, int]] = set()
        for existing_tx in self.transactions.values():
            for inp in existing_tx.inputs:
                if not inp.is_coinbase():
                    spent_outputs.add((inp.previous_txid, inp.previous_output_index))

        # Check if any input in the candidate tx conflicts
        for inp in tx.inputs:
            if not inp.is_coinbase():
                if (inp.previous_txid, inp.previous_output_index) in spent_outputs:
                    return True
        return False

    @property
    def size(self) -> int:
        """Return the number of transactions currently in the mempool."""
        return len(self.transactions)

    def _calculate_fee_rate(self, tx: "Transaction", utxo_set: "UTXOSet | None" = None) -> float:
        """
        Calculate the fee rate for a transaction in satoshis per byte.

        fee_rate = (sum_of_input_values - sum_of_output_values) / tx_size_bytes

        If the UTXO set is not available (or any input cannot be resolved),
        the fee rate defaults to 0.

        Args:
            tx: The transaction to evaluate.
            utxo_set: The UTXO set used to look up input values.

        Returns:
            The fee rate as a float (satoshis per byte), or 0.0 if it
            cannot be calculated.
        """
        if utxo_set is None:
            return 0.0

        try:
            total_input_value = 0
            for inp in tx.inputs:
                if inp.is_coinbase():
                    return 0.0
                utxo = utxo_set.get_utxo(inp.previous_txid, inp.previous_output_index)
                if utxo is None:
                    return 0.0
                total_input_value += utxo.value

            total_output_value = sum(out.value for out in tx.outputs)
            fee = total_input_value - total_output_value
            if fee < 0:
                return 0.0

            tx_size = len(tx.serialize())
            if tx_size == 0:
                return 0.0

            return fee / tx_size
        except Exception:
            return 0.0

    def to_dict(self) -> dict:
        """
        Serialize the mempool state to a JSON-compatible dictionary.

        Returns:
            Dictionary with 'transactions' and 'fee_index' keys.
        """
        return {
            "transactions": {txid: tx.to_dict() for txid, tx in self.transactions.items()},
            "fee_index": self._fee_index,
        }

    def __repr__(self) -> str:
        return f"Mempool(size={self.size})"
