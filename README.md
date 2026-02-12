# Bitcoin Blockchain Implementation

An educational Bitcoin full archival node built from first principles, implementing core concepts from the [Bitcoin whitepaper](https://bitcoin.org/bitcoin.pdf). No P2P networking — focuses on the blockchain data structures, consensus rules, and cryptography.

## Features

- **80-byte block headers** matching the real Bitcoin protocol
- **Proof-of-Work mining** with brute-force nonce search and compact difficulty (nBits)
- **UTXO model** for transaction tracking (not account-based)
- **ECDSA signatures** on the secp256k1 curve for transaction authorization
- **Merkle trees** for efficient transaction commitment (built from scratch)
- **Difficulty adjustment** every N blocks to maintain target block time
- **Fork handling** with chain reorganization (longest chain wins)
- **Wallet** with key management, coin selection, and transaction creation
- **JSON export/import** for blockchain state persistence
- **CLI visualization** using the `rich` library

## Quick Start

```bash
# Install dependencies
pip install ecdsa base58 pytest rich

# Run examples
python -m examples.01_basic_mining          # Mine blocks, see wallet balance
python -m examples.02_send_transaction      # Send BTC between wallets
python -m examples.03_fork_handling         # Fork creation and resolution
python -m examples.04_difficulty_adjust     # Difficulty adjustment over blocks

# Run tests (200 tests)
pytest tests/
```

## Project Structure

```
src/
├── core/
│   ├── block.py           # Block and BlockHeader (80-byte Bitcoin format)
│   ├── transaction.py     # Transaction, inputs, outputs
│   ├── blockchain.py      # Central coordinator: chain management, forks, reorgs
│   ├── utxo.py            # Unspent Transaction Output set
│   └── mempool.py         # Transaction memory pool with fee prioritization
├── crypto/
│   ├── hash.py            # SHA-256, RIPEMD-160, double_sha256, hash160
│   ├── keys.py            # ECDSA key pairs, signing, verification, WIF export
│   └── merkle.py          # Custom Merkle tree (from scratch using hashlib)
├── mining/
│   └── miner.py           # PoW mining, compact bits conversion, block templates
├── consensus/
│   ├── difficulty.py      # Difficulty adjustment algorithm, block reward halving
│   ├── rules.py           # Block size, coinbase, maturity, timestamp validation
│   └── validation.py      # Full block and transaction validation pipeline
├── wallet/
│   └── wallet.py          # Key management, balance tracking, coin selection
└── utils/
    ├── encoding.py        # Base58Check, hex/bytes conversions, varint
    ├── serialization.py   # Binary serialization helpers
    └── visualizer.py      # CLI blockchain visualization (rich library)

examples/
├── 01_basic_mining.py     # Mine blocks, show wallet balance
├── 02_send_transaction.py # Create wallets, mine, send BTC between them
├── 03_fork_handling.py    # Fork creation and resolution demo
├── 04_difficulty_adjust.py # Difficulty adjustment over multiple blocks
└── helpers/
    └── blockchain_tester.py # Programmatic fork creation helper

tests/                     # 200 tests across 10 test files
```

## Development vs Production Mode

The blockchain supports two modes:

| Parameter | Dev Mode (default) | Production Mode |
|---|---|---|
| Difficulty | `0x1f0fffff` (~0.01s/block) | `0x1d00ffff` (real Bitcoin) |
| Adjustment interval | 10 blocks | 2016 blocks |
| Target block time | 5 seconds | 600 seconds (10 min) |
| Coinbase maturity | 5 blocks | 100 blocks |

```python
from src.core.blockchain import Blockchain

blockchain = Blockchain(development_mode=True)   # Easy mining, fast iteration
blockchain = Blockchain(development_mode=False)   # Real Bitcoin parameters
```

## How It Works

### Mining a Block
1. `mine_next_block()` creates a block template with a coinbase transaction
2. The miner brute-forces nonces until the block header hash is below the difficulty target
3. The block is validated (PoW, merkle root, timestamps, transactions) and added to the chain
4. The UTXO set is updated: spent outputs removed, new outputs added

### Sending a Transaction
1. The wallet selects UTXOs to cover the send amount + fee (coin selection)
2. A transaction is created with inputs referencing the selected UTXOs
3. Each input is signed with the corresponding private key (ECDSA/secp256k1)
4. The transaction is added to the mempool
5. A miner includes it in the next block

### Fork Resolution
1. Two competing blocks at the same height are both stored
2. The first-seen block remains the best chain tip (equal height = no reorg)
3. When one branch grows strictly longer, a chain reorganization occurs:
   - Old branch blocks are unwound (UTXOs reverted, transactions returned to mempool)
   - New branch blocks are applied
   - Best chain tip is updated

## Key Concepts Demonstrated

- **Why blocks are linked via cryptographic hashes** — tampering detection
- **Why brute-force mining is necessary** — no mathematical shortcuts
- **How the UTXO model prevents double-spending**
- **Why coinbase maturity exists** — protection against deep reorgs
- **How difficulty adjustment maintains steady block rate**
- **How forks occur and resolve** — longest chain wins

## Dependencies

- Python 3.10+
- `ecdsa` — ECDSA signatures (secp256k1 curve)
- `base58` — Bitcoin address encoding (Base58Check)
- `pytest` — Testing framework
- `rich` — CLI visualization (tables, trees, formatted output)

## Resources

- [Bitcoin Whitepaper](https://bitcoin.org/bitcoin.pdf)
- Key whitepaper sections: 3 (Timestamp Server), 4 (Proof-of-Work), 5 (Network/Consensus), 7 (Merkle Trees)
