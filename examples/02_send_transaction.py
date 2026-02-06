"""
Example 02: Sending a Transaction
===================================

This example demonstrates how Bitcoin transactions work:
1. Mine blocks to give Alice some bitcoins.
2. Create Bob's wallet with a receiving address.
3. Alice creates, signs, and sends a transaction to Bob.
4. Mine a block to confirm the transaction.
5. Show both wallets' final balances.

In Bitcoin, sending a transaction involves:
- Selecting UTXOs (unspent transaction outputs) to spend
- Creating inputs that reference those UTXOs
- Creating outputs that specify recipients and amounts
- Signing each input with the appropriate private key
- Broadcasting to the network (here, adding to the mempool)
- Waiting for a miner to include it in a block (confirmation)

Usage:
    python -m examples.02_send_transaction
"""

import sys
sys.path.insert(0, "/home/user/bitcoin-blockchain")

def main():
    try:
        from src.core.blockchain import Blockchain
        from src.wallet.wallet import Wallet
    except ImportError as e:
        print(f"Import error: {e}")
        print("Make sure all modules are available. Run from the project root:")
        print("  python -m examples.02_send_transaction")
        return

    print("=" * 60)
    print("Bitcoin Blockchain - Send Transaction Example")
    print("=" * 60)

    # Step 1: Set up the blockchain and Alice's wallet.
    print("\n[Step 1] Setting up blockchain and Alice's wallet...")
    blockchain = Blockchain(development_mode=True)

    alice_wallet = Wallet(blockchain=blockchain, name="Alice")
    alice_address = alice_wallet.generate_address()
    alice_keypair = alice_wallet.get_keypair(alice_address)
    alice_pubkey_hash = alice_keypair.public_key.get_hash160()

    print(f"  Alice's address: {alice_address}")

    # Step 2: Mine blocks to give Alice some BTC.
    # Mining rewards go to Alice's pubkey hash.
    num_blocks = 5
    print(f"\n[Step 2] Mining {num_blocks} blocks (rewards to Alice)...")
    for i in range(num_blocks):
        blockchain.mine_next_block(coinbase_address=alice_pubkey_hash)

    alice_balance = alice_wallet.get_balance()
    print(f"  Alice's balance: {alice_balance} satoshis ({alice_balance / 1e8:.8f} BTC)")

    # Step 3: Create Bob's wallet.
    print("\n[Step 3] Creating Bob's wallet...")
    bob_wallet = Wallet(blockchain=blockchain, name="Bob")
    bob_address = bob_wallet.generate_address()
    print(f"  Bob's address: {bob_address}")
    print(f"  Bob's balance: {bob_wallet.get_balance()} satoshis")

    # Step 4: Alice sends BTC to Bob.
    # The send() method creates the transaction, signs it, and adds it to the mempool.
    send_amount = 100_000_000  # 1 BTC in satoshis
    fee = 10_000  # 0.0001 BTC fee
    print(f"\n[Step 4] Alice sends {send_amount} satoshis ({send_amount / 1e8:.8f} BTC) to Bob...")
    print(f"  Transaction fee: {fee} satoshis")

    tx = alice_wallet.send(to_address=bob_address, amount=send_amount, fee=fee)

    print(f"  Transaction ID: {tx.txid[:32]}...")
    print(f"  Inputs: {len(tx.inputs)}")
    print(f"  Outputs: {len(tx.outputs)}")
    for i, out in enumerate(tx.outputs):
        print(f"    Output {i}: {out.value} satoshis to {out.pubkey_script[:16]}...")

    # Show mempool state
    print(f"\n  Mempool size: {blockchain.mempool.size} transaction(s)")

    # Step 5: Mine a block to confirm the transaction.
    # Miners select transactions from the mempool and include them in blocks.
    print("\n[Step 5] Mining a block to confirm the transaction...")
    block = blockchain.mine_next_block(coinbase_address=alice_pubkey_hash)
    print(f"  Block mined at height {blockchain.get_chain_height()}")
    print(f"  Transactions in block: {len(block.transactions)}")
    print(f"  Mempool size after mining: {blockchain.mempool.size}")

    # Step 6: Show final balances.
    print("\n[Step 6] Final balances:")
    alice_final = alice_wallet.get_balance()
    bob_final = bob_wallet.get_balance()
    print(f"  Alice: {alice_final} satoshis ({alice_final / 1e8:.8f} BTC)")
    print(f"  Bob:   {bob_final} satoshis ({bob_final / 1e8:.8f} BTC)")

    print("\n" + "=" * 60)
    print("Transaction complete! Bob received bitcoins from Alice.")
    print("=" * 60)


if __name__ == "__main__":
    main()
