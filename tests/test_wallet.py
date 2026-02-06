"""
Tests for Wallet (Task 12.7)
==============================

Tests cover:
- Address generation
- Key management (import/export)
- Balance calculation
- Coin selection
- Transaction creation
- Transaction signing
- send() convenience method
"""

import sys

sys.path.insert(0, "/home/user/bitcoin-blockchain")

import pytest

from src.wallet.wallet import Wallet
from src.crypto.keys import PrivateKey, KeyPair
from src.core.blockchain import Blockchain
from src.core.transaction import Transaction


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def blockchain():
    """A fresh blockchain in development mode."""
    return Blockchain(development_mode=True)


@pytest.fixture
def wallet(blockchain):
    """A wallet connected to a blockchain."""
    return Wallet(blockchain=blockchain, name="test_wallet")


@pytest.fixture
def funded_wallet(blockchain):
    """A wallet with some BTC from mining."""
    w = Wallet(blockchain=blockchain, name="funded")
    address = w.generate_address()
    keypair = w.get_keypair(address)
    pubkey_hash = keypair.public_key.get_hash160()

    # Mine 3 blocks to give the wallet some funds
    for _ in range(3):
        blockchain.mine_next_block(coinbase_address=pubkey_hash)

    return w


@pytest.fixture
def recipient_wallet(blockchain):
    """A recipient wallet for transaction tests."""
    w = Wallet(blockchain=blockchain, name="recipient")
    w.generate_address()
    return w


# ---------------------------------------------------------------------------
# Key Management Tests
# ---------------------------------------------------------------------------

class TestKeyManagement:
    """Tests for wallet key management."""

    def test_generate_address(self, wallet):
        """generate_address should return a valid Bitcoin address."""
        address = wallet.generate_address()
        assert isinstance(address, str)
        assert len(address) > 0
        assert address[0] == "1"  # Mainnet address

    def test_generate_multiple_addresses(self, wallet):
        """Each generated address should be unique."""
        addr1 = wallet.generate_address()
        addr2 = wallet.generate_address()
        assert addr1 != addr2

    def test_get_addresses(self, wallet):
        """get_addresses should return all generated addresses."""
        wallet.generate_address()
        wallet.generate_address()
        addresses = wallet.get_addresses()
        assert len(addresses) == 2

    def test_has_address(self, wallet):
        """has_address should return True for wallet addresses."""
        address = wallet.generate_address()
        assert wallet.has_address(address) is True
        assert wallet.has_address("1NonExistentAddress") is False

    def test_get_keypair(self, wallet):
        """get_keypair should return the correct KeyPair."""
        address = wallet.generate_address()
        keypair = wallet.get_keypair(address)
        assert keypair is not None
        assert isinstance(keypair, KeyPair)
        assert keypair.address == address

    def test_get_keypair_nonexistent(self, wallet):
        """get_keypair for a non-wallet address should return None."""
        assert wallet.get_keypair("1NonExistent") is None


# ---------------------------------------------------------------------------
# Import/Export Tests
# ---------------------------------------------------------------------------

class TestImportExport:
    """Tests for WIF import/export."""

    def test_export_private_key(self, wallet):
        """export_private_key should return a WIF string."""
        address = wallet.generate_address()
        wif = wallet.export_private_key(address)
        assert isinstance(wif, str)
        assert wif[0] in ("K", "L")  # Compressed mainnet

    def test_export_nonexistent_raises(self, wallet):
        """Exporting a key for a non-wallet address should raise ValueError."""
        with pytest.raises(ValueError):
            wallet.export_private_key("1NoSuchAddress")

    def test_import_private_key(self, wallet):
        """Importing a WIF key should add it to the wallet."""
        # Generate a key externally
        pk = PrivateKey.generate()
        wif = pk.to_wif(compressed=True, testnet=False)

        address = wallet.import_private_key(wif)
        assert wallet.has_address(address) is True

        # The imported key should produce the correct address
        expected_address = pk.public_key.to_address(testnet=False)
        assert address == expected_address

    def test_import_export_roundtrip(self, wallet):
        """Import + export should preserve the key."""
        pk = PrivateKey.generate()
        wif_original = pk.to_wif(compressed=True, testnet=False)

        address = wallet.import_private_key(wif_original)
        wif_exported = wallet.export_private_key(address)

        assert wif_original == wif_exported


# ---------------------------------------------------------------------------
# Balance Tests
# ---------------------------------------------------------------------------

class TestBalance:
    """Tests for wallet balance tracking."""

    def test_empty_wallet_balance(self, wallet):
        """A wallet with no addresses should have 0 balance (after generating one)."""
        wallet.generate_address()
        assert wallet.get_balance() == 0

    def test_funded_wallet_balance(self, funded_wallet):
        """A wallet that received mining rewards should have positive balance."""
        balance = funded_wallet.get_balance()
        assert balance > 0

    def test_no_blockchain_raises(self):
        """get_balance without a blockchain should raise RuntimeError."""
        w = Wallet(blockchain=None, name="offline")
        w.generate_address()
        with pytest.raises(RuntimeError):
            w.get_balance()

    def test_get_utxos(self, funded_wallet):
        """get_utxos should return UTXOs for the funded wallet."""
        utxos = funded_wallet.get_utxos()
        assert len(utxos) > 0
        # Each entry should be a (txid, index, utxo_entry) tuple
        for txid, index, entry in utxos:
            assert isinstance(txid, str)
            assert isinstance(index, int)
            assert entry.value > 0


