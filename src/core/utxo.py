"""
Bitcoin UTXO (Unspent Transaction Output) Set management.

The UTXO set is one of the most critical data structures in Bitcoin. It
represents the current state of all spendable outputs -- every bitcoin
that exists and has not yet been spent. When a new transaction is validated,
the node checks that its inputs reference valid entries in the UTXO set.

This module provides:

- **UTXOEntry**: Metadata about a single unspent output, including its value,
  locking script, the block height where it was created, and whether it came
  from a coinbase transaction (which has special maturity rules).

- **UTXOSet**: An in-memory collection of all UTXOs, keyed by
  ``"txid:output_index"``. It supports adding/removing UTXOs as blocks are
  connected or disconnected, querying balances for addresses, and deep-copying
  for fork handling.
"""

from __future__ import annotations

import copy
from typing import Optional

from src.core.transaction import TransactionOutput


# ---------------------------------------------------------------------------
# UTXOEntry
# ---------------------------------------------------------------------------

class UTXOEntry:
    """
    Metadata for a single unspent transaction output.

    Each UTXO entry records everything needed to validate and spend the
    output later: its value, the locking script that must be satisfied,
    the block height where it was confirmed, and whether it originated
    from a coinbase transaction.

    Coinbase outputs have a special maturity rule: they cannot be spent
    until 100 blocks have been mined on top of the block that created them.

    Attributes:
        value: Amount in satoshis.
        pubkey_script: Hex-encoded locking script / public key hash.
        block_height: Block height where this UTXO was created.
        is_coinbase: Whether this UTXO comes from a coinbase transaction.
    """

    def __init__(
        self,
        value: int,
        pubkey_script: str,
        block_height: int,
        is_coinbase: bool = False,
    ):
        """
        Initialize a UTXO entry.

        Args:
            value: Amount in satoshis.
            pubkey_script: Hex-encoded locking script.
            block_height: Height of the block containing this output.
            is_coinbase: True if from a coinbase transaction.
        """
        self.value = value
        self.pubkey_script = pubkey_script
        self.block_height = block_height
        self.is_coinbase = is_coinbase

    def to_dict(self) -> dict:
        """
        Convert this entry to a JSON-serializable dictionary.

        Returns:
            Dictionary with all UTXO entry fields.
        """
        return {
            'value': self.value,
            'pubkey_script': self.pubkey_script,
            'block_height': self.block_height,
            'is_coinbase': self.is_coinbase,
        }

    @classmethod
    def from_dict(cls, data: dict) -> UTXOEntry:
        """
        Reconstruct a UTXOEntry from a dictionary.

        Args:
            data: Dictionary as produced by ``to_dict()``.

        Returns:
            A new UTXOEntry instance.
        """
        return cls(
            value=data['value'],
            pubkey_script=data['pubkey_script'],
            block_height=data['block_height'],
            is_coinbase=data.get('is_coinbase', False),
        )

    def __repr__(self) -> str:
        return (
            f"UTXOEntry(value={self.value}, "
            f"height={self.block_height}, "
            f"coinbase={self.is_coinbase})"
        )

    def __eq__(self, other) -> bool:
        if not isinstance(other, UTXOEntry):
            return NotImplemented
        return (
            self.value == other.value
            and self.pubkey_script == other.pubkey_script
            and self.block_height == other.block_height
            and self.is_coinbase == other.is_coinbase
        )


# ---------------------------------------------------------------------------
# UTXOSet
# ---------------------------------------------------------------------------

