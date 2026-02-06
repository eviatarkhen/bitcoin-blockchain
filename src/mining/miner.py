"""
Bitcoin Proof-of-Work Mining
==============================

This module implements the core Proof-of-Work (PoW) mining mechanism used in Bitcoin.

How Bitcoin Mining Works:
-------------------------
Mining is the process by which new blocks are added to the blockchain. To mine a block,
a miner must find a nonce value such that the SHA-256 hash of the block header, when
interpreted as a 256-bit integer, is less than a target value determined by the network's
current difficulty.

The mining process is essentially a brute-force search:
1. Construct a candidate block with a header containing the previous block's hash,
   a merkle root of the transactions, a timestamp, and a difficulty target.
2. Set the nonce to 0.
3. Compute the double-SHA-256 hash of the 80-byte block header.
4. If the hash (as a big-endian 256-bit integer) is less than the target, the block
   is valid -- broadcast it to the network.
5. Otherwise, increment the nonce and try again.
6. If the entire 32-bit nonce space (0 to 2^32 - 1) is exhausted without finding a
   valid hash, modify the coinbase transaction's extra nonce field, recompute the
   merkle root, and restart the nonce search.

Compact Difficulty Representation (nBits):
------------------------------------------
Bitcoin encodes the 256-bit target as a compact 4-byte value called "nBits" or
"difficulty_bits". The format is:

    bits = 0xAABBCCDD

where:
    - AA (first byte) = exponent (number of bytes in the full target)
    - BBCCDD (next 3 bytes) = coefficient (mantissa)

    target = coefficient * 256^(exponent - 3)

For example, the genesis block difficulty bits 0x1d00ffff means:
    exponent = 0x1d = 29
    coefficient = 0x00ffff = 65535
    target = 65535 * 256^(29-3) = 65535 * 256^26

This produces a very large target, making mining easy. As difficulty increases,
the target decreases, requiring more hash attempts on average to find a valid block.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.core.block import Block, BlockHeader
    from src.core.transaction import Transaction


# ---------------------------------------------------------------------------
# Compact difficulty (nBits) conversion utilities
# ---------------------------------------------------------------------------

def compact_bits_to_target(bits: int) -> int:
    """
    Convert a compact 4-byte difficulty representation (nBits) to a full
    256-bit target integer.

    In Bitcoin, the difficulty target is stored in the block header as a
    compact 4-byte value. This function expands it to the full target.

    Format:
        bits = 0xAABBCCDD
        exponent = AA (first byte)
        coefficient = 0xBBCCDD (remaining 3 bytes)
        target = coefficient * 256^(exponent - 3)

    Args:
        bits: The compact difficulty representation (e.g., 0x1d00ffff).

    Returns:
        The full 256-bit target as a Python integer.

    Raises:
        ValueError: If bits is negative or zero.

    Examples:
        >>> hex(compact_bits_to_target(0x1d00ffff))  # Genesis block target
        '0xffff0000000000000000000000000000000000000000000000000000'
        >>> compact_bits_to_target(0x1f0fffff)  # Easy dev difficulty
        > 0  # A very large target
    """
    if bits <= 0:
        raise ValueError(f"Invalid difficulty bits: {bits}. Must be positive.")

    # Extract the exponent (top byte) and coefficient (lower 3 bytes)
    exponent = (bits >> 24) & 0xFF
    coefficient = bits & 0x7FFFFF  # Mask out the sign bit (bit 23)

    # Handle the sign bit (bit 23 of the original coefficient area)
    # In Bitcoin, if bit 23 is set, the target is negative (treated as 0)
    if bits & 0x800000:
        coefficient = -coefficient

    # Calculate target = coefficient * 256^(exponent - 3)
    if exponent <= 3:
        # If exponent <= 3, we right-shift the coefficient
        target = coefficient >> (8 * (3 - exponent))
    else:
        target = coefficient << (8 * (exponent - 3))

    # Target cannot be negative
    if target < 0:
        return 0

    return target


def target_to_compact_bits(target: int) -> int:
    """
    Convert a full 256-bit target integer back to the compact 4-byte
    difficulty representation (nBits).

    This is the inverse of compact_bits_to_target(). It finds the most
    compact representation of the target value.

    The algorithm:
    1. Convert target to bytes (big-endian, without leading zeros).
    2. The number of bytes is the exponent.
    3. The top 3 bytes are the coefficient.
    4. If the highest bit of the coefficient is set, we need to add a
       leading zero byte (to avoid confusion with the sign bit), which
       increases the exponent by 1.

    Args:
        target: The full 256-bit target as a Python integer.

    Returns:
        The compact difficulty representation as a 4-byte integer.

    Raises:
        ValueError: If target is negative.

    Examples:
        >>> hex(target_to_compact_bits(compact_bits_to_target(0x1d00ffff)))
        '0x1d00ffff'
    """
    if target < 0:
        raise ValueError(f"Target cannot be negative: {target}")
    if target == 0:
        return 0

    # Convert target to raw bytes (big-endian, no leading zeros)
    # Calculate number of bytes needed
    byte_length = (target.bit_length() + 7) // 8
    target_bytes = target.to_bytes(byte_length, byteorder='big')

    # The exponent is the number of bytes
    exponent = len(target_bytes)

    # Extract the top 3 bytes as the coefficient
    if exponent >= 3:
        coefficient = int.from_bytes(target_bytes[:3], byteorder='big')
    else:
        # Pad with trailing zeros to get 3 bytes
        padded = target_bytes + b'\x00' * (3 - exponent)
        coefficient = int.from_bytes(padded, byteorder='big')

    # If the highest bit (bit 23) of the coefficient is set, we must add a
    # leading zero byte to avoid the value being interpreted as negative.
    if coefficient & 0x800000:
        coefficient >>= 8
        exponent += 1

    # Assemble the compact bits: exponent in top byte, coefficient in lower 3 bytes
    compact = (exponent << 24) | (coefficient & 0x7FFFFF)
    return compact


def calculate_difficulty(target: int) -> float:
    """
    Calculate the human-readable difficulty value from a target.

    Difficulty is defined as the ratio of the maximum (easiest) target to the
    current target. A higher difficulty means a lower target and more hash
    attempts needed on average.

    The formula is:
        difficulty = max_target / current_target

    where max_target is the target corresponding to difficulty_bits = 0x1d00ffff
    (the Bitcoin genesis block difficulty).

    In Bitcoin's early days, difficulty was 1.0. As of 2024, difficulty is in
    the tens of trillions.

    Args:
        target: The current 256-bit target integer.

    Returns:
        The difficulty as a floating-point number (>= 1.0 for valid targets).

    Raises:
        ValueError: If target is zero or negative.

    Examples:
        >>> calculate_difficulty(compact_bits_to_target(0x1d00ffff))
        1.0
    """
    if target <= 0:
        raise ValueError(f"Target must be positive, got {target}")

    # max_target corresponds to the genesis block difficulty bits 0x1d00ffff
    max_target = compact_bits_to_target(0x1d00ffff)

    return max_target / target


# ---------------------------------------------------------------------------
# Miner class - Proof-of-Work mining engine
# ---------------------------------------------------------------------------

class Miner:
    """
    Bitcoin Proof-of-Work miner.

    The miner repeatedly hashes block headers with different nonce values
    until finding one that produces a hash below the target threshold.

    In real Bitcoin mining, this is done by specialized ASIC hardware capable
    of trillions of hashes per second. This implementation uses Python for
    educational purposes.

    Attributes:
        instant_mine: If True, skip PoW and accept any nonce (for testing).
        hash_count: Total number of hashes computed since instantiation.
        _mining: Internal flag used to interrupt the mining loop.

    Example:
        >>> miner = Miner(instant_mine=True)
        >>> mined_block = miner.mine_block(block)
    """

    def __init__(self, instant_mine: bool = False):
        """
        Initialize the miner.

        Args:
            instant_mine: If True, blocks are accepted immediately without
                performing any proof-of-work computation. Useful for testing
                and development.
        """
        self.instant_mine = instant_mine
        self.hash_count = 0
        self._mining = False

    def mine_block(self, block: 'Block', target: int = None) -> 'Block':
        """
        Mine a block by finding a valid nonce through proof-of-work.

        This method implements the core mining loop:
        1. If instant_mine is enabled, set nonce=0, compute hash, and return.
        2. Otherwise, derive the target from the block header's difficulty_bits
           (or use the provided target).
        3. Iterate through nonces 0 to 2^32 - 1, hashing the header each time.
        4. If a valid hash is found (hash < target), return the mined block.
        5. If the nonce space is exhausted, modify the extra nonce in the
           coinbase transaction and restart the search.

        Args:
            block: The candidate block to mine. Its header.nonce will be modified.
            target: Optional explicit target. If None, derived from
                    block.header.difficulty_bits.

        Returns:
            The same block object with a valid nonce set (header modified in-place).

        Raises:
            RuntimeError: If mining is stopped externally via stop().
        """
        self._mining = True

        # Instant mining mode: skip PoW entirely (for testing/development)
        if self.instant_mine:
            block.header.nonce = 0
            # Force a hash recalculation by calling calculate_hash
            block.header.calculate_hash()
            return block

        # Derive target from difficulty_bits if not explicitly provided
        if target is None:
            target = compact_bits_to_target(block.header.difficulty_bits)

        extra_nonce = 0
        max_nonce = 2**32  # 4,294,967,296 possible nonce values

        start_time = time.time()

        while self._mining:
            # Search the entire 32-bit nonce space
            for nonce in range(max_nonce):
                if not self._mining:
                    raise RuntimeError("Mining was stopped externally.")

                block.header.nonce = nonce
                block_hash = block.header.calculate_hash()

                self.hash_count += 1

                # Print progress every 100,000 hashes
                if self.hash_count % 100000 == 0:
                    elapsed = time.time() - start_time
                    hashrate = self.get_hashrate(elapsed) if elapsed > 0 else 0
                    print(
                        f"Mining: {self.hash_count} hashes, "
                        f"{hashrate:.0f} H/s, "
                        f"nonce={nonce}, extra_nonce={extra_nonce}"
                    )

                # Check if the hash meets the difficulty target.
                # The hash is a hex string; interpret it as a big-endian integer.
                hash_int = int(block_hash, 16)
                if hash_int < target:
                    elapsed = time.time() - start_time
                    print(
                        f"Block mined! Nonce: {nonce}, "
                        f"Hash: {block_hash}, "
                        f"Hashes: {self.hash_count}, "
                        f"Time: {elapsed:.2f}s"
                    )
                    return block

            # Nonce space exhausted -- modify the extra nonce in the coinbase
            # transaction and recompute the merkle root to get a new search space.
            extra_nonce += 1
            self._handle_extra_nonce(block, extra_nonce)
            print(
                f"Nonce space exhausted. Incrementing extra_nonce to {extra_nonce}. "
                f"Recalculated merkle root."
            )

        raise RuntimeError("Mining was stopped externally.")

    def stop(self):
        """
        Stop the mining process.

        Sets the internal _mining flag to False, which causes the mining loop
        to terminate at the next nonce check.

        This is useful for multi-threaded scenarios where mining needs to be
        interrupted (e.g., when a new block is received from the network).
        """
        self._mining = False

    def _handle_extra_nonce(self, block: 'Block', extra_nonce: int) -> None:
        """
        Handle nonce space exhaustion by modifying the coinbase transaction.

        When all 2^32 nonce values have been tried without finding a valid
        hash, miners modify the coinbase transaction's scriptSig to include
        an "extra nonce" value. This changes the transaction's hash, which
        changes the merkle root, which effectively gives a completely new
        set of 2^32 nonces to try.

        In real Bitcoin mining, the extra nonce is a critical part of the
        mining process since modern ASICs can exhaust the 32-bit nonce space
        in under a second.

        Args:
            block: The block whose coinbase transaction will be modified.
            extra_nonce: The new extra nonce value to embed in the coinbase.
        """
        coinbase_tx = block.get_coinbase()
        if coinbase_tx is None:
            return

        # Modify the coinbase's signature script to include the extra nonce.
        # The coinbase transaction's first input has a scriptSig (signature_script)
        # that can contain arbitrary data. We append the extra nonce bytes.
        if coinbase_tx.inputs:
            coinbase_input = coinbase_tx.inputs[0]
            # Encode extra_nonce as bytes and set it in the signature script.
            # We calculate the byte length needed and encode as little-endian.
            extra_nonce_bytes = extra_nonce.to_bytes(
                max(1, (extra_nonce.bit_length() + 7) // 8),
                byteorder='little'
            )
            # Set or append the extra nonce to the signature script
            if hasattr(coinbase_input, 'signature_script'):
                # Replace or append extra nonce data
                coinbase_input.signature_script = (
                    coinbase_input.signature_script + extra_nonce_bytes
                )
            elif hasattr(coinbase_input, 'script_sig'):
                coinbase_input.script_sig = (
                    coinbase_input.script_sig + extra_nonce_bytes
                )

        # Recalculate the merkle root since the coinbase transaction changed
        block.header.merkle_root = block.calculate_merkle_root()

    def get_hashrate(self, elapsed_seconds: float) -> float:
        """
        Calculate the mining hash rate.

        Args:
            elapsed_seconds: The number of seconds elapsed since mining started.

        Returns:
            The hash rate in hashes per second (H/s).
        """
        if elapsed_seconds <= 0:
            return 0.0
        return self.hash_count / elapsed_seconds


# ---------------------------------------------------------------------------
# Block template creation helper
# ---------------------------------------------------------------------------

def create_block_template(
    previous_block_hash: str,
    height: int,
    difficulty_bits: int,
    transactions: list,
    coinbase_address: str,
    reward_amount: int,
    extra_nonce: int = 0
) -> 'Block':
    """
    Create a block template ready for mining.

    This helper function assembles a complete block with all required
    fields populated, ready to be passed to a Miner for proof-of-work
    computation. It:

    1. Creates a coinbase transaction that pays the mining reward to the
       specified address.
    2. Constructs a block header with the appropriate version, previous
       block hash, timestamp, and difficulty bits.
    3. Adds all provided transactions (with the coinbase first).
    4. Calculates and sets the merkle root.
    5. Returns the block with nonce=0, ready for mining.

    Args:
        previous_block_hash: The hex hash of the previous block in the chain.
        height: The height of the new block (used in coinbase).
        difficulty_bits: The compact difficulty target (nBits) for this block.
        transactions: List of Transaction objects to include in the block
                     (excluding the coinbase, which is created automatically).
        coinbase_address: The address to receive the mining reward.
        reward_amount: The block reward in satoshis (including fees).
        extra_nonce: Optional extra nonce value for the coinbase transaction.

    Returns:
        A Block object with all fields set, ready for mining (nonce=0).

    Example:
        >>> template = create_block_template(
        ...     previous_block_hash="00" * 32,
        ...     height=0,
        ...     difficulty_bits=0x1f0fffff,
        ...     transactions=[],
        ...     coinbase_address="1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
        ...     reward_amount=50_00000000
        ... )
    """
    # Import here to avoid circular imports at module load time
    from src.core.transaction import Transaction
    from src.core.block import Block, BlockHeader

    # Step 1: Create the coinbase transaction
    coinbase_tx = Transaction.create_coinbase(
        block_height=height,
        reward_address=coinbase_address,
        reward_amount=reward_amount,
        extra_nonce=extra_nonce
    )

    # Step 2: Assemble the full transaction list (coinbase first)
    all_transactions = [coinbase_tx] + list(transactions)

    # Step 3: Create the block header
    header = BlockHeader(
        version=1,
        previous_block_hash=previous_block_hash,
        merkle_root="00" * 32,  # Placeholder; calculated below
        timestamp=int(time.time()),
        difficulty_bits=difficulty_bits,
        nonce=0
    )

    # Step 4: Create the block
    block = Block(
        header=header,
        transactions=all_transactions
    )

    # Set the block height if the Block supports it
    if hasattr(block, '_height'):
        block._height = height

    # Step 5: Calculate and set the merkle root
    merkle_root = block.calculate_merkle_root()
    block.header.merkle_root = merkle_root

    return block
