"""
Bitcoin Cryptographic Hash Functions
=====================================

This module implements the core hash functions used throughout the Bitcoin protocol.

Bitcoin relies heavily on two hash functions:
- **SHA-256**: The primary hash function used for block headers, transaction IDs,
  and as a building block for other hash constructions.
- **RIPEMD-160**: Used in combination with SHA-256 to create shorter (160-bit)
  hashes for Bitcoin addresses.

Key constructions:
- **double SHA-256** (also called hash256): SHA-256 applied twice. Bitcoin uses this
  for block header hashing and transaction ID computation. The double application
  provides protection against length-extension attacks.
- **hash160**: RIPEMD-160(SHA-256(data)). Used to derive the 20-byte hash that
  forms the core of a Bitcoin address. The combination of two different hash
  functions provides defense-in-depth: even if one is broken, the other still
  provides security.
"""

import hashlib


def sha256(data: bytes) -> bytes:
    """
    Compute the SHA-256 hash of the input data.

    SHA-256 (Secure Hash Algorithm 256-bit) produces a 32-byte (256-bit) digest.
    It is the fundamental hash function in Bitcoin, used for mining, transaction
    IDs, and as a building block for hash160 and double-SHA-256.

    Args:
        data: The raw bytes to hash.

    Returns:
        The 32-byte SHA-256 digest.

    Example:
        >>> sha256(b"hello").hex()
        '2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824'
    """
    return hashlib.sha256(data).digest()


def double_sha256(data: bytes) -> bytes:
    """
    Compute the double SHA-256 hash: SHA-256(SHA-256(data)).

    Bitcoin uses double SHA-256 (sometimes called hash256) extensively:
    - Block header hashing for proof-of-work
    - Transaction ID (txid) computation
    - Merkle tree node hashing

    The double application mitigates length-extension attacks that single SHA-256
    is vulnerable to. In a length-extension attack, an attacker who knows H(m)
    can compute H(m || padding || m') without knowing m. Double hashing prevents
    this because the inner hash output is a fixed-size input to the outer hash.

    Args:
        data: The raw bytes to hash.

    Returns:
        The 32-byte double-SHA-256 digest.

    Example:
        >>> double_sha256(b"hello").hex()
        '9595c9df90075148eb06860365df33584b75bff782a510c6cd4883a419833d50'
    """
    return hashlib.sha256(hashlib.sha256(data).digest()).digest()


def hash256(data: bytes) -> str:
    """
    Compute the double SHA-256 hash and return it as a lowercase hex string.

    This is a convenience wrapper around double_sha256() that returns the result
    as a hexadecimal string, which is useful for display and comparison purposes.

    Args:
        data: The raw bytes to hash.

    Returns:
        The double-SHA-256 digest as a lowercase hex string (64 characters).

    Example:
        >>> hash256(b"hello")
        '9595c9df90075148eb06860365df33584b75bff782a510c6cd4883a419833d50'
    """
    return double_sha256(data).hex()


def ripemd160(data: bytes) -> bytes:
    """
    Compute the RIPEMD-160 hash of the input data.

    RIPEMD-160 (RACE Integrity Primitives Evaluation Message Digest) produces
    a 20-byte (160-bit) digest. In Bitcoin, it is never used alone but always
    in combination with SHA-256 as part of hash160.

    RIPEMD-160 was chosen for Bitcoin addresses because:
    1. It produces a shorter hash (160 bits vs 256 bits), making addresses shorter
    2. It is from a different hash function family than SHA-256, providing
       defense-in-depth against potential future cryptanalytic breakthroughs

    Args:
        data: The raw bytes to hash.

    Returns:
        The 20-byte RIPEMD-160 digest.

    Example:
        >>> ripemd160(b"hello").hex()
        '108f07b8382412612c048d07d13f814118445acd'
    """
    return hashlib.new('ripemd160', data).digest()


def hash160(data: bytes) -> bytes:
    """
    Compute hash160: RIPEMD-160(SHA-256(data)).

    This is the hash construction used to derive the 20-byte payload of a
    Bitcoin address from a public key. The process is:
    1. SHA-256 the public key bytes to get a 32-byte hash
    2. RIPEMD-160 the SHA-256 result to get a 20-byte hash

    The resulting 20-byte value is called the "public key hash" (PKH) and is
    the core component of a P2PKH (Pay-to-Public-Key-Hash) Bitcoin address.

    Args:
        data: The raw bytes to hash (typically a serialized public key).

    Returns:
        The 20-byte hash160 digest.

    Example:
        >>> hash160(b"hello").hex()
        'b6a9c8c230722b7c748331a8b450f05566dc7d0f'
    """
    return ripemd160(sha256(data))


def hash160_hex(data: bytes) -> str:
    """
    Compute hash160 and return the result as a lowercase hex string.

    This is a convenience wrapper around hash160() that returns the result
    as a hexadecimal string. Useful for embedding in scripts or displaying
    the public key hash component of an address.

    Args:
        data: The raw bytes to hash (typically a serialized public key).

    Returns:
        The hash160 digest as a lowercase hex string (40 characters).

    Example:
        >>> hash160_hex(b"hello")
        'b6a9c8c230722b7c748331a8b450f05566dc7d0f'
    """
    return hash160(data).hex()
