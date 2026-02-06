"""
Tests for Block and BlockHeader (Task 12.1)
=============================================

Tests cover:
- BlockHeader serialization produces exactly 80 bytes
- Hash calculation produces a 64-character hex string
- Difficulty target checking
- Block merkle root calculation
- Block to_dict / from_dict round-tripping
- Block size calculation
"""

import sys
import time

sys.path.insert(0, "/home/user/bitcoin-blockchain")

import pytest

from src.core.block import Block, BlockHeader
from src.core.transaction import Transaction, TransactionInput, TransactionOutput


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def default_header():
    """A block header with default values."""
    return BlockHeader(
        version=1,
        previous_block_hash="0" * 64,
        merkle_root="ab" * 32,
        timestamp=1700000000,
        difficulty_bits=0x1f0fffff,
        nonce=0,
    )


@pytest.fixture
def coinbase_tx():
    """A simple coinbase transaction."""
    return Transaction.create_coinbase(
        block_height=1,
        reward_address="aa" * 20,
        reward_amount=50_00000000,
    )


@pytest.fixture
def sample_block(default_header, coinbase_tx):
    """A block with a header and one coinbase transaction."""
    block = Block(header=default_header, transactions=[coinbase_tx])
    block.header.merkle_root = block.calculate_merkle_root()
    block.header._hash = None
    return block


# ---------------------------------------------------------------------------
# BlockHeader Tests
# ---------------------------------------------------------------------------

class TestBlockHeader:
    """Tests for the BlockHeader class."""

    def test_serialize_produces_80_bytes(self, default_header):
        """Block header serialization must produce exactly 80 bytes."""
        serialized = default_header.serialize()
        assert len(serialized) == 80

    def test_hash_is_64_hex_chars(self, default_header):
        """Block hash should be a 64-character lowercase hex string."""
        block_hash = default_header.hash
        assert len(block_hash) == 64
        assert all(c in "0123456789abcdef" for c in block_hash)

    def test_hash_is_deterministic(self, default_header):
        """Same header should always produce the same hash."""
        hash1 = default_header.calculate_hash()
        hash2 = default_header.calculate_hash()
        assert hash1 == hash2

    def test_different_nonce_produces_different_hash(self):
        """Changing the nonce should change the hash."""
        h1 = BlockHeader(nonce=0, timestamp=1000, difficulty_bits=0x1f0fffff)
        h2 = BlockHeader(nonce=1, timestamp=1000, difficulty_bits=0x1f0fffff)
        assert h1.hash != h2.hash

    def test_different_timestamp_produces_different_hash(self):
        """Changing the timestamp should change the hash."""
        h1 = BlockHeader(timestamp=1000, difficulty_bits=0x1f0fffff)
        h2 = BlockHeader(timestamp=2000, difficulty_bits=0x1f0fffff)
        assert h1.hash != h2.hash

    def test_meets_difficulty_target_easy(self):
        """With very easy difficulty, almost any nonce should meet the target."""
        # 0x2100ffff is an extremely easy target
        header = BlockHeader(
            version=1,
            previous_block_hash="0" * 64,
            merkle_root="0" * 64,
            timestamp=1000,
            difficulty_bits=0x2100ffff,
            nonce=0,
        )
        # With such an easy target, it should almost certainly pass
        assert header.meets_difficulty_target() is True

    def test_get_target(self, default_header):
        """get_target should return a positive integer."""
        target = default_header.get_target()
        assert isinstance(target, int)
        assert target > 0

    def test_to_dict_contains_required_fields(self, default_header):
        """to_dict should include all header fields."""
        d = default_header.to_dict()
        assert "version" in d
        assert "previous_block_hash" in d
        assert "merkle_root" in d
        assert "timestamp" in d
        assert "difficulty_bits" in d
        assert "nonce" in d
        assert "hash" in d

    def test_from_dict_roundtrip(self, default_header):
        """from_dict(to_dict()) should produce an equivalent header."""
        d = default_header.to_dict()
        restored = BlockHeader.from_dict(d)
        assert restored.version == default_header.version
        assert restored.previous_block_hash == default_header.previous_block_hash
        assert restored.merkle_root == default_header.merkle_root
        assert restored.timestamp == default_header.timestamp
        assert restored.difficulty_bits == default_header.difficulty_bits
        assert restored.nonce == default_header.nonce

    def test_serialize_deserialize_roundtrip(self, default_header):
        """Serialization followed by deserialization should recover the header."""
        data = default_header.serialize()
        restored, consumed = BlockHeader.deserialize(data)
        assert consumed == 80
        assert restored.version == default_header.version
        assert restored.previous_block_hash == default_header.previous_block_hash
        assert restored.timestamp == default_header.timestamp
        assert restored.nonce == default_header.nonce

    def test_deserialize_insufficient_data(self):
        """Deserializing fewer than 80 bytes should raise ValueError."""
        with pytest.raises(ValueError):
            BlockHeader.deserialize(b"\x00" * 79)


# ---------------------------------------------------------------------------
# Block Tests
# ---------------------------------------------------------------------------

class TestBlock:
    """Tests for the Block class."""

    def test_merkle_root_single_transaction(self, coinbase_tx):
        """Merkle root of a single tx should be the tx's txid."""
        block = Block(transactions=[coinbase_tx])
        root = block.calculate_merkle_root()
        assert root == coinbase_tx.txid

    def test_merkle_root_no_transactions(self):
        """Merkle root with no transactions should be all zeros."""
        block = Block(transactions=[])
        root = block.calculate_merkle_root()
        assert root == "0" * 64

    def test_merkle_root_multiple_transactions(self, coinbase_tx):
        """Merkle root with multiple transactions should differ from single tx."""
        tx2 = Transaction.create_coinbase(
            block_height=2,
            reward_address="bb" * 20,
            reward_amount=50_00000000,
        )
        block1 = Block(transactions=[coinbase_tx])
        block2 = Block(transactions=[coinbase_tx, tx2])
        assert block1.calculate_merkle_root() != block2.calculate_merkle_root()

    def test_get_size(self, sample_block):
        """Block size should be positive and include header + transactions."""
        size = sample_block.get_size()
        assert size >= 80  # At minimum, the header

    def test_get_coinbase(self, sample_block, coinbase_tx):
        """get_coinbase should return the coinbase transaction."""
        cb = sample_block.get_coinbase()
        assert cb is not None
        assert cb.is_coinbase()

    def test_to_dict_from_dict_roundtrip(self, sample_block):
        """Block should survive a to_dict / from_dict round trip."""
        d = sample_block.to_dict()
        restored = Block.from_dict(d)
        assert restored.header.hash == sample_block.header.hash
        assert len(restored.transactions) == len(sample_block.transactions)

    def test_height_property(self, sample_block):
        """Block height should be gettable and settable."""
        sample_block._height = 42
        assert sample_block.height == 42

    def test_add_transaction(self, sample_block):
        """Adding a transaction should update the merkle root."""
        old_root = sample_block.header.merkle_root
        tx2 = Transaction.create_coinbase(
            block_height=2,
            reward_address="cc" * 20,
            reward_amount=25_00000000,
        )
        sample_block.add_transaction(tx2)
        assert sample_block.header.merkle_root != old_root
        assert len(sample_block.transactions) == 2

    def test_block_equality(self):
        """Two blocks with the same header hash should be equal."""
        h = BlockHeader(timestamp=12345, difficulty_bits=0x1f0fffff)
        b1 = Block(header=h)
        b2 = Block(header=h)
        assert b1 == b2
