"""Statistical distribution samplers for Monte Carlo simulation."""

import numpy as np
from typing import Union


def sample_poisson(lam: float, n_samples: int = 1) -> np.ndarray:
    """
    Sample from Poisson distribution.

    Used for discrete events: receptions, attempts, TDs, INTs, fumbles.

    Args:
        lam: Expected value (lambda parameter)
        n_samples: Number of samples to draw

    Returns:
        Array of integer samples
    """
    if lam <= 0:
        return np.zeros(n_samples, dtype=int)
    return np.random.poisson(lam=lam, size=n_samples)


def sample_normal(
    mean: float,
    std: float,
    n_samples: int = 1,
    min_val: float = None
) -> np.ndarray:
    """
    Sample from Normal distribution.

    Used for yards per attempt, game scores.

    Args:
        mean: Mean of distribution
        std: Standard deviation
        n_samples: Number of samples
        min_val: Optional minimum value (clips samples below this)

    Returns:
        Array of float samples
    """
    samples = np.random.normal(loc=mean, scale=std, size=n_samples)
    if min_val is not None:
        samples = np.maximum(min_val, samples)
    return samples


def sample_yards_given_events(
    events: np.ndarray,
    yards_per_event: float,
    std_per_event: float,
    min_yards: float = 0.0
) -> np.ndarray:
    """
    Sample total yards given number of events (receptions, carries, completions).

    For each simulation, the total yards is sampled from a normal distribution
    where the mean scales with events and variance scales with sqrt(events).

    This approximates the sum of individual yards-per-event draws.

    Args:
        events: Array of event counts (receptions, carries, etc.)
        yards_per_event: Average yards per event
        std_per_event: Standard deviation per event
        min_yards: Minimum yards (default 0)

    Returns:
        Array of total yards (float)
    """
    # Mean = events * yards_per_event
    means = events * yards_per_event

    # Std dev of sum = sqrt(n) * std_per_event
    # Handle zero events case
    stds = np.sqrt(np.maximum(events, 0)) * std_per_event

    # Sample and clip to minimum
    samples = np.random.normal(means, np.maximum(stds, 0.01))
    return np.maximum(min_yards, samples)


def sample_touchdowns(
    events: np.ndarray,
    td_rate: float
) -> np.ndarray:
    """
    Sample touchdowns given number of events.

    Uses Poisson with rate = events * td_rate_per_event.

    Args:
        events: Array of event counts
        td_rate: TD rate per event (e.g., 0.1 = 10% of carries result in TD)

    Returns:
        Array of touchdown counts
    """
    expected_tds = events * td_rate
    return np.array([
        np.random.poisson(lam=max(0, exp)) for exp in expected_tds
    ])


def sample_binomial(n: np.ndarray, p: float) -> np.ndarray:
    """
    Sample from Binomial distribution.

    Can be used for completions given attempts, etc.

    Args:
        n: Array of trial counts
        p: Success probability

    Returns:
        Array of success counts
    """
    return np.array([
        np.random.binomial(int(max(0, trials)), p) for trials in n
    ])
