"""
Bitcoin Difficulty Adjustment Algorithm
=========================================

This module implements Bitcoin's difficulty adjustment mechanism, which is one of
the most elegant aspects of the protocol's design.

How Difficulty Adjustment Works:
--------------------------------
Bitcoin aims to produce one block approximately every 10 minutes. Since the total
hash power of the network fluctuates as miners join and leave, the protocol must
periodically adjust the mining difficulty to maintain this target block interval.

Every 2016 blocks (approximately 2 weeks), Bitcoin compares the actual time taken
to mine those blocks against the expected time (2016 * 10 minutes = 20,160 minutes).

- If blocks were mined too quickly (actual < expected), difficulty increases
  (target decreases), making mining harder.
- If blocks were mined too slowly (actual > expected), difficulty decreases
  (target increases), making mining easier.

The adjustment is clamped to a factor of 4 in either direction to prevent
dramatic swings:
- Maximum increase: 4x harder (target / 4)
- Maximum decrease: 4x easier (target * 4)

Block Reward Halving:
---------------------
Bitcoin's monetary policy is implemented through block reward halving. The initial
reward was 50 BTC per block. Every 210,000 blocks (approximately 4 years), the
reward is cut in half:

- Blocks 0-209,999: 50 BTC
- Blocks 210,000-419,999: 25 BTC
- Blocks 420,000-629,999: 12.5 BTC
- Blocks 630,000-839,999: 6.25 BTC
- ... and so on

This creates a geometric series that converges to a maximum supply of 21 million BTC.
The last satoshi will be mined around the year 2140.

Development Mode:
-----------------
For testing, this module includes development-mode constants with much shorter
intervals and easier difficulty, allowing blocks to be mined in seconds on
a standard computer.
"""

from __future__ import annotations

from src.mining.miner import compact_bits_to_target, target_to_compact_bits


# ---------------------------------------------------------------------------
# Production mode constants (Bitcoin mainnet parameters)
# ---------------------------------------------------------------------------

DIFFICULTY_ADJUSTMENT_INTERVAL = 2016
"""Number of blocks between difficulty adjustments.
2016 blocks at 10 minutes each is approximately 2 weeks (20,160 minutes)."""

TARGET_BLOCK_TIME = 600
"""Target time between blocks in seconds (10 minutes)."""

TARGET_TIMESPAN = DIFFICULTY_ADJUSTMENT_INTERVAL * TARGET_BLOCK_TIME
"""Expected total time for one difficulty adjustment period in seconds.
2016 * 600 = 1,209,600 seconds = exactly 2 weeks."""

MAX_ADJUSTMENT_FACTOR = 4
"""Maximum difficulty adjustment factor per period.
Difficulty can increase by at most 4x or decrease by at most 4x
in a single adjustment. This prevents sudden large changes that
could destabilize the network."""

GENESIS_DIFFICULTY_BITS = 0x1d00ffff
"""Compact difficulty bits for the Bitcoin genesis block (mainnet).
This corresponds to a difficulty of 1.0 and a very high target,
making it trivial to mine (Bitcoin was very easy to mine in January 2009)."""

# ---------------------------------------------------------------------------
# Development mode constants
# ---------------------------------------------------------------------------

DEV_DIFFICULTY_ADJUSTMENT_INTERVAL = 10
"""Number of blocks between adjustments in development mode.
Much shorter than mainnet for rapid testing."""

DEV_TARGET_BLOCK_TIME = 5
"""Target block time in dev mode: 5 seconds instead of 10 minutes."""

DEV_TARGET_TIMESPAN = DEV_DIFFICULTY_ADJUSTMENT_INTERVAL * DEV_TARGET_BLOCK_TIME
"""Expected total time for one dev adjustment period: 10 * 5 = 50 seconds."""

DEV_GENESIS_DIFFICULTY_BITS = 0x1f0fffff
"""Very easy difficulty for development mode.
With exponent=0x1f=31 and coefficient=0x0fffff, the target is enormous,
allowing blocks to be mined almost instantly with CPU mining."""

