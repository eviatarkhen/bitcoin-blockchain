"""
Bitcoin Blockchain Management
==============================

This module implements the central Blockchain class that ties together all
components of the Bitcoin protocol: blocks, transactions, the UTXO set,
the mempool, consensus rules, mining, and difficulty adjustment.

The Blockchain class is the "coordinator" -- it is the single source of truth
for the state of the chain. It handles:

- **Genesis Block Creation** (Task 5.1): Every blockchain starts with a
  hardcoded genesis block. In Bitcoin, this was mined by Satoshi Nakamoto
  on January 3, 2009.

- **Block Storage and Indexing** (Task 5.2): Blocks are stored in a hash-map
  keyed by their block hash, with secondary indexes by height. This allows
  O(1) lookups by hash and efficient traversal by height.

- **Chain Tips and Best Chain** (Task 5.3): The blockchain is really a
  block-*tree*. Multiple branches (forks) can exist simultaneously.  The
  "best chain" is the one with the most cumulative proof-of-work (in this
  simplified implementation, the longest chain).

- **Validation** (Tasks 5.4, 5.5): Every block and transaction must pass
  consensus validation before being accepted.

- **Fork Detection and Chain Reorganization** (Tasks 5.6, 5.7): When a
  competing branch overtakes the current best chain, the node must "reorg":
  unwind the old branch (returning its transactions to the mempool and
  reverting its UTXO changes) and then apply the new branch.

- **JSON Export / Import** (Task 10.2): The entire blockchain state can be
  serialized to JSON for inspection, debugging, or persistence.

Development mode vs. production mode:
  In development mode, the difficulty is very low, blocks are mined
  almost instantly, and the difficulty adjustment interval is short (10
  blocks instead of 2016). This makes it practical to experiment with the
  blockchain locally.
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.core.block import Block, BlockHeader
    from src.core.transaction import Transaction

logger = logging.getLogger(__name__)


class Blockchain:
    """
    The Bitcoin blockchain -- a chain of blocks forming an append-only ledger.

    This class manages the entire lifecycle of the blockchain: creation of
    the genesis block, addition and validation of new blocks, fork detection
    and reorganization, UTXO set maintenance, and interaction with the
    transaction mempool.

    Attributes:
        blocks: Hash-map of all known blocks, keyed by block hash.
        block_height_index: Maps a block height to the list of block hashes
            at that height (there may be more than one during forks).
        chain_tips: List of block hashes that are currently chain tips
            (blocks with no known children).
        best_chain_tip: Hash of the tip of the longest (best) chain.
        utxo_set: The Unspent Transaction Output set for the best chain.
        mempool: The transaction memory pool.
        development_mode: Whether the chain operates with relaxed parameters
            suitable for local experimentation.
    """

    def __init__(self, development_mode: bool = True) -> None:
        """
        Initialize a new blockchain.

        Sets up empty data structures and creates the genesis block.

        Args:
            development_mode: If True, use low difficulty and short adjustment
                intervals.  If False, use real Bitcoin parameters.
        """
        from src.core.utxo import UTXOSet
        from src.core.mempool import Mempool

        self.blocks: dict[str, Block] = {}
        self.block_height_index: dict[int, list[str]] = {}
        self.chain_tips: list[str] = []
        self.best_chain_tip: str | None = None
        self.utxo_set: UTXOSet = UTXOSet()
        self.mempool: Mempool = Mempool()
        self.development_mode: bool = development_mode

        # Difficulty and timing parameters
        if development_mode:
            from src.consensus.difficulty import (
                DEV_GENESIS_DIFFICULTY_BITS,
                DEV_DIFFICULTY_ADJUSTMENT_INTERVAL,
                DEV_TARGET_BLOCK_TIME,
            )
            self._difficulty_bits: int = DEV_GENESIS_DIFFICULTY_BITS
            self._adjustment_interval: int = DEV_DIFFICULTY_ADJUSTMENT_INTERVAL
            self._target_block_time: int = DEV_TARGET_BLOCK_TIME
        else:
            from src.consensus.difficulty import (
                GENESIS_DIFFICULTY_BITS,
                DIFFICULTY_ADJUSTMENT_INTERVAL,
                TARGET_BLOCK_TIME,
            )
            self._difficulty_bits = GENESIS_DIFFICULTY_BITS
            self._adjustment_interval = DIFFICULTY_ADJUSTMENT_INTERVAL
            self._target_block_time = TARGET_BLOCK_TIME

        # The target timespan is the ideal total time for one adjustment interval
        self._target_timespan: int = self._adjustment_interval * self._target_block_time

        # Create the genesis block to bootstrap the chain
        self._create_genesis_block()

    # ------------------------------------------------------------------
    # Genesis block creation  (Task 5.1)
    # ------------------------------------------------------------------

    def _create_genesis_block(self) -> "Block":
        """
        Create and add the hardcoded genesis block.

        The genesis block is the very first block in the chain. It is
        hard-coded rather than mined because there is no previous block to
        reference. Bitcoin's real genesis block was created on 2009-01-03
        with the famous embedded message:

            "The Times 03/Jan/2009 Chancellor on brink of second bailout for banks"

        In development mode the proof-of-work requirement is relaxed (nonce=0
        is accepted) so that initialization is instantaneous.

        Returns:
            The genesis Block object.
        """
        from src.core.block import Block, BlockHeader
        from src.core.transaction import Transaction

        # Bitcoin genesis timestamp: January 3, 2009 18:15:05 UTC
        genesis_timestamp = 1231006505

        # Create coinbase transaction paying the genesis reward
        from src.consensus.difficulty import get_block_reward
        reward = get_block_reward(0)

        coinbase_tx = Transaction.create_coinbase(
            block_height=0,
            reward_address="0000000000000000000000000000000000000000",
            reward_amount=reward,
            extra_nonce=0,
        )

        # Compute the merkle root from the single coinbase transaction
        from src.crypto.merkle import compute_merkle_root
        merkle_root = compute_merkle_root([coinbase_tx.txid])

        # Build the genesis block header
        header = BlockHeader(
            version=1,
            previous_block_hash="0" * 64,
            merkle_root=merkle_root,
            timestamp=genesis_timestamp,
            difficulty_bits=self._difficulty_bits,
            nonce=0,
        )

        genesis_block = Block(header=header, transactions=[coinbase_tx])
        genesis_block._height = 0

        # Store the genesis block
        genesis_hash = genesis_block.header.hash
        self.blocks[genesis_hash] = genesis_block
        self.block_height_index[0] = [genesis_hash]
        self.chain_tips = [genesis_hash]
        self.best_chain_tip = genesis_hash

        # Update the UTXO set with the genesis coinbase outputs
        self._apply_block(genesis_block)

        logger.info("Genesis block created: %s", genesis_hash[:16])
        return genesis_block

    # ------------------------------------------------------------------
    # Block storage and retrieval  (Task 5.2)
    # ------------------------------------------------------------------

    def add_block(self, block: "Block") -> bool:
        """
        Attempt to add a new block to the blockchain.

        The block goes through full validation. If accepted, it is stored in
        the block index, chain tips are updated, and -- if the block extends
        the best chain -- the UTXO set is updated and confirmed transactions
        are removed from the mempool.

        If the block creates or extends a competing fork that overtakes the
        current best chain, a chain reorganization is triggered.

        Args:
            block: The candidate block.

        Returns:
            True if the block was accepted, False otherwise.
        """
        block_hash = block.header.hash

        # Already known?
        if block_hash in self.blocks:
            logger.debug("Block %s already known", block_hash[:16])
            return False

        # Validate the block
        try:
            self.validate_new_block(block)
        except Exception as e:
            logger.warning("Block %s rejected: %s", block_hash[:16], e)
            return False

        # Determine the block height
        prev_hash = block.header.previous_block_hash
        if prev_hash == "0" * 64:
            block._height = 0
        else:
            parent = self.blocks.get(prev_hash)
            if parent is not None and parent.height is not None:
                block._height = parent.height + 1
            else:
                block._height = self.get_chain_height() + 1

        height = block.height

        # Store block
        self.blocks[block_hash] = block

        # Update height index
        if height not in self.block_height_index:
            self.block_height_index[height] = []
        self.block_height_index[height].append(block_hash)

        # Update chain tips:
        # - The new block's parent is no longer a tip (if it was one)
        # - The new block becomes a tip
        if prev_hash in self.chain_tips:
            self.chain_tips.remove(prev_hash)
        self.chain_tips.append(block_hash)

        # Determine if this block extends the best chain or creates a fork
        is_fork = self._detect_fork(block)

        if self.best_chain_tip is None:
            # First block after genesis
            self.best_chain_tip = block_hash
            self._apply_block(block)
            self.mempool.clear_confirmed(block)
        elif prev_hash == self.best_chain_tip:
            # Extends the current best chain (common case)
            self.best_chain_tip = block_hash
            self._apply_block(block)
            self.mempool.clear_confirmed(block)
        elif is_fork:
            # This block extends a side chain -- check if it overtakes
            new_chain_height = height
            best_chain_height = self.get_chain_height()
            if new_chain_height > best_chain_height:
                logger.info(
                    "Fork at height %d overtakes best chain (new height %d > %d). Reorganizing.",
                    height, new_chain_height, best_chain_height,
                )
                self._reorganize_chain(block_hash)
            else:
                logger.info(
                    "Fork at height %d does not overtake best chain (%d <= %d). Stored as orphan tip.",
                    height, new_chain_height, best_chain_height,
                )
        else:
            # Extends the best chain (parent was the best tip before some update)
            self.best_chain_tip = block_hash
            self._apply_block(block)
            self.mempool.clear_confirmed(block)

        logger.info(
            "Block %s added at height %d (chain tip: %s)",
            block_hash[:16], height, self.best_chain_tip[:16] if self.best_chain_tip else "none",
        )
        return True

    def get_block(self, block_hash: str) -> "Block | None":
        """
        Retrieve a block by its hash.

        Args:
            block_hash: The hex-encoded block hash.

        Returns:
            The Block object, or None if not found.
        """
        return self.blocks.get(block_hash)

    def get_block_by_height(self, height: int) -> "Block | None":
        """
        Retrieve the block at the given height on the best chain.

        If there are multiple blocks at the same height (due to forks),
        only the one on the best chain is returned.

        Args:
            height: The block height.

        Returns:
            The Block on the best chain at the given height, or None.
        """
        hashes = self.block_height_index.get(height, [])
        if not hashes:
            return None

        # If only one block at this height, return it directly
        if len(hashes) == 1:
            return self.blocks.get(hashes[0])

        # Multiple blocks at this height: determine which is on the best chain.
        best_chain_blocks = set()
        current_hash = self.best_chain_tip
        while current_hash and current_hash != "0" * 64:
            blk = self.blocks.get(current_hash)
            if blk is None:
                break
            best_chain_blocks.add(current_hash)
            current_hash = blk.header.previous_block_hash

        for h in hashes:
            if h in best_chain_blocks:
                return self.blocks.get(h)

        # Fallback: return the first one
        return self.blocks.get(hashes[0]) if hashes else None

    def get_blocks_at_height(self, height: int) -> list["Block"]:
        """
        Retrieve all blocks at a given height (including forks).

        Args:
            height: The block height.

        Returns:
            List of Block objects at that height, possibly from different
            branches.
        """
        hashes = self.block_height_index.get(height, [])
        return [self.blocks[h] for h in hashes if h in self.blocks]

    # ------------------------------------------------------------------
    # Chain tips and navigation  (Task 5.3)
    # ------------------------------------------------------------------

    def get_chain_tip(self) -> "Block | None":
        """
        Return the block at the tip of the best (longest) chain.

        Returns:
            The tip Block, or None if the chain is empty.
        """
        if self.best_chain_tip is None:
            return None
        return self.blocks.get(self.best_chain_tip)

    def get_chain_height(self) -> int:
        """
        Return the height of the best chain's tip.

        Returns:
            The integer height, or -1 if the chain is empty.
        """
        tip = self.get_chain_tip()
        if tip is None:
            return -1
        if tip.height is not None:
            return tip.height
        # Fallback: walk the chain
        return len(self.get_chain()) - 1

    def get_chain(self, tip_hash: str | None = None) -> list["Block"]:
        """
        Walk the chain backwards from *tip_hash* to the genesis block.

        Args:
            tip_hash: The hash to start from.  Defaults to best_chain_tip.

        Returns:
            List of Blocks from genesis (index 0) to the tip (last element).
        """
        if tip_hash is None:
            tip_hash = self.best_chain_tip
        if tip_hash is None:
            return []

        chain: list[Block] = []
        current_hash = tip_hash
        visited: set[str] = set()

        while current_hash and current_hash != "0" * 64:
            if current_hash in visited:
                break  # Prevent infinite loops
            visited.add(current_hash)
            blk = self.blocks.get(current_hash)
            if blk is None:
                break
            chain.append(blk)
            current_hash = blk.header.previous_block_hash

        chain.reverse()
        return chain

    def get_current_difficulty(self) -> int:
        """
        Return the current difficulty_bits for the next block to be mined.

        Returns:
            The compact difficulty target (4-byte integer).
        """
        next_height = self.get_chain_height() + 1
        return self._get_next_difficulty(next_height)

    # ------------------------------------------------------------------
    # Fork detection  (Task 5.6)
    # ------------------------------------------------------------------

    def _detect_fork(self, block: "Block") -> bool:
        """
        Determine whether *block* creates or extends a fork.

        A fork exists when a block's parent already has another child in the
        blockchain. This means two different miners found valid blocks that
        build on the same parent, creating two competing branches.

        Args:
            block: The newly received block.

        Returns:
            True if the block's parent already has at least one other child.
        """
        prev_hash = block.header.previous_block_hash
        if prev_hash == "0" * 64:
            return False

        # Check if the parent already has children other than this block
        block_hash = block.header.hash
        for other_hash, other_block in self.blocks.items():
            if other_hash == block_hash:
                continue
            if other_block.header.previous_block_hash == prev_hash:
                return True
        return False

    # ------------------------------------------------------------------
    # Chain reorganization  (Task 5.7)
    # ------------------------------------------------------------------

    def _reorganize_chain(self, new_tip_hash: str) -> bool:
        """
        Reorganize the blockchain to follow the chain ending at *new_tip_hash*.

        Chain reorganization ("reorg") is one of the most critical operations
        in a Bitcoin node.  It happens when a competing branch becomes longer
        than the current best chain.  The steps are:

        1. Find the common ancestor of the current best chain and the new
           chain.
        2. **Unwind** blocks on the old branch from the current tip back to
           the common ancestor: revert UTXO changes and return transactions
           to the mempool.
        3. **Apply** blocks on the new branch from the common ancestor to
           the new tip: apply UTXO changes and remove transactions from the
           mempool.
        4. Update best_chain_tip.

        Args:
            new_tip_hash: The hash of the tip of the competing chain that
                has overtaken the current best chain.

        Returns:
            True if the reorganization succeeded, False otherwise.
        """
        old_tip_hash = self.best_chain_tip
        if old_tip_hash is None:
            self.best_chain_tip = new_tip_hash
            return True

        # Step 1: Find common ancestor
        common_ancestor_hash = self._find_common_ancestor(old_tip_hash, new_tip_hash)
        if common_ancestor_hash is None:
            logger.error("Could not find common ancestor for reorg")
            return False

        logger.info(
            "Reorg: old tip=%s, new tip=%s, common ancestor=%s",
            old_tip_hash[:16], new_tip_hash[:16], common_ancestor_hash[:16],
        )

        # Step 2: Collect blocks to unwind (old branch: current tip -> ancestor, exclusive)
        blocks_to_unwind: list[Block] = []
        current = old_tip_hash
        while current != common_ancestor_hash:
            blk = self.blocks.get(current)
            if blk is None:
                logger.error("Missing block %s during reorg unwind", current[:16])
                return False
            blocks_to_unwind.append(blk)
            current = blk.header.previous_block_hash

        # Step 3: Collect blocks to apply (new branch: ancestor -> new tip)
        blocks_to_apply: list[Block] = []
        current = new_tip_hash
        while current != common_ancestor_hash:
            blk = self.blocks.get(current)
            if blk is None:
                logger.error("Missing block %s during reorg apply", current[:16])
                return False
            blocks_to_apply.append(blk)
            current = blk.header.previous_block_hash
        blocks_to_apply.reverse()  # Apply from oldest to newest

        # Step 4: Unwind old blocks (newest first)
        for blk in blocks_to_unwind:
            self._unwind_block(blk)
            # Return non-coinbase transactions to the mempool
            for tx in blk.transactions:
                if not tx.is_coinbase():
                    self.mempool.add_transaction(tx, self.utxo_set)

        # Step 5: Apply new blocks (oldest first)
        for blk in blocks_to_apply:
            self._apply_block(blk)
            self.mempool.clear_confirmed(blk)

        # Step 6: Update the best chain tip
        self.best_chain_tip = new_tip_hash
        logger.info("Reorg complete. New best tip: %s", new_tip_hash[:16])
        return True

    def _find_common_ancestor(self, hash_a: str, hash_b: str) -> str | None:
        """
        Find the most recent common ancestor of two chains.

        This is done by walking both chains backwards in lockstep.  At each
        step, the higher chain advances one block. When both pointers point
        to the same block, that is the common ancestor.

        Args:
            hash_a: Tip hash of the first chain.
            hash_b: Tip hash of the second chain.

        Returns:
            The block hash of the common ancestor, or None if none found.
        """
        # Collect the set of block hashes on each chain for fast lookup
        chain_a_hashes: set[str] = set()
        current = hash_a
        while current and current != "0" * 64:
            chain_a_hashes.add(current)
            blk = self.blocks.get(current)
            if blk is None:
                break
            current = blk.header.previous_block_hash

        # Walk chain B back until we find a hash that's also on chain A
        current = hash_b
        while current and current != "0" * 64:
            if current in chain_a_hashes:
                return current
            blk = self.blocks.get(current)
            if blk is None:
                break
            current = blk.header.previous_block_hash

        return None

    def _unwind_block(self, block: "Block") -> None:
        """
        Reverse the UTXO set changes made by a block.

        This is the inverse of _apply_block.  For each transaction in the
        block (processed in reverse order):
        - Remove UTXOs created by the transaction's outputs
        - Re-add UTXOs consumed by the transaction's inputs

        Args:
            block: The block to unwind.
        """
        # Process transactions in reverse order
        for tx in reversed(block.transactions):
            # Remove outputs (they were added when the block was applied)
            for idx, _ in enumerate(tx.outputs):
                try:
                    self.utxo_set.remove_utxo(tx.txid, idx)
                except Exception:
                    pass

            # Re-add inputs (they were removed when the block was applied)
            if not tx.is_coinbase():
                for inp in tx.inputs:
                    if not inp.is_coinbase():
                        # We need the original UTXO data. Since we don't
                        # store full undo data, we attempt to reconstruct
                        # from the referenced transaction.
                        prev_tx = self._find_transaction(inp.previous_txid)
                        if prev_tx and inp.previous_output_index < len(prev_tx.outputs):
                            output = prev_tx.outputs[inp.previous_output_index]
                            # Determine height of the block containing prev_tx
                            prev_block_height = 0
                            for bh, blk in self.blocks.items():
                                for t in blk.transactions:
                                    if t.txid == inp.previous_txid:
                                        prev_block_height = blk.height if blk.height is not None else 0
                                        break
                            try:
                                self.utxo_set.add_utxo(
                                    inp.previous_txid,
                                    inp.previous_output_index,
                                    output,
                                    prev_block_height,
                                    is_coinbase=prev_tx.is_coinbase(),
                                )
                            except Exception:
                                pass

    def _apply_block(self, block: "Block") -> None:
        """
        Apply the UTXO set changes for a block.

        For each transaction in the block:
        - Remove UTXOs consumed by the transaction's inputs
        - Add UTXOs created by the transaction's outputs

        Args:
            block: The block to apply.
        """
        height = block.height if block.height is not None else 0

        for tx in block.transactions:
            # Remove spent UTXOs (skip coinbase inputs which create coins)
            if not tx.is_coinbase():
                for inp in tx.inputs:
                    if not inp.is_coinbase():
                        try:
                            self.utxo_set.remove_utxo(
                                inp.previous_txid, inp.previous_output_index
                            )
                        except Exception:
                            pass

            # Add new UTXOs from outputs
            for idx, output in enumerate(tx.outputs):
                try:
                    self.utxo_set.add_utxo(
                        tx.txid, idx, output, height,
                        is_coinbase=tx.is_coinbase(),
                    )
                except Exception as e:
                    logger.warning("Failed to add UTXO %s:%d: %s", tx.txid[:16], idx, e)

    def _find_transaction(self, txid: str) -> "Transaction | None":
        """
        Search all known blocks for a transaction by its txid.

        This is a linear scan and should only be used for reorgs or debugging.

        Args:
            txid: The transaction ID to find.

        Returns:
            The Transaction object, or None if not found.
        """
        for block in self.blocks.values():
            for tx in block.transactions:
                if tx.txid == txid:
                    return tx
        return None

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def validate_new_block(self, block: "Block") -> bool:
        """
        Validate a candidate block against the current blockchain state.

        Delegates to the validation module's ``validate_block`` function.

        Args:
            block: The block to validate.

        Returns:
            True if valid.

        Raises:
            ValidationError or Exception if invalid.
        """
        from src.consensus.validation import validate_block
        return validate_block(block, self)

    # ------------------------------------------------------------------
    # Difficulty adjustment
    # ------------------------------------------------------------------

    def _get_next_difficulty(self, height: int) -> int:
        """
        Calculate the expected difficulty_bits for a block at *height*.

        If the height falls on a difficulty adjustment boundary, the new
        difficulty is calculated from the timestamps of the previous
        adjustment interval. Otherwise, the current difficulty is unchanged.

        Args:
            height: The height of the block being validated or mined.

        Returns:
            The expected compact difficulty target (difficulty_bits).
        """
        from src.consensus.difficulty import (
            should_adjust,
            calculate_next_difficulty,
        )

        if height == 0:
            return self._difficulty_bits

        if not should_adjust(height, self._adjustment_interval):
            return self._difficulty_bits

        # Gather timestamps for the adjustment calculation.
        # We need the timestamps spanning the last adjustment_interval blocks.
        chain = self.get_chain()
        if len(chain) < 2:
            return self._difficulty_bits

        # Get timestamps of the blocks in the most recent adjustment interval
        interval_start = max(0, len(chain) - self._adjustment_interval)
        block_timestamps = [blk.header.timestamp for blk in chain[interval_start:]]

        if len(block_timestamps) < 2:
            return self._difficulty_bits

        new_bits = calculate_next_difficulty(
            block_timestamps,
            self._difficulty_bits,
            self._adjustment_interval,
            self._target_timespan,
        )

        self._difficulty_bits = new_bits
        logger.info("Difficulty adjusted at height %d: new bits = %#x", height, new_bits)
        return new_bits

    # ------------------------------------------------------------------
    # Mining convenience method
    # ------------------------------------------------------------------

    def mine_next_block(
        self,
        coinbase_address: str,
        transactions: list["Transaction"] | None = None,
    ) -> "Block | None":
        """
        Convenience method to create a block template, mine it, and add it
        to the chain.

        This combines template creation (from the mining module), proof-of-work
        mining, and block addition into a single call.

        Args:
            coinbase_address: The address to receive the block reward.
            transactions: Optional list of transactions to include. If None,
                transactions are pulled from the mempool.

        Returns:
            The mined and accepted Block, or None if mining/addition failed.
        """
        try:
            from src.mining.miner import Miner, create_block_template
            from src.consensus.difficulty import get_block_reward
        except ImportError as e:
            logger.error("Cannot mine: missing module: %s", e)
            return None

        tip = self.get_chain_tip()
        if tip is None:
            logger.error("Cannot mine: no chain tip")
            return None

        prev_hash = tip.header.hash
        height = self.get_chain_height() + 1
        difficulty_bits = self._get_next_difficulty(height)
        reward = get_block_reward(height)

        # Select transactions from mempool if none provided
        if transactions is None:
            transactions = self.mempool.get_transactions()

        block = create_block_template(
            previous_block_hash=prev_hash,
            height=height,
            difficulty_bits=difficulty_bits,
            transactions=transactions,
            coinbase_address=coinbase_address,
            reward_amount=reward,
        )

        # Mine the block
        miner = Miner(instant_mine=False)
        block = miner.mine_block(block)

        # Add to the chain
        if self.add_block(block):
            return block
        else:
            logger.warning("Mined block was not accepted by the chain")
            return None

    # ------------------------------------------------------------------
    # Utility: timestamp lookups
    # ------------------------------------------------------------------

    def get_previous_timestamps(self, block_hash: str, count: int = 11) -> list[int]:
        """
        Retrieve the timestamps of the *count* blocks preceding (and including)
        the block identified by *block_hash*.

        This is used for the Median Time Past (MTP) calculation, which
        Bitcoin uses to validate block timestamps. A block's timestamp must
        be greater than the median of the previous 11 blocks' timestamps.

        Args:
            block_hash: Starting block hash.
            count: Number of timestamps to collect.

        Returns:
            List of integer timestamps (most recent first).
        """
        timestamps: list[int] = []
        current_hash = block_hash
        while current_hash and current_hash != "0" * 64 and len(timestamps) < count:
            blk = self.blocks.get(current_hash)
            if blk is None:
                break
            timestamps.append(blk.header.timestamp)
            current_hash = blk.header.previous_block_hash
        return timestamps

    # ------------------------------------------------------------------
    # JSON Export / Import  (Task 10.2)
    # ------------------------------------------------------------------

    def export_to_json(self, filename: str) -> None:
        """
        Save the entire blockchain state to a JSON file.

        The exported data includes all blocks, the height index, chain tips,
        the UTXO set, the mempool, and configuration parameters. This allows
        the blockchain to be reloaded later for inspection or continued use.

        Args:
            filename: Path to the output JSON file.
        """
        data = self.to_dict()
        with open(filename, "w") as f:
            json.dump(data, f, indent=2, default=str)
        logger.info("Blockchain exported to %s", filename)

    @classmethod
    def import_from_json(cls, filename: str) -> "Blockchain":
        """
        Load a blockchain from a JSON file previously created by export_to_json.

        The blockchain is reconstructed by replaying block additions in height
        order, which naturally rebuilds the UTXO set and indexes.

        Args:
            filename: Path to the JSON file.

        Returns:
            A fully reconstructed Blockchain instance.
        """
        from src.core.block import Block
        from src.core.transaction import Transaction

        with open(filename, "r") as f:
            data = json.load(f)

        dev_mode = data.get("development_mode", True)
        blockchain = cls(development_mode=dev_mode)

        # Load blocks in height order, skipping genesis (already created)
        blocks_data = data.get("blocks", {})

        # Sort blocks by height
        sorted_blocks: list[tuple[int, str, dict]] = []
        for block_hash, block_dict in blocks_data.items():
            height = block_dict.get("height", 0)
            sorted_blocks.append((height, block_hash, block_dict))
        sorted_blocks.sort(key=lambda x: x[0])

        for height, block_hash, block_dict in sorted_blocks:
            if height == 0:
                continue  # Genesis already exists
            try:
                block = Block.from_dict(block_dict)
                block._height = height
                blockchain.add_block(block)
            except Exception as e:
                logger.warning("Failed to import block %s: %s", block_hash[:16], e)

        # Restore mempool transactions
        mempool_data = data.get("mempool", {})
        tx_data = mempool_data.get("transactions", {})
        for txid, tx_dict in tx_data.items():
            try:
                tx = Transaction.from_dict(tx_dict)
                blockchain.mempool.add_transaction(tx, blockchain.utxo_set)
            except Exception as e:
                logger.warning("Failed to import mempool tx %s: %s", txid[:16], e)

        logger.info("Blockchain imported from %s", filename)
        return blockchain

    def to_dict(self) -> dict:
        """
        Serialize the blockchain state to a JSON-compatible dictionary.

        Returns:
            Dictionary containing all blockchain state.
        """
        blocks_dict = {}
        for block_hash, block in self.blocks.items():
            block_data = block.to_dict()
            block_data["height"] = block.height
            blocks_dict[block_hash] = block_data

        return {
            "development_mode": self.development_mode,
            "best_chain_tip": self.best_chain_tip,
            "chain_tips": self.chain_tips,
            "chain_height": self.get_chain_height(),
            "block_count": len(self.blocks),
            "block_height_index": {
                str(h): hashes for h, hashes in self.block_height_index.items()
            },
            "blocks": blocks_dict,
            "utxo_set": self.utxo_set.to_dict(),
            "mempool": self.mempool.to_dict(),
            "difficulty_bits": self._difficulty_bits,
            "adjustment_interval": self._adjustment_interval,
            "target_timespan": self._target_timespan,
            "target_block_time": self._target_block_time,
        }

    def __repr__(self) -> str:
        return (
            f"Blockchain(height={self.get_chain_height()}, "
            f"blocks={len(self.blocks)}, "
            f"tips={len(self.chain_tips)}, "
            f"dev={self.development_mode})"
        )
