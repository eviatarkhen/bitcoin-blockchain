"""
Tests for Merkle Tree (Task 12.3)
==================================

Tests cover:
- Merkle tree building from transaction hashes
- Root calculation
- Merkle proof generation and verification
- Edge cases: empty, single leaf, odd number of leaves
"""

import hashlib

import pytest

from src.crypto.merkle import MerkleTree, compute_merkle_root


def double_sha256(data: bytes) -> bytes:
    """Helper: compute double SHA-256."""
    return hashlib.sha256(hashlib.sha256(data).digest()).digest()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def two_hashes():
    """Two sample transaction hashes."""
    return [
        "aa" * 32,
        "bb" * 32,
    ]


@pytest.fixture
def four_hashes():
    """Four sample transaction hashes."""
    return [
        "aa" * 32,
        "bb" * 32,
        "cc" * 32,
        "dd" * 32,
    ]


@pytest.fixture
def three_hashes():
    """Three sample transaction hashes (odd count)."""
    return [
        "aa" * 32,
        "bb" * 32,
        "cc" * 32,
    ]


# ---------------------------------------------------------------------------
# MerkleTree Tests
# ---------------------------------------------------------------------------

class TestMerkleTree:
    """Tests for the MerkleTree class."""

    def test_empty_tree(self):
        """An empty tree should have None root."""
        tree = MerkleTree([])
        tree.build_tree()
        assert tree.get_root() is None

    def test_single_leaf(self):
        """A tree with one leaf should have that leaf as the root."""
        leaf = "ab" * 32
        tree = MerkleTree([leaf])
        tree.build_tree()
        assert tree.get_root() == leaf

    def test_two_leaves(self, two_hashes):
        """Tree with two leaves should have a valid root different from either leaf."""
        tree = MerkleTree(two_hashes)
        tree.build_tree()
        root = tree.get_root()
        assert root is not None
        assert len(root) == 64
        assert root != two_hashes[0]
        assert root != two_hashes[1]

    def test_two_leaves_manual_verification(self, two_hashes):
        """Manually verify the root of a 2-leaf tree."""
        tree = MerkleTree(two_hashes)
        tree.build_tree()
        root = tree.get_root()

        # Manual computation: H(leaf0 || leaf1)
        left = bytes.fromhex(two_hashes[0])
        right = bytes.fromhex(two_hashes[1])
        expected = double_sha256(left + right).hex()
        assert root == expected

    def test_four_leaves(self, four_hashes):
        """Tree with four leaves should produce a valid root."""
        tree = MerkleTree(four_hashes)
        tree.build_tree()
        root = tree.get_root()
        assert root is not None
        assert len(root) == 64

    def test_odd_leaves_duplication(self, three_hashes):
        """Tree with odd number of leaves should duplicate the last leaf."""
        tree = MerkleTree(three_hashes)
        tree.build_tree()
        root = tree.get_root()
        assert root is not None

    def test_different_inputs_different_roots(self, two_hashes, four_hashes):
        """Different sets of leaves should produce different roots."""
        tree1 = MerkleTree(two_hashes)
        tree1.build_tree()
        tree2 = MerkleTree(four_hashes)
        tree2.build_tree()
        assert tree1.get_root() != tree2.get_root()

    def test_root_is_deterministic(self, four_hashes):
        """Building the same tree twice should produce the same root."""
        tree1 = MerkleTree(four_hashes)
        tree1.build_tree()
        tree2 = MerkleTree(four_hashes)
        tree2.build_tree()
        assert tree1.get_root() == tree2.get_root()

    def test_add_leaf(self):
        """Adding a leaf and rebuilding should change the root."""
        tree = MerkleTree(["aa" * 32])
        tree.build_tree()
        root1 = tree.get_root()

        tree.add_leaf("bb" * 32)
        tree.build_tree()
        root2 = tree.get_root()

        assert root1 != root2


# ---------------------------------------------------------------------------
# Merkle Proof Tests
# ---------------------------------------------------------------------------

class TestMerkleProof:
    """Tests for Merkle proof generation and verification."""

    def test_proof_two_leaves(self, two_hashes):
        """Proof for a leaf in a 2-leaf tree should have 1 step."""
        tree = MerkleTree(two_hashes)
        tree.build_tree()
        proof = tree.get_proof(0)
        assert len(proof) == 1

    def test_proof_four_leaves(self, four_hashes):
        """Proof for a leaf in a 4-leaf tree should have 2 steps."""
        tree = MerkleTree(four_hashes)
        tree.build_tree()
        proof = tree.get_proof(0)
        assert len(proof) == 2

    def test_verify_proof_valid(self, four_hashes):
        """A valid proof should verify successfully."""
        tree = MerkleTree(four_hashes)
        tree.build_tree()
        root = tree.get_root()

        for i in range(len(four_hashes)):
            proof = tree.get_proof(i)
            assert MerkleTree.verify_proof(four_hashes[i], proof, root) is True

    def test_verify_proof_wrong_leaf(self, four_hashes):
        """Proof for one leaf should not verify against a different leaf."""
        tree = MerkleTree(four_hashes)
        tree.build_tree()
        root = tree.get_root()
        proof = tree.get_proof(0)
        # Use wrong leaf hash
        assert MerkleTree.verify_proof(four_hashes[1], proof, root) is False

    def test_verify_proof_wrong_root(self, four_hashes):
        """A proof should not verify against a wrong root."""
        tree = MerkleTree(four_hashes)
        tree.build_tree()
        proof = tree.get_proof(0)
        wrong_root = "ff" * 32
        assert MerkleTree.verify_proof(four_hashes[0], proof, wrong_root) is False

    def test_proof_index_out_of_range(self, two_hashes):
        """Requesting proof for an invalid index should raise IndexError."""
        tree = MerkleTree(two_hashes)
        tree.build_tree()
        with pytest.raises(IndexError):
            tree.get_proof(5)

    def test_proof_before_build(self):
        """Requesting proof before build_tree() should raise ValueError."""
        tree = MerkleTree(["aa" * 32])
        with pytest.raises(ValueError):
            tree.get_proof(0)

    def test_proof_odd_leaves(self, three_hashes):
        """Proofs should work correctly with odd number of leaves."""
        tree = MerkleTree(three_hashes)
        tree.build_tree()
        root = tree.get_root()

        for i in range(len(three_hashes)):
            proof = tree.get_proof(i)
            assert MerkleTree.verify_proof(three_hashes[i], proof, root) is True


# ---------------------------------------------------------------------------
# compute_merkle_root Tests
# ---------------------------------------------------------------------------

class TestComputeMerkleRoot:
    """Tests for the compute_merkle_root convenience function."""

    def test_empty_list(self):
        """Empty list should return 64 zeros."""
        assert compute_merkle_root([]) == "0" * 64

    def test_single_hash(self):
        """Single hash should be returned as-is."""
        h = "ab" * 32
        assert compute_merkle_root([h]) == h

    def test_multiple_hashes(self, four_hashes):
        """Multiple hashes should produce a valid root."""
        root = compute_merkle_root(four_hashes)
        assert len(root) == 64
        assert all(c in "0123456789abcdef" for c in root)

    def test_matches_tree_build(self, four_hashes):
        """compute_merkle_root should match building a tree manually."""
        root1 = compute_merkle_root(four_hashes)
        tree = MerkleTree(four_hashes)
        tree.build_tree()
        root2 = tree.get_root()
        assert root1 == root2
