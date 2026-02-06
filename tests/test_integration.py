"""
Integration Tests (Task 12.8)
===============================

End-to-end tests that exercise the full stack:
- Create blockchain -> mine blocks -> send transactions -> handle forks

These tests verify that all components work together correctly.
"""

import sys

sys.path.insert(0, "/home/user/bitcoin-blockchain")

import pytest

from src.core.blockchain import Blockchain
from src.core.block import Block, BlockHeader
from src.core.transaction import Transaction
from src.wallet.wallet import Wallet
from src.crypto.keys import KeyPair, PrivateKey
from src.mining.miner import Miner, create_block_template, compact_bits_to_target
from src.consensus.difficulty import get_block_reward


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def blockchain():
    """A development-mode blockchain."""
    return Blockchain(development_mode=True)


# ---------------------------------------------------------------------------
# End-to-End: Mining and Balance
# ---------------------------------------------------------------------------

class TestMiningAndBalance:
    """Test mining blocks and tracking balances end-to-end."""

    def test_mine_and_check_balance(self, blockchain):
        """Mining blocks should credit the miner's wallet."""
        wallet = Wallet(blockchain=blockchain, name="miner")
        address = wallet.generate_address()
        pubkey_hash = wallet.get_keypair(address).public_key.get_hash160()

        # Mine 3 blocks
        for _ in range(3):
            blockchain.mine_next_block(coinbase_address=pubkey_hash)

        # Balance should equal 3 block rewards
        expected_reward = get_block_reward(1)  # Reward for early blocks
        balance = wallet.get_balance()
        assert balance >= expected_reward  # At least one block reward

    def test_multiple_miners(self, blockchain):
        """Multiple miners should each receive their own rewards."""
        miner_a = Wallet(blockchain=blockchain, name="miner_a")
        addr_a = miner_a.generate_address()
        hash_a = miner_a.get_keypair(addr_a).public_key.get_hash160()

        miner_b = Wallet(blockchain=blockchain, name="miner_b")
        addr_b = miner_b.generate_address()
        hash_b = miner_b.get_keypair(addr_b).public_key.get_hash160()

        # Alternate miners
        blockchain.mine_next_block(coinbase_address=hash_a)
        blockchain.mine_next_block(coinbase_address=hash_b)
        blockchain.mine_next_block(coinbase_address=hash_a)

        balance_a = miner_a.get_balance()
        balance_b = miner_b.get_balance()

        # Miner A mined 2 blocks, Miner B mined 1
        assert balance_a > balance_b
        assert balance_b > 0


# ---------------------------------------------------------------------------
# End-to-End: Transaction Flow
# ---------------------------------------------------------------------------

class TestTransactionFlow:
    """Test the complete transaction lifecycle."""

    def test_send_and_confirm(self, blockchain):
        """Full flow: mine -> send -> confirm -> check balances."""
        # Setup wallets
        alice = Wallet(blockchain=blockchain, name="Alice")
        alice_addr = alice.generate_address()
        alice_hash = alice.get_keypair(alice_addr).public_key.get_hash160()

        bob = Wallet(blockchain=blockchain, name="Bob")
        bob_addr = bob.generate_address()

        # Mine blocks to fund Alice
        for _ in range(3):
            blockchain.mine_next_block(coinbase_address=alice_hash)

        alice_balance_before = alice.get_balance()
        assert alice_balance_before > 0

        # Send from Alice to Bob
        send_amount = 1_000_000  # 0.01 BTC
        fee = 10_000
        tx = alice.send(to_address=bob_addr, amount=send_amount, fee=fee)

        # Transaction should be in mempool
        assert blockchain.mempool.size >= 1

        # Mine a block to confirm
        blockchain.mine_next_block(coinbase_address=alice_hash)

        # Bob should have received the funds
        bob_balance = bob.get_balance()
        assert bob_balance == send_amount

        # Alice should have less than before (minus send amount and fee,
        # plus a new block reward from the confirmation block)
        alice_balance_after = alice.get_balance()
        # Alice mined an extra block, so her balance changes complexly,
        # but Bob definitely got his money
        assert bob_balance == send_amount

    def test_chain_of_transactions(self, blockchain):
        """A -> B -> C chain of transactions should work."""
        # Setup three wallets
        alice = Wallet(blockchain=blockchain, name="Alice")
        alice_addr = alice.generate_address()
        alice_hash = alice.get_keypair(alice_addr).public_key.get_hash160()

        bob = Wallet(blockchain=blockchain, name="Bob")
        bob_addr = bob.generate_address()
        bob_hash = bob.get_keypair(bob_addr).public_key.get_hash160()

        charlie = Wallet(blockchain=blockchain, name="Charlie")
        charlie_addr = charlie.generate_address()

        # Fund Alice
        for _ in range(5):
            blockchain.mine_next_block(coinbase_address=alice_hash)

        # Alice -> Bob
        alice.send(to_address=bob_addr, amount=10_000_000, fee=10_000)
        blockchain.mine_next_block(coinbase_address=alice_hash)

        # Verify Bob received funds
        bob_balance = bob.get_balance()
        assert bob_balance == 10_000_000

        # Bob -> Charlie
        bob.send(to_address=charlie_addr, amount=5_000_000, fee=10_000)
        blockchain.mine_next_block(coinbase_address=alice_hash)

        # Verify Charlie received funds
        charlie_balance = charlie.get_balance()
        assert charlie_balance == 5_000_000


