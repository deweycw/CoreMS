"""Plotting utility functions for PyQtGraph."""

from typing import Tuple, List
import numpy as np


def decimate_for_display(mz: np.ndarray, abundance: np.ndarray,
                         target_points: int = 50000) -> Tuple[np.ndarray, np.ndarray]:
    """Reduce data points for display while preserving peaks.

    Uses max-pooling to ensure peak maxima are preserved when
    decimating large datasets for faster rendering.

    Args:
        mz: Array of m/z values
        abundance: Array of abundance values
        target_points: Maximum number of points to return

    Returns:
        Tuple of (decimated_mz, decimated_abundance)
    """
    if len(mz) <= target_points:
        return mz, abundance

    # Calculate decimation factor
    factor = len(mz) // target_points
    n_chunks = len(mz) // factor

    # Reshape for chunked operations
    mz_chunks = mz[:n_chunks * factor].reshape(-1, factor)
    abund_chunks = abundance[:n_chunks * factor].reshape(-1, factor)

    # Take max from each chunk to preserve peaks
    max_idx = np.argmax(abund_chunks, axis=1)
    mz_dec = mz_chunks[np.arange(n_chunks), max_idx]
    abund_dec = abund_chunks[np.arange(n_chunks), max_idx]

    return mz_dec, abund_dec


def generate_color_palette(n_colors: int) -> List[str]:
    """Generate a palette of distinct colors.

    Args:
        n_colors: Number of colors to generate

    Returns:
        List of hex color strings
    """
    # Material Design colors
    base_colors = [
        '#E91E63',  # Pink
        '#9C27B0',  # Purple
        '#673AB7',  # Deep Purple
        '#3F51B5',  # Indigo
        '#2196F3',  # Blue
        '#00BCD4',  # Cyan
        '#009688',  # Teal
        '#4CAF50',  # Green
        '#8BC34A',  # Light Green
        '#CDDC39',  # Lime
        '#FF9800',  # Orange
        '#FF5722',  # Deep Orange
    ]

    colors = []
    for i in range(n_colors):
        colors.append(base_colors[i % len(base_colors)])

    return colors


def format_mz(mz: float, precision: int = 4) -> str:
    """Format m/z value for display.

    Args:
        mz: m/z value
        precision: Number of decimal places

    Returns:
        Formatted string
    """
    return f"{mz:.{precision}f}"


def format_abundance(abundance: float) -> str:
    """Format abundance value for display.

    Args:
        abundance: Abundance value

    Returns:
        Formatted string (scientific notation for large values)
    """
    if abs(abundance) >= 1e6:
        return f"{abundance:.2e}"
    elif abs(abundance) >= 1000:
        return f"{abundance:.0f}"
    else:
        return f"{abundance:.2f}"


def format_time(time_minutes: float) -> str:
    """Format retention time for display.

    Args:
        time_minutes: Time in minutes

    Returns:
        Formatted string (MM:SS.ss format)
    """
    minutes = int(time_minutes)
    seconds = (time_minutes - minutes) * 60
    return f"{minutes}:{seconds:05.2f}"


def ppm_to_mz_window(mz: float, ppm: float) -> Tuple[float, float]:
    """Calculate m/z window from ppm tolerance.

    Args:
        mz: Center m/z value
        ppm: Tolerance in ppm

    Returns:
        Tuple of (min_mz, max_mz)
    """
    delta = mz * ppm / 1e6
    return (mz - delta, mz + delta)


def mz_to_ppm_error(measured: float, theoretical: float) -> float:
    """Calculate ppm error between two m/z values.

    Args:
        measured: Measured m/z
        theoretical: Theoretical m/z

    Returns:
        Error in ppm
    """
    return (measured - theoretical) / theoretical * 1e6
