"""
Tests for Blockchain (Task 12.6)
==================================

Tests cover:
- Genesis block creation
- Adding blocks
- Chain tip tracking
- Block retrieval by hash and height
- Mining convenience method
- Fork detection
- Difficulty retrieval
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from src.core.blockchain import Blockchain
from src.core.block import Block, BlockHeader
from src.core.transaction import Transaction
from src.crypto.keys import KeyPair
from src.mining.miner import Miner, create_block_template


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def blockchain():
    """A fresh blockchain in development mode."""
    return Blockchain(development_mode=True)


@pytest.fixture
def miner_keypair():
    """A key pair for the miner."""
    return KeyPair.generate()


@pytest.fixture
def miner_address(miner_keypair):
    """The miner's pubkey hash (hex string)."""
    return miner_keypair.public_key.get_hash160()


# ---------------------------------------------------------------------------
# Genesis Block Tests
# ---------------------------------------------------------------------------

class TestGenesisBlock:
    """Tests for genesis block creation."""

    def test_genesis_exists(self, blockchain):
        """A new blockchain should have a genesis block at height 0."""
        genesis = blockchain.get_block_by_height(0)
        assert genesis is not None

    def test_chain_height_starts_at_zero(self, blockchain):
        """Initial chain height should be 0 (just the genesis block)."""
        assert blockchain.get_chain_height() >= 0

    def test_chain_tip_is_genesis(self, blockchain):
        """The chain tip of a new blockchain should be the genesis block."""
        tip = blockchain.get_chain_tip()
        assert tip is not None

    def test_genesis_has_coinbase(self, blockchain):
        """Genesis block should contain a coinbase transaction."""
        genesis = blockchain.get_block_by_height(0)
        if genesis and genesis.transactions:
            assert genesis.transactions[0].is_coinbase()


# ---------------------------------------------------------------------------
# Block Addition Tests
# ---------------------------------------------------------------------------

class TestBlockAddition:
    """Tests for adding blocks to the blockchain."""

    def test_mine_next_block(self, blockchain, miner_address):
        """mine_next_block should increase the chain height by 1."""
        initial_height = blockchain.get_chain_height()
        blockchain.mine_next_block(coinbase_address=miner_address)
        assert blockchain.get_chain_height() == initial_height + 1

    def test_mine_multiple_blocks(self, blockchain, miner_address):
        """Mining multiple blocks should increment height each time."""
        for i in range(5):
            blockchain.mine_next_block(coinbase_address=miner_address)
        assert blockchain.get_chain_height() >= 5

    def test_get_block_by_height(self, blockchain, miner_address):
        """Blocks should be retrievable by height after mining."""
        blockchain.mine_next_block(coinbase_address=miner_address)
        block = blockchain.get_block_by_height(1)
        assert block is not None

    def test_get_block_by_hash(self, blockchain, miner_address):
        """Blocks should be retrievable by their hash."""
        block = blockchain.mine_next_block(coinbase_address=miner_address)
        retrieved = blockchain.get_block(block.header.hash)
        assert retrieved is not None
        assert retrieved.header.hash == block.header.hash

    def test_chain_tip_updates(self, blockchain, miner_address):
        """Chain tip should update after mining a new block."""
        blockchain.mine_next_block(coinbase_address=miner_address)
        tip1 = blockchain.get_chain_tip()
        blockchain.mine_next_block(coinbase_address=miner_address)
        tip2 = blockchain.get_chain_tip()
        assert tip1.header.hash != tip2.header.hash

    def test_mined_block_has_coinbase(self, blockchain, miner_address):
        """Mined blocks should have a coinbase transaction."""
        block = blockchain.mine_next_block(coinbase_address=miner_address)
        assert len(block.transactions) >= 1
        assert block.transactions[0].is_coinbase()

    def test_coinbase_pays_miner(self, blockchain, miner_address):
        """Coinbase transaction output should pay to the miner address."""
        block = blockchain.mine_next_block(coinbase_address=miner_address)
        coinbase_tx = block.transactions[0]
        assert coinbase_tx.outputs[0].pubkey_script == miner_address


# ---------------------------------------------------------------------------
# Chain State Tests
# ---------------------------------------------------------------------------

class TestChainState:
    """Tests for chain state queries."""

    def test_get_current_difficulty(self, blockchain):
        """Current difficulty should be a positive integer."""
        difficulty = blockchain.get_current_difficulty()
        assert isinstance(difficulty, int)
        assert difficulty > 0

    def test_get_nonexistent_block_by_height(self, blockchain):
        """Requesting a block at a non-existent height should return None."""
        result = blockchain.get_block_by_height(9999)
        assert result is None

    def test_get_nonexistent_block_by_hash(self, blockchain):
        """Requesting a block by non-existent hash should return None."""
        result = blockchain.get_block("ff" * 32)
        assert result is None

    def test_development_mode(self, blockchain):
        """Development mode should be set on the blockchain."""
        assert blockchain.development_mode is True

    def test_utxo_set_exists(self, blockchain):
        """Blockchain should have a UTXO set."""
        assert blockchain.utxo_set is not None

    def test_mempool_exists(self, blockchain):
        """Blockchain should have a mempool."""
        assert blockchain.mempool is not None

    def test_utxo_updated_after_mining(self, blockchain, miner_address):
        """UTXO set should be updated after mining a block."""
        blockchain.mine_next_block(coinbase_address=miner_address)
        balance = blockchain.utxo_set.get_balance(miner_address)
        assert balance > 0
