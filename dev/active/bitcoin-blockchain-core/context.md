# Context: Bitcoin Blockchain Core Implementation

**Last Updated**: 2026-02-06

---

## Critical Files

### Files to Create

**Core Components:**
- `src/core/block.py` - Block and BlockHeader classes (80-byte header, Bitcoin-accurate)
- `src/core/transaction.py` - Transaction, TransactionInput, TransactionOutput classes
- `src/core/blockchain.py` - Blockchain management, chain tips, fork handling
- `src/core/utxo.py` - UTXO set management (track unspent outputs)
- `src/core/mempool.py` - Transaction pool with fee prioritization

**Cryptography:**
- `src/crypto/hash.py` - SHA-256, RIPEMD-160 hashing utilities
- `src/crypto/keys.py` - ECDSA key management (secp256k1), signing, verification
- `src/crypto/merkle.py` - Merkle tree wrapper using merkletools library

**Mining:**
- `src/mining/miner.py` - Proof-of-Work mining, nonce search, difficulty handling

**Consensus:**
- `src/consensus/difficulty.py` - Difficulty adjustment algorithm (every 2016 blocks)
- `src/consensus/rules.py` - All Bitcoin consensus rules
- `src/consensus/validation.py` - Block and transaction validation logic

**Wallet:**
- `src/wallet/wallet.py` - Key management, balance tracking, transaction creation

**Utilities:**
- `src/utils/serialization.py` - Binary serialization for blocks/transactions
- `src/utils/encoding.py` - Base58Check, hex conversions
- `src/utils/visualizer.py` - CLI blockchain visualization (rich library)

**Examples:**
- `examples/01_basic_mining.py` - Mine first block demonstration
- `examples/02_send_transaction.py` - Create and send transaction
- `examples/03_fork_handling.py` - Fork creation and resolution
- `examples/04_difficulty_adjust.py` - Difficulty adjustment demonstration
- `examples/05_full_demo.py` - Complete system demonstration
- `examples/debug_flows/01_mine_first_block.py` - Debug script with breakpoints
- `examples/debug_flows/02_send_transaction.py` - Transaction debug script
- `examples/debug_flows/03_fork_resolution.py` - Fork handling debug script
- `examples/debug_flows/04_difficulty_adjustment.py` - Difficulty debug script
- `examples/helpers/blockchain_tester.py` - Fork testing utilities

**Tests:**
- `tests/test_block.py` - Block and header tests
- `tests/test_transaction.py` - Transaction tests
- `tests/test_utxo.py` - UTXO set tests
- `tests/test_keys.py` - Cryptography tests
- `tests/test_merkle.py` - Merkle tree tests
- `tests/test_mining.py` - Mining and PoW tests
- `tests/test_difficulty.py` - Difficulty adjustment tests
- `tests/test_blockchain.py` - Blockchain management tests
- `tests/test_wallet.py` - Wallet functionality tests
- `tests/test_integration.py` - End-to-end integration tests

**Configuration:**
- `requirements.txt` - Python dependencies
- `setup.py` - Package setup
- `.gitignore` - Git ignore patterns
- `README.md` - Project documentation

### Files to Modify

None - this is a new implementation from scratch

---

## Architectural Decisions

1. **Decision**: Build full archival node without P2P networking
   - **Reasoning**: Focus on core blockchain concepts first, networking adds complexity without educational value for fundamentals
   - **Trade-offs**: Single instance only, can't participate in distributed network (can add later in Phase 2)

2. **Decision**: Use exact Bitcoin 80-byte block header format
   - **Reasoning**: Learn real Bitcoin design, not simplified version; production-accurate implementation
   - **Trade-offs**: More complex than minimal implementation, but provides realistic understanding

3. **Decision**: UTXO model instead of account-based
   - **Reasoning**: This is Bitcoin's actual design; understanding UTXO is fundamental
   - **Trade-offs**: More complex than account model, but necessary for authentic implementation

4. **Decision**: Use merkletools library for Merkle trees
   - **Reasoning**: Well-tested library, focus learning on usage not implementation details
   - **Trade-offs**: External dependency, but saves time for more interesting components

