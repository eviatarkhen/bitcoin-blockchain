"""
Tests for UTXOSet and UTXOEntry (Task 12.2)
=============================================

Tests cover:
- Adding and removing UTXOs
- Getting UTXOs by txid and index
- Balance calculation for addresses
- Address-based UTXO lookups
- Copying the UTXO set
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from src.core.utxo import UTXOSet, UTXOEntry
from src.core.transaction import TransactionOutput


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def utxo_set():
    """A fresh empty UTXO set."""
    return UTXOSet()


@pytest.fixture
def sample_output():
    """A sample transaction output."""
    return TransactionOutput(value=50_00000000, pubkey_script="aa" * 20)


@pytest.fixture
def populated_utxo_set(utxo_set, sample_output):
    """A UTXO set with one entry."""
    txid = "ff" * 32
    utxo_set.add_utxo(txid, 0, sample_output, height=1, is_coinbase=True)
    return utxo_set


# ---------------------------------------------------------------------------
# UTXOSet Tests
# ---------------------------------------------------------------------------

class TestUTXOSet:
    """Tests for the UTXOSet class."""

    def test_add_utxo(self, utxo_set, sample_output):
        """Adding a UTXO should make it retrievable."""
        txid = "ff" * 32
        utxo_set.add_utxo(txid, 0, sample_output, height=1)
        assert utxo_set.has_utxo(txid, 0) is True

    def test_get_utxo(self, populated_utxo_set):
        """get_utxo should return the correct UTXOEntry."""
        txid = "ff" * 32
        entry = populated_utxo_set.get_utxo(txid, 0)
        assert entry is not None
        assert entry.value == 50_00000000
        assert entry.pubkey_script == "aa" * 20

    def test_get_utxo_nonexistent(self, utxo_set):
        """get_utxo for a nonexistent UTXO should return None."""
        result = utxo_set.get_utxo("00" * 32, 0)
        assert result is None

    def test_has_utxo_false(self, utxo_set):
        """has_utxo should return False for nonexistent UTXOs."""
        assert utxo_set.has_utxo("00" * 32, 0) is False

    def test_remove_utxo(self, populated_utxo_set):
        """Removing a UTXO should make it no longer retrievable."""
        txid = "ff" * 32
        removed = populated_utxo_set.remove_utxo(txid, 0)
        assert removed is not None
        assert populated_utxo_set.has_utxo(txid, 0) is False

    def test_get_balance(self, utxo_set, sample_output):
        """get_balance should sum all UTXOs for an address (pubkey hash)."""
        address = "aa" * 20
        txid1 = "ff" * 32
        txid2 = "ee" * 32
        out1 = TransactionOutput(value=100_000, pubkey_script=address)
        out2 = TransactionOutput(value=200_000, pubkey_script=address)
        utxo_set.add_utxo(txid1, 0, out1, height=1)
        utxo_set.add_utxo(txid2, 0, out2, height=2)
        balance = utxo_set.get_balance(address)
        assert balance == 300_000

    def test_get_balance_empty(self, utxo_set):
        """Balance for an address with no UTXOs should be 0."""
        assert utxo_set.get_balance("bb" * 20) == 0

    def test_get_utxos_for_address(self, utxo_set):
        """get_utxos_for_address should return all UTXOs for that address."""
        address = "cc" * 20
        txid1 = "ff" * 32
        txid2 = "ee" * 32
        out1 = TransactionOutput(value=100, pubkey_script=address)
        out2 = TransactionOutput(value=200, pubkey_script=address)
        utxo_set.add_utxo(txid1, 0, out1, height=1)
        utxo_set.add_utxo(txid2, 1, out2, height=2)

        utxos = utxo_set.get_utxos_for_address(address)
        assert len(utxos) == 2
        values = {entry.value for _, _, entry in utxos}
        assert values == {100, 200}

    def test_get_utxos_for_address_empty(self, utxo_set):
        """Address with no UTXOs should return empty list."""
        utxos = utxo_set.get_utxos_for_address("dd" * 20)
        assert utxos == []

    def test_copy(self, populated_utxo_set):
        """Copying the UTXO set should produce an independent copy."""
        copy = populated_utxo_set.copy()
        txid = "ff" * 32

        # Both should have the UTXO
        assert copy.has_utxo(txid, 0) is True

        # Removing from the copy should not affect the original
        copy.remove_utxo(txid, 0)
        assert copy.has_utxo(txid, 0) is False
        assert populated_utxo_set.has_utxo(txid, 0) is True

    def test_multiple_outputs_same_tx(self, utxo_set):
        """Multiple outputs from the same transaction should be tracked separately."""
        txid = "ff" * 32
        out0 = TransactionOutput(value=100, pubkey_script="aa" * 20)
        out1 = TransactionOutput(value=200, pubkey_script="bb" * 20)
        utxo_set.add_utxo(txid, 0, out0, height=1)
        utxo_set.add_utxo(txid, 1, out1, height=1)

        assert utxo_set.has_utxo(txid, 0) is True
        assert utxo_set.has_utxo(txid, 1) is True
        assert utxo_set.get_utxo(txid, 0).value == 100
        assert utxo_set.get_utxo(txid, 1).value == 200
