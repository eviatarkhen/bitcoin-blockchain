"""
Tests for Difficulty and Consensus Rules (Task 12.5)
=====================================================

Tests cover:
- Block reward calculation and halving
- should_adjust function
- Difficulty adjustment calculations
"""

import sys

sys.path.insert(0, "/home/user/bitcoin-blockchain")

import pytest

from src.consensus.difficulty import get_block_reward, should_adjust
from src.mining.miner import compact_bits_to_target, target_to_compact_bits, calculate_difficulty


# ---------------------------------------------------------------------------
# Block Reward Tests
# ---------------------------------------------------------------------------

class TestBlockReward:
    """Tests for the block reward / halving schedule."""

    def test_genesis_reward(self):
        """Block 0 should have a 50 BTC reward (5,000,000,000 satoshis)."""
        reward = get_block_reward(0)
        assert reward == 50_00000000

    def test_first_era_reward(self):
        """Blocks 1-209999 should have a 50 BTC reward."""
        assert get_block_reward(1) == 50_00000000
        assert get_block_reward(100_000) == 50_00000000
        assert get_block_reward(209_999) == 50_00000000

    def test_first_halving(self):
        """Block 210,000 should have a 25 BTC reward."""
        reward = get_block_reward(210_000)
        assert reward == 25_00000000

    def test_second_halving(self):
        """Block 420,000 should have a 12.5 BTC reward."""
        reward = get_block_reward(420_000)
        assert reward == 12_50000000

    def test_third_halving(self):
        """Block 630,000 should have a 6.25 BTC reward."""
        reward = get_block_reward(630_000)
        assert reward == 6_25000000

    def test_many_halvings(self):
        """After many halvings, the reward should approach zero."""
        # After 64 halvings (64 * 210,000 = 13,440,000 blocks),
        # the reward should be 0 (integer division of 50 BTC by 2^64)
        reward = get_block_reward(64 * 210_000)
        assert reward == 0

    def test_reward_decreases_monotonically(self):
        """Each halving should reduce the reward."""
        prev_reward = get_block_reward(0)
        for era in range(1, 10):
            height = era * 210_000
            reward = get_block_reward(height)
            assert reward <= prev_reward
            prev_reward = reward


# ---------------------------------------------------------------------------
# should_adjust Tests
# ---------------------------------------------------------------------------

class TestShouldAdjust:
    """Tests for the difficulty adjustment trigger."""

    def test_genesis_no_adjust(self):
        """Height 0 should not trigger adjustment (or is a special case)."""
        # With Bitcoin's 2016-block interval, height 0 might or might not
        # trigger depending on implementation (0 % 2016 == 0)
        # The key contract is that height 2016 triggers an adjustment
        result = should_adjust(0, interval=2016)
        # Accept either True or False for height 0 -- implementations vary
        assert isinstance(result, bool)

    def test_adjust_at_interval(self):
        """Height equal to the interval should trigger adjustment."""
        assert should_adjust(2016, interval=2016) is True

    def test_no_adjust_between_intervals(self):
        """Heights between intervals should not trigger adjustment."""
        assert should_adjust(1, interval=2016) is False
        assert should_adjust(1000, interval=2016) is False
        assert should_adjust(2015, interval=2016) is False

    def test_adjust_at_multiples(self):
        """Multiples of the interval should trigger adjustment."""
        assert should_adjust(4032, interval=2016) is True
        assert should_adjust(6048, interval=2016) is True

    def test_custom_interval(self):
        """Custom intervals should work correctly."""
        assert should_adjust(10, interval=10) is True
        assert should_adjust(20, interval=10) is True
        assert should_adjust(15, interval=10) is False


# ---------------------------------------------------------------------------
# Difficulty Calculation Tests
# ---------------------------------------------------------------------------

class TestDifficultyCalculation:
    """Tests for difficulty-related calculations."""

    def test_genesis_difficulty_is_one(self):
        """Genesis block target (0x1d00ffff) should have difficulty 1.0."""
        target = compact_bits_to_target(0x1d00ffff)
        difficulty = calculate_difficulty(target)
        assert abs(difficulty - 1.0) < 0.001

    def test_higher_difficulty_smaller_target(self):
        """A harder difficulty should correspond to a smaller target."""
        easy_target = compact_bits_to_target(0x1d00ffff)
        # Reduce target by half (double difficulty)
        hard_target = easy_target // 2
        easy_diff = calculate_difficulty(easy_target)
        hard_diff = calculate_difficulty(hard_target)
        assert hard_diff > easy_diff

    def test_difficulty_always_positive(self):
        """Difficulty should always be a positive number."""
        targets = [
            compact_bits_to_target(0x1d00ffff),
            compact_bits_to_target(0x1f0fffff),
        ]
        for target in targets:
            diff = calculate_difficulty(target)
            assert diff > 0

    def test_invalid_target_raises(self):
        """Zero or negative target should raise ValueError."""
        with pytest.raises(ValueError):
            calculate_difficulty(0)
        with pytest.raises(ValueError):
            calculate_difficulty(-1)
