"""
Bitcoin block data structures.

This module implements the two core structures that make up a Bitcoin block:

- **BlockHeader**: The fixed 80-byte header containing the protocol version,
  a reference to the previous block, the Merkle root of all transactions,
  a timestamp, the difficulty target in compact form, and the mining nonce.

- **Block**: A full block consisting of a header and a list of transactions.
  The first transaction is always the coinbase transaction that creates
  the block reward.

The block hash is the double SHA-256 of the serialized 80-byte header,
displayed in reversed byte order following Bitcoin convention (so the hash
appears to have leading zeros when the block meets its difficulty target).
"""

from __future__ import annotations

import hashlib
from typing import Optional

from src.utils.encoding import (
    bytes_to_hex,
    hex_to_bytes,
    int_to_little_endian,
    little_endian_to_int,
    encode_varint,
    decode_varint,
)
from src.core.transaction import Transaction


def double_sha256(data: bytes) -> bytes:
    """Compute double SHA-256 hash as used in Bitcoin."""
    return hashlib.sha256(hashlib.sha256(data).digest()).digest()


# ---------------------------------------------------------------------------
# BlockHeader
# ---------------------------------------------------------------------------

class BlockHeader:
    """
    The 80-byte block header that miners hash to find a valid proof-of-work.

    Fields (total 80 bytes when serialized):
        - version (4 bytes): Protocol version.
        - previous_block_hash (32 bytes): Hash of the preceding block.
        - merkle_root (32 bytes): Root of the Merkle tree of transaction hashes.
        - timestamp (4 bytes): Approximate creation time (Unix epoch).
        - difficulty_bits (4 bytes): Compact representation of the target.
        - nonce (4 bytes): Value miners vary to find a valid hash.

    All integer fields are serialized in little-endian byte order. Hash fields
    (previous_block_hash, merkle_root) are stored in internal byte order
    (natural hash output) during serialization but displayed in reversed order.

    Attributes:
        version: Protocol version number.
        previous_block_hash: Hex-encoded hash of the previous block (display order).
        merkle_root: Hex-encoded Merkle root (display order).
        timestamp: Unix timestamp.
        difficulty_bits: Compact difficulty target.
        nonce: Mining nonce.
    """

    def __init__(
        self,
        version: int = 1,
        previous_block_hash: str = "0" * 64,
        merkle_root: str = "0" * 64,
        timestamp: int = 0,
        difficulty_bits: int = 0x1d00ffff,
        nonce: int = 0,
    ):
        """
        Initialize a block header.

        Args:
            version: Protocol version (default 1).
            previous_block_hash: Hex hash of previous block (default genesis zero hash).
            merkle_root: Hex Merkle root of transactions.
            timestamp: Unix timestamp of block creation.
            difficulty_bits: Compact difficulty target.
            nonce: Mining nonce (default 0).
        """
        self.version = version
        self.previous_block_hash = previous_block_hash
        self.merkle_root = merkle_root
        self.timestamp = timestamp
        self.difficulty_bits = difficulty_bits
        self.nonce = nonce
        self._hash: Optional[str] = None

    @property
    def hash(self) -> str:
        """
        The block hash -- the primary identifier for this block.

        Computed as the double SHA-256 of the serialized 80-byte header,
        with the resulting bytes reversed for display (Bitcoin convention).
        A valid block's hash will have leading zeros when the nonce satisfies
        the proof-of-work difficulty target.

        Returns:
            64-character lowercase hex string.
        """
        if self._hash is None:
            self._hash = self.calculate_hash()
        return self._hash

    def calculate_hash(self) -> str:
        """
        Compute the block hash from the serialized header.

        Returns:
            64-character lowercase hex string (reversed byte order).
        """
        serialized = self.serialize()
        hash_bytes = double_sha256(serialized)
        # Reverse byte order for display (Bitcoin convention)
        return bytes_to_hex(hash_bytes[::-1])

    def serialize(self) -> bytes:
        """
        Serialize this header to exactly 80 bytes.

        Format (all little-endian):
            - version: 4 bytes
            - previous_block_hash: 32 bytes (internal byte order = reversed display)
            - merkle_root: 32 bytes (internal byte order = reversed display)
            - timestamp: 4 bytes
            - difficulty_bits: 4 bytes
            - nonce: 4 bytes

        Returns:
            Exactly 80 bytes.
        """
        result = int_to_little_endian(self.version, 4)
        # Hash fields are stored in internal byte order (reversed from display)
        result += hex_to_bytes(self.previous_block_hash)[::-1]
        result += hex_to_bytes(self.merkle_root)[::-1]
        result += int_to_little_endian(self.timestamp, 4)
        result += int_to_little_endian(self.difficulty_bits, 4)
        result += int_to_little_endian(self.nonce, 4)
        return result

    @classmethod
    def deserialize(cls, data: bytes, offset: int = 0) -> tuple:
        """
        Deserialize a BlockHeader from binary data.

        Args:
            data: Raw bytes containing at least 80 bytes from offset.
            offset: Starting byte position.

        Returns:
            A tuple of (BlockHeader, bytes_consumed) where bytes_consumed is 80.

        Raises:
            ValueError: If there are fewer than 80 bytes available.
        """
        if len(data) - offset < 80:
            raise ValueError(
                f"Not enough data to deserialize BlockHeader: "
                f"need 80 bytes, have {len(data) - offset}"
            )

        start = offset

        version = little_endian_to_int(data[offset:offset + 4])
        offset += 4

        # Reverse from internal byte order to display order
        previous_block_hash = bytes_to_hex(data[offset:offset + 32][::-1])
        offset += 32

        merkle_root = bytes_to_hex(data[offset:offset + 32][::-1])
        offset += 32

        timestamp = little_endian_to_int(data[offset:offset + 4])
        offset += 4

        difficulty_bits = little_endian_to_int(data[offset:offset + 4])
        offset += 4

        nonce = little_endian_to_int(data[offset:offset + 4])
        offset += 4

        return (cls(
            version=version,
            previous_block_hash=previous_block_hash,
            merkle_root=merkle_root,
            timestamp=timestamp,
            difficulty_bits=difficulty_bits,
            nonce=nonce,
        ), offset - start)

    def get_target(self) -> int:
        """
        Convert the compact difficulty_bits to a full 256-bit target value.

        The compact format encodes the target as:
            target = coefficient * 2^(8 * (exponent - 3))

        where:
            - exponent = first byte of difficulty_bits
            - coefficient = remaining 3 bytes of difficulty_bits

        A block's hash (interpreted as a 256-bit integer) must be less than
        this target for the block to be valid.

        Returns:
            The 256-bit target as a Python integer.
        """
        # Extract the exponent (number of bytes) and coefficient
        exponent = (self.difficulty_bits >> 24) & 0xff
        coefficient = self.difficulty_bits & 0x007fffff

        # Handle the sign bit (bit 23 of coefficient) -- in Bitcoin,
        # if set, the target is negative, which we treat as zero
        if self.difficulty_bits & 0x00800000:
            coefficient = -coefficient

        if exponent <= 3:
            target = coefficient >> (8 * (3 - exponent))
        else:
            target = coefficient << (8 * (exponent - 3))

        # Target cannot be negative or exceed 2^256
        return max(0, target)

    def meets_difficulty_target(self) -> bool:
        """
        Check whether this block's hash satisfies the difficulty target.

        The block hash (as a 256-bit big-endian integer) must be less than
        or equal to the target derived from difficulty_bits.

        Returns:
            True if the block hash meets the difficulty requirement.
        """
        target = self.get_target()
        # Convert the block hash to an integer for comparison
        # The hash is in display order (big-endian), so interpret directly
        block_hash_int = int(self.hash, 16)
        return block_hash_int <= target

    def to_dict(self) -> dict:
        """
        Convert this header to a JSON-serializable dictionary.

        Returns:
            Dictionary with all header fields and the computed hash.
        """
        return {
            'version': self.version,
            'previous_block_hash': self.previous_block_hash,
            'merkle_root': self.merkle_root,
            'timestamp': self.timestamp,
            'difficulty_bits': self.difficulty_bits,
            'nonce': self.nonce,
            'hash': self.hash,
        }

    @classmethod
    def from_dict(cls, data: dict) -> BlockHeader:
        """
        Reconstruct a BlockHeader from a dictionary.

        Args:
            data: Dictionary as produced by ``to_dict()``.

        Returns:
            A new BlockHeader instance.
        """
        header = cls(
            version=data['version'],
            previous_block_hash=data['previous_block_hash'],
            merkle_root=data['merkle_root'],
            timestamp=data['timestamp'],
            difficulty_bits=data['difficulty_bits'],
            nonce=data['nonce'],
        )
        # Cache the hash if it was present
        if 'hash' in data:
            header._hash = data['hash']
        return header

    def __repr__(self) -> str:
        return (
            f"BlockHeader(hash='{self.hash[:16]}...', "
            f"height=?, nonce={self.nonce})"
        )

    def __eq__(self, other) -> bool:
        if not isinstance(other, BlockHeader):
            return NotImplemented
        return self.hash == other.hash

    def __hash__(self) -> int:
        return hash(self.hash)