5. **Decision**: Multiple mining modes (low difficulty, instant, deterministic)
   - **Reasoning**: Real mining takes too long for development/debugging
   - **Trade-offs**: Need to carefully switch between modes, but essential for practical development

6. **Decision**: In-memory storage (no database)
   - **Reasoning**: Simpler for learning, easier to debug, sufficient for educational purposes
   - **Trade-offs**: Limited scalability, data not persisted (can add JSON export/import)

7. **Decision**: Simplified P2PKH-only scripts (no full Bitcoin Script)
   - **Reasoning**: Full Script language is complex and not essential for understanding blockchain fundamentals
   - **Trade-offs**: Can't implement advanced Bitcoin features like multisig, timelocks (can add in Phase 3)

8. **Decision**: Python 3.10+ as implementation language
   - **Reasoning**: Easy to read and understand, rich ecosystem, ideal for learning
   - **Trade-offs**: Not production-performance (not the goal), but perfect for educational implementation

9. **Decision**: Rich library for CLI visualization
   - **Reasoning**: Makes blockchain state visible and understandable during development
   - **Trade-offs**: Additional dependency, but significantly improves learning experience

10. **Decision**: Comprehensive debug flow scripts with breakpoints
    - **Reasoning**: User wants to step through code with debugger to understand execution
    - **Trade-offs**: Extra maintenance, but critical for deep learning via code exploration

---

## Dependencies

### Package Dependencies

- `hashlib` (stdlib) - SHA-256 hashing
- `json` (stdlib) - JSON serialization
- `datetime` (stdlib) - Timestamps
- `ecdsa` - ECDSA signatures (secp256k1 curve)
- `base58` - Bitcoin address encoding with checksum
- `merkletools` - Merkle tree construction and proof generation
- `pytest` - Testing framework
- `rich` - CLI visualization (tables, trees, formatted output)
- `flask` (optional) - Web interface for blockchain explorer

### External Services

None - this is a standalone local implementation

### Internal Dependencies

**Critical Path:**
1. Must complete cryptography (Task 2.x) before transaction signing works
2. Must complete UTXO set (Task 1.6) before transaction validation works
3. Must complete block validation (Task 5.4) before blockchain can accept blocks
4. Must complete mining (Task 3.x) before can create valid blocks
5. Must complete wallet (Task 6.x) before can create transactions

**Parallel Workstreams:**
- Cryptography (Phase 2) can be done independently
- Mining (Phase 3) depends on block structure (Phase 1)
- Difficulty adjustment (Phase 4) depends on blockchain management (Phase 5)
- Wallet (Phase 6) depends on transactions (Phase 1) and cryptography (Phase 2)
- Visualization (Phase 10) can be done late, depends on blockchain being functional

---

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|-----------|
| Complexity overwhelming for learning | High | Break into small phases, comprehensive comments, debug scripts for stepping through |
| Mining takes too long for development | High | Multiple mining modes (low difficulty, instant mine, pre-computed blocks) |
| Difficult to visualize blockchain state | Medium | Rich CLI visualization, JSON export, optional Flask web interface |
| Hard to create fork scenarios for testing | Medium | BlockchainTester helper class with pre-programmed scenarios |
| ECDSA cryptography complexity | Medium | Use well-tested ecdsa library, focus on understanding usage not implementation |
| Merkle tree implementation time-consuming | Low | Use existing merkletools library instead of building from scratch |
| Context loss between sessions | Medium | Detailed documentation, JSON state export, comprehensive code comments |
| Bugs hard to reproduce | Medium | Deterministic mining mode, debug logging, comprehensive test suite |

---

## Key Constraints

**Technical Constraints:**
- Must match Bitcoin's 80-byte block header format exactly
- Must use UTXO model (not account-based)
- Must implement Proof-of-Work (with dev mode for practical mining)
- Must use secp256k1 curve for ECDSA
- Must implement difficulty adjustment every 2016 blocks
- Must handle chain reorganization correctly
- Block size limit: 1 MB (Bitcoin legacy)
- Coinbase maturity: 100 blocks
- Halving schedule: every 210,000 blocks

**Educational Constraints:**
- Code must be readable and well-commented
- Must include debug scripts for stepping through with debugger
- Must include visualization tools to see blockchain state
- Must include example scripts demonstrating all major features
- Focus on understanding, not performance optimization

