"""
Tests for Cryptographic Key Operations (Task 12.3)
====================================================

Tests cover:
- Private key generation (random and from bytes)
- Public key derivation
- ECDSA signing and verification
- Bitcoin address derivation
- WIF import/export
- KeyPair generation
"""

import pytest

from src.crypto.keys import PrivateKey, PublicKey, KeyPair


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def private_key():
    """A randomly generated private key."""
    return PrivateKey.generate()


@pytest.fixture
def deterministic_key():
    """A private key from known bytes for reproducible tests."""
    key_bytes = bytes(range(1, 33))  # 32 bytes: 0x01 through 0x20
    return PrivateKey(key_bytes)


@pytest.fixture
def keypair():
    """A randomly generated key pair."""
    return KeyPair.generate()


# ---------------------------------------------------------------------------
# PrivateKey Tests
# ---------------------------------------------------------------------------

class TestPrivateKey:
    """Tests for the PrivateKey class."""

    def test_generate_produces_32_bytes(self, private_key):
        """Generated private key should be exactly 32 bytes."""
        assert len(private_key.to_bytes()) == 32

    def test_generate_is_random(self):
        """Two generated keys should (almost certainly) be different."""
        k1 = PrivateKey.generate()
        k2 = PrivateKey.generate()
        assert k1.to_bytes() != k2.to_bytes()

    def test_from_bytes(self):
        """Creating a key from specific bytes should store those bytes."""
        key_bytes = b"\x01" * 32
        pk = PrivateKey(key_bytes)
        assert pk.to_bytes() == key_bytes

    def test_from_bytes_wrong_length(self):
        """Creating a key with wrong-length bytes should raise ValueError."""
        with pytest.raises(ValueError):
            PrivateKey(b"\x01" * 31)
        with pytest.raises(ValueError):
            PrivateKey(b"\x01" * 33)

    def test_to_hex(self, deterministic_key):
        """to_hex should produce a 64-character hex string."""
        hex_str = deterministic_key.to_hex()
        assert len(hex_str) == 64
        assert all(c in "0123456789abcdef" for c in hex_str)

    def test_from_hex(self, deterministic_key):
        """from_hex should reconstruct the key."""
        hex_str = deterministic_key.to_hex()
        restored = PrivateKey.from_hex(hex_str)
        assert restored.to_bytes() == deterministic_key.to_bytes()

    def test_public_key_derivation(self, private_key):
        """Deriving a public key should return a PublicKey instance."""
        pub = private_key.public_key
        assert isinstance(pub, PublicKey)

    def test_public_key_is_cached(self, private_key):
        """Repeated access to public_key should return the same object."""
        pub1 = private_key.public_key
        pub2 = private_key.public_key
        assert pub1 is pub2

    def test_sign_produces_bytes(self, private_key):
        """Signing should produce a non-empty bytes signature."""
        sig = private_key.sign(b"test message")
        assert isinstance(sig, bytes)
        assert len(sig) > 0

    def test_sign_different_messages_different_sigs(self, deterministic_key):
        """Signing different messages should produce different signatures."""
        sig1 = deterministic_key.sign(b"message one")
        sig2 = deterministic_key.sign(b"message two")
        # Different messages should (almost always) produce different signatures
        assert sig1 != sig2

    def test_wif_export_mainnet_compressed(self, private_key):
        """WIF export with compressed=True should start with 'K' or 'L'."""
        wif = private_key.to_wif(compressed=True, testnet=False)
        assert wif[0] in ("K", "L")

    def test_wif_export_mainnet_uncompressed(self, private_key):
        """WIF export with compressed=False should start with '5'."""
        wif = private_key.to_wif(compressed=False, testnet=False)
        assert wif[0] == "5"

    def test_wif_import_roundtrip(self, private_key):
        """Exporting to WIF and importing back should give the same key."""
        wif = private_key.to_wif(compressed=True, testnet=False)
        restored = PrivateKey.from_wif(wif)
        assert restored.to_bytes() == private_key.to_bytes()

    def test_wif_import_testnet(self, private_key):
        """WIF testnet roundtrip should work correctly."""
        wif = private_key.to_wif(compressed=True, testnet=True)
        assert wif[0] == "c"
        restored = PrivateKey.from_wif(wif)
        assert restored.to_bytes() == private_key.to_bytes()

    def test_wif_invalid(self):
        """Importing an invalid WIF string should raise ValueError."""
        with pytest.raises((ValueError, Exception)):
            PrivateKey.from_wif("invalid_wif_string_that_is_definitely_wrong")

    def test_equality(self, deterministic_key):
        """Two keys from the same bytes should be equal."""
        key_bytes = deterministic_key.to_bytes()
        other = PrivateKey(key_bytes)
        assert deterministic_key == other

    def test_inequality(self):
        """Two different keys should not be equal."""
        k1 = PrivateKey.generate()
        k2 = PrivateKey.generate()
        assert k1 != k2


# ---------------------------------------------------------------------------
# PublicKey Tests
# ---------------------------------------------------------------------------

