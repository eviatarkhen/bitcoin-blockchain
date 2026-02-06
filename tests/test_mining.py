"""
Tests for Mining (Task 12.4)
==============================

Tests cover:
- Miner finds a valid nonce
- Instant mining mode
- compact_bits_to_target conversion
- target_to_compact_bits conversion
- Block template creation
"""

import sys
import time

sys.path.insert(0, "/home/user/bitcoin-blockchain")

import pytest

from src.core.block import Block, BlockHeader
from src.core.transaction import Transaction
from src.mining.miner import (
    Miner,
    compact_bits_to_target,
    target_to_compact_bits,
    create_block_template,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def easy_block():
    """A block template with a very easy difficulty target."""
    coinbase_tx = Transaction.create_coinbase(
        block_height=1,
        reward_address="aa" * 20,
        reward_amount=50_00000000,
    )
    header = BlockHeader(
        version=1,
        previous_block_hash="0" * 64,
        merkle_root=coinbase_tx.txid,
        timestamp=int(time.time()),
        difficulty_bits=0x2100ffff,  # Very easy target
        nonce=0,
    )
    block = Block(header=header, transactions=[coinbase_tx])
    block._height = 1
    return block


@pytest.fixture
def instant_miner():
    """A miner in instant mine mode."""
    return Miner(instant_mine=True)


@pytest.fixture
def real_miner():
    """A miner with actual PoW (but we use easy difficulty)."""
    return Miner(instant_mine=False)


# ---------------------------------------------------------------------------
# Miner Tests
# ---------------------------------------------------------------------------

class TestMiner:
    """Tests for the Miner class."""

    def test_instant_mine(self, instant_miner, easy_block):
        """Instant mining should return immediately with nonce=0."""
        result = instant_miner.mine_block(easy_block)
        assert result is easy_block
        assert result.header.nonce == 0

    def test_real_mine_easy_target(self, real_miner, easy_block):
        """Mining with a very easy target should find a nonce quickly."""
        result = real_miner.mine_block(easy_block)
        assert result is easy_block
        # The hash should be a valid 64-char hex string
        assert len(result.header.hash) == 64

    def test_mined_block_meets_target(self, real_miner, easy_block):
        """A mined block should meet its difficulty target."""
        result = real_miner.mine_block(easy_block)
        target = compact_bits_to_target(result.header.difficulty_bits)
        hash_int = int(result.header.hash, 16)
        assert hash_int < target

    def test_hash_count_increases(self, real_miner, easy_block):
        """Mining should increment the hash counter."""
        initial_count = real_miner.hash_count
        real_miner.mine_block(easy_block)
        assert real_miner.hash_count >= initial_count

    def test_instant_mine_hash_count(self, instant_miner, easy_block):
        """Instant mining should not increment the hash counter."""
        initial_count = instant_miner.hash_count
        instant_miner.mine_block(easy_block)
        assert instant_miner.hash_count == initial_count

    def test_get_hashrate(self, real_miner):
        """get_hashrate should return a non-negative float."""
        real_miner.hash_count = 1000
        rate = real_miner.get_hashrate(1.0)
        assert rate == 1000.0

    def test_get_hashrate_zero_time(self, real_miner):
        """get_hashrate with zero elapsed time should return 0."""
        rate = real_miner.get_hashrate(0)
        assert rate == 0.0


# ---------------------------------------------------------------------------
# Compact Bits Conversion Tests
# ---------------------------------------------------------------------------

class TestCompactBits:
    """Tests for compact difficulty representation conversions."""

    def test_genesis_target(self):
        """Genesis block difficulty bits 0x1d00ffff should produce correct target."""
        target = compact_bits_to_target(0x1d00ffff)
        assert target > 0
        # The target should be a large number
        assert target.bit_length() > 200

    def test_easy_dev_target(self):
        """Development mode difficulty should produce a very large target."""
        target = compact_bits_to_target(0x1f0fffff)
        assert target > 0

    def test_round_trip(self):
        """Converting to target and back should give the same compact bits."""
        original_bits = 0x1d00ffff
        target = compact_bits_to_target(original_bits)
        recovered_bits = target_to_compact_bits(target)
        assert recovered_bits == original_bits

    def test_round_trip_dev(self):
        """Round trip for development difficulty."""
        original_bits = 0x1f0fffff
        target = compact_bits_to_target(original_bits)
        recovered_bits = target_to_compact_bits(target)
        assert recovered_bits == original_bits

    def test_invalid_bits(self):
        """Zero or negative bits should raise ValueError."""
        with pytest.raises(ValueError):
            compact_bits_to_target(0)
        with pytest.raises(ValueError):
            compact_bits_to_target(-1)

    def test_negative_target(self):
        """Negative target should raise ValueError."""
        with pytest.raises(ValueError):
            target_to_compact_bits(-1)

    def test_zero_target(self):
        """Zero target should return 0."""
        assert target_to_compact_bits(0) == 0

    def test_higher_difficulty_lower_target(self):
        """Higher difficulty bits exponent should mean lower target (harder)."""
        easy_target = compact_bits_to_target(0x1f0fffff)
        hard_target = compact_bits_to_target(0x1d00ffff)
        assert easy_target > hard_target


# ---------------------------------------------------------------------------
# Block Template Tests
# ---------------------------------------------------------------------------

class TestBlockTemplate:
    """Tests for create_block_template."""

    def test_creates_valid_block(self):
        """Block template should have correct structure."""
        block = create_block_template(
            previous_block_hash="0" * 64,
            height=1,
            difficulty_bits=0x1f0fffff,
            transactions=[],
            coinbase_address="aa" * 20,
            reward_amount=50_00000000,
        )
        assert isinstance(block, Block)
        assert block.header.version == 1
        assert block.header.previous_block_hash == "0" * 64
        assert block.header.difficulty_bits == 0x1f0fffff

    def test_includes_coinbase(self):
        """Block template should have a coinbase transaction."""
        block = create_block_template(
            previous_block_hash="0" * 64,
            height=1,
            difficulty_bits=0x1f0fffff,
            transactions=[],
            coinbase_address="aa" * 20,
            reward_amount=50_00000000,
        )
        assert len(block.transactions) >= 1
        assert block.transactions[0].is_coinbase()

    def test_merkle_root_is_set(self):
        """Block template should have a valid merkle root."""
        block = create_block_template(
            previous_block_hash="0" * 64,
            height=1,
            difficulty_bits=0x1f0fffff,
            transactions=[],
            coinbase_address="aa" * 20,
            reward_amount=50_00000000,
        )
        assert block.header.merkle_root != "0" * 64

    def test_includes_extra_transactions(self):
        """Block template should include provided extra transactions."""
        extra_tx = Transaction.create_coinbase(
            block_height=0,
            reward_address="bb" * 20,
            reward_amount=25_00000000,
        )
        block = create_block_template(
            previous_block_hash="0" * 64,
            height=1,
            difficulty_bits=0x1f0fffff,
            transactions=[extra_tx],
            coinbase_address="aa" * 20,
            reward_amount=50_00000000,
        )
        # Should have coinbase + the extra transaction
        assert len(block.transactions) == 2

    def test_height_is_set(self):
        """Block template should have the correct height set."""
        block = create_block_template(
            previous_block_hash="0" * 64,
            height=42,
            difficulty_bits=0x1f0fffff,
            transactions=[],
            coinbase_address="aa" * 20,
            reward_amount=50_00000000,
        )
        assert block._height == 42