**Resource Constraints:**
- Single developer (user) studying the implementation
- No external team or code reviews
- Development time: ~3-5 days for implementation, 1-2 weeks for deep study
- No production deployment requirements

**Scope Constraints:**
- Phase 1 only: No P2P networking
- Phase 1 only: No full Bitcoin Script (P2PKH only)
- Phase 1 only: No SegWit, Lightning Network, advanced features
- In-memory storage only (no persistent database)

---

## Key Concepts to Understand

**Blockchain Fundamentals:**
- Why blocks are linked via cryptographic hashes
- How tampering with history is detected
- Why genesis block is hardcoded

**Proof-of-Work:**
- Why brute force is necessary (no mathematical shortcuts)
- How difficulty controls block time
- Why difficulty adjustment is needed
- Hash rate and mining economics

**UTXO Model:**
- Why Bitcoin uses UTXOs instead of accounts
- How double-spending is prevented
- Coin selection algorithms
- Transaction fees

**Digital Signatures:**
- Public key cryptography basics
- ECDSA on secp256k1 curve
- Why signatures prevent forgery
- Address derivation (SHA-256 → RIPEMD-160 → Base58Check)

**Merkle Trees:**
- How they enable efficient proofs
- SPV (Simplified Payment Verification)
- Why block header only needs Merkle root
- Log n proof size

**Fork Handling:**
- Why forks occur (network propagation delays)
- Longest chain rule
- Chain reorganization process
- Orphan blocks

**Consensus Rules:**
- Why all nodes must enforce identical rules
- Block size limits (DoS prevention)
- Coinbase maturity (prevent spending of orphaned rewards)
- Halving schedule (monetary policy)

---

## Quick Links

**Related Documentation:**
- Bitcoin Whitepaper: https://bitcoin.org/bitcoin.pdf
- Plan file: `/Users/eviatarkhen/.claude/plans/swirling-coalescing-wand.md`
- GitHub repository: https://github.com/eviatarkhen/bitcoin-blockchain
- Local repository: `/Users/eviatarkhen/Dropbox (Personal)/Development/blockchain_test/bitcoin-blockchain`

**Key Whitepaper Sections:**
- Section 3: Timestamp Server (block linking)
- Section 4: Proof-of-Work (mining, difficulty)
- Section 5: Network (consensus, longest chain)
- Section 7: Reclaiming Disk Space (Merkle trees, SPV)
- Section 8: Simplified Payment Verification (SPV nodes)
- Section 11: Calculations (51% attack analysis)

**Development Tools:**
- Python debugger: `python -m pdb script.py`
- VS Code launch.json for debug configurations
- pytest for running tests: `pytest tests/`
- rich for CLI visualization
- JSON export for state inspection

**Learning Strategy:**
1. Read plan thoroughly (understand architecture)
2. Review code with detailed comments (understand implementation)
3. Run example scripts (see it in action)
4. Use debug flow scripts with breakpoints (step through execution)
5. Modify code to experiment (hands-on learning)
6. Create fork scenarios (understand edge cases)
7. Read tests (understand expected behavior)

---

## Success Criteria

**You understand blockchain when you can:**
- Explain every field in the 80-byte block header
- Trace a transaction from creation through UTXO set
- Manually verify a block's Proof-of-Work
- Explain why changing one block invalidates all subsequent blocks
- Demonstrate a fork and explain how it resolves
- Calculate mining difficulty and expected block time
- Explain why UTXO model prevents double-spending
- Verify a Merkle proof by hand

**Implementation is complete when:**
- Can mine 100+ block chain with difficulty adjustment
- Can create wallets and send transactions between them
- Can create forks and observe reorganization
- All consensus rules enforced and tested
- Visualization tools show blockchain state clearly
- Debug scripts work for stepping through code
- All tests pass
- Can export/import blockchain state via JSON

**Ready for Phase 2 (P2P Networking) when:**
- Deep understanding of all Phase 1 components
- Can explain design decisions and trade-offs
- Can modify implementation to add features
- Comfortable debugging blockchain issues
- Understanding extends beyond just "how" to "why"
