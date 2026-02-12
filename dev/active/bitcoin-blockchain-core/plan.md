# Plan: Bitcoin Blockchain Core Implementation

**Status**: Completed
**Created**: 2026-02-06
**Last Updated**: 2026-02-06 (implementation complete, code simplified)

---

# Bitcoin Blockchain Implementation Plan - Production-Grade Learning

## Context
User is learning blockchain technology from first principles by implementing concepts from the Bitcoin whitepaper. Background: CS Master's degree, experienced entrepreneur with healthcare domain knowledge, exploring startup ideas in blockchain space. **User wants close-to-reality implementation, not toy examples.**

## Recommendation: Full Archival Node (Single Instance, No P2P)

### Approach: Build Complete Bitcoin Full Node (Without Network Layer)

**Phase 1: Full Archival Node Implementation**

**Node Type: FULL ARCHIVAL NODE**
- ✅ Stores **complete blockchain** (all blocks from genesis)
- ✅ Stores **all transactions** (including fully spent ones)
- ✅ Maintains **full UTXO set** (all unspent outputs)
- ✅ Validates **every block** completely
- ✅ Validates **every transaction** completely
- ✅ Enforces **all consensus rules**
- ✅ Can mine new blocks
- ✅ Can create and validate transactions
- ✅ Handles forks and reorganizations
- ❌ No P2P networking (single instance only)

**This IS a Full Node (Minus Networking):**
- Same functionality as Bitcoin Core full node
- Can independently verify entire blockchain
- Never trusts external data
- Maintains complete history
- Can serve as authoritative data source
- Just can't communicate with other nodes

**Real Bitcoin-style block structure (80-byte header):**
- Exactly matches Bitcoin protocol specification
- Full Proof-of-Work mining implementation
- Difficulty adjustment algorithm (every 2016 blocks)
- Complete UTXO transaction model
- ECDSA signatures (secp256k1 curve)
- Merkle trees for transaction commitment
- All consensus rules enforced

**Why Full Node First:**
1. Learn real-world implementation details, not simplified versions
2. Understand ALL components of a blockchain node
3. See how all pieces fit together
4. Foundation matches actual Bitcoin architecture
5. Can add networking later (Phase 2)
6. Better for exploring startup ideas (realistic understanding)

**What We're Building:**
```
Full Archival Node (Bitcoin Core equivalent - no network):
├── Complete blockchain storage (all blocks)
├── Full UTXO set (all unspent outputs)
├── Full transaction index (all transactions)
├── PoW mining capability
├── Complete validation logic
├── Wallet functionality
├── Mempool management
├── Fork handling
└── Chain reorganization
```

**What We're Skipping (for Phase 1):**
```
- P2P networking (single node only)
  - No peer discovery
  - No block propagation
  - No transaction relay
  - No network consensus
- Advanced Bitcoin features
  - Full Bitcoin Script (using simplified P2PKH only)
  - SegWit
  - Lightning Network
- Production optimizations
  - LevelDB (using memory/JSON)
  - Bloom filters
  - Compact blocks
```

**Clarification on "Full Node":**

**You WILL have:**
- Complete blockchain (every block from genesis)
- Every transaction ever made
- Full validation capability
- Independent verification
- Archival node capabilities

