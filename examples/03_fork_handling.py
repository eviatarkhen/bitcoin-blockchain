"""
Example 03: Fork Handling
==========================

This example demonstrates how Bitcoin handles blockchain forks:
1. Build a chain of blocks.
2. Create a fork by generating two competing blocks at the same height.
3. Show how the blockchain resolves the fork using the longest-chain rule.

In Bitcoin, forks are a natural occurrence:
- **Accidental forks**: Two miners find valid blocks at nearly the same time.
  The network temporarily disagrees on which block is the chain tip.
- **Resolution**: As more blocks are mined, one branch inevitably grows longer
  than the other. Nodes follow the "longest chain" rule (technically, the chain
  with the most cumulative proof-of-work) and abandon the shorter branch.
- **Orphan blocks**: Blocks on the abandoned branch are called "orphan" or
  "stale" blocks. Their transactions return to the mempool to be re-mined.

This is why Bitcoin recommends waiting for 6 confirmations (blocks on top of
the block containing your transaction) before considering a transaction final.

Usage:
    python -m examples.03_fork_handling
"""

import sys
sys.path.insert(0, "/home/user/bitcoin-blockchain")

def main():
    try:
        from src.core.blockchain import Blockchain
        from src.wallet.wallet import Wallet
        from examples.helpers.blockchain_tester import BlockchainTester
    except ImportError as e:
        print(f"Import error: {e}")
        print("Make sure all modules are available. Run from the project root:")
        print("  python -m examples.03_fork_handling")
        return

    print("=" * 60)
    print("Bitcoin Blockchain - Fork Handling Example")
    print("=" * 60)

    # Step 1: Create a blockchain with several blocks.
    print("\n[Step 1] Creating blockchain with 10 blocks...")
    blockchain, miner_wallet = BlockchainTester.create_chain(10)
    print(f"  Chain height: {blockchain.get_chain_height()}")
    print(f"  Chain tip: {blockchain.get_chain_tip().header.hash[:24]}...")

    # Step 2: Show the chain before forking.
    print("\n[Step 2] Chain before fork:")
    for h in range(max(0, blockchain.get_chain_height() - 3), blockchain.get_chain_height() + 1):
        block = blockchain.get_block_by_height(h)
        if block:
            print(f"  Height {h}: {block.header.hash[:24]}...")

    # Step 3: Demonstrate fork resolution.
    # This creates competing blocks and resolves the fork by extending one branch.
    print("\n[Step 3] Creating and resolving a fork...")
    print("-" * 40)
    blockchain = BlockchainTester.demonstrate_fork_resolution(blockchain)
    print("-" * 40)

    # Step 4: Show final chain state.
    print("\n[Step 4] Final chain state:")
    print(f"  Chain height: {blockchain.get_chain_height()}")
    print(f"  Chain tip: {blockchain.get_chain_tip().header.hash[:24]}...")

    # Show the last few blocks
    print("\n  Recent blocks:")
    for h in range(max(0, blockchain.get_chain_height() - 5), blockchain.get_chain_height() + 1):
        block = blockchain.get_block_by_height(h)
        if block:
            tx_count = len(block.transactions)
            print(f"    Height {h}: {block.header.hash[:24]}... ({tx_count} tx)")

    print("\n" + "=" * 60)
    print("Fork resolved! The longest chain wins in Bitcoin.")
    print("=" * 60)


if __name__ == "__main__":
    main()
