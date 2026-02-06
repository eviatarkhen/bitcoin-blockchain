"""
Tests for Transaction, TransactionInput, TransactionOutput (Task 12.2)
=======================================================================

Tests cover:
- Transaction creation and field access
- Coinbase transaction creation and identification
- Transaction serialization and deserialization
- Transaction ID (txid) computation
- TransactionOutput and TransactionInput to_dict/from_dict
"""

import sys

sys.path.insert(0, "/home/user/bitcoin-blockchain")

import pytest

from src.core.transaction import Transaction, TransactionInput, TransactionOutput


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_output():
    """A simple transaction output."""
    return TransactionOutput(value=50_00000000, pubkey_script="aa" * 20)


@pytest.fixture
def sample_input():
    """A simple transaction input."""
    return TransactionInput(
        previous_txid="bb" * 32,
        previous_output_index=0,
        signature_script="cc" * 36,
        sequence=0xffffffff,
    )


@pytest.fixture
def coinbase_input():
    """A coinbase transaction input."""
    return TransactionInput(
        previous_txid="0" * 64,
        previous_output_index=0xffffffff,
        signature_script="04" + "01" * 8,
        sequence=0xffffffff,
    )


@pytest.fixture
def coinbase_tx():
    """A coinbase transaction created via the factory method."""
    return Transaction.create_coinbase(
        block_height=1,
        reward_address="aa" * 20,
        reward_amount=50_00000000,
    )


@pytest.fixture
def regular_tx(sample_input, sample_output):
    """A regular (non-coinbase) transaction."""
    return Transaction(
        version=1,
        inputs=[sample_input],
        outputs=[sample_output],
        locktime=0,
    )


# ---------------------------------------------------------------------------
# TransactionOutput Tests
# ---------------------------------------------------------------------------

class TestTransactionOutput:
    """Tests for TransactionOutput."""

    def test_creation(self, sample_output):
        """Output should store value and pubkey_script."""
        assert sample_output.value == 50_00000000
        assert sample_output.pubkey_script == "aa" * 20

    def test_to_dict(self, sample_output):
        """to_dict should return a dictionary with value and pubkey_script."""
        d = sample_output.to_dict()
        assert d["value"] == 50_00000000
        assert d["pubkey_script"] == "aa" * 20

    def test_from_dict(self, sample_output):
        """from_dict should reconstruct the output."""
        d = sample_output.to_dict()
        restored = TransactionOutput.from_dict(d)
        assert restored.value == sample_output.value
        assert restored.pubkey_script == sample_output.pubkey_script

    def test_serialize_deserialize(self, sample_output):
        """Serialization/deserialization roundtrip should preserve data."""
        data = sample_output.serialize()
        restored, consumed = TransactionOutput.deserialize(data)
        assert restored.value == sample_output.value
        assert restored.pubkey_script == sample_output.pubkey_script

    def test_is_dust(self):
        """Outputs below 546 satoshis should be considered dust."""
        dust = TransactionOutput(value=100, pubkey_script="aa" * 20)
        not_dust = TransactionOutput(value=1000, pubkey_script="aa" * 20)
        assert dust.is_dust() is True
        assert not_dust.is_dust() is False


# ---------------------------------------------------------------------------
# TransactionInput Tests
# ---------------------------------------------------------------------------

class TestTransactionInput:
    """Tests for TransactionInput."""

    def test_creation(self, sample_input):
        """Input should store all fields correctly."""
        assert sample_input.previous_txid == "bb" * 32
        assert sample_input.previous_output_index == 0
        assert sample_input.sequence == 0xffffffff

    def test_is_coinbase_regular(self, sample_input):
        """Regular inputs should not be identified as coinbase."""
        assert sample_input.is_coinbase() is False

    def test_is_coinbase_true(self, coinbase_input):
        """Coinbase inputs should be identified correctly."""
        assert coinbase_input.is_coinbase() is True

    def test_to_dict(self, sample_input):
        """to_dict should include all fields."""
        d = sample_input.to_dict()
        assert "previous_txid" in d
        assert "previous_output_index" in d
        assert "signature_script" in d
        assert "sequence" in d

    def test_from_dict(self, sample_input):
        """from_dict should reconstruct the input."""
        d = sample_input.to_dict()
        restored = TransactionInput.from_dict(d)
        assert restored.previous_txid == sample_input.previous_txid
        assert restored.previous_output_index == sample_input.previous_output_index

    def test_serialize_deserialize(self, sample_input):
        """Serialization/deserialization roundtrip should preserve data."""
        data = sample_input.serialize()
        restored, consumed = TransactionInput.deserialize(data)
        assert restored.previous_txid == sample_input.previous_txid
        assert restored.previous_output_index == sample_input.previous_output_index
        assert restored.sequence == sample_input.sequence


