"""
Bitcoin ECDSA Key Management, Signing, and Address Derivation
==============================================================

This module implements the Elliptic Curve Digital Signature Algorithm (ECDSA)
key management system used by Bitcoin, including:

- **Private keys**: 256-bit random numbers that serve as the secret component
  of the key pair. Whoever controls the private key controls the associated
  bitcoins. Private keys must be kept secret and never shared.

- **Public keys**: Points on the secp256k1 elliptic curve derived from the
  private key via elliptic curve point multiplication. Public keys can be
  shared freely and are used to verify signatures and derive addresses.

- **Digital signatures**: ECDSA signatures prove that the holder of a private
  key authorized a transaction without revealing the private key itself. This
  is the fundamental mechanism that secures Bitcoin ownership.

- **Bitcoin addresses**: Human-readable identifiers derived from public keys
  through a series of hash functions and Base58Check encoding. Addresses
  provide a layer of indirection that adds privacy and protects against
  potential future weaknesses in elliptic curve cryptography.

The secp256k1 Curve
--------------------
Bitcoin uses the secp256k1 elliptic curve, defined by the equation:
    y^2 = x^3 + 7  (mod p)

where p is a 256-bit prime. This curve was chosen by Satoshi Nakamoto,
likely because:
1. It was not designed by any government agency (unlike NIST curves)
2. Its parameters are derived in a verifiable way (not random)
3. It offers efficient computation

Wallet Import Format (WIF)
---------------------------
WIF is a Base58Check-encoded format for private keys that includes:
- A version byte (0x80 for mainnet, 0xef for testnet)
- The 32-byte private key
- An optional compression flag byte (0x01)
- A 4-byte checksum (first 4 bytes of double-SHA-256 of the above)
"""

import hashlib
import os

import base58
import ecdsa
from ecdsa import SECP256k1, SigningKey, VerifyingKey
from ecdsa.util import sigencode_der, sigdecode_der

from .hash import double_sha256, hash160


# =============================================================================
# Internal Helper Functions
# =============================================================================

def _base58check_encode(version: bytes, payload: bytes) -> str:
    """
    Encode data with Base58Check encoding used in Bitcoin.

    Base58Check encoding adds a version byte prefix and a 4-byte checksum
    suffix to the payload, then encodes the result using Base58.

    Base58 is like Base64 but omits characters that are easily confused:
    0 (zero), O (capital o), I (capital i), l (lowercase L), +, and /.
    This makes addresses easier to read and transcribe by hand.

    The checksum (first 4 bytes of double-SHA-256) detects typos in
    manually entered addresses.

    Args:
        version: The version byte(s) identifying the data type.
                 0x00 = mainnet address, 0x05 = mainnet P2SH,
                 0x6f = testnet address, 0x80 = mainnet WIF, etc.
        payload: The data to encode.

    Returns:
        The Base58Check-encoded string.
    """
    data = version + payload
    checksum = hashlib.sha256(hashlib.sha256(data).digest()).digest()[:4]
    return base58.b58encode(data + checksum).decode('ascii')


def _base58check_decode(encoded: str) -> tuple:
    """
    Decode a Base58Check-encoded string.

    Validates the checksum and separates the version byte from the payload.

    Args:
        encoded: The Base58Check-encoded string to decode.

    Returns:
        A tuple of (version_bytes, payload_bytes).

    Raises:
        ValueError: If the checksum does not match (invalid or corrupted data).
    """
    decoded = base58.b58decode(encoded)
    # Last 4 bytes are the checksum
    payload = decoded[:-4]
    checksum = decoded[-4:]
    expected = hashlib.sha256(hashlib.sha256(payload).digest()).digest()[:4]
    if checksum != expected:
        raise ValueError("Invalid Base58Check checksum")
    return payload[0:1], payload[1:]


# =============================================================================
# PublicKey Class
# =============================================================================

