"""
Bitcoin transaction data structures.

This module implements the core transaction types used in Bitcoin:

- **TransactionOutput**: Represents a transaction output (TXO) with a value
  (in satoshis) and a locking script (pubkey_script) that specifies the
  conditions under which the output can be spent.

- **TransactionInput**: References a previous transaction output and provides
  an unlocking script (signature_script) to prove authorization to spend it.

- **Transaction**: A complete Bitcoin transaction consisting of a version,
  a list of inputs, a list of outputs, and a locktime. The transaction ID
  (txid) is the double SHA-256 hash of the serialized transaction displayed
  in reversed byte order (matching Bitcoin convention).

Serialization follows the Bitcoin wire protocol format with little-endian
integers and variable-length integer prefixes for lists and byte arrays.
"""

from __future__ import annotations

import hashlib
import struct
from typing import Optional

from src.utils.encoding import (
    bytes_to_hex,
    hex_to_bytes,
    int_to_little_endian,
    little_endian_to_int,
    encode_varint,
    decode_varint,
    base58check_encode,
)


def double_sha256(data: bytes) -> bytes:
    """Compute double SHA-256 hash as used in Bitcoin."""
    return hashlib.sha256(hashlib.sha256(data).digest()).digest()


# ---------------------------------------------------------------------------
# TransactionOutput
# ---------------------------------------------------------------------------

class TransactionOutput:
    """
    A transaction output assigns a value (in satoshis) to a locking script.

    In a P2PKH (Pay-to-Public-Key-Hash) transaction, the pubkey_script is
    the hex-encoded hash of the recipient's public key. The recipient must
    provide a valid signature and public key to spend this output.

    Attributes:
        value: Amount in satoshis (1 BTC = 100,000,000 satoshis).
        pubkey_script: Hex-encoded locking script / public key hash.
    """

    def __init__(self, value: int, pubkey_script: str):
        """
        Initialize a transaction output.

        Args:
            value: Amount in satoshis.
            pubkey_script: Hex-encoded locking script.
        """
        self.value = value
        self.pubkey_script = pubkey_script

    def serialize(self) -> bytes:
        """
        Serialize this output to binary format.

        Format:
            - value: 8 bytes, little-endian (int64)
            - script_length: varint
            - pubkey_script: raw bytes

        Returns:
            Serialized bytes.
        """
        result = int_to_little_endian(self.value, 8)
        script_bytes = hex_to_bytes(self.pubkey_script)
        result += encode_varint(len(script_bytes))
        result += script_bytes
        return result

    @classmethod
    def deserialize(cls, data: bytes, offset: int = 0) -> tuple:
        """
        Deserialize a TransactionOutput from binary data.

        Args:
            data: Raw bytes containing the serialized output.
            offset: Starting byte position.

        Returns:
            A tuple of (TransactionOutput, bytes_consumed).
        """
        start = offset

        value = little_endian_to_int(data[offset:offset + 8])
        offset += 8

        script_length, varint_size = decode_varint(data, offset)
        offset += varint_size

        script_bytes = data[offset:offset + script_length]
        pubkey_script = bytes_to_hex(script_bytes)
        offset += script_length

        return (cls(value=value, pubkey_script=pubkey_script), offset - start)

    def is_dust(self, threshold: int = 546) -> bool:
        """
        Check if this output is below the dust limit.

        Dust outputs are uneconomical to spend because the fee required to
        include them in a transaction exceeds their value. Bitcoin Core
        uses a default dust threshold of 546 satoshis for P2PKH outputs.

        Args:
            threshold: Minimum value in satoshis (default 546).

        Returns:
            True if the value is below the threshold.
        """
        return self.value < threshold

    def get_address(self) -> str:
        """
        Derive a Bitcoin address from the pubkey_script.

        Assumes a P2PKH script where pubkey_script is the hex-encoded
        20-byte public key hash. Encodes it with version byte 0x00
        (mainnet) using Base58Check.

        Returns:
            A Base58Check-encoded Bitcoin address string.
        """
        pubkey_hash = hex_to_bytes(self.pubkey_script)
        return base58check_encode(b'\x00', pubkey_hash)

    def to_dict(self) -> dict:
        """
        Convert this output to a JSON-serializable dictionary.

        Returns:
            Dictionary with 'value' and 'pubkey_script' keys.
        """
        return {
            'value': self.value,
            'pubkey_script': self.pubkey_script,
        }

    @classmethod
    def from_dict(cls, data: dict) -> TransactionOutput:
        """
        Reconstruct a TransactionOutput from a dictionary.

        Args:
            data: Dictionary as produced by ``to_dict()``.

        Returns:
            A new TransactionOutput instance.
        """
        return cls(
            value=data['value'],
            pubkey_script=data['pubkey_script'],
        )

    def __repr__(self) -> str:
        return (
            f"TransactionOutput(value={self.value}, "
            f"pubkey_script='{self.pubkey_script[:16]}...')"
        )


