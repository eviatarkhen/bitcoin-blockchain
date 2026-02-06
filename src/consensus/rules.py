"""
Bitcoin Consensus Rules
========================

This module implements the core consensus rules that every Bitcoin full node
must enforce to validate blocks and transactions. Consensus rules are the
foundation of Bitcoin's trustless operation -- every node independently
verifies every block and transaction, and any violation results in rejection.

These rules ensure:
- Blocks cannot exceed the maximum size (1 MB for legacy blocks)
- Coinbase transactions follow strict formatting rules
- Coinbase outputs cannot be spent until they have matured (100 blocks)
- Timestamps follow the Median Time Past rule and aren't too far in the future
- Transaction amounts are valid and don't create money from nothing
- No duplicate transaction IDs exist within a single block

Why These Rules Matter:
-----------------------
Without consensus rules, malicious miners could:
- Create money out of thin air (amount validation)
- Spend the same output twice (UTXO validation)
- Manipulate timestamps to game difficulty adjustments (timestamp rules)
- Create enormous blocks to overwhelm the network (size limits)
- Spend coinbase rewards before they're confirmed (maturity rules)

The genius of Bitcoin is that every participant independently enforces these
rules. If a miner produces an invalid block, honest nodes will simply reject
it, wasting the miner's electricity without any reward.

Median Time Past (MTP):
-----------------------
Rather than requiring block timestamps to simply increase, Bitcoin uses a
more sophisticated rule: a block's timestamp must be greater than the median
of the previous 11 blocks' timestamps. This prevents miners from manipulating
timestamps while still allowing for minor clock drift between nodes.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from src.consensus.difficulty import get_block_reward

if TYPE_CHECKING:
    from src.core.block import Block
    from src.core.transaction import Transaction


# ---------------------------------------------------------------------------
# Consensus constants
# ---------------------------------------------------------------------------

MAX_BLOCK_SIZE = 1_000_000
"""Maximum block size in bytes (1 MB).
This is the legacy block size limit. Blocks larger than this are rejected.
The SegWit upgrade later introduced a weight-based limit of 4 million weight
units, but this implementation uses the simpler original limit."""

MAX_BLOCK_SIGOPS = 4000
"""Maximum number of signature operations (sigops) allowed in a block.
This prevents blocks from containing computationally expensive transactions
that could slow down validation."""

COINBASE_MATURITY = 100
"""Number of confirmations required before coinbase outputs can be spent.
This prevents issues that would arise if a block were reorganized out of the
chain after its coinbase output had already been spent. By requiring 100
confirmations, the likelihood of such a deep reorganization is negligible."""

MAX_MONEY = 21_000_000 * 100_000_000
"""Maximum number of satoshis that can ever exist (21 million BTC).
No single output or transaction can exceed this value. This is the hard cap
on Bitcoin's monetary supply: 2,100,000,000,000,000 satoshis."""

MEDIAN_TIME_PAST_BLOCKS = 11
"""Number of previous blocks used to calculate the Median Time Past.
Bitcoin uses the median of the last 11 timestamps rather than requiring
strict chronological ordering, to tolerate minor clock differences."""

MAX_FUTURE_BLOCK_TIME = 2 * 60 * 60
"""Maximum time (in seconds) a block's timestamp can be ahead of the node's
current time. Currently 2 hours (7200 seconds). Blocks with timestamps too
far in the future are rejected to prevent timestamp manipulation."""


# ---------------------------------------------------------------------------
# Block validation functions
# ---------------------------------------------------------------------------

def validate_block_size(block: 'Block') -> bool:
    """
    Validate that a block does not exceed the maximum allowed size.

    The block size limit is a critical consensus rule that prevents denial-of-service
    attacks through oversized blocks. Historically, this limit has been one of the
    most debated aspects of Bitcoin's protocol, leading to the "block size wars"
    and the creation of Bitcoin Cash.

    This function serializes the block (or estimates its size) and checks
    that it falls within the 1 MB limit.

    Args:
        block: The Block object to validate.

    Returns:
        True if the block size is within limits.

    Raises:
        ValueError: If the block exceeds MAX_BLOCK_SIZE bytes, with the
            actual size included in the error message.
    """
    block_size = block.get_size()

    if block_size > MAX_BLOCK_SIZE:
        raise ValueError(
            f"Block size {block_size} bytes exceeds maximum of "
            f"{MAX_BLOCK_SIZE} bytes ({MAX_BLOCK_SIZE / 1_000_000:.1f} MB). "
            f"Excess: {block_size - MAX_BLOCK_SIZE} bytes."
        )

    return True