# ---------------------------------------------------------------------------
# Halving constants
# ---------------------------------------------------------------------------

HALVING_INTERVAL = 210_000
"""Number of blocks between reward halvings.
At ~10 min/block, this is approximately 4 years."""

INITIAL_REWARD = 50_00000000
"""Initial block reward in satoshis (50 BTC = 5,000,000,000 satoshis)."""


# ---------------------------------------------------------------------------
# Difficulty adjustment functions
# ---------------------------------------------------------------------------

def calculate_next_difficulty(
    block_timestamps: list[int],
    current_bits: int,
    adjustment_interval: int = DIFFICULTY_ADJUSTMENT_INTERVAL,
    target_timespan: int = TARGET_TIMESPAN,
    max_target_bits: int = None
) -> int:
    """
    Calculate the next difficulty target based on how long the previous
    adjustment interval took to mine.

    This implements Bitcoin's core difficulty adjustment algorithm:

    1. Measure the actual time taken for the last `adjustment_interval` blocks
       by computing: time_taken = last_timestamp - first_timestamp
    2. Compare to the expected time (target_timespan).
    3. Adjust the target proportionally:
       new_target = old_target * time_taken / target_timespan
       - If blocks were mined too fast: time_taken < target_timespan,
         so new_target < old_target (harder to mine).
       - If blocks were mined too slow: time_taken > target_timespan,
         so new_target > old_target (easier to mine).
    4. Clamp the adjustment so that the target cannot change by more than
       a factor of 4 in either direction.
    5. Ensure the new target does not exceed the maximum target (easiest
       allowed difficulty).

    Args:
        block_timestamps: List of timestamps (unix epoch) for the blocks in
            the adjustment period. Must have at least 2 entries. The first
            entry is the timestamp of the first block in the period, and the
            last entry is the timestamp of the last block.
        current_bits: The current compact difficulty bits (nBits).
        adjustment_interval: Number of blocks per adjustment period
            (default: 2016 for mainnet).
        target_timespan: Expected time in seconds for the adjustment period
            (default: 1,209,600 for mainnet).
        max_target_bits: The compact difficulty bits representing the maximum
            allowed target (minimum difficulty). In Bitcoin Core this is the
            chain-specific "powLimit". Defaults to GENESIS_DIFFICULTY_BITS
            for mainnet. Use DEV_GENESIS_DIFFICULTY_BITS for dev mode.

    Returns:
        The new compact difficulty bits (nBits) for the next period.

    Raises:
        ValueError: If fewer than 2 timestamps are provided or if timestamps
            are invalid.

    Example:
        >>> # If blocks took exactly the expected time, difficulty stays the same
        >>> timestamps = [0, TARGET_TIMESPAN]
        >>> hex(calculate_next_difficulty(timestamps, 0x1d00ffff))
        '0x1d00ffff'
    """
    if len(block_timestamps) < 2:
        raise ValueError(
            f"Need at least 2 timestamps to calculate difficulty adjustment, "
            f"got {len(block_timestamps)}"
        )

    # Step 1: Calculate actual time taken for this adjustment period
    time_taken = block_timestamps[-1] - block_timestamps[0]

    # Step 2: Clamp the time_taken to prevent extreme adjustments.
    # If time_taken is too small, cap at target_timespan / MAX_ADJUSTMENT_FACTOR
    # (difficulty can increase by at most 4x).
    # If time_taken is too large, cap at target_timespan * MAX_ADJUSTMENT_FACTOR
    # (difficulty can decrease by at most 4x).
    min_timespan = target_timespan // MAX_ADJUSTMENT_FACTOR
    max_timespan = target_timespan * MAX_ADJUSTMENT_FACTOR

    if time_taken < min_timespan:
        time_taken = min_timespan
    elif time_taken > max_timespan:
        time_taken = max_timespan

    # Step 3: Calculate the new target
    # new_target = old_target * time_taken / target_timespan
    old_target = compact_bits_to_target(current_bits)
    new_target = (old_target * time_taken) // target_timespan

    # Step 4: Ensure the new target does not exceed the maximum allowed target
    # (i.e., difficulty does not go below the minimum for the chain).
    # In Bitcoin Core, this is the chain-specific "powLimit" parameter.
    if max_target_bits is None:
        max_target_bits = GENESIS_DIFFICULTY_BITS
    max_target = compact_bits_to_target(max_target_bits)
    if new_target > max_target:
        new_target = max_target

    # Ensure target is at least 1 (avoid zero target)
    if new_target < 1:
        new_target = 1

    # Step 5: Convert back to compact bits format
    return target_to_compact_bits(new_target)