# ---------------------------------------------------------------------------
# TransactionInput
# ---------------------------------------------------------------------------

class TransactionInput:
    """
    A transaction input references a previous output and provides proof of
    authorization to spend it.

    The previous output is identified by its transaction ID and output index.
    The signature_script (also called scriptSig) contains the cryptographic
    signature and public key needed to satisfy the referenced output's
    locking script.

    Attributes:
        previous_txid: Hex-encoded transaction ID of the output being spent.
        previous_output_index: Index of the specific output in that transaction.
        signature_script: Hex-encoded unlocking script.
        sequence: Sequence number (default 0xffffffff for final).
    """

    def __init__(
        self,
        previous_txid: str,
        previous_output_index: int,
        signature_script: str = "",
        sequence: int = 0xffffffff,
    ):
        """
        Initialize a transaction input.

        Args:
            previous_txid: Hex string of the transaction ID being spent.
            previous_output_index: Output index within that transaction.
            signature_script: Hex-encoded unlocking script (default empty).
            sequence: Sequence number (default 0xffffffff).
        """
        self.previous_txid = previous_txid
        self.previous_output_index = previous_output_index
        self.signature_script = signature_script
        self.sequence = sequence

    def serialize(self) -> bytes:
        """
        Serialize this input to binary format.

        Format:
            - previous_txid: 32 bytes (reversed, as in Bitcoin wire format)
            - previous_output_index: 4 bytes, little-endian
            - script_length: varint
            - signature_script: raw bytes
            - sequence: 4 bytes, little-endian

        Returns:
            Serialized bytes.
        """
        # txid is stored in internal byte order (reversed from display)
        result = bytes.fromhex(self.previous_txid)[::-1]
        result += int_to_little_endian(self.previous_output_index, 4)

        if self.signature_script:
            script_bytes = hex_to_bytes(self.signature_script)
        else:
            script_bytes = b''
        result += encode_varint(len(script_bytes))
        result += script_bytes

        result += int_to_little_endian(self.sequence, 4)
        return result

    @classmethod
    def deserialize(cls, data: bytes, offset: int = 0) -> tuple:
        """
        Deserialize a TransactionInput from binary data.

        Args:
            data: Raw bytes containing the serialized input.
            offset: Starting byte position.

        Returns:
            A tuple of (TransactionInput, bytes_consumed).
        """
        start = offset

        # txid is in internal (reversed) byte order
        previous_txid = bytes_to_hex(data[offset:offset + 32][::-1])
        offset += 32

        previous_output_index = little_endian_to_int(data[offset:offset + 4])
        offset += 4

        script_length, varint_size = decode_varint(data, offset)
        offset += varint_size

        if script_length > 0:
            signature_script = bytes_to_hex(data[offset:offset + script_length])
        else:
            signature_script = ""
        offset += script_length

        sequence = little_endian_to_int(data[offset:offset + 4])
        offset += 4

        return (cls(
            previous_txid=previous_txid,
            previous_output_index=previous_output_index,
            signature_script=signature_script,
            sequence=sequence,
        ), offset - start)

    def is_coinbase(self) -> bool:
        """
        Check if this input is a coinbase input.

        A coinbase input has a previous_txid of all zeros and
        previous_output_index of 0xffffffff. Coinbase transactions
        create new bitcoins as mining rewards.

        Returns:
            True if this is a coinbase input.
        """
        return (
            self.previous_txid == "0" * 64
            and self.previous_output_index == 0xffffffff
        )

    def to_dict(self) -> dict:
        """
        Convert this input to a JSON-serializable dictionary.

        Returns:
            Dictionary with all input fields.
        """
        return {
            'previous_txid': self.previous_txid,
            'previous_output_index': self.previous_output_index,
            'signature_script': self.signature_script,
            'sequence': self.sequence,
        }

    @classmethod
    def from_dict(cls, data: dict) -> TransactionInput:
        """
        Reconstruct a TransactionInput from a dictionary.

        Args:
            data: Dictionary as produced by ``to_dict()``.

        Returns:
            A new TransactionInput instance.
        """
        return cls(
            previous_txid=data['previous_txid'],
            previous_output_index=data['previous_output_index'],
            signature_script=data.get('signature_script', ''),
            sequence=data.get('sequence', 0xffffffff),
        )

    def __repr__(self) -> str:
        return (
            f"TransactionInput(txid='{self.previous_txid[:16]}...', "
            f"index={self.previous_output_index})"
        )


