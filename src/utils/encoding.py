"""
Bitcoin encoding utilities.

This module provides fundamental encoding and decoding functions used throughout
the Bitcoin protocol, including:

- Hex/bytes conversions
- Little-endian and big-endian integer encoding
- Base58 and Base58Check encoding (used for Bitcoin addresses)
- Variable-length integer (varint) encoding (used in transaction/block serialization)

Bitcoin uses little-endian byte order for most serialized integer fields.
Base58Check encoding is used for addresses to provide a human-readable format
with a built-in checksum for error detection.
"""

from src.crypto.hash import double_sha256

# Base58 alphabet used by Bitcoin (excludes 0, O, I, l to avoid ambiguity)
BASE58_ALPHABET = '123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz'


# ---------------------------------------------------------------------------
# Hex / bytes conversions
# ---------------------------------------------------------------------------

def bytes_to_hex(data: bytes) -> str:
    """
    Convert bytes to a lowercase hex string.

    Args:
        data: The bytes to convert.

    Returns:
        Lowercase hexadecimal string representation.

    Example:
        >>> bytes_to_hex(b'\\xab\\xcd')
        'abcd'
    """
    return data.hex()


def hex_to_bytes(hex_string: str) -> bytes:
    """
    Convert a hex string to bytes.

    Args:
        hex_string: Hexadecimal string (with or without '0x' prefix).

    Returns:
        The decoded bytes.

    Raises:
        ValueError: If the string is not valid hex.

    Example:
        >>> hex_to_bytes('abcd')
        b'\\xab\\xcd'
    """
    if hex_string.startswith('0x') or hex_string.startswith('0X'):
        hex_string = hex_string[2:]
    return bytes.fromhex(hex_string)


# ---------------------------------------------------------------------------
# Endian conversions
# ---------------------------------------------------------------------------

def int_to_little_endian(value: int, length: int) -> bytes:
    """
    Encode an integer as little-endian bytes of the specified length.

    Bitcoin serializes most integer fields in little-endian byte order.

    Args:
        value: Non-negative integer to encode.
        length: Number of bytes in the output.

    Returns:
        Little-endian encoded bytes.

    Example:
        >>> int_to_little_endian(1, 4)
        b'\\x01\\x00\\x00\\x00'
    """
    return value.to_bytes(length, byteorder='little')


def little_endian_to_int(data: bytes) -> int:
    """
    Decode little-endian bytes to an integer.

    Args:
        data: Little-endian encoded bytes.

    Returns:
        The decoded integer value.

    Example:
        >>> little_endian_to_int(b'\\x01\\x00\\x00\\x00')
        1
    """
    return int.from_bytes(data, byteorder='little')


def int_to_big_endian(value: int, length: int) -> bytes:
    """
    Encode an integer as big-endian bytes of the specified length.

    Args:
        value: Non-negative integer to encode.
        length: Number of bytes in the output.

    Returns:
        Big-endian encoded bytes.

    Example:
        >>> int_to_big_endian(256, 4)
        b'\\x00\\x00\\x01\\x00'
    """
    return value.to_bytes(length, byteorder='big')


def big_endian_to_int(data: bytes) -> int:
    """
    Decode big-endian bytes to an integer.

    Args:
        data: Big-endian encoded bytes.

    Returns:
        The decoded integer value.

    Example:
        >>> big_endian_to_int(b'\\x00\\x00\\x01\\x00')
        256
    """
    return int.from_bytes(data, byteorder='big')


# ---------------------------------------------------------------------------
# Base58 encoding / decoding
# ---------------------------------------------------------------------------

def base58_encode(data: bytes) -> str:
    """
    Encode bytes using Base58 encoding (Bitcoin variant).

    Base58 is a binary-to-text encoding that uses a 58-character alphabet,
    avoiding characters that look similar (0, O, I, l) to prevent
    transcription errors. Leading zero bytes are preserved as '1' characters.

    Args:
        data: The bytes to encode.

    Returns:
        Base58 encoded string.

    Example:
        >>> base58_encode(b'\\x00\\x00hello')
        '11tzb1rNi'
    """
    # Count leading zero bytes -- each maps to a '1' in Base58
    num_leading_zeros = 0
    for byte in data:
        if byte == 0:
            num_leading_zeros += 1
        else:
            break

    # Convert bytes to a large integer
    num = int.from_bytes(data, byteorder='big')

    # Repeatedly divide by 58 to extract Base58 digits
    result = ''
    while num > 0:
        num, remainder = divmod(num, 58)
        result = BASE58_ALPHABET[remainder] + result

    # Prepend '1' for each leading zero byte
    return '1' * num_leading_zeros + result


def base58_decode(s: str) -> bytes:
    """
    Decode a Base58 encoded string back to bytes.

    Args:
        s: Base58 encoded string.

    Returns:
        The decoded bytes (including leading zero bytes for leading '1's).

    Raises:
        ValueError: If the string contains invalid Base58 characters.

    Example:
        >>> base58_decode('11tzb1rNi')
        b'\\x00\\x00hello'
    """
    # Count leading '1' characters (each represents a 0x00 byte)
    num_leading_ones = 0
    for char in s:
        if char == '1':
            num_leading_ones += 1
        else:
            break

    # Convert from Base58 to integer
    num = 0
    for char in s:
        if char not in BASE58_ALPHABET:
            raise ValueError(f"Invalid Base58 character: '{char}'")
        num = num * 58 + BASE58_ALPHABET.index(char)

    # Convert integer to bytes
    if num == 0:
        result = b''
    else:
        # Calculate the number of bytes needed
        byte_length = (num.bit_length() + 7) // 8
        result = num.to_bytes(byte_length, byteorder='big')

    # Prepend zero bytes for each leading '1'
    return b'\x00' * num_leading_ones + result