class PublicKey:
    """
    Represents a Bitcoin public key on the secp256k1 elliptic curve.

    A public key is a point (x, y) on the secp256k1 curve, derived from a
    private key via scalar multiplication: PublicKey = PrivateKey * G, where
    G is the curve's generator point.

    Public keys can be serialized in two formats:
    - **Uncompressed** (65 bytes): 0x04 || x (32 bytes) || y (32 bytes)
    - **Compressed** (33 bytes): (0x02 if y is even, 0x03 if y is odd) || x (32 bytes)

    Modern Bitcoin uses compressed keys exclusively because they are shorter
    and produce smaller transactions, but the code supports both formats for
    compatibility.
    """

    def __init__(self, key: VerifyingKey):
        """
        Initialize a PublicKey from an ecdsa VerifyingKey.

        Args:
            key: An ecdsa.VerifyingKey instance on the SECP256k1 curve.
        """
        self._key = key

    def verify(self, message: bytes, signature: bytes) -> bool:
        """
        Verify an ECDSA signature against a message.

        The message is first hashed with double SHA-256 (the same hash used
        during signing), and then the signature is verified against the hash.

        In Bitcoin, this is used to verify that a transaction input was
        authorized by the holder of the private key corresponding to this
        public key.

        Args:
            message: The original message bytes (will be double-SHA-256 hashed).
            signature: The DER-encoded ECDSA signature to verify.

        Returns:
            True if the signature is valid, False otherwise.
        """
        try:
            message_hash = double_sha256(message)
            self._key.verify_digest(signature, message_hash, sigdecode=sigdecode_der)
            return True
        except (ecdsa.BadSignatureError, ecdsa.BadDigestError, Exception):
            return False

    def to_bytes(self, compressed: bool = True) -> bytes:
        """
        Serialize the public key to bytes.

        Args:
            compressed: If True (default), return the 33-byte compressed format.
                       If False, return the 65-byte uncompressed format.

        Returns:
            The serialized public key bytes.

        Compressed format explanation:
            Since the curve equation y^2 = x^3 + 7 means every x coordinate
            has at most two valid y values (one even, one odd), we only need
            to store x and a single bit indicating which y to use. This saves
            32 bytes per public key.
        """
        # Get the raw uncompressed point (64 bytes: 32 for x, 32 for y)
        raw = self._key.to_string()
        x = raw[:32]
        y = raw[32:]

        if not compressed:
            # Uncompressed: 0x04 + x + y
            return b'\x04' + x + y

        # Compressed: check if y is even or odd
        if y[-1] % 2 == 0:
            return b'\x02' + x
        else:
            return b'\x03' + x

    def to_hex(self, compressed: bool = True) -> str:
        """
        Serialize the public key to a lowercase hex string.

        Args:
            compressed: If True (default), return the compressed format hex.

        Returns:
            The serialized public key as a lowercase hex string.
        """
        return self.to_bytes(compressed).hex()

    def to_address(self, testnet: bool = False) -> str:
        """
        Derive a Bitcoin P2PKH address from this public key.

        The address derivation process:
        1. Serialize the public key in compressed format (33 bytes)
        2. Compute hash160: RIPEMD-160(SHA-256(pubkey_bytes))  -> 20 bytes
        3. Prepend a version byte: 0x00 for mainnet, 0x6f for testnet
        4. Compute a checksum: first 4 bytes of double-SHA-256 of (version + hash)
        5. Base58 encode the whole thing: version + hash + checksum

        The resulting address is a human-readable string like "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"
        (the genesis block coinbase address).

        Addresses starting with '1' are mainnet P2PKH addresses.
        Addresses starting with 'm' or 'n' are testnet P2PKH addresses.

        Args:
            testnet: If True, generate a testnet address (version 0x6f).

        Returns:
            The Base58Check-encoded Bitcoin address string.
        """
        pubkey_bytes = self.to_bytes(compressed=True)
        h160 = hash160(pubkey_bytes)
        version = b'\x6f' if testnet else b'\x00'
        return _base58check_encode(version, h160)

    def get_hash160(self, compressed: bool = True) -> str:
        """
        Compute the hash160 of the public key and return it as hex.

        This 20-byte hash is what appears in P2PKH scriptPubKey scripts:
            OP_DUP OP_HASH160 <pubkey_hash> OP_EQUALVERIFY OP_CHECKSIG

        Args:
            compressed: If True, use the compressed public key.

        Returns:
            The hash160 as a lowercase hex string (40 characters).
        """
        pubkey_bytes = self.to_bytes(compressed=compressed)
        return hash160(pubkey_bytes).hex()

    @classmethod
    def from_bytes(cls, data: bytes) -> 'PublicKey':
        """
        Deserialize a public key from compressed or uncompressed bytes.

        Handles three formats:
        - 65 bytes starting with 0x04: uncompressed
        - 33 bytes starting with 0x02: compressed (even y)
        - 33 bytes starting with 0x03: compressed (odd y)

        For compressed keys, the full y coordinate is recovered from the
        curve equation y^2 = x^3 + 7 (mod p).

        Args:
            data: The serialized public key bytes.

        Returns:
            A PublicKey instance.

        Raises:
            ValueError: If the data format is not recognized.
        """
        if len(data) == 65 and data[0] == 0x04:
            # Uncompressed format: strip the 0x04 prefix
            key = VerifyingKey.from_string(data[1:], curve=SECP256k1)
            return cls(key)
        elif len(data) == 33 and data[0] in (0x02, 0x03):
            # Compressed format: recover y from x
            x = int.from_bytes(data[1:], 'big')
            p = SECP256k1.curve.p()

            # Compute y^2 = x^3 + 7 (mod p)
            y_squared = (pow(x, 3, p) + 7) % p

            # Compute modular square root using Tonelli-Shanks
            # For secp256k1, p % 4 == 3, so y = y_squared^((p+1)/4) mod p
            y = pow(y_squared, (p + 1) // 4, p)

            # Select the correct y based on the prefix byte
            if data[0] == 0x02 and y % 2 != 0:
                y = p - y
            elif data[0] == 0x03 and y % 2 == 0:
                y = p - y

            # Construct the uncompressed point (64 bytes: x + y)
            x_bytes = x.to_bytes(32, 'big')
            y_bytes = y.to_bytes(32, 'big')
            key = VerifyingKey.from_string(x_bytes + y_bytes, curve=SECP256k1)
            return cls(key)
        else:
            raise ValueError(
                f"Invalid public key format: expected 33 (compressed) or 65 "
                f"(uncompressed) bytes, got {len(data)} bytes with prefix "
                f"0x{data[0]:02x}" if data else "empty data"
            )

    def __repr__(self) -> str:
        return f"PublicKey({self.to_hex(compressed=True)})"

    def __eq__(self, other) -> bool:
        if not isinstance(other, PublicKey):
            return NotImplemented
        return self.to_bytes(compressed=True) == other.to_bytes(compressed=True)

    def __hash__(self) -> int:
        return hash(self.to_bytes(compressed=True))


# =============================================================================
# PrivateKey Class
# =============================================================================

class PrivateKey:
    """
    Represents a Bitcoin private key for the secp256k1 elliptic curve.

    A Bitcoin private key is simply a 256-bit (32-byte) random number within
    the valid range [1, n-1], where n is the order of the secp256k1 curve
    (approximately 1.158 * 10^77).

    The private key is the sole proof of ownership in Bitcoin. Anyone who
    knows a private key can spend all bitcoins associated with the
    corresponding public key/address. Private keys must be:
    - Generated with a cryptographically secure random number generator
    - Stored securely (encrypted, backed up)
    - Never shared or transmitted over insecure channels

    Wallet Import Format (WIF) provides a standardized way to represent
    private keys as Base58Check-encoded strings for import/export between
    wallet software.
    """

    def __init__(self, key_bytes: bytes = None):
        """
        Create a PrivateKey from raw bytes or generate a new random one.

        Args:
            key_bytes: Optional 32-byte private key. If None, a new random
                      key is securely generated using os.urandom().

        Raises:
            ValueError: If key_bytes is provided but not exactly 32 bytes.
        """
        if key_bytes is not None:
            if len(key_bytes) != 32:
                raise ValueError(
                    f"Private key must be exactly 32 bytes, got {len(key_bytes)}"
                )
            self._key = SigningKey.from_string(key_bytes, curve=SECP256k1)
        else:
            self._key = SigningKey.generate(curve=SECP256k1)
        self._public_key = None

    @property
    def public_key(self) -> PublicKey:
        """
        Derive and return the corresponding public key.

        The public key is computed from the private key using elliptic curve
        point multiplication: Q = d * G, where d is the private key scalar
        and G is the generator point of secp256k1.

        This operation is computationally easy (private -> public) but
        computationally infeasible to reverse (public -> private). This
        one-way property is the foundation of Bitcoin's security.

        The result is cached after first computation.

        Returns:
            The PublicKey corresponding to this private key.
        """
        if self._public_key is None:
            self._public_key = PublicKey(self._key.get_verifying_key())
        return self._public_key

    def sign(self, message: bytes) -> bytes:
        """
        Sign a message using ECDSA with this private key.

        The signing process:
        1. Compute the double-SHA-256 hash of the message
        2. Sign the 32-byte hash using ECDSA with the secp256k1 curve
        3. Return the signature in DER (Distinguished Encoding Rules) format

        DER encoding is the standard format for ECDSA signatures in Bitcoin
        transactions. A DER-encoded signature consists of:
        - 0x30 (compound structure marker)
        - Total length of the following data
        - 0x02 (integer marker for r)
        - Length of r
        - r value (big-endian integer)
        - 0x02 (integer marker for s)
        - Length of s
        - s value (big-endian integer)

        Args:
            message: The raw message bytes to sign.

        Returns:
            The DER-encoded ECDSA signature bytes.
        """
        message_hash = double_sha256(message)
        return self._key.sign_digest(message_hash, sigencode=sigencode_der)

    def to_bytes(self) -> bytes:
        """
        Return the raw 32-byte private key.

        Returns:
            The 32-byte private key scalar as bytes.
        """
        return self._key.to_string()

    def to_hex(self) -> str:
        """
        Return the private key as a lowercase hex string.

        Returns:
            The 64-character lowercase hex string of the private key.
        """
        return self.to_bytes().hex()

    def to_wif(self, compressed: bool = True, testnet: bool = False) -> str:
        """
        Export the private key in Wallet Import Format (WIF).

        WIF is a Base58Check-encoded representation of the private key that
        includes metadata about which network (mainnet/testnet) and which
        public key format (compressed/uncompressed) should be used.

        Encoding process:
        1. Start with a version byte: 0x80 (mainnet) or 0xef (testnet)
        2. Append the 32-byte raw private key
        3. If compressed: append 0x01 compression flag
        4. Compute 4-byte checksum (first 4 bytes of double-SHA-256)
        5. Base58 encode everything: version + key + [flag] + checksum

        WIF-compressed keys start with 'K' or 'L' on mainnet, 'c' on testnet.
        WIF-uncompressed keys start with '5' on mainnet, '9' on testnet.

        Args:
            compressed: If True (default), encode as a compressed WIF key.
            testnet: If True, use testnet version byte.

        Returns:
            The WIF-encoded private key string.
        """
        version = b'\xef' if testnet else b'\x80'
        payload = self.to_bytes()
        if compressed:
            payload += b'\x01'
        return _base58check_encode(version, payload)

    @classmethod
    def from_wif(cls, wif_string: str) -> 'PrivateKey':
        """
        Import a private key from Wallet Import Format (WIF).

        Decodes a WIF string and extracts the raw private key bytes.
        Validates the checksum to detect corruption or typos.

        Args:
            wif_string: The WIF-encoded private key string.

        Returns:
            A PrivateKey instance.

        Raises:
            ValueError: If the WIF string has an invalid checksum or format.
        """
        version, payload = _base58check_decode(wif_string)

        if version not in (b'\x80', b'\xef'):
            raise ValueError(
                f"Invalid WIF version byte: 0x{version.hex()}. "
                f"Expected 0x80 (mainnet) or 0xef (testnet)."
            )

        # If the key is compressed, the payload is 33 bytes (32 + 0x01 flag)
        if len(payload) == 33 and payload[-1] == 0x01:
            key_bytes = payload[:32]
        elif len(payload) == 32:
            key_bytes = payload
        else:
            raise ValueError(
                f"Invalid WIF payload length: {len(payload)}. "
                f"Expected 32 (uncompressed) or 33 (compressed) bytes."
            )

        return cls(key_bytes)

    @classmethod
    def from_hex(cls, hex_string: str) -> 'PrivateKey':
        """
        Create a PrivateKey from a hexadecimal string.

        Args:
            hex_string: A 64-character hex string representing 32 bytes.

        Returns:
            A PrivateKey instance.

        Raises:
            ValueError: If the hex string is invalid or wrong length.
        """
        key_bytes = bytes.fromhex(hex_string)
        return cls(key_bytes)

    @classmethod
    def generate(cls) -> 'PrivateKey':
        """
        Generate a new random private key.

        Uses the ecdsa library's key generation, which internally uses
        os.urandom() for cryptographically secure random bytes.

        Returns:
            A new randomly generated PrivateKey instance.
        """
        return cls()

    def __repr__(self) -> str:
        # Only show a partial fingerprint to discourage accidental exposure
        hex_str = self.to_hex()
        return f"PrivateKey({hex_str[:8]}...{hex_str[-8:]})"

    def __eq__(self, other) -> bool:
        if not isinstance(other, PrivateKey):
            return NotImplemented
        return self.to_bytes() == other.to_bytes()

    def __hash__(self) -> int:
        return hash(self.to_bytes())


# =============================================================================
# KeyPair Class
# =============================================================================

class KeyPair:
    """
    A convenience wrapper that holds a matched private key, public key,
    and derived Bitcoin address.

    In Bitcoin, a key pair is all you need to send and receive bitcoins:
    - The **address** (derived from the public key) is shared with others so
      they can send you bitcoins.
    - The **private key** is used to sign transactions that spend those bitcoins.
    - The **public key** is included in the spending transaction so nodes can
      verify the signature.
    """

    def __init__(self, private_key: PrivateKey, public_key: PublicKey, address: str):
        """
        Initialize a KeyPair with precomputed components.

        Args:
            private_key: The private key.
            public_key: The corresponding public key.
            address: The Bitcoin address derived from the public key.
        """
        self.private_key = private_key
        self.public_key = public_key
        self.address = address

    @classmethod
    def generate(cls) -> 'KeyPair':
        """
        Generate a new random key pair with its Bitcoin address.

        Returns:
            A KeyPair containing a fresh private key, its derived public key,
            and the corresponding mainnet P2PKH address.
        """
        private_key = PrivateKey.generate()
        public_key = private_key.public_key
        address = public_key.to_address(testnet=False)
        return cls(private_key, public_key, address)

    def __repr__(self) -> str:
        return f"KeyPair(address={self.address})"


# =============================================================================
# Transaction Signing and Verification Functions
# =============================================================================

def sign_transaction_input(tx_serialized: bytes, private_key: PrivateKey) -> bytes:
    """
    Sign a serialized transaction with a private key.

    In Bitcoin, each transaction input must be signed to prove that the spender
    controls the private key corresponding to the output being spent. The
    signing process involves:

    1. Serializing the transaction (with certain modifications depending on
       the signature hash type -- simplified here)
    2. Double-SHA-256 hashing the serialized transaction
    3. Signing the hash with the private key's ECDSA key

    This is a simplified implementation that signs the entire serialized
    transaction data. A full Bitcoin implementation would handle SIGHASH
    types (ALL, NONE, SINGLE, ANYONECANPAY) to control which parts of
    the transaction are covered by the signature.

    Args:
        tx_serialized: The serialized transaction bytes to sign.
        private_key: The PrivateKey to sign with.

    Returns:
        The DER-encoded ECDSA signature bytes.
    """
    return private_key.sign(tx_serialized)


def verify_transaction_input(
    tx_serialized: bytes,
    signature: bytes,
    public_key: PublicKey
) -> bool:
    """
    Verify a transaction signature against a public key.

    When a node receives a transaction, it must verify each input's signature
    to ensure the spender is authorized. This involves:

    1. Reconstructing the data that was signed (serialized transaction)
    2. Double-SHA-256 hashing it (same hash the signer used)
    3. Verifying the ECDSA signature against the hash and public key

    If verification succeeds, the node accepts the input as validly signed.
    If it fails, the entire transaction is rejected.

    Args:
        tx_serialized: The serialized transaction bytes that were signed.
        signature: The DER-encoded ECDSA signature to verify.
        public_key: The PublicKey to verify against.

    Returns:
        True if the signature is valid for the given transaction and key,
        False otherwise.
    """
    return public_key.verify(tx_serialized, signature)
