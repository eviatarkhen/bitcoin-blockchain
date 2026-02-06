"""
Example 04: Difficulty Adjustment
===================================

This example demonstrates Bitcoin's difficulty adjustment mechanism:
1. Create a blockchain and mine through a difficulty adjustment period.
2. Show how the difficulty changes based on block timing.

In Bitcoin, the difficulty adjusts every 2,016 blocks to maintain an average
block time of ~10 minutes. If blocks were mined too fast (miners got faster),
difficulty increases. If too slow, it decreases.

The formula is:
    new_target = old_target * (actual_time / expected_time)

where:
    - actual_time = timestamp of block 2016 - timestamp of block 0
    - expected_time = 2016 * 10 minutes = 20,160 minutes

This self-regulating mechanism is one of Bitcoin's key innovations, allowing
the network to maintain a predictable block rate regardless of how much
mining power is added or removed.

Note: In development mode with instant mining, we simulate this with a
smaller adjustment interval to demonstrate the concept.

Usage:
    python -m examples.04_difficulty_adjust
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def main():
    try:
        from src.core.blockchain import Blockchain
        from src.wallet.wallet import Wallet
        from src.mining.miner import compact_bits_to_target, target_to_compact_bits
        from src.consensus.difficulty import get_block_reward, should_adjust
    except ImportError as e:
        print(f"Import error: {e}")
        print("Make sure all modules are available. Run from the project root:")
        print("  python -m examples.04_difficulty_adjust")
        return

    print("=" * 60)
    print("Bitcoin Blockchain - Difficulty Adjustment Example")
    print("=" * 60)

    # Step 1: Create blockchain in development mode.
    print("\n[Step 1] Creating blockchain...")
    blockchain = Blockchain(development_mode=True)

    wallet = Wallet(blockchain=blockchain, name="difficulty_miner")
    address = wallet.generate_address()
    keypair = wallet.get_keypair(address)
    pubkey_hash = keypair.public_key.get_hash160()

    initial_difficulty = blockchain.get_current_difficulty()
    initial_target = compact_bits_to_target(initial_difficulty)
    print(f"  Initial difficulty bits: 0x{initial_difficulty:08x}")
    print(f"  Initial target: {initial_target:#x}" if initial_target < 2**64 else f"  Initial target: (very large)")

    # Step 2: Mine blocks and observe difficulty.
    # We mine enough blocks to potentially trigger a difficulty adjustment.
    # The exact interval depends on the blockchain's configuration.
    num_blocks = 25
    print(f"\n[Step 2] Mining {num_blocks} blocks and tracking difficulty...")

    difficulty_changes = []
    prev_difficulty = initial_difficulty

    for i in range(1, num_blocks + 1):
        block = blockchain.mine_next_block(coinbase_address=pubkey_hash)
        current_difficulty = blockchain.get_current_difficulty()

        height = blockchain.get_chain_height()

        # Check if difficulty changed
        if current_difficulty != prev_difficulty:
            difficulty_changes.append({
                "height": height,
                "old_bits": prev_difficulty,
                "new_bits": current_difficulty,
            })
            print(f"  Block {i} (height {height}): DIFFICULTY ADJUSTED!")
            print(f"    Old bits: 0x{prev_difficulty:08x}")
            print(f"    New bits: 0x{current_difficulty:08x}")
            prev_difficulty = current_difficulty
        elif i % 5 == 0 or i == 1:
            print(f"  Block {i} (height {height}): difficulty=0x{current_difficulty:08x}")

    # Step 3: Show block reward halving schedule.
    print("\n[Step 3] Block reward schedule (halving every 210,000 blocks):")
    halving_heights = [0, 210_000, 420_000, 630_000, 840_000]
    for h in halving_heights:
        reward = get_block_reward(h)
        btc_reward = reward / 100_000_000
        print(f"  Height {h:>10,}: reward = {reward:>15,} satoshis ({btc_reward:.8f} BTC)")

    # Step 4: Show difficulty adjustment check.
    print("\n[Step 4] Difficulty adjustment intervals:")
    check_heights = [0, 1, 2015, 2016, 2017, 4032]
    for h in check_heights:
        # Check with Bitcoin's real interval of 2016
        adjusts = should_adjust(h, interval=2016)
        print(f"  Height {h:>6}: should_adjust(interval=2016) = {adjusts}")

    # Step 5: Summary.
    print(f"\n[Step 5] Summary:")
    print(f"  Total blocks mined: {num_blocks}")
    print(f"  Chain height: {blockchain.get_chain_height()}")
    print(f"  Difficulty adjustments observed: {len(difficulty_changes)}")
    final_difficulty = blockchain.get_current_difficulty()
    print(f"  Final difficulty bits: 0x{final_difficulty:08x}")

    balance = wallet.get_balance()
    print(f"  Miner balance: {balance} satoshis ({balance / 1e8:.8f} BTC)")

    print("\n" + "=" * 60)
    print("Difficulty adjustment ensures blocks are mined at a steady rate.")
    print("=" * 60)


if __name__ == "__main__":
    main()