# ---------------------------------------------------------------------------
# Transaction Creation Tests
# ---------------------------------------------------------------------------

class TestTransactionCreation:
    """Tests for creating transactions."""

    def test_create_transaction(self, funded_wallet, recipient_wallet):
        """create_transaction should produce a valid unsigned transaction."""
        recipient_address = recipient_wallet.get_addresses()[0]
        tx = funded_wallet.create_transaction(
            to_address=recipient_address,
            amount=1_000_000,
            fee=10_000,
        )
        assert isinstance(tx, Transaction)
        assert len(tx.inputs) > 0
        assert len(tx.outputs) >= 1  # At least the recipient output

    def test_create_transaction_with_change(self, funded_wallet, recipient_wallet):
        """If input > amount + fee, a change output should be created."""
        recipient_address = recipient_wallet.get_addresses()[0]
        # Send a small amount relative to the mining reward
        tx = funded_wallet.create_transaction(
            to_address=recipient_address,
            amount=1_000_000,
            fee=10_000,
        )
        # Should have recipient output and change output
        assert len(tx.outputs) == 2

    def test_create_transaction_insufficient_funds(self, wallet, recipient_wallet):
        """Creating a transaction with insufficient funds should raise ValueError."""
        wallet.generate_address()
        recipient_address = recipient_wallet.get_addresses()[0]
        with pytest.raises(ValueError, match="Insufficient funds"):
            wallet.create_transaction(
                to_address=recipient_address,
                amount=1_000_000_000,
                fee=10_000,
            )

    def test_create_transaction_no_addresses(self, blockchain, recipient_wallet):
        """Creating a transaction with no wallet addresses should raise ValueError."""
        w = Wallet(blockchain=blockchain, name="empty")
        recipient_address = recipient_wallet.get_addresses()[0]
        with pytest.raises(ValueError):
            w.create_transaction(
                to_address=recipient_address,
                amount=1_000,
                fee=1_000,
            )


# ---------------------------------------------------------------------------
# Transaction Signing Tests
# ---------------------------------------------------------------------------

class TestTransactionSigning:
    """Tests for signing transactions."""

    def test_sign_transaction(self, funded_wallet, recipient_wallet):
        """sign_transaction should populate signature_scripts."""
        recipient_address = recipient_wallet.get_addresses()[0]
        tx = funded_wallet.create_transaction(
            to_address=recipient_address,
            amount=1_000_000,
            fee=10_000,
        )
        signed_tx = funded_wallet.sign_transaction(tx)

        # All non-coinbase inputs should have a signature script
        for tx_input in signed_tx.inputs:
            if not tx_input.is_coinbase():
                assert len(tx_input.signature_script) > 0

    def test_signed_tx_has_valid_format(self, funded_wallet, recipient_wallet):
        """Signed transaction's signature_script should contain hex data."""
        recipient_address = recipient_wallet.get_addresses()[0]
        tx = funded_wallet.create_transaction(
            to_address=recipient_address,
            amount=1_000_000,
            fee=10_000,
        )
        signed_tx = funded_wallet.sign_transaction(tx)

        for tx_input in signed_tx.inputs:
            if not tx_input.is_coinbase():
                script = tx_input.signature_script
                # Should be valid hex (all chars in 0-9, a-f)
                assert all(c in "0123456789abcdef" for c in script)
                # Should contain both signature and pubkey
                # DER signature is typically 70-72 bytes (140-144 hex chars)
                # Compressed pubkey is 33 bytes (66 hex chars)
                assert len(script) > 66  # At least pubkey length


# ---------------------------------------------------------------------------
# send() Convenience Method Tests
# ---------------------------------------------------------------------------

class TestSend:
    """Tests for the send() convenience method."""

    def test_send(self, funded_wallet, recipient_wallet, blockchain):
        """send() should create, sign, and broadcast a transaction."""
        recipient_address = recipient_wallet.get_addresses()[0]
        tx = funded_wallet.send(
            to_address=recipient_address,
            amount=1_000_000,
            fee=10_000,
        )
        assert isinstance(tx, Transaction)
        # The transaction should be in the mempool
        assert blockchain.mempool.size >= 1

    def test_send_no_blockchain_raises(self, recipient_wallet):
        """send() without a blockchain should raise RuntimeError."""
        w = Wallet(blockchain=None, name="offline")
        w.generate_address()
        recipient_address = recipient_wallet.get_addresses()[0]
        with pytest.raises(RuntimeError):
            w.send(
                to_address=recipient_address,
                amount=1_000,
                fee=1_000,
            )

    def test_wallet_repr(self, wallet):
        """Wallet repr should include the name and address count."""
        wallet.generate_address()
        r = repr(wallet)
        assert "test_wallet" in r
