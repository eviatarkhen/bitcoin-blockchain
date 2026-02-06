"""
Bitcoin binary serialization helpers.

This module serves as a convenience layer that re-exports the core encoding
functions used for binary serialization across the Bitcoin protocol. It also
provides high-level serialize/deserialize dispatch functions for blocks and
transactions.

The actual serialization logic lives in each data-structure class
(Transaction, Block, BlockHeader, etc.) via their `serialize()` and
`deserialize()` class methods. This module simply provides a unified entry
point and re-exports commonly used primitives.
"""

# Re-export encoding primitives so callers can do:
#   from src.utils.serialization import encode_varint, int_to_little_endian, ...
from src.utils.encoding import (
    bytes_to_hex,
    hex_to_bytes,
    int_to_little_endian,
    little_endian_to_int,
    int_to_big_endian,
    big_endian_to_int,
    encode_varint,
    decode_varint,
    base58_encode,
    base58_decode,
    base58check_encode,
    base58check_decode,
    double_sha256,
)


def serialize_transaction(tx) -> bytes:
    """
    Serialize a Transaction object to its binary representation.

    This is a convenience wrapper around ``tx.serialize()``.

    Args:
        tx: A Transaction instance.

    Returns:
        The serialized bytes of the transaction.
    """
    return tx.serialize()


def deserialize_transaction(data: bytes, offset: int = 0):
    """
    Deserialize a Transaction from binary data.

    This is a convenience wrapper that imports and delegates to
    ``Transaction.deserialize()``.

    Args:
        data: Raw bytes containing a serialized transaction.
        offset: Starting byte position within *data*.

    Returns:
        A tuple of (Transaction, bytes_consumed).
    """
    from src.core.transaction import Transaction
    return Transaction.deserialize(data, offset)


def serialize_block_header(header) -> bytes:
    """
    Serialize a BlockHeader to its 80-byte binary representation.

    This is a convenience wrapper around ``header.serialize()``.

    Args:
        header: A BlockHeader instance.

    Returns:
        Exactly 80 bytes representing the serialized header.
    """
    return header.serialize()


def deserialize_block_header(data: bytes, offset: int = 0):
    """
    Deserialize a BlockHeader from binary data.

    This is a convenience wrapper that imports and delegates to
    ``BlockHeader.deserialize()``.

    Args:
        data: Raw bytes containing a serialized block header.
        offset: Starting byte position within *data*.

    Returns:
        A tuple of (BlockHeader, bytes_consumed).
    """
    from src.core.block import BlockHeader
    return BlockHeader.deserialize(data, offset)


def serialize_block(block) -> bytes:
    """
    Serialize a full Block (header + transactions) to binary.

    Format: header (80 bytes) + varint(tx_count) + serialized transactions.

    Args:
        block: A Block instance.

    Returns:
        The serialized bytes of the entire block.
    """
    result = block.header.serialize()
    result += encode_varint(len(block.transactions))
    for tx in block.transactions:
        result += tx.serialize()
    return result


def deserialize_block(data: bytes, offset: int = 0):
    """
    Deserialize a full Block from binary data.

    Args:
        data: Raw bytes containing a serialized block.
        offset: Starting byte position within *data*.

    Returns:
        A tuple of (Block, bytes_consumed).
    """
    from src.core.block import Block, BlockHeader
    from src.core.transaction import Transaction

    start = offset

    header, header_size = BlockHeader.deserialize(data, offset)
    offset += header_size

    tx_count, varint_size = decode_varint(data, offset)
    offset += varint_size

    transactions = []
    for _ in range(tx_count):
        tx, tx_size = Transaction.deserialize(data, offset)
        transactions.append(tx)
        offset += tx_size

    block = Block(header=header, transactions=transactions)
    return (block, offset - start)