**You will NOT have:**
- Network layer (can't talk to other nodes)
- Can only interact via local API/CLI
- Single instance (not distributed)

**This is like:** Running Bitcoin Core with -connect=0 (no peers)
- Still a full node
- Still validates everything
- Just isolated (no network)

---

## Phase 1 Implementation: Production-Quality Blockchain

### Goals
- Implement Bitcoin-accurate block structure (80-byte header)
- Full Proof-of-Work mining with difficulty adjustment
- Complete UTXO transaction model with digital signatures
- Merkle trees for transaction commitment
- Fork handling and chain reorganization
- All consensus rules from Bitcoin whitepaper

### Architecture Overview

```
Core Components:
1. Block (header + transactions)
2. Transaction (inputs, outputs, signatures)
3. UTXO Set (unspent transaction outputs)
4. Blockchain (chain management, validation)
5. Miner (PoW search, block creation)
6. Wallet (key management, transaction creation)
7. Mempool (pending transactions)
```

---

### 1. Block Header & Block Structure

**File:** `src/core/block.py`

#### BlockHeader Class (80 bytes - Bitcoin-accurate)

**Fields (exactly as in Bitcoin):**
- `version` (4 bytes) - Protocol version number
- `previous_block_hash` (32 bytes) - Hash of previous block header
- `merkle_root` (32 bytes) - Root of Merkle tree of transactions
- `timestamp` (4 bytes) - Unix timestamp (seconds since epoch)
- `difficulty_bits` (4 bytes) - Compact encoding of difficulty target
- `nonce` (4 bytes) - Mining nonce (0 to 2^32)

**Methods:**
- `calculate_hash()` - SHA-256(SHA-256(serialize(header)))
- `serialize()` - Convert to 80-byte binary format
- `deserialize(bytes)` - Parse from binary
- `meets_difficulty_target()` - Check if hash < target
- `to_dict()` / `from_dict()` - JSON serialization

**Key Concepts:**
- Exactly 80 bytes (Bitcoin protocol spec)
- Double SHA-256 hashing
- Big-endian vs little-endian encoding
- Compact difficulty target representation

#### Block Class

**Fields:**
- `header` - BlockHeader instance
- `transactions` - List of Transaction objects
- `height` - Block number in chain (derived)

**Methods:**
- `calculate_merkle_root()` - Build Merkle tree from transactions
- `add_transaction(tx)` - Add transaction to block
- `is_valid()` - Comprehensive validation
- `get_size()` - Block size in bytes
- `to_dict()` / `from_dict()` - Serialization

**Validation Rules:**
- PoW hash meets difficulty target
- Merkle root matches transactions
- Timestamp within acceptable window (not too far in future)
- First transaction is coinbase (only first)
- All other transactions valid
- Block size within limit

---

### 2. Transaction System (UTXO Model)

**Files:** `src/core/transaction.py`, `src/core/utxo.py`

#### Transaction Class

**Fields:**
- `version` (4 bytes) - Transaction version
- `inputs` - List of TransactionInput
- `outputs` - List of TransactionOutput
- `locktime` (4 bytes) - Earliest time transaction is valid
- `txid` - Transaction ID (double SHA-256 of transaction)

**Methods:**
- `calculate_txid()` - Hash of serialized transaction
- `is_coinbase()` - Check if this is coinbase (mining reward)
- `get_fee()` - Calculate: sum(inputs) - sum(outputs)
- `serialize()` / `deserialize()` - Binary format
- `to_dict()` / `from_dict()` - JSON format

#### TransactionInput Class

**Fields:**
- `previous_output` - Reference to UTXO being spent
  - `txid` - Transaction ID (32 bytes)
  - `output_index` - Which output of that transaction
- `signature_script` - Unlocking script (signature + public key)
- `sequence` - Sequence number (for replace-by-fee)

**Methods:**
- `serialize()` / `deserialize()`
- `is_valid_signature()` - Verify signature matches public key
- `get_referenced_output()` - Look up UTXO in UTXO set

#### TransactionOutput Class

**Fields:**
- `value` - Amount in satoshis (int64)
- `pubkey_script` - Locking script (public key hash)

**Methods:**
- `serialize()` / `deserialize()`
- `is_dust()` - Check if value is too small
- `get_address()` - Derive address from pubkey script

#### UTXO Set Class

**File:** `src/core/utxo.py`

**Purpose:** Track all unspent transaction outputs

**Data Structure:**
```python
utxo_set = {
    "txid:output_index": {
        "value": 50_000_000,  # satoshis
        "pubkey_script": "...",
        "block_height": 100,
        "is_coinbase": False
    }
}
```

**Methods:**
- `add_utxo(txid, index, output, height, is_coinbase)` - Add new unspent output
- `remove_utxo(txid, index)` - Mark as spent
- `get_utxo(txid, index)` - Look up specific UTXO
- `get_utxos_for_address(address)` - Find all UTXOs for an address
- `get_balance(address)` - Sum UTXOs for address
- `is_spent(txid, index)` - Check if already spent

**Key Concepts:**
- UTXO = "coin" in Bitcoin's model
- Spending = consuming inputs, creating new outputs
- Double-spend prevention (UTXO can only be spent once)
- Coinbase maturity (can't spend coinbase for 100 blocks)

---

### 3. Digital Signatures (ECDSA)

**File:** `src/crypto/keys.py`

#### Private/Public Key Management

**Uses:** secp256k1 curve (same as Bitcoin)

**Classes:**
- `PrivateKey` - Wraps private key, can sign
- `PublicKey` - Wraps public key, can verify
- `KeyPair` - Private + public key pair

**Functions:**
- `generate_keypair()` - Create new random key pair
- `sign_transaction(tx, private_key)` - Create ECDSA signature
- `verify_signature(tx, signature, public_key)` - Verify signature
- `public_key_to_address(pubkey)` - Derive Bitcoin address
  - SHA-256(pubkey)
  - RIPEMD-160(hash)
  - Base58Check encoding

**Key Concepts:**
- ECDSA (Elliptic Curve Digital Signature Algorithm)
- secp256k1 curve (used by Bitcoin)
- Public key derivation (not reversible)
- Address derivation (hash + checksum)

---

### 4. Merkle Trees

**File:** `src/crypto/merkle.py`

#### MerkleTree Class

**Purpose:** Efficiently commit to all transactions in block

**Structure:**
```
        Root Hash
        /        \
    Hash01      Hash23
    /    \      /    \
  Hash0 Hash1 Hash2 Hash3
    |     |     |     |
   Tx0   Tx1   Tx2   Tx3
```

**Methods:**
- `build_tree(transactions)` - Build Merkle tree from transaction list
- `get_root()` - Return root hash (Merkle root)
- `get_proof(tx_index)` - Generate Merkle proof for transaction
- `verify_proof(tx, proof, root)` - Verify transaction was in block
- `get_tree_depth()` - Calculate tree depth

**Key Concepts:**
- Bottom-up construction (hash pairs)
- Odd number of transactions (duplicate last)
- Efficient proofs (log n size)
- SPV support (verify without full block)

---

### 5. Proof-of-Work Mining

**File:** `src/mining/miner.py`

#### Miner Class

**Purpose:** Find valid nonce to meet difficulty target

**Methods:**
- `mine_block(block_template, difficulty_target)` - Main mining loop
  - Try nonce from 0 to 2^32
  - Calculate hash for each nonce
  - If hash < target, return block
  - If no valid nonce in range, increment extra_nonce and retry
- `calculate_target(difficulty_bits)` - Convert compact form to 256-bit target
- `difficulty_from_target(target)` - Calculate human-readable difficulty
- `estimate_time(hash_rate, difficulty)` - Expected time to find block

**Mining Loop:**
```python
def mine_block(self, block_template, difficulty_target):
    extra_nonce = 0
    while True:
        # Try all 4 billion nonces
        for nonce in range(2**32):
            block_template.header.nonce = nonce
            hash_result = block_template.header.calculate_hash()

            if hash_result < difficulty_target:
                return block_template  # Found valid block!

        # Exhausted nonce space, modify block slightly
        extra_nonce += 1
        block_template.transactions[0].set_extra_nonce(extra_nonce)
        block_template.header.merkle_root = block_template.calculate_merkle_root()
```

**Key Concepts:**
- Brute force search (no shortcuts)
- Hash rate measurement (hashes per second)
- Extra nonce (when standard nonce exhausted)
- Difficulty target (leading zeros in hash)

---

### 6. Difficulty Adjustment

**File:** `src/consensus/difficulty.py`

#### Difficulty Adjustment Logic

**Purpose:** Maintain 10-minute average block time

**Algorithm (Bitcoin's algorithm):**
```python
def adjust_difficulty(blockchain):
    # Adjust every 2016 blocks
    if blockchain.height % 2016 != 0:
        return blockchain.get_latest_block().header.difficulty_bits

    # Get time for last 2016 blocks
    first_block = blockchain.get_block_by_height(blockchain.height - 2016)
    last_block = blockchain.get_latest_block()

    time_taken = last_block.header.timestamp - first_block.header.timestamp
    expected_time = 2016 * 10 * 60  # 2 weeks in seconds

    # Calculate adjustment
    adjustment = expected_time / time_taken

    # Limit adjustment to 4x in either direction
    if adjustment > 4.0:
        adjustment = 4.0
    elif adjustment < 0.25:
        adjustment = 0.25

    # Calculate new target
    old_target = calculate_target(last_block.header.difficulty_bits)
    new_target = old_target * adjustment

    return target_to_compact_bits(new_target)
```

**Functions:**
- `calculate_next_difficulty(blockchain)` - Run adjustment algorithm
- `target_to_compact_bits(target)` - Encode target in 4 bytes
- `compact_bits_to_target(bits)` - Decode target from 4 bytes
- `validate_difficulty(block, blockchain)` - Verify difficulty is correct

**Key Concepts:**
- Adjustment every 2016 blocks (~2 weeks)
- Target: 10 minutes per block
- Limited adjustment (prevent wild swings)
- Consensus rule (all nodes must agree)

---

### 7. Blockchain Class (Chain Management)

**File:** `src/core/blockchain.py`

#### Blockchain Class

**Purpose:** Manage chain of blocks, handle forks, validate

**Fields:**
- `blocks` - Dictionary: block_hash → Block
- `block_height_index` - Dictionary: height → list of block hashes (for forks)
- `chain_tips` - List of competing chain tips
- `best_chain` - Current longest chain
- `utxo_set` - Current UTXO set for best chain
- `mempool` - Pending transactions

**Methods:**

**Chain Operations:**
- `add_block(block)` - Add block, update chain
- `get_block(block_hash)` - Retrieve block by hash
- `get_block_by_height(height)` - Get block at specific height
- `get_chain_tip()` - Return tip of longest chain
- `get_chain_height()` - Return current height

**Validation:**
- `validate_block(block)` - Full block validation
  - PoW verification
  - Previous block exists
  - Merkle root correct
  - All transactions valid
  - Difficulty correct
  - Timestamp reasonable
- `validate_transaction(tx)` - Transaction validation
  - Inputs exist in UTXO set
  - Inputs not already spent
  - Signatures valid
  - Output amounts positive, no overflow
  - Fee >= 0

**Fork Handling:**
- `handle_fork(block)` - Detect competing blocks
- `reorganize_chain(new_tip)` - Switch to longer chain
  - Find common ancestor
  - Unwind blocks from old chain
  - Apply blocks from new chain
  - Update UTXO set
  - Return transactions to mempool
- `calculate_chain_work(from_block, to_block)` - Sum difficulty

**Genesis Block:**
- `create_genesis_block()` - Hardcoded first block
  - Height 0
  - Previous hash = 0x00...00
  - Contains initial mining reward
  - Timestamp: Bitcoin genesis (Jan 3, 2009)

---

### 8. Wallet Functionality

**File:** `src/wallet/wallet.py`

#### Wallet Class

**Purpose:** Manage keys, create transactions, track balance

**Fields:**
- `keypairs` - List of KeyPair objects
- `utxo_set` - Reference to blockchain's UTXO set
- `addresses` - List of addresses owned

**Methods:**

**Key Management:**
- `generate_new_keypair()` - Create new address
- `import_private_key(wif)` - Import key
- `export_private_key(address)` - Export key (WIF format)
- `get_all_addresses()` - List owned addresses

**Balance:**
- `get_balance()` - Sum all UTXOs for owned addresses
- `get_utxos()` - Get all UTXOs for wallet

**Transaction Creation:**
- `create_transaction(to_address, amount, fee)` - Build transaction
  - Select UTXOs (coin selection)
  - Create inputs (reference selected UTXOs)
  - Create outputs (payment + change)
  - Sign all inputs
  - Return Transaction object
- `sign_transaction(tx)` - Sign transaction inputs
- `broadcast_transaction(tx)` - Add to mempool

**Coin Selection:**
- Select UTXOs to cover amount + fee
- Minimize inputs (for lower fees)
- Create change output if needed

---

### 9. Mempool (Transaction Pool)

**File:** `src/core/mempool.py`

#### Mempool Class

**Purpose:** Hold pending transactions waiting to be mined

**Fields:**
- `transactions` - Dictionary: txid → Transaction
- `fee_priority` - Sorted list by fee rate

**Methods:**
- `add_transaction(tx)` - Add if valid
- `remove_transaction(txid)` - Remove (after mining or invalid)
- `get_transactions(limit)` - Get highest-fee transactions
- `get_transaction(txid)` - Look up specific transaction
- `clear_confirmed(block)` - Remove transactions included in block
- `is_double_spend(tx)` - Check if spends same UTXO as existing tx

**Key Concepts:**
- Fee market (miners prioritize high-fee transactions)
- Replace-by-fee (higher fee replaces pending tx)
- Mempool size limits
- Double-spend detection

---

### 10. Consensus Rules

**File:** `src/consensus/rules.py`

#### All Bitcoin Consensus Rules

**Block Rules:**
- Maximum block size: 1 MB (legacy) or 4 MB (SegWit)
- Maximum 4,000 signature operations per block
- Block timestamp must be greater than median of last 11 blocks
- Block timestamp cannot be more than 2 hours in future
- First transaction must be coinbase (only first!)
- Coinbase reward: 50 BTC initially, halves every 210,000 blocks
- Coinbase cannot be spent for 100 blocks (maturity rule)

**Transaction Rules:**
- No duplicate transactions in same block
- All inputs must reference existing UTXOs
- UTXOs cannot be double-spent
- Sum of inputs >= sum of outputs
- All signatures must be valid
- Output values must be >= 0 (no negative amounts)
- Locktime must be satisfied
- Transaction size limits

**Script Rules (simplified for Phase 1):**
- P2PKH (Pay to Public Key Hash) - standard payment
- Signature must match public key
- Public key hash must match output script

**Difficulty Rules:**
- Adjust every 2016 blocks
- Maximum 4x change per adjustment
- Target: 10 minutes per block

---

### File Structure (Complete)

```
bitcoin-blockchain/
├── README.md
├── requirements.txt
├── setup.py
├── .gitignore
│
├── src/
│   ├── __init__.py
│   │
│   ├── core/
│   │   ├── __init__.py
│   │   ├── block.py          # Block & BlockHeader classes
│   │   ├── transaction.py    # Transaction, TxInput, TxOutput
│   │   ├── blockchain.py     # Blockchain management
│   │   ├── utxo.py          # UTXO set management
│   │   └── mempool.py       # Transaction pool
│   │
│   ├── crypto/
│   │   ├── __init__.py
│   │   ├── hash.py          # SHA-256, RIPEMD-160
│   │   ├── keys.py          # ECDSA, key management
│   │   └── merkle.py        # Merkle tree implementation
│   │
│   ├── mining/
│   │   ├── __init__.py
│   │   └── miner.py         # PoW mining logic
│   │
│   ├── consensus/
│   │   ├── __init__.py
│   │   ├── difficulty.py    # Difficulty adjustment
│   │   ├── rules.py         # Consensus rules
│   │   └── validation.py    # Block/transaction validation
│   │
│   ├── wallet/
│   │   ├── __init__.py
│   │   └── wallet.py        # Wallet functionality
│   │
│   └── utils/
│       ├── __init__.py
│       ├── serialization.py # Binary serialization
│       └── encoding.py      # Base58, hex conversions
│
├── tests/
│   ├── __init__.py
│   ├── test_block.py
│   ├── test_transaction.py
│   ├── test_utxo.py
│   ├── test_mining.py
│   ├── test_difficulty.py
│   ├── test_blockchain.py
│   ├── test_merkle.py
│   ├── test_keys.py
│   └── test_wallet.py
│
└── examples/
    ├── __init__.py
    ├── 01_basic_mining.py       # Mine first block
    ├── 02_send_transaction.py   # Create and send transaction
    ├── 03_fork_handling.py      # Demonstrate fork resolution
    ├── 04_difficulty_adjust.py  # Show difficulty adjustment
    └── 05_full_demo.py          # Complete demonstration
```

---

### Implementation Details

**Bitcoin-Accurate:**
- 80-byte block header (exact Bitcoin format)
- UTXO model (not account-based)
- Proof-of-Work (leading zeros in hash)
- Difficulty adjustment (every 2016 blocks)
- Merkle trees (transaction commitment)
- ECDSA signatures (secp256k1)
- Halving schedule (50 → 25 → 12.5 → 6.25 ...)

**Simplified (for Phase 1):**
- No P2P network (single node)
- Simplified script system (P2PKH only, no full Bitcoin Script)
- No SegWit (legacy transactions only)
- No Lightning Network
- Memory storage (no LevelDB)
- No full Bitcoin protocol messages

**Libraries:**
- `hashlib` - SHA-256 (stdlib)
- `ecdsa` - Elliptic curve signatures
- `base58` - Bitcoin address encoding
- `merkletools` - Merkle tree implementation (existing library)
- `json` - Serialization
- `pytest` - Testing
- `rich` - Beautiful CLI output and visualization
- `flask` - Optional web interface for blockchain explorer

---

### Success Criteria

**Phase 1 Complete When You Can:**

1. **Mine blocks:**
   - Create genesis block
   - Mine new blocks with PoW
   - See difficulty adjustment working
   - Observe block time averaging 10 minutes

2. **Handle transactions:**
   - Create wallet with addresses
   - Send coins between addresses
   - See UTXO model in action
   - Verify signatures

3. **Validate everything:**
   - Reject invalid blocks (bad PoW, bad Merkle root)
   - Reject double-spends
   - Reject invalid signatures
   - Enforce all consensus rules

4. **Handle forks:**
   - Create competing blocks
   - See longest chain rule
   - Observe chain reorganization
   - Understand orphan blocks

5. **Understand deeply:**
   - Explain why PoW works
   - Explain why UTXO model is used
   - Explain how difficulty adjustment maintains security
   - Explain Merkle tree benefits
   - Explain fork resolution

---

### User-Specific Requirements & Implementation Details

#### 1. Block Height - Why Not in Header?

**Answer:** Height is **derived**, not stored in header. This is Bitcoin's actual design.

**Reasons:**
- **Redundant:** Can be calculated by counting blocks from genesis
- **Immutable:** Block header must be exactly 80 bytes (Bitcoin spec)
- **Derivable:** height = count of blocks before this one
- **Efficiency:** No need to store what can be computed
- **Consensus:** All nodes derive same height independently

**Implementation:**
```python
class Block:
    def __init__(self, header, transactions):
        self.header = header  # 80 bytes
        self.transactions = transactions
        self._height = None  # Cached, computed later

    @property
    def height(self):
        """Derived property, not stored in header"""
        if self._height is None:
            # Calculate by walking chain backwards
            self._height = self.blockchain.calculate_height(self)
        return self._height
```

**Where height IS stored:**
- Blockchain's index: `{height → [block_hashes]}`
- Database for fast lookup
- Not in the 80-byte header itself

---

#### 2. Block Size Validation - Why Needed?

**Answer:** It's a **consensus rule** - all nodes must enforce same limits.

**Reasons:**

**Prevent spam/DoS:**
- Without limit, attacker creates huge blocks
- Network bandwidth exhausted
- Nodes can't keep up
- Centralization pressure (only powerful nodes survive)

**Network constraints:**
- 10-minute block time target
- Large blocks take longer to propagate
- Increases orphan rate (more forks)
- Bitcoin chose 1 MB initially (now 4 MB with SegWit)

**Consensus requirement:**
- All nodes must agree on valid blocks
- If node A accepts 10 MB block but node B rejects it
- Network splits permanently
- Therefore: hard limit in consensus rules

**Our implementation:**
```python
MAX_BLOCK_SIZE = 1_000_000  # 1 MB (Bitcoin legacy)

def validate_block_size(block):
    block_size = len(block.serialize())
    if block_size > MAX_BLOCK_SIZE:
        raise ValidationError(f"Block too large: {block_size} > {MAX_BLOCK_SIZE}")
    return True
```

---

#### 3. Merkle Tree - Use Existing Implementation

**Agreed!** We'll use `merkletools` library instead of implementing from scratch.

**Why:**
- Well-tested production library
- Focus on understanding usage, not implementation
- Saves time for more interesting parts

**Implementation:**
```python
from merkletools import MerkleTools

class Block:
    def calculate_merkle_root(self):
        """Calculate Merkle root using merkletools library"""
        mt = MerkleTools(hash_type='sha256')

        # Add all transaction IDs
        for tx in self.transactions:
            mt.add_leaf(tx.txid, do_hash=False)  # Already hashed

        mt.make_tree()
        return mt.get_merkle_root()

    def get_merkle_proof(self, tx_index):
        """Get Merkle proof for transaction at index"""
        mt = MerkleTools(hash_type='sha256')
        for tx in self.transactions:
            mt.add_leaf(tx.txid, do_hash=False)
        mt.make_tree()

        return mt.get_proof(tx_index)

    @staticmethod
    def verify_merkle_proof(tx_hash, merkle_root, proof):
        """Verify transaction was in block"""
        mt = MerkleTools(hash_type='sha256')
        return mt.validate_proof(proof, tx_hash, merkle_root)
```

**You'll learn:**
- How to use Merkle trees
- Why they're useful (SPV, pruning)
- Proof verification
- Not implementation details (less interesting)

---

#### 4. Development Mode - Mock Mining for Debugging

**Problem:** Real mining takes minutes/hours - impossible to debug.

**Solution:** Multiple mining modes

##### Mode 1: Low Difficulty (Development Default)

```python
class Blockchain:
    def __init__(self, development_mode=True):
        if development_mode:
            self.DEVELOPMENT_DIFFICULTY = 0x1f0fffff  # Very easy (1-2 leading zeros)
            self.BLOCK_TIME_TARGET = 5  # 5 seconds instead of 10 minutes
            self.DIFFICULTY_ADJUSTMENT_INTERVAL = 10  # Every 10 blocks, not 2016
        else:
            # Production Bitcoin settings
            self.DIFFICULTY = 0x1d00ffff
            self.BLOCK_TIME_TARGET = 600  # 10 minutes
            self.DIFFICULTY_ADJUSTMENT_INTERVAL = 2016

class Miner:
    def mine_block(self, block_template, difficulty_target):
        """Mining with low difficulty finds blocks in ~1 second"""
        for nonce in range(2**32):
            block_template.header.nonce = nonce
            hash_result = block_template.header.calculate_hash()

            if hash_result < difficulty_target:
                print(f"Block mined! Nonce: {nonce}")
                return block_template

            # In dev mode, only tries ~1000 nonces before finding one
```

**Result:** Blocks mine in 1-5 seconds instead of 10 minutes

##### Mode 2: Instant Mine (Skip PoW Entirely)

```python
class Miner:
    def __init__(self, instant_mine=False):
        self.instant_mine = instant_mine

    def mine_block(self, block_template, difficulty_target):
        if self.instant_mine:
            # Skip PoW completely - set nonce to 0
            block_template.header.nonce = 0
            print("Instant mine mode - skipping PoW")
            return block_template
        else:
            # Real mining
            return self._do_proof_of_work(block_template, difficulty_target)
```

**Use for:** Testing transaction logic, fork handling, validation - not PoW itself

##### Mode 3: Pre-Computed Blocks

```python
# Pre-computed valid blocks for testing
PRECOMPUTED_BLOCKS = {
    "genesis": {
        "header": {...},
        "transactions": [...]
    },
    "block_1": {
        "header": {...},
        "transactions": [...]
    },
    # ... more blocks
}

def load_precomputed_blockchain():
    """Load pre-mined blocks for instant testing"""
    blockchain = Blockchain()
    for block_data in PRECOMPUTED_BLOCKS.values():
        block = Block.from_dict(block_data)
        blockchain.add_block(block)
    return blockchain
```

**Use for:** Quickly get to interesting state (e.g., 100 blocks deep) without waiting

##### Mode 4: Deterministic Mining (For Debugging)

```python
class Miner:
    def mine_block_deterministic(self, block_template, target_nonce):
        """Mine with specific nonce (for reproducing bugs)"""
        block_template.header.nonce = target_nonce
        hash_result = block_template.header.calculate_hash()

        if hash_result < difficulty_target:
            return block_template
        else:
            raise ValueError(f"Nonce {target_nonce} doesn't produce valid block")
```

**Configuration:**

```python
# config.py
DEVELOPMENT_MODE = True  # Set to False for production-like behavior
INSTANT_MINE = False     # Set to True to skip PoW entirely
LOW_DIFFICULTY = True    # Set to True for 1-second mining
```

---

#### 5. Creating Fork Situations - Helper Functions

##### Manual Fork Creation

```python
class BlockchainTester:
    """Helper class for creating test scenarios"""

    @staticmethod
    def create_fork(blockchain, fork_height, num_branches=2):
        """Create a fork at specific height

        Args:
            blockchain: Blockchain instance
            fork_height: Height to fork at
            num_branches: Number of competing branches (default 2)

        Returns:
            List of competing block chains
        """
        # Get block to fork from
        fork_point = blockchain.get_block_by_height(fork_height)

        competing_blocks = []
        for i in range(num_branches):
            # Create different block at same height
            block = Block(
                header=BlockHeader(
                    version=1,
                    previous_block_hash=fork_point.header.hash,
                    timestamp=int(time.time()) + i,  # Different timestamp
                    difficulty_bits=blockchain.get_current_difficulty()
                ),
                transactions=[
                    create_coinbase_transaction(
                        reward_address=f"miner_{i}",
                        block_height=fork_height + 1
                    )
                ]
            )

            # Mine the block
            miner = Miner()
            mined_block = miner.mine_block(block, blockchain.get_current_difficulty())
            competing_blocks.append(mined_block)

        return competing_blocks

    @staticmethod
    def demonstrate_fork_resolution(blockchain):
        """Create fork and show resolution"""
        print("Creating fork at block 10...")

        # Mine to block 10
        for i in range(11):
            blockchain.mine_next_block()

        # Create competing blocks at height 11
        block_11a, block_11b = BlockchainTester.create_fork(blockchain, 10, 2)

        # Add both (creates fork)
        blockchain.add_block(block_11a)
        print(f"Added block 11a - Chain tips: {len(blockchain.chain_tips)}")

        blockchain.add_block(block_11b)
        print(f"Added block 11b - Chain tips: {len(blockchain.chain_tips)}")

        # Mine on top of 11a (makes it winner)
        blockchain.mine_next_block(parent=block_11a)
        print(f"Mined block 12 - Chain reorganized! Winner: {blockchain.best_chain.tip.header.hash[:8]}")

        return blockchain
```

---

#### 6. Blockchain Visualization

##### Option 1: CLI Visualization (Built-in)

```python
from rich.console import Console
from rich.table import Table
from rich.tree import Tree

class BlockchainVisualizer:
    def __init__(self, blockchain):
        self.blockchain = blockchain
        self.console = Console()

    def print_chain(self, start_height=0, end_height=None):
        """Print blockchain in terminal"""
        table = Table(title="Blockchain")
        table.add_column("Height", style="cyan")
        table.add_column("Hash", style="magenta")
        table.add_column("Nonce", style="green")
        table.add_column("Txs", style="yellow")
        table.add_column("Timestamp", style="blue")

        end = end_height or self.blockchain.height
        for height in range(start_height, end + 1):
            block = self.blockchain.get_block_by_height(height)
            table.add_row(
                str(height),
                block.header.hash[:16] + "...",
                str(block.header.nonce),
                str(len(block.transactions)),
                datetime.fromtimestamp(block.header.timestamp).strftime("%Y-%m-%d %H:%M:%S")
            )

        self.console.print(table)

    def print_fork_tree(self):
        """Visualize forks as tree"""
        tree = Tree("🔗 Blockchain")

        def add_block_to_tree(block, parent_tree):
            node = parent_tree.add(
                f"Block {block.height}: {block.header.hash[:8]}..."
            )
            # Recursively add children
            for child in self.blockchain.get_children(block):
                add_block_to_tree(child, node)

        genesis = self.blockchain.get_block_by_height(0)
        add_block_to_tree(genesis, tree)

        self.console.print(tree)

    def print_block_details(self, block_hash_or_height):
        """Print detailed block information"""
        block = self.blockchain.get_block(block_hash_or_height)

        self.console.print(f"\n[bold]Block {block.height}[/bold]")
        self.console.print(f"Hash: {block.header.hash}")
        self.console.print(f"Previous: {block.header.previous_block_hash}")
        self.console.print(f"Merkle Root: {block.header.merkle_root}")
        self.console.print(f"Timestamp: {datetime.fromtimestamp(block.header.timestamp)}")
        self.console.print(f"Nonce: {block.header.nonce}")
        self.console.print(f"Difficulty: {block.header.difficulty_bits}")
        self.console.print(f"\nTransactions ({len(block.transactions)}):")

        for i, tx in enumerate(block.transactions):
            self.console.print(f"  [{i}] {tx.txid[:16]}... ({len(tx.inputs)} in, {len(tx.outputs)} out)")
```

**Usage:**
```python
visualizer = BlockchainVisualizer(blockchain)
visualizer.print_chain()  # Print all blocks
visualizer.print_fork_tree()  # Show fork structure
visualizer.print_block_details(10)  # Show block 10 details
```

##### Option 2: Web Interface (Flask - Optional)

```python
# examples/blockchain_explorer.py
from flask import Flask, render_template, jsonify

app = Flask(__name__)
blockchain = None  # Set by main()

@app.route('/')
def index():
    """Homepage - show latest blocks"""
    return render_template('index.html',
                         height=blockchain.height,
                         latest_blocks=blockchain.get_latest_blocks(10))

@app.route('/block/<int:height>')
def block_detail(height):
    """Block detail page"""
    block = blockchain.get_block_by_height(height)
    return render_template('block.html', block=block)

@app.route('/api/chain')
def api_chain():
    """API: Full chain as JSON"""
    return jsonify({
        'height': blockchain.height,
        'blocks': [block.to_dict() for block in blockchain.get_all_blocks()]
    })

if __name__ == '__main__':
    blockchain = load_blockchain()
    app.run(debug=True, port=5000)
```

Access at: `http://localhost:5000`

##### Option 3: JSON Export

```python
class Blockchain:
    def export_to_json(self, filename):
        """Export entire blockchain to JSON file"""
        data = {
            'height': self.height,
            'blocks': [block.to_dict() for block in self.get_all_blocks()],
            'utxo_set': self.utxo_set.to_dict(),
            'chain_tips': [tip.hash for tip in self.chain_tips]
        }

        with open(filename, 'w') as f:
            json.dump(data, f, indent=2)

        print(f"Blockchain exported to {filename}")

    @staticmethod
    def import_from_json(filename):
        """Load blockchain from JSON file"""
        with open(filename, 'r') as f:
            data = json.load(f)

        blockchain = Blockchain()
        for block_data in data['blocks']:
            block = Block.from_dict(block_data)
            blockchain.add_block(block)

        return blockchain
```

**Usage:**
```python
blockchain.export_to_json('blockchain_snapshot.json')
# View in text editor or JSON viewer
```

---

#### 7. Debug Flow Scripts - Step Through Code

##### Flow Script 1: Mine First Block

```python
# examples/debug_flows/01_mine_first_block.py
"""
Debug Flow: Mine first block after genesis

Set breakpoints at:
- Line XX: Before mining starts
- Line XX: Inside mining loop (try different nonces)
- Line XX: When valid nonce found
- Line XX: Block added to chain
"""

def debug_mine_first_block():
    # Initialize blockchain
    blockchain = Blockchain(development_mode=True)
    print(f"Genesis block: {blockchain.get_chain_tip().header.hash}")

    # Create wallet
    wallet = Wallet(blockchain)
    miner_address = wallet.generate_new_keypair()

    # Create block template
    coinbase_tx = create_coinbase_transaction(
        reward_address=miner_address,
        block_height=1,
        reward_amount=50_00000000  # 50 BTC
    )

    # BREAKPOINT HERE: Examine coinbase transaction
    import pdb; pdb.set_trace()

    # Create block
    block_template = Block(
        header=BlockHeader(
            version=1,
            previous_block_hash=blockchain.get_chain_tip().header.hash,
            timestamp=int(time.time()),
            difficulty_bits=blockchain.get_current_difficulty()
        ),
        transactions=[coinbase_tx]
    )

    # Calculate Merkle root
    block_template.header.merkle_root = block_template.calculate_merkle_root()

    # BREAKPOINT HERE: Examine block template before mining
    import pdb; pdb.set_trace()

    # Mine block
    miner = Miner()
    print("Starting mining...")
    mined_block = miner.mine_block(block_template, blockchain.get_current_difficulty())

    # BREAKPOINT HERE: Examine mined block
    import pdb; pdb.set_trace()

    # Add to blockchain
    blockchain.add_block(mined_block)

    print(f"Block 1 mined! Hash: {mined_block.header.hash}")
    print(f"Nonce: {mined_block.header.nonce}")
    print(f"Wallet balance: {wallet.get_balance()} satoshis")

    return blockchain
```

**Run with:**
```bash
python -m pdb examples/debug_flows/01_mine_first_block.py
```

##### Flow Script 2: Send Transaction

```python
# examples/debug_flows/02_send_transaction.py
"""
Debug Flow: Create and send transaction between wallets

Set breakpoints at:
- Line XX: Before transaction creation
- Line XX: UTXO selection (coin selection algorithm)
- Line XX: Transaction signing
- Line XX: Transaction validation
- Line XX: Adding to mempool
- Line XX: Mining block with transaction
"""

def debug_send_transaction():
    # Setup: Mine 110 blocks to Alice (100 for maturity + 10 to spend)
    blockchain = Blockchain(development_mode=True)
    alice_wallet = Wallet(blockchain)
    alice_address = alice_wallet.generate_new_keypair()

    print("Mining 110 blocks to Alice...")
    for i in range(110):
        blockchain.mine_next_block(coinbase_address=alice_address)

    print(f"Alice balance: {alice_wallet.get_balance()} satoshis")

    # BREAKPOINT HERE: Examine Alice's UTXOs
    import pdb; pdb.set_trace()

    # Create Bob's wallet
    bob_wallet = Wallet(blockchain)
    bob_address = bob_wallet.generate_new_keypair()

    # Alice creates transaction to Bob
    print("Creating transaction...")
    tx = alice_wallet.create_transaction(
        to_address=bob_address,
        amount=25_00000000,  # 25 BTC
        fee=10000  # 0.0001 BTC
    )

    # BREAKPOINT HERE: Examine transaction before signing
    import pdb; pdb.set_trace()

    # Sign transaction
    alice_wallet.sign_transaction(tx)

    # BREAKPOINT HERE: Examine signed transaction
    import pdb; pdb.set_trace()

    # Validate transaction
    print("Validating transaction...")
    blockchain.validate_transaction(tx)

    # Add to mempool
    blockchain.mempool.add_transaction(tx)
    print(f"Transaction added to mempool: {tx.txid}")

    # BREAKPOINT HERE: Examine mempool state
    import pdb; pdb.set_trace()

    # Mine block with transaction
    print("Mining block with transaction...")
    blockchain.mine_next_block(coinbase_address=alice_address)

    # Check balances
    print(f"Alice balance: {alice_wallet.get_balance()} satoshis")
    print(f"Bob balance: {bob_wallet.get_balance()} satoshis")

    # BREAKPOINT HERE: Examine updated UTXO set
    import pdb; pdb.set_trace()

    return blockchain
```

---

## Future Phases (Optional Extensions)

### Phase 2: P2P Networking (Optional)
**New Components:**
- Peer discovery (DNS seeds, address exchange)
- P2P message protocol (version, getdata, inv, block, tx)
- Block propagation and relay
- Transaction gossip protocol
- Peer connection management
- Network consensus (multiple nodes)

**Learning Goals:**
- Understand distributed consensus without coordinator
- See how nodes discover and communicate
- Experience network partitions and healing
- Understand eclipse attacks and Sybil resistance

**Implementation:**
- Socket-based P2P communication
- Multiple nodes running locally
- Block/transaction synchronization
- Fork resolution across network

---

## Technology Stack

**Language:** Python 3.10+
- Easy to read and understand
- Great for learning (not production)
- Rich ecosystem (cryptography libraries)

**Libraries:**
- `hashlib` - SHA-256 hashing (standard library)
- `json` - Serialization (standard library)
- `datetime` - Timestamps (standard library)
- `ecdsa` - Digital signatures
- `base58` - Bitcoin address encoding
- `merkletools` - Merkle tree implementation
- `pytest` - Testing framework
- `rich` - CLI visualization
- `flask` - Optional web interface

---

## Success Metrics

**Phase 1 Complete When You Can:**

**Technical Demonstrations:**
- [ ] Mine genesis block with valid PoW
- [ ] Mine 100 blocks and observe difficulty adjustment
- [ ] Create wallets and generate addresses
- [ ] Send transactions between wallets
- [ ] Verify UTXO model working (balance updates correctly)
- [ ] Create fork and see reorganization
- [ ] Validate all consensus rules enforced
- [ ] Run full test suite (all tests pass)
- [ ] Demonstrate Merkle proof verification

**Conceptual Understanding:**
- [ ] Explain why PoW makes blockchain secure
- [ ] Explain how difficulty adjustment maintains 10-minute blocks
- [ ] Explain UTXO model vs account model
- [ ] Explain why Merkle trees enable SPV
- [ ] Explain fork resolution (longest chain rule)
- [ ] Explain double-spend prevention
- [ ] Explain why signatures are necessary
- [ ] Explain all consensus rules and their purpose

**Practical Skills:**
- [ ] Can read any block in the chain
- [ ] Can trace a transaction through UTXO set
- [ ] Can calculate mining profitability
- [ ] Can estimate time to mine block at given difficulty
- [ ] Can verify block validity manually
- [ ] Can explain every field in block header
- [ ] Can modify code to add new features
- [ ] Can debug issues in blockchain logic

---

## Notes

**This is NOT a production implementation:**
- Security is simplified
- Performance not optimized
- Error handling is basic
- Focus is on understanding concepts

**After completing all phases, you'll understand:**
- How Bitcoin actually works under the hood
- Where different blockchain types differ (PoS, PoA, etc.)
- Tradeoffs in blockchain design
- Potential applications in healthcare (your domain)

**Healthcare-Blockchain Ideas (for later exploration):**
- Medical record verification (Merkle proofs)
- Credential verification (decentralized)
- Supply chain integrity (pharmaceuticals)
- Clinical trial data integrity
- Patient consent management