# ---------------------------------------------------------------------------
# Transaction Tests
# ---------------------------------------------------------------------------

class TestTransaction:
    """Tests for Transaction."""

    def test_coinbase_creation(self, coinbase_tx):
        """create_coinbase should produce a valid coinbase transaction."""
        assert coinbase_tx.is_coinbase() is True
        assert len(coinbase_tx.inputs) == 1
        assert len(coinbase_tx.outputs) == 1
        assert coinbase_tx.outputs[0].value == 50_00000000

    def test_txid_is_64_hex(self, coinbase_tx):
        """Transaction ID should be a 64-character hex string."""
        txid = coinbase_tx.txid
        assert len(txid) == 64
        assert all(c in "0123456789abcdef" for c in txid)

    def test_txid_is_deterministic(self, coinbase_tx):
        """Same transaction should always produce the same txid."""
        txid1 = coinbase_tx.txid
        txid2 = coinbase_tx.calculate_txid()
        assert txid1 == txid2

    def test_different_transactions_different_txids(self):
        """Different transactions should have different txids."""
        tx1 = Transaction.create_coinbase(1, "aa" * 20, 50_00000000)
        tx2 = Transaction.create_coinbase(2, "aa" * 20, 50_00000000)
        assert tx1.txid != tx2.txid

    def test_is_coinbase_false_for_regular(self, regular_tx):
        """Regular transactions should not be identified as coinbase."""
        assert regular_tx.is_coinbase() is False

    def test_serialize_produces_bytes(self, coinbase_tx):
        """Serialization should produce non-empty bytes."""
        data = coinbase_tx.serialize()
        assert isinstance(data, bytes)
        assert len(data) > 0

    def test_serialize_deserialize_roundtrip(self, coinbase_tx):
        """Serialization/deserialization should preserve the transaction."""
        data = coinbase_tx.serialize()
        restored, consumed = Transaction.deserialize(data)
        assert restored.version == coinbase_tx.version
        assert len(restored.inputs) == len(coinbase_tx.inputs)
        assert len(restored.outputs) == len(coinbase_tx.outputs)
        assert restored.outputs[0].value == coinbase_tx.outputs[0].value

    def test_to_dict(self, coinbase_tx):
        """to_dict should contain all required fields."""
        d = coinbase_tx.to_dict()
        assert "version" in d
        assert "txid" in d
        assert "inputs" in d
        assert "outputs" in d
        assert "locktime" in d

    def test_from_dict_roundtrip(self, coinbase_tx):
        """from_dict(to_dict()) should produce an equivalent transaction."""
        d = coinbase_tx.to_dict()
        restored = Transaction.from_dict(d)
        assert restored.txid == coinbase_tx.txid
        assert restored.version == coinbase_tx.version

    def test_default_version(self):
        """Default version should be 1."""
        tx = Transaction()
        assert tx.version == 1

    def test_default_locktime(self):
        """Default locktime should be 0."""
        tx = Transaction()
        assert tx.locktime == 0

    def test_empty_transaction(self):
        """An empty transaction should have no inputs or outputs."""
        tx = Transaction()
        assert len(tx.inputs) == 0
        assert len(tx.outputs) == 0

    def test_coinbase_output_address(self, coinbase_tx):
        """Coinbase output pubkey_script should match the reward address."""
        assert coinbase_tx.outputs[0].pubkey_script == "aa" * 20
