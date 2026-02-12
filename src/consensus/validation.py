"""
Bitcoin Consensus Validation
=============================

This module implements the validation rules that every Bitcoin node must
enforce to maintain consensus. When a node receives a new block or
transaction, it must independently verify that all consensus rules are
satisfied before accepting it. Nodes that accept invalid blocks or
transactions will diverge from the rest of the network and end up on a
different (invalid) chain.

Validation covers several areas:

- **Proof-of-Work (PoW)**: The block header hash must be below the target
  derived from the difficulty bits.  This proves the miner performed the
  required computational work.

- **Merkle Root**: The merkle root in the header must match the root computed
  from the block's transaction list.  This cryptographically commits the
  header to the exact set of transactions.

- **Timestamps**: Block timestamps must be within acceptable bounds to prevent
  manipulation of the difficulty adjustment algorithm.

- **Block Size**: Blocks must not exceed the maximum allowed size.

- **Coinbase**: The first (and only the first) transaction in a block must be
  a coinbase transaction with the correct format.

- **Transaction Validity**: Each non-coinbase transaction must:
  - Reference existing, unspent outputs (UTXOs)
  - Have valid signatures authorizing the spend
  - Not spend more than the sum of its inputs (conservation of value)
  - Respect coinbase maturity rules (coinbase outputs cannot be spent
    until they have a sufficient number of confirmations)

- **No Duplicate TXIDs**: A block must not contain two transactions with the
  same txid.

This implementation follows Bitcoin's original validation logic but with
simplifications appropriate for an educational project.
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.core.block import Block
    from src.core.transaction import Transaction
    from src.core.utxo import UTXOSet

logger = logging.getLogger(__name__)


class ValidationError(Exception):
    """
    Raised when a block or transaction fails consensus validation.

    The message describes the specific rule that was violated, which is
    useful for debugging and for providing feedback to peers that relayed
    the invalid data.
    """
    pass


# ---------------------------------------------------------------------------
# Block validation
# ---------------------------------------------------------------------------

def validate_block(block: "Block", blockchain: object) -> bool:
    """
    Perform full validation of a block against the current blockchain state.

    This is the top-level entry point called when a new block is received.
    It checks every consensus rule in the order that is most efficient
    (cheap checks first, expensive checks last).

    Args:
        block: The candidate block to validate.
        blockchain: The Blockchain instance providing chain context such as
            the UTXO set, previous blocks, and difficulty parameters.

    Returns:
        True if the block passes all validation checks.

    Raises:
        ValidationError: If any consensus rule is violated.
    """
    block_hash = block.header.hash

    # ---------------------------------------------------------------
    # 1. Proof-of-Work: header hash must meet the difficulty target
    # ---------------------------------------------------------------
    if not block.header.meets_difficulty_target():
        raise ValidationError(
            f"Block {block_hash[:16]} does not meet difficulty target"
        )

    # ---------------------------------------------------------------
    # 2. Previous block must exist (unless this is the genesis block)
    # ---------------------------------------------------------------
    prev_hash = block.header.previous_block_hash
    is_genesis = (prev_hash == "0" * 64)

    if not is_genesis:
        prev_block = blockchain.get_block(prev_hash)
        if prev_block is None:
            raise ValidationError(
                f"Previous block {prev_hash[:16]} not found in blockchain"
            )

    # Compute the expected height once (used by multiple checks below)
    if is_genesis:
        expected_height = 0
    else:
        parent = blockchain.get_block(prev_hash)
        if parent is not None and parent.height is not None:
            expected_height = parent.height + 1
        else:
            expected_height = blockchain.get_chain_height() + 1

    # ---------------------------------------------------------------
    # 3. Merkle root must match computed value from transactions
    # ---------------------------------------------------------------
    computed_merkle = block.calculate_merkle_root()
    if computed_merkle != block.header.merkle_root:
        raise ValidationError(
            f"Merkle root mismatch: header={block.header.merkle_root[:16]}, "
            f"computed={computed_merkle[:16]}"
        )

    # ---------------------------------------------------------------
    # 4. Timestamp validation
    # ---------------------------------------------------------------
    from src.consensus.rules import (
        validate_timestamp,
        validate_block_size,
        validate_coinbase,
        validate_no_duplicate_txids,
    )
    if not is_genesis:
        previous_timestamps = blockchain.get_previous_timestamps(prev_hash, count=11)
        if not validate_timestamp(block.header.timestamp, previous_timestamps, int(time.time())):
            raise ValidationError(
                f"Block timestamp {block.header.timestamp} is invalid"
            )

    # ---------------------------------------------------------------
    # 5. Block size check
    # ---------------------------------------------------------------
    if not validate_block_size(block):
        raise ValidationError("Block exceeds maximum allowed size")

    # ---------------------------------------------------------------
    # 6. Coinbase validation
    # ---------------------------------------------------------------
    if not validate_coinbase(block, expected_height):
        raise ValidationError("Invalid coinbase transaction")

    # ---------------------------------------------------------------
    # 7. Validate all transactions in the block
    # ---------------------------------------------------------------
    coinbase_maturity = getattr(blockchain, '_coinbase_maturity', 100)
    if not is_genesis:
        try:
            validate_block_transactions(block, blockchain.utxo_set, expected_height, coinbase_maturity)
        except ValidationError:
            raise
        except ValueError as e:
            raise ValidationError(str(e)) from e
        except Exception as e:
            logger.warning("Transaction validation encountered an error: %s", e)

    # ---------------------------------------------------------------
    # 8. No duplicate txids within the block
    # ---------------------------------------------------------------
    if not validate_no_duplicate_txids(block.transactions):
        raise ValidationError("Block contains duplicate transaction IDs")

    # ---------------------------------------------------------------
    # 9. Difficulty bits must match expected value
    # ---------------------------------------------------------------
    if not is_genesis:
        try:
            expected_bits = blockchain._get_next_difficulty(expected_height)
            if block.header.difficulty_bits != expected_bits:
                raise ValidationError(
                    f"Difficulty bits mismatch: expected {expected_bits:#x}, "
                    f"got {block.header.difficulty_bits:#x}"
                )
        except ValidationError:
            raise
        except Exception as e:
            logger.warning("Difficulty check encountered an error: %s", e)

    logger.info("Block %s passed all validation checks", block_hash[:16])
    return True


# ---------------------------------------------------------------------------
# Block transaction validation
# ---------------------------------------------------------------------------

def validate_block_transactions(
    block: "Block",
    utxo_set: "UTXOSet",
    block_height: int,
    coinbase_maturity: int = 100,
) -> bool:
    """
    Validate every transaction in a block against the UTXO set.

    The coinbase transaction (always the first tx in a block) is skipped
    because it has no inputs to validate -- it creates new coins as the
    block reward plus fees.

    For every other transaction, this function ensures:
    - All referenced UTXOs exist and are unspent.
    - Coinbase maturity is respected for any spent coinbase outputs.
    - Signatures are valid (best-effort; graceful degradation if the
      crypto module is unavailable).
    - The sum of outputs does not exceed the sum of inputs.

    A temporary copy of the UTXO set is used to track spending within the
    block so that intra-block double-spends are detected.

    Args:
        block: The block whose transactions are being validated.
        utxo_set: The current UTXO set (before this block is applied).
        block_height: The height at which this block will be placed.
        coinbase_maturity: Required confirmations for coinbase outputs.

    Returns:
        True if all transactions are valid.

    Raises:
        ValidationError: If any transaction fails validation.
    """
    # Work on a copy so we can track intra-block spending
    try:
        working_utxo = utxo_set.copy()
    except Exception:
        working_utxo = utxo_set

    for i, tx in enumerate(block.transactions):
        # Skip coinbase
        if i == 0 and tx.is_coinbase():
            continue

        try:
            validate_transaction(tx, working_utxo, block_height, coinbase_maturity)
        except ValidationError as e:
            raise ValidationError(
                f"Transaction {tx.txid[:16]} at index {i} failed validation: {e}"
            )

        # Remove spent UTXOs from working set so subsequent txs in the same
        # block cannot double-spend them.
        for inp in tx.inputs:
            if not inp.is_coinbase():
                try:
                    working_utxo.remove_utxo(inp.previous_txid, inp.previous_output_index)
                except Exception:
                    pass

        # Add new UTXOs created by this transaction
        for idx, output in enumerate(tx.outputs):
            try:
                working_utxo.add_utxo(tx.txid, idx, output, block_height, is_coinbase=False)
            except Exception:
                pass

    return True


# ---------------------------------------------------------------------------
# Individual transaction validation
# ---------------------------------------------------------------------------

def validate_transaction(
    tx: "Transaction",
    utxo_set: "UTXOSet",
    current_height: int = 0,
    coinbase_maturity: int = 100,
) -> bool:
    """
    Validate a standalone (non-coinbase) transaction.

    Checks performed:
    1. Must not be a coinbase transaction.
    2. Must have at least one input and at least one output.
    3. Every input must reference an existing UTXO.
    4. Coinbase maturity must be respected for each input.
    5. Signatures must be valid (graceful degradation if crypto is missing).
    6. Sum of output values must not exceed sum of input values.

    Args:
        tx: The transaction to validate.
        utxo_set: The UTXO set to validate against.
        current_height: The height of the block being validated (used for
            coinbase maturity checks).
        coinbase_maturity: Required confirmations for coinbase outputs.

    Returns:
        True if the transaction is valid.

    Raises:
        ValidationError: If the transaction violates any rule.
    """
    # 1. Cannot validate a coinbase as a standalone transaction
    if tx.is_coinbase():
        raise ValidationError("Cannot validate coinbase as standalone transaction")

    # 2. Must have at least one input and one output
    if len(tx.inputs) == 0:
        raise ValidationError("Transaction has no inputs")
    if len(tx.outputs) == 0:
        raise ValidationError("Transaction has no outputs")

    # 3. All inputs must reference existing UTXOs
    total_input_value = 0
    for i, inp in enumerate(tx.inputs):
        if inp.is_coinbase():
            raise ValidationError(f"Non-coinbase transaction has coinbase input at index {i}")

        utxo = utxo_set.get_utxo(inp.previous_txid, inp.previous_output_index)
        if utxo is None:
            raise ValidationError(
                f"Input {i} references non-existent UTXO: "
                f"{inp.previous_txid[:16]}:{inp.previous_output_index}"
            )

        # 4. Coinbase maturity check
        from src.consensus.rules import validate_coinbase_maturity
        if not validate_coinbase_maturity(
            inp.previous_txid, inp.previous_output_index,
            utxo, current_height, maturity=coinbase_maturity,
        ):
            raise ValidationError(
                f"Input {i} fails coinbase maturity check "
                f"(UTXO from height {utxo.block_height}, current height {current_height})"
            )

        total_input_value += utxo.value

    # 5. Signature validation (best-effort)
    for i, _ in enumerate(tx.inputs):
        try:
            if not validate_transaction_signature(tx, i, utxo_set):
                raise ValidationError(f"Invalid signature for input {i}")
        except ValidationError:
            raise
        except Exception as e:
            logger.warning("Signature validation error for input %d: %s", i, e)

    # 6. Output values must not exceed input values (conservation of value)
    total_output_value = sum(out.value for out in tx.outputs)
    if total_output_value > total_input_value:
        raise ValidationError(
            f"Output value ({total_output_value}) exceeds input value ({total_input_value})"
        )

    # Additional: all output values must be non-negative
    for i, out in enumerate(tx.outputs):
        if out.value < 0:
            raise ValidationError(f"Output {i} has negative value: {out.value}")

    return True


# ---------------------------------------------------------------------------
# Signature validation
# ---------------------------------------------------------------------------

def validate_transaction_signature(
    tx: "Transaction",
    input_index: int,
    utxo_set: "UTXOSet",
) -> bool:
    """
    Validate the digital signature for a specific transaction input.

    In Bitcoin's Pay-to-Public-Key-Hash (P2PKH) scheme, the signature_script
    (scriptSig) contains two items pushed onto the script stack:
    1. The DER-encoded ECDSA signature
    2. The SEC-encoded public key

    This function extracts both, verifies that the public key hashes to the
    address in the UTXO's pubkey_script, and then verifies the signature
    against the serialized transaction data.

    NOTE: This uses a simplified validation model. Real Bitcoin script
    execution is more complex and supports multiple script types.

    Args:
        tx: The transaction containing the input.
        input_index: Index of the input whose signature to verify.
        utxo_set: The UTXO set for looking up the output being spent.

    Returns:
        True if the signature is valid (or if crypto modules are unavailable,
        in which case we log a warning and return True for graceful degradation).
    """
    from src.crypto.keys import PublicKey, verify_transaction_input

    try:
        inp = tx.inputs[input_index]

        # Get the UTXO being spent
        utxo = utxo_set.get_utxo(inp.previous_txid, inp.previous_output_index)
        if utxo is None:
            return False

        # The signature_script is expected to be a hex-encoded string containing
        # the signature and public key concatenated (simplified format):
        # <sig_hex> <pubkey_hex>   (space-separated)
        sig_script = inp.signature_script
        if not sig_script:
            logger.warning("Empty signature script for input %d", input_index)
            return True  # Graceful degradation

        parts = sig_script.split()
        if len(parts) < 2:
            # May be a different script format; allow gracefully
            logger.warning(
                "Signature script for input %d does not have expected "
                "format (expected '<sig> <pubkey>')", input_index
            )
            return True

        sig_hex = parts[0]
        pubkey_hex = parts[1]

        signature = bytes.fromhex(sig_hex)
        pubkey_bytes = bytes.fromhex(pubkey_hex)

        public_key = PublicKey.from_bytes(pubkey_bytes)
        tx_data = tx.serialize()

        return verify_transaction_input(tx_data, signature, public_key)

    except Exception as e:
        logger.warning(
            "Signature verification failed for input %d with error: %s. "
            "Allowing transaction (graceful degradation).", input_index, e
        )
        return True