# ---------------------------------------------------------------------------
# Transaction
# ---------------------------------------------------------------------------

class Transaction:
    """
    A complete Bitcoin transaction.

    A transaction transfers value by consuming existing unspent transaction
    outputs (UTXOs) via its inputs and creating new outputs. The difference
    between the total input value and total output value is the transaction
    fee, collected by the miner.

    The transaction ID (txid) is the double SHA-256 hash of the serialized
    transaction, displayed in reversed byte order following Bitcoin convention.

    Attributes:
        version: Transaction version number (default 1).
        inputs: List of TransactionInput objects.
        outputs: List of TransactionOutput objects.
        locktime: Earliest block/time when the tx can be included (default 0).
    """

    def __init__(
        self,
        version: int = 1,
        inputs: Optional[list] = None,
        outputs: Optional[list] = None,
        locktime: int = 0,
    ):
        """
        Initialize a transaction.

        Args:
            version: Transaction version (default 1).
            inputs: List of TransactionInput objects.
            outputs: List of TransactionOutput objects.
            locktime: Lock time (default 0, meaning no lock).
        """
        self.version = version
        self.inputs = inputs if inputs is not None else []
        self.outputs = outputs if outputs is not None else []
        self.locktime = locktime
        self._txid: Optional[str] = None

    @property
    def txid(self) -> str:
        """
        The transaction ID -- a unique identifier for this transaction.

        Computed as the double SHA-256 of the serialized transaction,
        displayed in reversed byte order (Bitcoin convention: the hash
        is computed in natural order but displayed with bytes reversed).

        Returns:
            64-character lowercase hex string.
        """
        if self._txid is None:
            self._txid = self.calculate_txid()
        return self._txid

    def calculate_txid(self) -> str:
        """
        Compute the transaction ID by double-hashing the serialized form.

        The raw hash bytes are reversed before hex-encoding to match the
        Bitcoin display convention where block and transaction hashes are
        shown with the most-significant byte first.

        Returns:
            64-character lowercase hex string.
        """
        serialized = self.serialize()
        hash_bytes = double_sha256(serialized)
        # Reverse byte order for display (Bitcoin convention)
        return bytes_to_hex(hash_bytes[::-1])

    def serialize(self) -> bytes:
        """
        Serialize this transaction to Bitcoin wire format.

        Format:
            - version: 4 bytes, little-endian
            - input_count: varint
            - inputs: serialized sequentially
            - output_count: varint
            - outputs: serialized sequentially
            - locktime: 4 bytes, little-endian

        Returns:
            Complete serialized transaction bytes.
        """
        result = int_to_little_endian(self.version, 4)

        result += encode_varint(len(self.inputs))
        for txin in self.inputs:
            result += txin.serialize()

        result += encode_varint(len(self.outputs))
        for txout in self.outputs:
            result += txout.serialize()

        result += int_to_little_endian(self.locktime, 4)
        return result

    @classmethod
    def deserialize(cls, data: bytes, offset: int = 0) -> tuple:
        """
        Deserialize a Transaction from binary data.

        Args:
            data: Raw bytes containing the serialized transaction.
            offset: Starting byte position.

        Returns:
            A tuple of (Transaction, bytes_consumed).
        """
        start = offset

        version = little_endian_to_int(data[offset:offset + 4])
        offset += 4

        input_count, varint_size = decode_varint(data, offset)
        offset += varint_size

        inputs = []
        for _ in range(input_count):
            txin, consumed = TransactionInput.deserialize(data, offset)
            inputs.append(txin)
            offset += consumed

        output_count, varint_size = decode_varint(data, offset)
        offset += varint_size

        outputs = []
        for _ in range(output_count):
            txout, consumed = TransactionOutput.deserialize(data, offset)
            outputs.append(txout)
            offset += consumed

        locktime = little_endian_to_int(data[offset:offset + 4])
        offset += 4

        return (cls(
            version=version,
            inputs=inputs,
            outputs=outputs,
            locktime=locktime,
        ), offset - start)

    def is_coinbase(self) -> bool:
        """
        Check if this is a coinbase transaction.

        A coinbase transaction has exactly one input whose previous_txid
        is all zeros and previous_output_index is 0xffffffff. It is the
        first transaction in every block and creates the block reward.

        Returns:
            True if this is a coinbase transaction.
        """
        return (
            len(self.inputs) == 1
            and self.inputs[0].is_coinbase()
        )

    def get_fee(self, utxo_set=None) -> int:
        """
        Calculate the transaction fee.

        The fee is the difference between the total input value and the
        total output value. For coinbase transactions, the fee is 0.

        Requires a UTXO set to look up the values of the inputs being spent.

        Args:
            utxo_set: A UTXOSet instance to look up input values.

        Returns:
            The fee in satoshis.

        Raises:
            ValueError: If an input references a non-existent UTXO.
        """
        if self.is_coinbase():
            return 0

        if utxo_set is None:
            raise ValueError("UTXO set required to calculate fee for non-coinbase transactions")

        total_input = 0
        for txin in self.inputs:
            utxo = utxo_set.get_utxo(txin.previous_txid, txin.previous_output_index)
            if utxo is None:
                raise ValueError(
                    f"Input references non-existent UTXO: "
                    f"{txin.previous_txid}:{txin.previous_output_index}"
                )
            total_input += utxo.value

        total_output = sum(txout.value for txout in self.outputs)

        return total_input - total_output

    def to_dict(self) -> dict:
        """
        Convert this transaction to a JSON-serializable dictionary.

        Returns:
            Dictionary with all transaction fields including the txid.
        """
        return {
            'version': self.version,
            'txid': self.txid,
            'inputs': [txin.to_dict() for txin in self.inputs],
            'outputs': [txout.to_dict() for txout in self.outputs],
            'locktime': self.locktime,
        }

    @classmethod
    def from_dict(cls, data: dict) -> Transaction:
        """
        Reconstruct a Transaction from a dictionary.

        Args:
            data: Dictionary as produced by ``to_dict()``.

        Returns:
            A new Transaction instance.
        """
        tx = cls(
            version=data['version'],
            inputs=[TransactionInput.from_dict(inp) for inp in data['inputs']],
            outputs=[TransactionOutput.from_dict(out) for out in data['outputs']],
            locktime=data.get('locktime', 0),
        )
        # Cache the txid if it was present in the dict to avoid recomputation
        if 'txid' in data:
            tx._txid = data['txid']
        return tx

    @staticmethod
    def create_coinbase(
        block_height: int,
        reward_address: str,
        reward_amount: int,
        extra_nonce: int = 0,
    ) -> Transaction:
        """
        Create a coinbase transaction for a new block.

        The coinbase transaction is the first transaction in every block.
        It has no real inputs -- instead, it has a single special input with
        a null previous txid and an output index of 0xffffffff. The
        signature_script field of the coinbase input contains the block
        height (BIP 34) and an optional extra nonce for additional mining
        entropy.

        Args:
            block_height: The height of the block this coinbase belongs to.
            reward_address: Hex-encoded public key hash of the miner receiving
                            the block reward.
            reward_amount: Total reward in satoshis (subsidy + fees).
            extra_nonce: Additional nonce value for mining (default 0).

        Returns:
            A new coinbase Transaction.
        """
        # Encode block height as little-endian bytes for the signature script
        # BIP 34 requires the block height to be serialized in the coinbase
        if block_height == 0:
            height_bytes = b'\x00'
        else:
            # Calculate minimum bytes needed
            byte_length = (block_height.bit_length() + 7) // 8
            height_bytes = block_height.to_bytes(byte_length, byteorder='little')

        # Script format: <height_length> <height> <extra_nonce_as_8_bytes>
        extra_nonce_bytes = extra_nonce.to_bytes(8, byteorder='little')
        coinbase_script = (
            bytes([len(height_bytes)]) + height_bytes + extra_nonce_bytes
        )

        coinbase_input = TransactionInput(
            previous_txid="0" * 64,
            previous_output_index=0xffffffff,
            signature_script=bytes_to_hex(coinbase_script),
            sequence=0xffffffff,
        )

        coinbase_output = TransactionOutput(
            value=reward_amount,
            pubkey_script=reward_address,
        )

        return Transaction(
            version=1,
            inputs=[coinbase_input],
            outputs=[coinbase_output],
            locktime=0,
        )

    def __repr__(self) -> str:
        return (
            f"Transaction(txid='{self.txid[:16]}...', "
            f"inputs={len(self.inputs)}, outputs={len(self.outputs)})"
        )

    def __eq__(self, other) -> bool:
        if not isinstance(other, Transaction):
            return NotImplemented
        return self.txid == other.txid

    def __hash__(self) -> int:
        return hash(self.txid)