def base58check_encode(version: bytes, payload: bytes) -> str:
    """
    Encode data using Base58Check encoding with a version prefix and checksum.

    Base58Check adds error detection to Base58 by appending a 4-byte checksum
    derived from double SHA-256 hashing. This is used for Bitcoin addresses,
    private keys (WIF format), and extended keys.

    Format: Base58(version + payload + checksum)
    where checksum = first 4 bytes of double_sha256(version + payload)

    Args:
        version: Version byte(s) indicating the type of data
                 (e.g., b'\\x00' for mainnet P2PKH addresses).
        payload: The data to encode (e.g., 20-byte public key hash).

    Returns:
        Base58Check encoded string.

    Example:
        >>> # Encode a mainnet P2PKH address
        >>> base58check_encode(b'\\x00', bytes(20))
        '1111111111111111111114oLvT2'
    """
    data = version + payload
    checksum = double_sha256(data)[:4]
    return base58_encode(data + checksum)


def base58check_decode(s: str) -> tuple:
    """
    Decode a Base58Check encoded string, verifying the checksum.

    Args:
        s: Base58Check encoded string.

    Returns:
        A tuple of (version_bytes, payload_bytes).

    Raises:
        ValueError: If the checksum verification fails or data is too short.

    Example:
        >>> version, payload = base58check_decode('1111111111111111111114oLvT2')
        >>> version
        b'\\x00'
        >>> len(payload)
        20
    """
    data = base58_decode(s)

    if len(data) < 5:
        raise ValueError("Base58Check data too short (must be at least 5 bytes)")

    # Split into: version (1 byte) + payload + checksum (last 4 bytes)
    payload_with_version = data[:-4]
    checksum = data[-4:]

    # Verify the checksum
    expected_checksum = double_sha256(payload_with_version)[:4]
    if checksum != expected_checksum:
        raise ValueError(
            f"Base58Check checksum mismatch: "
            f"expected {expected_checksum.hex()}, got {checksum.hex()}"
        )

    version = payload_with_version[:1]
    payload = payload_with_version[1:]

    return (version, payload)


# ---------------------------------------------------------------------------
# Variable-length integer (varint) encoding
# ---------------------------------------------------------------------------

def encode_varint(value: int) -> bytes:
    """
    Encode an integer using Bitcoin's variable-length integer format.

    Bitcoin uses a compact encoding for integers that appear frequently
    in serialized data (e.g., the number of inputs/outputs in a transaction).

    Encoding rules:
    - 0x00-0xfc:       1 byte  (the value itself)
    - 0xfd-0xffff:     3 bytes (0xfd prefix + 2-byte little-endian)
    - 0x10000-0xffffffff: 5 bytes (0xfe prefix + 4-byte little-endian)
    - Larger:           9 bytes (0xff prefix + 8-byte little-endian)

    Args:
        value: Non-negative integer to encode.

    Returns:
        Variable-length encoded bytes.

    Raises:
        ValueError: If value is negative.

    Example:
        >>> encode_varint(252).hex()
        'fc'
        >>> encode_varint(255).hex()
        'fdff00'
    """
    if value < 0:
        raise ValueError(f"Varint value must be non-negative, got {value}")

    if value < 0xfd:
        return bytes([value])
    elif value <= 0xffff:
        return b'\xfd' + int_to_little_endian(value, 2)
    elif value <= 0xffffffff:
        return b'\xfe' + int_to_little_endian(value, 4)
    else:
        return b'\xff' + int_to_little_endian(value, 8)


def decode_varint(data: bytes, offset: int = 0) -> tuple:
    """
    Decode a Bitcoin variable-length integer from a byte stream.

    Args:
        data: The byte buffer containing the varint.
        offset: Starting position in the buffer.

    Returns:
        A tuple of (decoded_value, number_of_bytes_consumed).

    Raises:
        ValueError: If there are not enough bytes to decode.

    Example:
        >>> decode_varint(b'\\xfc')
        (252, 1)
        >>> decode_varint(b'\\xfd\\xff\\x00')
        (255, 3)
    """
    if offset >= len(data):
        raise ValueError("Not enough data to decode varint")

    first_byte = data[offset]

    if first_byte < 0xfd:
        return (first_byte, 1)
    elif first_byte == 0xfd:
        if offset + 3 > len(data):
            raise ValueError("Not enough data for 2-byte varint")
        value = little_endian_to_int(data[offset + 1:offset + 3])
        return (value, 3)
    elif first_byte == 0xfe:
        if offset + 5 > len(data):
            raise ValueError("Not enough data for 4-byte varint")
        value = little_endian_to_int(data[offset + 1:offset + 5])
        return (value, 5)
    else:  # 0xff
        if offset + 9 > len(data):
            raise ValueError("Not enough data for 8-byte varint")
        value = little_endian_to_int(data[offset + 1:offset + 9])
        return (value, 9)
