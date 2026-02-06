"""
Bitcoin Merkle Tree Implementation
====================================

This module implements the Merkle tree data structure used in Bitcoin blocks.

A Merkle tree (also called a hash tree) is a binary tree where:
- **Leaf nodes** contain the hashes of individual data items (transactions)
- **Internal nodes** contain the hash of their two child nodes concatenated
- The **root** is a single hash that summarizes all the data in the tree

In Bitcoin, every block header contains a Merkle root that commits to all
transactions in the block. This provides two key benefits:

1. **Efficient verification**: A lightweight client can verify that a specific
   transaction is included in a block by downloading only a Merkle proof
   (O(log n) hashes) instead of all transactions (O(n) data).

2. **Tamper evidence**: Any modification to any transaction changes the Merkle
   root, making it immediately detectable.

Bitcoin's Merkle Tree Specifics
--------------------------------
- Uses **double SHA-256** (SHA-256 applied twice) for all hash operations
- When a tree level has an **odd number** of nodes, the last node is
  **duplicated** to make it even (this is unique to Bitcoin's implementation)
- Transaction hashes (txids) are the leaf nodes
- The tree is built bottom-up from the transaction hashes

Merkle Proofs (SPV)
--------------------
A Merkle proof for a transaction consists of the sibling hashes along the
path from the leaf to the root. With these O(log n) hashes, anyone can
independently recompute the root and verify inclusion. This enables
Simplified Payment Verification (SPV) clients described in Section 8 of
the Bitcoin whitepaper.
"""

from .hash import double_sha256


