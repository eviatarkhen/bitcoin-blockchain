"""
Example 01: Basic Mining
=========================

This example demonstrates the fundamental Bitcoin mining workflow:
1. Create a new blockchain (which automatically creates the genesis block).
2. Create a wallet and generate an address to receive mining rewards.
3. Mine several blocks, collecting the block reward each time.
4. Display the wallet balance and chain state.

In Bitcoin, mining is the process of finding a valid proof-of-work nonce
for a block header. The miner who finds it first gets to add the block to
the chain and collect the block reward (newly created bitcoins) plus any
transaction fees in the block.

Usage:
    python -m examples.01_basic_mining
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
        print("  python -m examples.01_basic_mining")
        return

    print("=" * 60)
    print("Bitcoin Blockchain - Basic Mining Example")
    print("=" * 60)

    # Step 1: Create a new blockchain in development mode.
    # Development mode uses instant mining (no real proof-of-work computation),
    # which makes the examples run quickly.
    print("\n[Step 1] Creating a new blockchain (development mode)...")
    blockchain = Blockchain(development_mode=True)
    print(f"  Genesis block created!")
    print(f"  Chain height: {blockchain.get_chain_height()}")

    genesis = blockchain.get_block_by_height(0)
    if genesis:
        print(f"  Genesis hash: {genesis.header.hash[:32]}...")

    # Step 2: Create a wallet and generate a receiving address.
    # The wallet manages private keys and can track balances via the UTXO set.
    print("\n[Step 2] Creating a miner wallet...")
    wallet = Wallet(blockchain=blockchain, name="miner_alice")
    miner_address = wallet.generate_address()
    print(f"  Wallet name: {wallet.name}")
    print(f"  Miner address: {miner_address}")

    # We need the pubkey hash to use as the coinbase address.
    # The coinbase transaction pays the block reward to this hash.
    keypair = wallet.get_keypair(miner_address)
    coinbase_address = keypair.public_key.get_hash160()

    # Step 3: Mine 5 blocks.
    # Each block's coinbase transaction creates new bitcoins as the mining reward.
    # In early Bitcoin, the reward was 50 BTC per block. It halves every 210,000
    # blocks (approximately every 4 years).
    num_blocks = 5
    print(f"\n[Step 3] Mining {num_blocks} blocks...")

    for i in range(1, num_blocks + 1):
        block = blockchain.mine_next_block(coinbase_address=coinbase_address)
        block_hash = block.header.hash[:24]
        height = blockchain.get_chain_height()
        num_txs = len(block.transactions)
        print(f"  Block {i}: height={height}, hash={block_hash}..., txs={num_txs}")

    # Step 4: Display the final state.
    print("\n[Step 4] Final blockchain state:")
    print(f"  Chain height: {blockchain.get_chain_height()}")
    print(f"  Wallet addresses: {len(wallet.get_addresses())}")

    balance = wallet.get_balance()
    btc_balance = balance / 100_000_000
    print(f"  Wallet balance: {balance} satoshis ({btc_balance:.8f} BTC)")

    # Show the chain from genesis to tip
    print("\n  Block chain:")
    for h in range(blockchain.get_chain_height() + 1):
        block = blockchain.get_block_by_height(h)
        if block:
            tx_count = len(block.transactions)
            print(f"    Height {h}: {block.header.hash[:24]}... ({tx_count} tx)")

    print("\n" + "=" * 60)
    print("Mining complete! The miner earned block rewards for each block.")
    print("=" * 60)


if __name__ == "__main__":
    main()
