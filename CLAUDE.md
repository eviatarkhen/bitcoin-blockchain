# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Educational Bitcoin full archival node implementation (no P2P networking). Implements Bitcoin-accurate data structures, PoW mining, UTXO-based transactions, ECDSA signatures, Merkle trees, difficulty adjustment, fork handling, and chain reorganization. All in-memory with JSON export.

## Commands

```bash
# Run all tests (200 tests, ~2s)
pytest tests/

# Run a single test file
pytest tests/test_block.py -v

# Run a specific test
pytest tests/test_integration.py::TestMiningAndBalance::test_mine_and_check_balance -v

# Run examples (from project root)
python -m examples.01_basic_mining
python -m examples.02_send_transaction
python -m examples.03_fork_handling
python -m examples.04_difficulty_adjust

# Install dependencies
pip install ecdsa base58 pytest rich
```

## Architecture

**Central coordinator**: `Blockchain` class (`src/core/blockchain.py`) ties everything together — it owns the block store, UTXO set, mempool, and orchestrates validation, mining, and fork handling.

**Data flow for mining a block**:
`Blockchain.mine_next_block()` → `create_block_template()` (miner.py) → `Transaction.create_coinbase()` → `Miner.mine_block()` (brute-force nonce search) → `Blockchain.add_block()` → `validate_block()` (validation.py) → `_apply_block()` (updates UTXO set)

**Data flow for sending a transaction**:
`Wallet.create_transaction()` → coin selection from UTXO set → `Wallet.sign_transaction()` → `Mempool.add_transaction()` → included in next mined block

**Module dependency direction** (imports flow downward):
```
wallet.py → blockchain.py → validation.py → rules.py
                ↓                              ↓
            mempool.py            difficulty.py → miner.py
                ↓                                   ↓
            block.py ← merkle.py              (uses block.py, transaction.py)
                ↓
          transaction.py → encoding.py
                ↓
             utxo.py
                ↓
           keys.py, hash.py
```

Circular dependency avoidance: `blockchain.py` uses `TYPE_CHECKING` imports and local imports inside methods for `block.py`, `transaction.py`, `miner.py`, `difficulty.py`, and `validation.py`.

## Critical Integration Gotcha: Address vs PubkeyHash

The UTXO set stores and matches by **hash160 hex** (40-char pubkey hash), NOT Bitcoin addresses (Base58Check encoded). When querying UTXOs:

- **Correct**: `utxo_set.get_balance(keypair.public_key.get_hash160())` → `"7a0fa7c1700a7a94..."`
- **Wrong**: `utxo_set.get_balance("1BwdQcRjmVoHLjzB...")` → always returns 0

`mine_next_block(coinbase_address=...)` and `create_block_template(coinbase_address=...)` expect a hash160 hex string, not a Bitcoin address.

## Development vs Production Mode

`Blockchain(development_mode=True)` (default):
- Difficulty `0x1f0fffff` — blocks mine in ~0.01s (~1000-10000 nonce attempts)
- Adjustment interval: 10 blocks (not 2016)
- Target block time: 5 seconds (not 600)
- Coinbase maturity: 5 blocks (not 100) — mine at least 5 blocks before spending rewards

`Blockchain(development_mode=False)`:
- Real Bitcoin difficulty `0x1d00ffff`, 2016-block intervals, 10-minute targets
- Coinbase maturity: 100 blocks

**Important**: `Miner(instant_mine=True)` sets nonce=0 without doing PoW, but `validate_block()` still checks `meets_difficulty_target()`. Blocks from instant_mine will be rejected by `add_block()`. Use real mining with dev difficulty instead.

## Difficulty Adjustment

`_get_next_difficulty(height)` is a pure function — it derives everything from blocks already in the chain:
- Base difficulty comes from `block_by_height(height - 1)`, not mutable instance state
- Timestamps come from the fixed adjustment period window (heights `h - interval` to `h - 1`)
- `_max_target_bits` stores the genesis/minimum difficulty for the chain (dev or prod) and is passed to `calculate_next_difficulty` as the floor

Timestamps: `mine_next_block` bumps the block timestamp to `max(time(), tip.timestamp + 1)` to avoid Median Time Past validation failures when blocks mine faster than 1 second.

## Validation Flow

`validate_block` → `validate_block_transactions` → `validate_transaction` → `validate_coinbase_maturity`

The coinbase maturity value is threaded from `blockchain._coinbase_maturity` through all validation layers. Consensus rules in `rules.py` raise `ValueError`; the `validate_block` function catches these and converts them to `ValidationError` to ensure blocks are properly rejected.

## Key Design Decisions

- **80-byte BlockHeader**: Exactly matches Bitcoin protocol. Serialized as little-endian integers; hash displayed in reversed byte order.
- **UTXO model** (not account-based): Spending = consuming input UTXOs + creating new output UTXOs. Key: `"txid:output_index"`.
- **Simplified P2PKH only**: No full Bitcoin Script engine. `pubkey_script` is just the hash160 hex of the public key. `signature_script` is `signature_hex + pubkey_hex`.
- **Merkle tree from scratch**: `merkletools` library unavailable (pysha3 build fails). Custom implementation in `src/crypto/merkle.py` using `hashlib`.
- **Genesis block**: Hardcoded with nonce=0, inserted without PoW validation. Uses timestamp `1231006505` (Bitcoin's real genesis).
- **Coinbase maturity**: Configurable per mode — 5 blocks (dev) or 100 blocks (prod). Enforced in `rules.py`, threaded through validation.
- **Fork handling**: Longest chain wins. `_reorganize_chain()` finds common ancestor, unwinds old blocks (reverting UTXOs), applies new blocks. Equal-height forks keep the first-seen chain tip.

## Dependencies

Python 3.10+. Libraries: `ecdsa` (secp256k1 ECDSA), `base58` (address encoding), `pytest` (testing), `rich` (CLI visualization).