class MerkleTree:
    """
    A Merkle tree implementation following Bitcoin's specification.

    The tree is built from a list of leaf hashes (typically transaction IDs)
    and produces a single root hash that cryptographically commits to all
    leaves.

    Usage example:
        >>> tree = MerkleTree(['aabb...', 'ccdd...', 'eeff...'])
        >>> tree.build_tree()
        >>> root = tree.get_root()
        >>> proof = tree.get_proof(1)  # proof for second transaction
        >>> MerkleTree.verify_proof('ccdd...', proof, root)
        True
    """

    def __init__(self, hash_list: list = None):
        """
        Initialize the Merkle tree with optional leaf hashes.

        Args:
            hash_list: Optional list of hex strings representing leaf hashes
                      (e.g., transaction IDs). Each string should be a valid
                      hex-encoded 32-byte hash (64 hex characters).
                      If None, an empty tree is created.
        """
        self.leaves: list = []
        self._tree: list = []
        self._root: bytes = None

        if hash_list is not None:
            for h in hash_list:
                self.leaves.append(bytes.fromhex(h))

    def add_leaf(self, hash_hex: str) -> None:
        """
        Add a new leaf hash to the tree.

        After adding leaves, you must call build_tree() to (re)compute
        the tree structure and root hash.

        Args:
            hash_hex: A hex string representing the leaf hash to add.
        """
        self.leaves.append(bytes.fromhex(hash_hex))
        # Invalidate any previously computed tree
        self._tree = []
        self._root = None

    def build_tree(self) -> None:
        """
        Build the Merkle tree from the current set of leaves.

        The algorithm works bottom-up:
        1. Start with the leaf hashes as the first layer
        2. Pair adjacent nodes and hash each pair: H(left || right)
        3. If a layer has an odd number of nodes, duplicate the last node
        4. Repeat until a single root hash remains

        The tree structure is stored in self._tree as a list of layers:
        - _tree[0] = leaf hashes
        - _tree[1] = first level of internal nodes
        - ...
        - _tree[-1] = [root hash]

        Special cases:
        - No leaves: root is None
        - One leaf: root is that leaf's hash (no further hashing)
        """
        if not self.leaves:
            self._tree = []
            self._root = None
            return

        # Start with the leaves as the first layer
        current_layer = list(self.leaves)
        self._tree = [current_layer]

        # If there's only one leaf, it is the root
        if len(current_layer) == 1:
            self._root = current_layer[0]
            return

        # Build layers until we reach a single root
        while len(current_layer) > 1:
            next_layer = []

            # If odd number of elements, duplicate the last one
            # This is Bitcoin's specific behavior for Merkle trees
            if len(current_layer) % 2 != 0:
                current_layer = current_layer + [current_layer[-1]]

            # Hash pairs of nodes
            for i in range(0, len(current_layer), 2):
                left = current_layer[i]
                right = current_layer[i + 1]
                parent = double_sha256(left + right)
                next_layer.append(parent)

            self._tree.append(next_layer)
            current_layer = next_layer

        self._root = current_layer[0]

    def get_root(self) -> str:
        """
        Get the Merkle root hash as a hex string.

        Must be called after build_tree(). If the tree has no leaves,
        returns None.

        Returns:
            The Merkle root as a lowercase hex string, or None if the
            tree is empty.
        """
        if self._root is None:
            return None
        return self._root.hex()

    def get_proof(self, index: int) -> list:
        """
        Generate a Merkle proof for the leaf at the given index.

        A Merkle proof consists of the sibling hashes along the path from
        the target leaf to the root. Each element includes the sibling hash
        and a direction indicator ('left' or 'right') specifying which side
        the sibling is on.

        With this proof, anyone can recompute the root hash starting from
        the target leaf, verifying its inclusion in the tree.

        Args:
            index: The 0-based index of the leaf to prove.

        Returns:
            A list of (direction, hash_hex) tuples. Direction is 'left' if
            the sibling is on the left, 'right' if on the right.

        Raises:
            IndexError: If the index is out of range.
            ValueError: If the tree has not been built yet.
        """
        if not self._tree:
            raise ValueError(
                "Tree has not been built. Call build_tree() first."
            )

        if index < 0 or index >= len(self.leaves):
            raise IndexError(
                f"Leaf index {index} out of range [0, {len(self.leaves) - 1}]"
            )

        proof = []
        current_index = index

        for layer_idx in range(len(self._tree) - 1):
            layer = self._tree[layer_idx]

            # If odd number of nodes, conceptually duplicate the last
            if len(layer) % 2 != 0:
                layer = layer + [layer[-1]]

            # Determine the sibling
            if current_index % 2 == 0:
                # Current is on the left, sibling is on the right
                sibling_index = current_index + 1
                direction = 'right'
            else:
                # Current is on the right, sibling is on the left
                sibling_index = current_index - 1
                direction = 'left'

            sibling_hash = layer[sibling_index]
            proof.append((direction, sibling_hash.hex()))

            # Move to the parent index in the next layer
            current_index = current_index // 2

        return proof

    @staticmethod
    def verify_proof(leaf_hash: str, proof: list, root_hash: str) -> bool:
        """
        Verify a Merkle proof for a given leaf hash against a known root.

        The verification process:
        1. Start with the target leaf hash
        2. For each step in the proof, combine the current hash with the
           sibling hash (respecting left/right ordering) and hash the pair
        3. The final result should equal the known Merkle root

        This is the core mechanism behind Simplified Payment Verification
        (SPV), allowing lightweight clients to verify transaction inclusion
        without downloading the entire block.

        Args:
            leaf_hash: The hex string hash of the leaf to verify.
            proof: A list of (direction, hash_hex) tuples from get_proof().
            root_hash: The expected Merkle root as a hex string.

        Returns:
            True if the proof is valid (recomputed root matches), False otherwise.
        """
        current = bytes.fromhex(leaf_hash)

        for direction, sibling_hex in proof:
            sibling = bytes.fromhex(sibling_hex)
            if direction == 'left':
                # Sibling is on the left side
                current = double_sha256(sibling + current)
            else:
                # Sibling is on the right side
                current = double_sha256(current + sibling)

        return current.hex() == root_hash


def compute_merkle_root(tx_hashes: list) -> str:
    """
    Compute the Merkle root from a list of transaction hashes.

    This is a convenience function that creates a MerkleTree, builds it,
    and returns the root hash in a single call.

    In Bitcoin, this function is called during block construction to compute
    the Merkle root that goes into the block header. The block header's
    Merkle root commits to every transaction in the block.

    Args:
        tx_hashes: A list of transaction hash hex strings. In Bitcoin,
                  these are the txids of all transactions in a block.

    Returns:
        The Merkle root as a lowercase hex string.
        Returns "0" * 64 (64 zero characters) for an empty list.
        Returns the single hash unchanged if only one transaction.
    """
    if not tx_hashes:
        return "0" * 64

    if len(tx_hashes) == 1:
        return tx_hashes[0].lower()

    tree = MerkleTree(tx_hashes)
    tree.build_tree()
    return tree.get_root()