def should_adjust(height: int, interval: int = DIFFICULTY_ADJUSTMENT_INTERVAL) -> bool:
    """
    Determine whether a difficulty adjustment should occur at the given block height.

    Bitcoin adjusts difficulty every `interval` blocks (2016 on mainnet).
    The adjustment happens at the block whose height is a multiple of the
    interval (e.g., blocks 2016, 4032, 6048, ...).

    The genesis block (height 0) is never an adjustment point.

    Args:
        height: The block height to check.
        interval: The difficulty adjustment interval (default: 2016).

    Returns:
        True if difficulty should be recalculated at this height.

    Examples:
        >>> should_adjust(0)
        False
        >>> should_adjust(2016)
        True
        >>> should_adjust(2017)
        False
        >>> should_adjust(4032)
        True
    """
    if height <= 0:
        return False
    return height % interval == 0


def validate_difficulty(block_bits: int, expected_bits: int) -> bool:
    """
    Validate that a block's difficulty bits match the expected value.

    When validating a block received from the network, we independently
    calculate what the difficulty should be and compare it to the block's
    claimed difficulty_bits. They must match exactly.

    Args:
        block_bits: The difficulty_bits value from the block header.
        expected_bits: The difficulty_bits value we calculated independently.

    Returns:
        True if the difficulty bits match.

    Raises:
        ValueError: If the difficulty bits do not match, with a descriptive
            error message showing both values.
    """
    if block_bits != expected_bits:
        raise ValueError(
            f"Invalid difficulty bits: block has 0x{block_bits:08x}, "
            f"expected 0x{expected_bits:08x}. "
            f"Block target: {compact_bits_to_target(block_bits)}, "
            f"Expected target: {compact_bits_to_target(expected_bits)}"
        )
    return True


def get_block_reward(height: int) -> int:
    """
    Calculate the block reward (in satoshis) for a given block height,
    accounting for the halving schedule.

    Bitcoin's block reward starts at 50 BTC and halves every 210,000 blocks:

    - Blocks 0 to 209,999:          50.00000000 BTC (5,000,000,000 satoshis)
    - Blocks 210,000 to 419,999:    25.00000000 BTC (2,500,000,000 satoshis)
    - Blocks 420,000 to 629,999:    12.50000000 BTC (1,250,000,000 satoshis)
    - Blocks 630,000 to 839,999:     6.25000000 BTC   (625,000,000 satoshis)
    - ... continuing to halve until the reward rounds down to 0

    After approximately 33 halvings (around the year 2140), the reward
    becomes 0, and miners will rely solely on transaction fees.

    The total supply converges to exactly 21,000,000 BTC
    (2,100,000,000,000,000 satoshis).

    Args:
        height: The block height (0-indexed).

    Returns:
        The block reward in satoshis. Returns 0 once the reward has been
        halved to nothing (after ~33 halvings at block 6,930,000).

    Raises:
        ValueError: If height is negative.

    Examples:
        >>> get_block_reward(0)
        5000000000
        >>> get_block_reward(209999)
        5000000000
        >>> get_block_reward(210000)
        2500000000
        >>> get_block_reward(420000)
        1250000000
        >>> get_block_reward(6930000)
        0
    """
    if height < 0:
        raise ValueError(f"Block height cannot be negative: {height}")

    halvings = height // HALVING_INTERVAL

    # After 64 halvings, the right shift would exceed 64 bits and the
    # reward is definitely 0. In practice it reaches 0 much sooner (~33 halvings).
    if halvings >= 64:
        return 0

    reward = INITIAL_REWARD >> halvings
    return reward