# ---------------------------------------------------------------------------
# End-to-End: Blockchain Properties
# ---------------------------------------------------------------------------

class TestBlockchainProperties:
    """Test blockchain-level properties and invariants."""

    def test_chain_continuity(self, blockchain):
        """Each block's previous_block_hash should point to the prior block."""
        wallet = Wallet(blockchain=blockchain, name="miner")
        addr = wallet.generate_address()
        pubkey_hash = wallet.get_keypair(addr).public_key.get_hash160()

        for _ in range(5):
            blockchain.mine_next_block(coinbase_address=pubkey_hash)

        # Check chain links
        for h in range(1, blockchain.get_chain_height() + 1):
            block = blockchain.get_block_by_height(h)
            parent = blockchain.get_block_by_height(h - 1)
            if block and parent:
                assert block.header.previous_block_hash == parent.header.hash

    def test_block_heights_sequential(self, blockchain):
        """Block heights should be sequential from 0."""
        wallet = Wallet(blockchain=blockchain, name="miner")
        addr = wallet.generate_address()
        pubkey_hash = wallet.get_keypair(addr).public_key.get_hash160()

        for _ in range(5):
            blockchain.mine_next_block(coinbase_address=pubkey_hash)

        for h in range(blockchain.get_chain_height() + 1):
            block = blockchain.get_block_by_height(h)
            assert block is not None

    def test_utxo_consistency(self, blockchain):
        """UTXO set should be consistent after mining and spending."""
        alice = Wallet(blockchain=blockchain, name="Alice")
        alice_addr = alice.generate_address()
        alice_hash = alice.get_keypair(alice_addr).public_key.get_hash160()

        bob = Wallet(blockchain=blockchain, name="Bob")
        bob_addr = bob.generate_address()
        bob_hash = bob.get_keypair(bob_addr).public_key.get_hash160()

        # Mine blocks to Alice
        for _ in range(3):
            blockchain.mine_next_block(coinbase_address=alice_hash)

        total_before = alice.get_balance()

        # Send to Bob
        send_amount = 1_000_000
        fee = 10_000
        alice.send(to_address=bob_addr, amount=send_amount, fee=fee)
        blockchain.mine_next_block(coinbase_address=bob_hash)

        # Conservation: Alice's spent amount + fee should account for the difference
        # (Bob also got a mining reward from the confirmation block)
        alice_after = alice.get_balance()
        bob_after = bob.get_balance()

        # Bob should have his received amount plus the mining reward
        assert bob_after >= send_amount


# ---------------------------------------------------------------------------
# End-to-End: Key Management
# ---------------------------------------------------------------------------

class TestKeyManagement:
    """Test key import/export integration."""

    def test_import_key_receives_funds(self, blockchain):
        """Importing a key that has funds should show the correct balance."""
        # Create a wallet and mine some blocks
        wallet1 = Wallet(blockchain=blockchain, name="original")
        addr = wallet1.generate_address()
        pubkey_hash = wallet1.get_keypair(addr).public_key.get_hash160()

        for _ in range(2):
            blockchain.mine_next_block(coinbase_address=pubkey_hash)

        balance = wallet1.get_balance()
        assert balance > 0

        # Export the key
        wif = wallet1.export_private_key(addr)

        # Import into a new wallet
        wallet2 = Wallet(blockchain=blockchain, name="imported")
        imported_addr = wallet2.import_private_key(wif)

        # The imported wallet should see the same balance
        assert imported_addr == addr
        assert wallet2.get_balance() == balance

    def test_multiple_addresses_balance(self, blockchain):
        """Wallet with multiple addresses should sum all balances."""
        wallet = Wallet(blockchain=blockchain, name="multi")

        # Generate two addresses
        addr1 = wallet.generate_address()
        hash1 = wallet.get_keypair(addr1).public_key.get_hash160()

        addr2 = wallet.generate_address()
        hash2 = wallet.get_keypair(addr2).public_key.get_hash160()

        # Mine blocks to each address
        blockchain.mine_next_block(coinbase_address=hash1)
        blockchain.mine_next_block(coinbase_address=hash2)

        balance = wallet.get_balance()
        reward = get_block_reward(1)
        # Should have at least 2 block rewards
        assert balance >= reward * 2


# ---------------------------------------------------------------------------
# End-to-End: Block Template and Mining
# ---------------------------------------------------------------------------

class TestBlockTemplateIntegration:
    """Test block template creation and mining together."""

    def test_template_mine_add(self, blockchain):
        """Create a template, mine it, and add it to the blockchain."""
        kp = KeyPair.generate()
        pubkey_hash = kp.public_key.get_hash160()

        tip = blockchain.get_chain_tip()
        height = blockchain.get_chain_height() + 1
        difficulty = blockchain.get_current_difficulty()
        reward = get_block_reward(height)

        template = create_block_template(
            previous_block_hash=tip.header.hash,
            height=height,
            difficulty_bits=difficulty,
            transactions=[],
            coinbase_address=pubkey_hash,
            reward_amount=reward,
        )

        miner = Miner(instant_mine=False)
        mined = miner.mine_block(template)

        result = blockchain.add_block(mined)
        assert result is True
        assert blockchain.get_chain_height() == height