# ---------------------------------------------------------------------------
# Block
# ---------------------------------------------------------------------------

class Block:
    """
    A complete Bitcoin block consisting of a header and a list of transactions.

    The block's Merkle root ties the header to its transactions: changing
    any transaction changes the Merkle root, which changes the header hash,
    invalidating the proof-of-work. This is how Bitcoin ensures transaction
    integrity.

    The first transaction in every block is the coinbase transaction, which
    creates new bitcoins as the mining reward.

    Attributes:
        header: The block's 80-byte header.
        transactions: List of transactions included in the block.
    """

    def __init__(
        self,
        header: Optional[BlockHeader] = None,
        transactions: Optional[list] = None,
    ):
        """
        Initialize a block.

        Args:
            header: A BlockHeader instance (creates a default if None).
            transactions: List of Transaction instances (default empty).
        """
        self.header = header if header is not None else BlockHeader()
        self.transactions = transactions if transactions is not None else []
        self._height: Optional[int] = None

    @property
    def height(self) -> Optional[int]:
        """
        The block's position in the blockchain (0 for genesis).

        This is set externally by the blockchain when the block is added
        to the chain, as height is not stored in the block itself.

        Returns:
            Block height, or None if not yet assigned.
        """
        return self._height

    @height.setter
    def height(self, value: int):
        """Set the block height."""
        self._height = value

    def calculate_merkle_root(self) -> str:
        """
        Build a Merkle tree from the transaction IDs and return the root hash.

        The Merkle tree is a binary hash tree where:
        1. Leaf nodes are the double SHA-256 hashes of the transactions (txids).
        2. Internal nodes are the double SHA-256 of the concatenation of
           their two children.
        3. If a level has an odd number of nodes, the last node is duplicated.

        Special cases:
        - No transactions: returns "0" * 64.
        - Single transaction: returns the transaction's txid.

        Returns:
            64-character lowercase hex string of the Merkle root.
        """
        if not self.transactions:
            return "0" * 64

        if len(self.transactions) == 1:
            return self.transactions[0].txid

        # Start with transaction hashes in internal byte order (reversed txid)
        # Merkle tree operations use the raw hash bytes (internal order)
        current_level = []
        for tx in self.transactions:
            # txid is in display order (reversed); convert to internal order
            tx_hash = hex_to_bytes(tx.txid)[::-1]
            current_level.append(tx_hash)

        # Build the tree bottom-up
        while len(current_level) > 1:
            next_level = []

            # If odd number of hashes, duplicate the last one
            if len(current_level) % 2 != 0:
                current_level.append(current_level[-1])

            # Hash pairs together
            for i in range(0, len(current_level), 2):
                combined = current_level[i] + current_level[i + 1]
                next_level.append(double_sha256(combined))

            current_level = next_level

        # The root is in internal byte order; reverse to display order
        return bytes_to_hex(current_level[0][::-1])

    def add_transaction(self, tx: Transaction):
        """
        Append a transaction to this block.

        Invalidates the cached Merkle root and block hash since the
        transaction set has changed.

        Args:
            tx: The Transaction to add.
        """
        self.transactions.append(tx)
        # Invalidate cached values
        self.header.merkle_root = self.calculate_merkle_root()
        self.header._hash = None

    def get_size(self) -> int:
        """
        Calculate the total serialized size of this block in bytes.

        The size includes the 80-byte header, the varint encoding of the
        transaction count, and all serialized transactions.

        Returns:
            Total size in bytes.
        """
        size = 80  # Header is always 80 bytes
        size += len(encode_varint(len(self.transactions)))
        for tx in self.transactions:
            size += len(tx.serialize())
        return size

    def get_coinbase(self) -> Optional[Transaction]:
        """
        Return the coinbase transaction if present.

        The coinbase transaction is always the first transaction in a block
        and can be identified by its special null input.

        Returns:
            The coinbase Transaction, or None if the block has no transactions
            or the first transaction is not a coinbase.
        """
        if self.transactions and self.transactions[0].is_coinbase():
            return self.transactions[0]
        return None

    def to_dict(self) -> dict:
        """
        Convert this block to a JSON-serializable dictionary.

        Returns:
            Dictionary with header, transactions, and metadata.
        """
        return {
            'header': self.header.to_dict(),
            'transactions': [tx.to_dict() for tx in self.transactions],
            'height': self._height,
            'size': self.get_size(),
            'tx_count': len(self.transactions),
        }

    @classmethod
    def from_dict(cls, data: dict) -> Block:
        """
        Reconstruct a Block from a dictionary.

        Args:
            data: Dictionary as produced by ``to_dict()``.

        Returns:
            A new Block instance.
        """
        header = BlockHeader.from_dict(data['header'])
        transactions = [
            Transaction.from_dict(tx_data)
            for tx_data in data['transactions']
        ]
        block = cls(header=header, transactions=transactions)
        if data.get('height') is not None:
            block._height = data['height']
        return block

    def __repr__(self) -> str:
        return (
            f"Block(hash='{self.header.hash[:16]}...', "
            f"height={self._height}, "
            f"txs={len(self.transactions)})"
        )

    def __eq__(self, other) -> bool:
        if not isinstance(other, Block):
            return NotImplemented
        return self.header.hash == other.header.hash

    def __hash__(self) -> int:
        return hash(self.header.hash)