def validate_coinbase(block: 'Block', expected_height: int) -> bool:
    """
    Validate the coinbase transaction in a block.

    The coinbase transaction is the first transaction in every block, and it is
    the mechanism by which new bitcoins are created. It has special rules:

    1. The first transaction in the block MUST be a coinbase transaction.
    2. No other transaction in the block may be a coinbase transaction.
    3. The total value of the coinbase outputs must not exceed the allowed
       block reward plus the total transaction fees in the block.

    The block reward is determined by the halving schedule: 50 BTC initially,
    halving every 210,000 blocks. Transaction fees are the difference between
    total inputs and total outputs for all non-coinbase transactions.

    Args:
        block: The Block object to validate.
        expected_height: The expected height of this block, used to calculate
            the allowed block reward via the halving schedule.

    Returns:
        True if the coinbase transaction is valid.

    Raises:
        ValueError: If any coinbase rule is violated, with a specific
            description of the violation.
    """
    transactions = block.transactions

    if not transactions:
        raise ValueError("Block has no transactions. Every block must have at least a coinbase transaction.")

    # Rule 1: First transaction must be coinbase
    if not transactions[0].is_coinbase():
        raise ValueError(
            "First transaction in block is not a coinbase transaction. "
            "The first transaction must be a coinbase (with no real inputs)."
        )

    # Rule 2: No other transaction can be coinbase
    for i, tx in enumerate(transactions[1:], start=1):
        if tx.is_coinbase():
            raise ValueError(
                f"Transaction at index {i} is a coinbase transaction. "
                f"Only the first transaction in a block may be coinbase."
            )

    # Rule 3: Coinbase reward must not exceed allowed amount
    coinbase_tx = transactions[0]
    coinbase_output_total = sum(output.value for output in coinbase_tx.outputs)

    # Calculate the expected block reward from the halving schedule
    expected_reward = get_block_reward(expected_height)

    # Calculate total fees from non-coinbase transactions.
    # Fees = sum of inputs - sum of outputs for each transaction.
    # Note: We cannot verify input values without a UTXO set, so we compute
    # fees as (total input values - total output values) across all non-coinbase txs.
    # If the UTXO set is not available, we treat total_fees as 0
    # (a full validation would require UTXO lookups).
    total_fees = 0
    for tx in transactions[1:]:
        tx_output_total = sum(output.value for output in tx.outputs)
        # In a full implementation, we would look up each input's value from the UTXO set.
        # For now, fees are computed when the UTXO set is available during full validation.
        # We allow the coinbase to claim up to expected_reward + total_fees.
        # When total_fees is 0 (no UTXO context), we only check against the base reward.

    max_allowed = expected_reward + total_fees
    if coinbase_output_total > max_allowed:
        raise ValueError(
            f"Coinbase output total ({coinbase_output_total} satoshis) exceeds "
            f"maximum allowed ({max_allowed} satoshis). "
            f"Block reward: {expected_reward} satoshis, "
            f"Transaction fees: {total_fees} satoshis."
        )

    return True


def validate_coinbase_maturity(
    txid: str,
    output_index: int,
    utxo_entry,
    current_height: int
) -> bool:
    """
    Validate that a coinbase output has reached sufficient maturity before
    being spent.

    Coinbase outputs (the mining rewards) cannot be spent until 100 blocks
    have been built on top of the block containing them. This rule exists
    because:

    1. Blockchain reorganizations (reorgs) can orphan blocks, making their
       coinbase transactions invalid.
    2. If coinbase outputs could be spent immediately, a reorg could
       invalidate not just the coinbase but all subsequent transactions
       that spent those coins, creating a cascade of invalid transactions.
    3. The 100-block maturity requirement makes such cascading invalidation
       extremely unlikely, since reorgs deeper than 100 blocks are
       practically impossible.

    Args:
        txid: The transaction ID of the output being spent.
        output_index: The index of the output within the transaction.
        utxo_entry: The UTXO set entry for this output. Must have
            `is_coinbase` (bool) and `block_height` (int) attributes.
        current_height: The height of the block that contains the
            spending transaction.

    Returns:
        True if the output is mature enough to be spent (or is not from
        a coinbase transaction).

    Raises:
        ValueError: If the coinbase output has not reached the required
            maturity of COINBASE_MATURITY (100) blocks.
    """
    # Non-coinbase outputs can be spent immediately (no maturity requirement)
    if not utxo_entry.is_coinbase:
        return True

    # Calculate how many blocks have been built on top of the coinbase block
    confirmations = current_height - utxo_entry.block_height

    if confirmations < COINBASE_MATURITY:
        raise ValueError(
            f"Coinbase output {txid}:{output_index} is immature. "
            f"Has {confirmations} confirmations, needs {COINBASE_MATURITY}. "
            f"Coinbase block height: {utxo_entry.block_height}, "
            f"current height: {current_height}. "
            f"Must wait {COINBASE_MATURITY - confirmations} more blocks."
        )

    return True


