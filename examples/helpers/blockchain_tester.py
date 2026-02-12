"""
Blockchain Test Helper
=======================

Provides a BlockchainTester class for programmatically creating test scenarios
such as multi-block chains, forks, and fork resolution demonstrations.

This module is used by the example scripts and can also be used in tests
to quickly set up blockchain states without manually mining blocks.

Usage:
    from examples.helpers.blockchain_tester import BlockchainTester

    # Create a chain of 10 blocks with a miner wallet
    blockchain, wallet = BlockchainTester.create_chain(10)

    # Create a fork at height 5
    fork_blocks = BlockchainTester.create_fork(blockchain, fork_height=5)

    # Full fork resolution demonstration
    blockchain = BlockchainTester.demonstrate_fork_resolution()
"""

from __future__ import annotations

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.core.blockchain import Blockchain
from src.core.block import Block, BlockHeader
from src.core.transaction import Transaction
from src.wallet.wallet import Wallet
from src.mining.miner import Miner, create_block_template, compact_bits_to_target
from src.consensus.difficulty import get_block_reward


class BlockchainTester:
    """
    Helper class for programmatically creating blockchain test scenarios.

    All methods are static -- no instance state is needed. The class serves
    as a namespace for related helper functions.
    """

    @staticmethod
    def create_chain(
        num_blocks: int, development_mode: bool = True
    ) -> tuple[Blockchain, Wallet]:
        """
        Create a blockchain and mine a specified number of blocks.

        Sets up a fresh blockchain (which creates the genesis block
        automatically), generates a miner wallet with one address,
        and mines `num_blocks` additional blocks on top of genesis.

        Args:
            num_blocks: Number of blocks to mine after genesis.
            development_mode: If True, use instant mining (no PoW).

        Returns:
            A tuple of (blockchain, miner_wallet) where:
            - blockchain: The Blockchain instance with `num_blocks` + 1 blocks
              (genesis + mined blocks).
            - miner_wallet: A Wallet connected to the blockchain that received
              all block rewards.
        """
        blockchain = Blockchain(development_mode=development_mode)
        wallet = Wallet(blockchain=blockchain, name="miner")
        address = wallet.generate_address()
        pubkey_hash = wallet.get_keypair(address).public_key.get_hash160()

        for _ in range(num_blocks):
            blockchain.mine_next_block(coinbase_address=pubkey_hash)

        return blockchain, wallet

    @staticmethod
    def create_fork(
        blockchain: Blockchain,
        fork_height: int,
        num_branches: int = 2,
        miner_wallets: list[Wallet] | None = None,
    ) -> list[Block]:
        """
        Create competing blocks at a given height to simulate a fork.

        A fork occurs when two or more miners find valid blocks at nearly
        the same time, each extending the same parent block. The network
        temporarily has multiple chain tips until one branch grows longer.

        This method creates `num_branches` competing blocks that all have
        the same parent (the block at `fork_height`).

        Args:
            blockchain: The blockchain to fork.
            fork_height: The height of the parent block. The competing
                         blocks will be at height `fork_height + 1`.
            num_branches: Number of competing blocks to create (default 2).
            miner_wallets: Optional list of wallets for each branch miner.
                          If None, temporary wallets are created.

        Returns:
            A list of Block objects representing the competing branch tips.
        """
        # Get the parent block at fork_height
        parent_block = blockchain.get_block_by_height(fork_height)
        if parent_block is None:
            raise ValueError(f"No block found at height {fork_height}")

        parent_hash = parent_block.header.hash
        new_height = fork_height + 1
        # Use the difficulty from the existing block at this height (same
        # difficulty rules apply to fork blocks at the same height).
        existing = blockchain.get_block_by_height(new_height)
        if existing is not None:
            difficulty_bits = existing.header.difficulty_bits
        else:
            difficulty_bits = blockchain.get_current_difficulty()

        # Create wallets for miners if not provided
        if miner_wallets is None:
            miner_wallets = []
            for i in range(num_branches):
                w = Wallet(blockchain=blockchain, name=f"fork_miner_{i}")
                w.generate_address()
                miner_wallets.append(w)

        miner = Miner(instant_mine=False)
        competing_blocks = []

        for i in range(num_branches):
            wallet = miner_wallets[i % len(miner_wallets)]
            address = wallet.get_addresses()[0]
            pubkey_hash = wallet.get_keypair(address).public_key.get_hash160()

            reward = get_block_reward(new_height)

            block = create_block_template(
                previous_block_hash=parent_hash,
                height=new_height,
                difficulty_bits=difficulty_bits,
                transactions=[],
                coinbase_address=pubkey_hash,
                reward_amount=reward,
                extra_nonce=i,  # Different extra_nonce ensures different block hashes
            )

            # Adjust timestamp slightly so each block has a unique hash
            block.header.timestamp = int(time.time()) + i
            block.header._hash = None  # Invalidate cached hash

            mined_block = miner.mine_block(block)
            competing_blocks.append(mined_block)

        return competing_blocks

    @staticmethod
    def demonstrate_fork_resolution(
        blockchain: Blockchain | None = None,
    ) -> Blockchain:
        """
        Demonstrate a full fork creation and resolution scenario.

        Steps:
        1. Create a blockchain with 10 blocks (or use the provided one).
        2. Create a fork at the chain tip (two competing blocks).
        3. Extend one branch with additional blocks so it becomes the
           longest chain.
        4. The blockchain should resolve the fork by following the
           longest chain.

        This models the real Bitcoin behavior where temporary forks are
        resolved by the "longest chain wins" rule (technically,
        "most cumulative proof-of-work" rule).

        Args:
            blockchain: Optional existing blockchain to fork. If None,
                        a fresh chain of 10 blocks is created.

        Returns:
            The blockchain after fork resolution.
        """
        if blockchain is None:
            blockchain, wallet = BlockchainTester.create_chain(10)
        else:
            wallet = Wallet(blockchain=blockchain, name="fork_demo_miner")
            wallet.generate_address()

        fork_height = blockchain.get_chain_height() - 1
        print(f"Chain height before fork: {blockchain.get_chain_height()}")
        print(f"Creating fork at height {fork_height}...")

        # Create two competing blocks
        fork_wallets = []
        for i in range(2):
            w = Wallet(blockchain=blockchain, name=f"branch_{i}_miner")
            w.generate_address()
            fork_wallets.append(w)

        competing_blocks = BlockchainTester.create_fork(
            blockchain, fork_height, num_branches=2, miner_wallets=fork_wallets
        )

        print(f"Created {len(competing_blocks)} competing blocks:")
        for i, block in enumerate(competing_blocks):
            print(f"  Branch {i}: hash={block.header.hash[:16]}...")

        # Add the first competing block to the blockchain
        try:
            blockchain.add_block(competing_blocks[0])
            print(f"Added branch 0 block to blockchain")
        except Exception as e:
            print(f"Branch 0 block result: {e}")

        # Try to add the second competing block (this creates the fork)
        try:
            blockchain.add_block(competing_blocks[1])
            print(f"Added branch 1 block to blockchain (fork created)")
        except Exception as e:
            print(f"Branch 1 block result: {e}")

        print(f"Chain height after fork: {blockchain.get_chain_height()}")

        # Extend the main branch to resolve the fork
        main_address = wallet.get_addresses()[0] if wallet.get_addresses() else fork_wallets[0].get_addresses()[0]
        main_pubkey_hash = wallet.get_keypair(main_address).public_key.get_hash160() if wallet.get_addresses() else fork_wallets[0].get_keypair(main_address).public_key.get_hash160()
        print("Mining additional blocks to resolve fork...")
        for i in range(3):
            try:
                blockchain.mine_next_block(coinbase_address=main_pubkey_hash)
                print(f"  Mined block at height {blockchain.get_chain_height()}")
            except Exception as e:
                print(f"  Mining block failed: {e}")

        print(f"Final chain height: {blockchain.get_chain_height()}")
        print(f"Chain tip: {blockchain.get_chain_tip().header.hash[:16]}...")

        return blockchain