class UTXOSet:
    """
    In-memory set of all unspent transaction outputs.

    The UTXO set is the authoritative record of which outputs are available
    to be spent. It is updated every time a block is connected (outputs are
    added, spent inputs are removed) or disconnected during a chain
    reorganization (the reverse operations).

    UTXOs are keyed by ``"txid:output_index"`` for O(1) lookup.

    Attributes:
        _utxos: Internal dictionary mapping ``"txid:index"`` to UTXOEntry.
    """

    def __init__(self):
        """Initialize an empty UTXO set."""
        self._utxos: dict[str, UTXOEntry] = {}

    @staticmethod
    def _make_key(txid: str, index: int) -> str:
        """
        Create the dictionary key for a UTXO.

        Args:
            txid: Transaction ID (hex string).
            index: Output index within the transaction.

        Returns:
            Key string in the format ``"txid:index"``.
        """
        return f"{txid}:{index}"

    def add_utxo(
        self,
        txid: str,
        index: int,
        output: TransactionOutput,
        height: int,
        is_coinbase: bool = False,
    ):
        """
        Add a new unspent output to the set.

        Called when processing a new block's transactions -- each output
        that is created becomes a potential UTXO.

        Args:
            txid: Transaction ID that created this output.
            index: Output index within the transaction.
            output: The TransactionOutput object.
            height: Block height where this output was confirmed.
            is_coinbase: Whether this output is from a coinbase transaction.
        """
        key = self._make_key(txid, index)
        self._utxos[key] = UTXOEntry(
            value=output.value,
            pubkey_script=output.pubkey_script,
            block_height=height,
            is_coinbase=is_coinbase,
        )

    def remove_utxo(self, txid: str, index: int) -> UTXOEntry:
        """
        Remove and return a UTXO from the set.

        Called when an input spends an existing output. The UTXO is removed
        because it is no longer unspent.

        Args:
            txid: Transaction ID of the output to remove.
            index: Output index within the transaction.

        Returns:
            The removed UTXOEntry.

        Raises:
            KeyError: If the specified UTXO does not exist in the set.
        """
        key = self._make_key(txid, index)
        if key not in self._utxos:
            raise KeyError(
                f"UTXO not found: {txid}:{index}"
            )
        return self._utxos.pop(key)

    def get_utxo(self, txid: str, index: int) -> Optional[UTXOEntry]:
        """
        Look up a UTXO without removing it.

        Args:
            txid: Transaction ID.
            index: Output index.

        Returns:
            The UTXOEntry if it exists, otherwise None.
        """
        key = self._make_key(txid, index)
        return self._utxos.get(key)

    def has_utxo(self, txid: str, index: int) -> bool:
        """
        Check whether a UTXO exists in the set.

        Args:
            txid: Transaction ID.
            index: Output index.

        Returns:
            True if the UTXO exists.
        """
        key = self._make_key(txid, index)
        return key in self._utxos

    def get_utxos_for_address(self, address: str) -> list:
        """
        Find all UTXOs belonging to a given address.

        In this simplified implementation, address matching is done by
        comparing the ``pubkey_script`` field of each UTXO entry against
        the provided address string. In a full Bitcoin implementation, the
        address would be decoded and matched against the script pattern.

        Args:
            address: The address (pubkey_script hex) to search for.

        Returns:
            A list of (txid, output_index, UTXOEntry) tuples for all
            matching UTXOs.
        """
        results = []
        for key, entry in self._utxos.items():
            if entry.pubkey_script == address:
                # Parse the key back to txid and index
                txid, index_str = key.rsplit(':', 1)
                results.append((txid, int(index_str), entry))
        return results

    def get_balance(self, address: str) -> int:
        """
        Calculate the total balance for an address.

        Sums the values of all UTXOs whose pubkey_script matches the
        given address.

        Args:
            address: The address (pubkey_script hex) to query.

        Returns:
            Total balance in satoshis.
        """
        utxos = self.get_utxos_for_address(address)
        return sum(entry.value for _, _, entry in utxos)

    def get_all_utxos(self) -> dict:
        """
        Return the entire UTXO set.

        Returns:
            A dictionary mapping ``"txid:index"`` keys to UTXOEntry objects.
            Note: this returns the internal dictionary directly for efficiency;
            callers should not modify it.
        """
        return dict(self._utxos)

    def size(self) -> int:
        """
        Return the number of UTXOs in the set.

        Returns:
            The count of unspent outputs.
        """
        return len(self._utxos)

    def to_dict(self) -> dict:
        """
        Convert the entire UTXO set to a JSON-serializable dictionary.

        Returns:
            Dictionary with a 'utxos' key mapping to a dict of entries.
        """
        return {
            'utxos': {
                key: entry.to_dict()
                for key, entry in self._utxos.items()
            }
        }

    @classmethod
    def from_dict(cls, data: dict) -> UTXOSet:
        """
        Reconstruct a UTXOSet from a dictionary.

        Args:
            data: Dictionary as produced by ``to_dict()``.

        Returns:
            A new UTXOSet instance with all entries restored.
        """
        utxo_set = cls()
        for key, entry_data in data['utxos'].items():
            utxo_set._utxos[key] = UTXOEntry.from_dict(entry_data)
        return utxo_set

    def copy(self) -> UTXOSet:
        """
        Create a deep copy of this UTXO set.

        This is essential for fork handling: when the blockchain needs to
        evaluate a competing chain, it creates a copy of the UTXO set and
        applies the alternative blocks to it without affecting the main set.

        Returns:
            A new UTXOSet with independent copies of all entries.
        """
        new_set = UTXOSet()
        new_set._utxos = copy.deepcopy(self._utxos)
        return new_set

    def __repr__(self) -> str:
        return f"UTXOSet(size={self.size()})"

    def __len__(self) -> int:
        return self.size()