def validate_timestamp(
    block_timestamp: int,
    previous_timestamps: list[int],
    current_time: int = None
) -> bool:
    """
    Validate a block's timestamp against the Median Time Past and the
    maximum future time limit.

    Bitcoin uses two timestamp rules:

    1. **Median Time Past (MTP)**: A block's timestamp must be strictly
       greater than the median of the timestamps of the previous 11 blocks.
       This prevents miners from setting timestamps in the past, which could
       be used to manipulate difficulty adjustments.

    2. **Maximum Future Time**: A block's timestamp must be less than the
       node's current time plus 2 hours. This prevents miners from setting
       timestamps far in the future, which could also affect difficulty
       calculations.

    The MTP rule was introduced in BIP 113 and is one of the key mechanisms
    that ensures timestamp integrity across the Bitcoin network.

    Args:
        block_timestamp: The timestamp from the block header (Unix epoch seconds).
        previous_timestamps: List of timestamps from previous blocks, ordered
            from oldest to newest. The last MEDIAN_TIME_PAST_BLOCKS (11) entries
            are used to compute the median.
        current_time: The current time (Unix epoch seconds). If None, uses
            time.time().

    Returns:
        True if the timestamp is valid.

    Raises:
        ValueError: If the timestamp violates either the MTP rule or the
            maximum future time rule.
    """
    if current_time is None:
        current_time = int(time.time())

    # Rule 1: Median Time Past check
    # Only applies when we have at least MEDIAN_TIME_PAST_BLOCKS previous timestamps
    if len(previous_timestamps) >= MEDIAN_TIME_PAST_BLOCKS:
        # Use the last 11 timestamps to calculate the median
        recent_timestamps = previous_timestamps[-MEDIAN_TIME_PAST_BLOCKS:]
        median_time = calculate_median_time(recent_timestamps)

        if block_timestamp <= median_time:
            raise ValueError(
                f"Block timestamp {block_timestamp} is not greater than "
                f"the Median Time Past ({median_time}). "
                f"The block timestamp must exceed the median of the last "
                f"{MEDIAN_TIME_PAST_BLOCKS} block timestamps. "
                f"Recent timestamps: {recent_timestamps}"
            )

    # Rule 2: Maximum future time check
    max_allowed_time = current_time + MAX_FUTURE_BLOCK_TIME
    if block_timestamp > max_allowed_time:
        raise ValueError(
            f"Block timestamp {block_timestamp} is too far in the future. "
            f"Current time: {current_time}, "
            f"maximum allowed: {max_allowed_time} "
            f"(current + {MAX_FUTURE_BLOCK_TIME} seconds = current + 2 hours). "
            f"Excess: {block_timestamp - max_allowed_time} seconds."
        )

    return True


