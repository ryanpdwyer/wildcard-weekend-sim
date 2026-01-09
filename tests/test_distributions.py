"""Tests for statistical distributions."""

import pytest
import numpy as np
from src.simulation.distributions import (
    sample_poisson,
    sample_normal,
    sample_yards_given_events,
)


class TestPoissonSampling:
    """Test Poisson distribution sampling."""

    def test_poisson_mean(self):
        """Poisson samples should have mean close to lambda."""
        np.random.seed(42)
        lam = 5.0
        samples = sample_poisson(lam, 100000)
        assert abs(samples.mean() - lam) < 0.05

    def test_poisson_variance(self):
        """Poisson variance should equal lambda."""
        np.random.seed(42)
        lam = 5.0
        samples = sample_poisson(lam, 100000)
        assert abs(samples.var() - lam) < 0.1

    def test_poisson_zero_lambda(self):
        """Poisson with lambda=0 should return zeros."""
        samples = sample_poisson(0.0, 1000)
        assert np.all(samples == 0)

    def test_poisson_negative_lambda(self):
        """Poisson with negative lambda should return zeros."""
        samples = sample_poisson(-1.0, 1000)
        assert np.all(samples == 0)

    def test_poisson_returns_integers(self):
        """Poisson samples should be integers."""
        samples = sample_poisson(5.0, 100)
        assert samples.dtype == np.int64 or samples.dtype == np.int32


class TestNormalSampling:
    """Test Normal distribution sampling."""

    def test_normal_mean(self):
        """Normal samples should have mean close to specified."""
        np.random.seed(42)
        mean = 100.0
        std = 15.0
        samples = sample_normal(mean, std, 100000)
        assert abs(samples.mean() - mean) < 0.5

    def test_normal_std(self):
        """Normal samples should have std close to specified."""
        np.random.seed(42)
        mean = 100.0
        std = 15.0
        samples = sample_normal(mean, std, 100000)
        assert abs(samples.std() - std) < 0.5

    def test_normal_min_val(self):
        """Normal samples should be clipped to min_val."""
        np.random.seed(42)
        samples = sample_normal(0, 10, 10000, min_val=0)
        assert np.all(samples >= 0)

    def test_normal_no_min_val(self):
        """Normal samples can be negative without min_val."""
        np.random.seed(42)
        samples = sample_normal(0, 10, 10000)
        assert np.any(samples < 0)


class TestYardsGivenEvents:
    """Test yards sampling given number of events."""

    def test_yards_scale_with_events(self):
        """More events should generally mean more yards."""
        np.random.seed(42)
        events = np.array([5, 10, 20, 50])
        yards_per_event = 10.0
        std_per_event = 3.0

        yards = sample_yards_given_events(events, yards_per_event, std_per_event)

        # On average, more events = more yards
        # Run multiple times to check trend
        np.random.seed(42)
        totals = np.zeros((4, 1000))
        for i in range(1000):
            totals[:, i] = sample_yards_given_events(
                events, yards_per_event, std_per_event
            )

        means = totals.mean(axis=1)
        # Each should be approximately events * yards_per_event
        for i, event_count in enumerate(events):
            expected = event_count * yards_per_event
            assert abs(means[i] - expected) < 5.0  # Within 5 yards

    def test_yards_non_negative(self):
        """Yards should not be negative."""
        np.random.seed(42)
        events = np.array([5] * 10000)
        yards = sample_yards_given_events(events, 5.0, 10.0, min_yards=0)
        assert np.all(yards >= 0)

    def test_yards_zero_events(self):
        """Zero events should give approximately zero yards."""
        np.random.seed(42)
        events = np.array([0] * 1000)
        yards = sample_yards_given_events(events, 10.0, 5.0)
        # Mean should be close to 0 (some variance allowed)
        assert abs(yards.mean()) < 1.0


class TestDistributionReproducibility:
    """Test that distributions are reproducible with seed."""

    def test_poisson_reproducible(self):
        """Poisson should be reproducible with same seed."""
        np.random.seed(42)
        samples1 = sample_poisson(5.0, 100)
        np.random.seed(42)
        samples2 = sample_poisson(5.0, 100)
        assert np.array_equal(samples1, samples2)

    def test_normal_reproducible(self):
        """Normal should be reproducible with same seed."""
        np.random.seed(42)
        samples1 = sample_normal(10.0, 2.0, 100)
        np.random.seed(42)
        samples2 = sample_normal(10.0, 2.0, 100)
        assert np.array_equal(samples1, samples2)