class TestPublicKey:
    """Tests for the PublicKey class."""

    def test_compressed_is_33_bytes(self, private_key):
        """Compressed public key should be 33 bytes."""
        pub = private_key.public_key
        assert len(pub.to_bytes(compressed=True)) == 33

    def test_uncompressed_is_65_bytes(self, private_key):
        """Uncompressed public key should be 65 bytes."""
        pub = private_key.public_key
        assert len(pub.to_bytes(compressed=False)) == 65

    def test_compressed_prefix(self, private_key):
        """Compressed public key should start with 0x02 or 0x03."""
        pub_bytes = private_key.public_key.to_bytes(compressed=True)
        assert pub_bytes[0] in (0x02, 0x03)

    def test_uncompressed_prefix(self, private_key):
        """Uncompressed public key should start with 0x04."""
        pub_bytes = private_key.public_key.to_bytes(compressed=False)
        assert pub_bytes[0] == 0x04

    def test_to_hex_compressed(self, private_key):
        """Compressed hex should be 66 characters."""
        hex_str = private_key.public_key.to_hex(compressed=True)
        assert len(hex_str) == 66

    def test_verify_valid_signature(self, private_key):
        """Public key should verify a valid signature."""
        msg = b"verify this message"
        sig = private_key.sign(msg)
        assert private_key.public_key.verify(msg, sig) is True

    def test_verify_invalid_signature(self, private_key):
        """Public key should reject a tampered signature."""
        msg = b"verify this message"
        sig = private_key.sign(msg)
        # Tamper with the signature
        bad_sig = sig[:-1] + bytes([(sig[-1] + 1) % 256])
        assert private_key.public_key.verify(msg, bad_sig) is False

    def test_verify_wrong_message(self, private_key):
        """Signature should not verify against a different message."""
        sig = private_key.sign(b"original message")
        assert private_key.public_key.verify(b"different message", sig) is False

    def test_verify_wrong_key(self):
        """Signature should not verify against a different public key."""
        k1 = PrivateKey.generate()
        k2 = PrivateKey.generate()
        sig = k1.sign(b"test")
        assert k2.public_key.verify(b"test", sig) is False

    def test_to_address_mainnet(self, private_key):
        """Mainnet address should start with '1'."""
        address = private_key.public_key.to_address(testnet=False)
        assert address[0] == "1"
        assert len(address) >= 25  # Base58 addresses are 25-34 characters

    def test_to_address_testnet(self, private_key):
        """Testnet address should start with 'm' or 'n'."""
        address = private_key.public_key.to_address(testnet=True)
        assert address[0] in ("m", "n")

    def test_address_is_deterministic(self, deterministic_key):
        """Same key should always produce the same address."""
        addr1 = deterministic_key.public_key.to_address()
        addr2 = deterministic_key.public_key.to_address()
        assert addr1 == addr2

    def test_get_hash160(self, private_key):
        """get_hash160 should return a 40-character hex string."""
        h = private_key.public_key.get_hash160()
        assert len(h) == 40
        assert all(c in "0123456789abcdef" for c in h)

    def test_from_bytes_compressed(self, private_key):
        """PublicKey should be reconstructable from compressed bytes."""
        pub_bytes = private_key.public_key.to_bytes(compressed=True)
        restored = PublicKey.from_bytes(pub_bytes)
        assert restored.to_hex() == private_key.public_key.to_hex()

    def test_from_bytes_uncompressed(self, private_key):
        """PublicKey should be reconstructable from uncompressed bytes."""
        pub_bytes = private_key.public_key.to_bytes(compressed=False)
        restored = PublicKey.from_bytes(pub_bytes)
        assert restored.to_hex() == private_key.public_key.to_hex()

    def test_equality(self, deterministic_key):
        """Two public keys from the same private key should be equal."""
        pub1 = deterministic_key.public_key
        # Reconstruct from bytes
        pub2 = PublicKey.from_bytes(pub1.to_bytes())
        assert pub1 == pub2


# ---------------------------------------------------------------------------
# KeyPair Tests
# ---------------------------------------------------------------------------

class TestKeyPair:
    """Tests for the KeyPair class."""

    def test_generate(self, keypair):
        """KeyPair.generate() should produce valid components."""
        assert isinstance(keypair.private_key, PrivateKey)
        assert isinstance(keypair.public_key, PublicKey)
        assert isinstance(keypair.address, str)
        assert keypair.address[0] == "1"  # Mainnet address

    def test_address_matches_public_key(self, keypair):
        """The address should match what the public key would derive."""
        expected_address = keypair.public_key.to_address(testnet=False)
        assert keypair.address == expected_address

    def test_generate_unique(self):
        """Two generated key pairs should have different addresses."""
        kp1 = KeyPair.generate()
        kp2 = KeyPair.generate()
        assert kp1.address != kp2.address

    def test_repr(self, keypair):
        """repr should include the address."""
        r = repr(keypair)
        assert keypair.address in r