def validate_transaction_amounts(tx: 'Transaction', utxo_set=None) -> bool:
    """
    Validate that all transaction amounts are within acceptable bounds.

    This function enforces several critical monetary rules:

    1. **Non-negative outputs**: No output can have a negative value.
    2. **Individual output limit**: No single output can exceed MAX_MONEY
       (21 million BTC).
    3. **Total output limit**: The sum of all outputs cannot exceed MAX_MONEY.
    4. **Input >= Output** (when UTXO set is available): For non-coinbase
       transactions, the total input value must be >= total output value.
       The difference is the transaction fee, claimed by the miner.

    These rules together prevent inflation bugs, integer overflow attacks,
    and ensure conservation of value.

    Args:
        tx: The Transaction object to validate.
        utxo_set: Optional UTXO set for looking up input values. If provided
            and the transaction is not a coinbase, the function will verify
            that inputs >= outputs. The UTXO set should support
            `get(txid, output_index)` returning an object with a `value` attribute.

    Returns:
        True if all amounts are valid.

    Raises:
        ValueError: If any amount rule is violated, with a specific
            description of the violation.
    """
    total_output = 0

    for i, output in enumerate(tx.outputs):
        # Rule 1: Non-negative output values
        if output.value < 0:
            raise ValueError(
                f"Transaction {tx.txid} output {i} has negative value: "
                f"{output.value} satoshis. Output values must be >= 0."
            )

        # Rule 2: Individual output within MAX_MONEY
        if output.value > MAX_MONEY:
            raise ValueError(
                f"Transaction {tx.txid} output {i} value {output.value} satoshis "
                f"exceeds MAX_MONEY ({MAX_MONEY} satoshis = "
                f"{MAX_MONEY / 100_000_000:.0f} BTC)."
            )

        total_output += output.value

    # Rule 3: Total outputs within MAX_MONEY
    if total_output > MAX_MONEY:
        raise ValueError(
            f"Transaction {tx.txid} total output value {total_output} satoshis "
            f"exceeds MAX_MONEY ({MAX_MONEY} satoshis = "
            f"{MAX_MONEY / 100_000_000:.0f} BTC)."
        )

    # Rule 4: Inputs >= Outputs (only for non-coinbase when UTXO set is available)
    if utxo_set is not None and not tx.is_coinbase():
        total_input = 0
        for inp in tx.inputs:
            # Look up the previous output's value from the UTXO set
            utxo = utxo_set.get(inp.previous_txid, inp.previous_output_index)
            if utxo is None:
                raise ValueError(
                    f"Transaction {tx.txid} references unknown UTXO: "
                    f"{inp.previous_txid}:{inp.previous_output_index}. "
                    f"The referenced output does not exist in the UTXO set."
                )
            total_input += utxo.value

        if total_input < total_output:
            raise ValueError(
                f"Transaction {tx.txid} outputs ({total_output} satoshis) "
                f"exceed inputs ({total_input} satoshis). "
                f"Deficit: {total_output - total_input} satoshis. "
                f"Transactions cannot create money from nothing."
            )

    return True


def validate_no_duplicate_txids(transactions: list) -> bool:
    """
    Validate that no two transactions in a block share the same transaction ID.

    Duplicate transaction IDs within a block would create ambiguity in the
    UTXO set and could be exploited for double-spending attacks. This rule
    was strengthened after the BIP 30 / BIP 34 soft forks, which addressed
    historical duplicate coinbase transactions.

    Args:
        transactions: List of Transaction objects to check.

    Returns:
        True if all transaction IDs are unique.

    Raises:
        ValueError: If duplicate transaction IDs are found, listing the
            duplicated IDs.
    """
    seen_txids = set()
    duplicates = []

    for tx in transactions:
        txid = tx.txid
        if txid in seen_txids:
            duplicates.append(txid)
        seen_txids.add(txid)

    if duplicates:
        raise ValueError(
            f"Block contains duplicate transaction IDs: {duplicates}. "
            f"Each transaction in a block must have a unique txid."
        )

    return True


# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------

def calculate_median_time(timestamps: list[int]) -> int:
    """
    Calculate the median of a list of timestamps.

    Used to compute the Median Time Past (MTP), which is the median of the
    timestamps of the previous 11 blocks. The MTP serves as a monotonically
    increasing clock for consensus purposes, replacing the unreliable wall
    clock time.

    For an even number of timestamps, the lower of the two middle values
    is returned (consistent with Bitcoin Core's implementation).

    Args:
        timestamps: List of integer timestamps (Unix epoch seconds).

    Returns:
        The median timestamp. For an odd-length list, this is the middle
        value. For an even-length list, this is the lower of the two
        middle values.

    Raises:
        ValueError: If the timestamps list is empty.

    Examples:
        >>> calculate_median_time([1, 2, 3, 4, 5])
        3
        >>> calculate_median_time([1, 2, 3, 4])
        2
        >>> calculate_median_time([5, 1, 3, 2, 4])
        3
    """
    if not timestamps:
        raise ValueError("Cannot calculate median of empty timestamp list.")

    sorted_timestamps = sorted(timestamps)
    n = len(sorted_timestamps)

    # For odd length, return the middle element
    # For even length, return the lower of the two middle elements
    # (consistent with Bitcoin Core's integer division behavior)
    mid = n // 2
    if n % 2 == 1:
        return sorted_timestamps[mid]
    else:
        # Return the lower median (index mid - 1)
        return sorted_timestamps[mid - 1]
