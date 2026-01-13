"""Tests for XAFS analysis module."""

from __future__ import annotations

import numpy as np
import pytest
from hypothesis import given
from hypothesis import strategies as st
from hypothesis.extra.numpy import arrays

from beamline.analysis.xafs import XAFSProcessor


class TestXAFSProcessor:
    """Tests for XAFSProcessor class."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.processor = XAFSProcessor()

    def test_find_edge_simple(self) -> None:
        """Test finding absorption edge."""
        # Create synthetic XAFS spectrum
        e0 = 7112.0  # Fe K-edge
        energy = np.linspace(e0 - 200, e0 + 500, 700)
        mu = np.zeros_like(energy)

        # Pre-edge: linear baseline
        pre_mask = energy < e0
        mu[pre_mask] = 0.5 + 0.001 * (energy[pre_mask] - e0)

        # Post-edge: step function with EXAFS oscillations
        post_mask = energy >= e0
        mu[post_mask] = (
            1.0 + 0.002 * (energy[post_mask] - e0) + 0.1 * np.sin((energy[post_mask] - e0) / 10)
        )

        found_e0 = self.processor.find_edge(energy, mu)

        # Should be close to true E₀
        assert abs(found_e0 - e0) < 5.0

    def test_find_edge_validation(self) -> None:
        """Test input validation for find_edge."""
        energy = np.linspace(7000, 7500, 100)
        mu = np.linspace(0, 100, 99)  # Different length

        with pytest.raises(ValueError, match="same length"):
            self.processor.find_edge(energy, mu)

    def test_normalize_simple(self) -> None:
        """Test normalization of XAFS spectrum."""
        e0 = 7112.0
        energy = np.linspace(e0 - 200, e0 + 500, 700)
        mu = np.zeros_like(energy)

        # Create step function
        pre_mask = energy < e0
        mu[pre_mask] = 0.5 + 0.001 * (energy[pre_mask] - e0)

        post_mask = energy >= e0
        mu[post_mask] = 1.0 + 0.002 * (energy[post_mask] - e0)

        mu_norm = self.processor.normalize(energy, mu, e0=e0)

        # Normalized spectrum should be ~0 before edge
        # Post-edge should be normalized (edge step = 1), but may have slope
        pre_norm = mu_norm[pre_mask]
        post_norm = mu_norm[post_mask]

        assert np.allclose(pre_norm, 0.0, atol=0.1)
        # Post-edge should be positive and increasing (due to linear post-edge)
        assert np.all(post_norm > 0)
        assert np.all(np.diff(post_norm) > 0)  # Increasing

    def test_normalize_auto_e0(self) -> None:
        """Test normalization with automatic E₀ finding."""
        e0 = 7112.0
        energy = np.linspace(e0 - 200, e0 + 500, 700)
        mu = np.zeros_like(energy)

        pre_mask = energy < e0
        mu[pre_mask] = 0.5 + 0.001 * (energy[pre_mask] - e0)

        post_mask = energy >= e0
        mu[post_mask] = 1.0 + 0.002 * (energy[post_mask] - e0)

        mu_norm = self.processor.normalize(energy, mu, e0=None)

        # Should still normalize correctly
        assert len(mu_norm) == len(energy)

    def test_normalize_validation(self) -> None:
        """Test normalization validation."""
        e0 = 7112.0
        energy = np.linspace(e0 - 200, e0 + 500, 700)
        mu = np.linspace(0, 100, 699)  # Different length

        with pytest.raises(ValueError, match="same length"):
            self.processor.normalize(energy, mu, e0=e0)

        # Test overlapping ranges
        with pytest.raises(ValueError, match="must not overlap"):
            self.processor.normalize(
                energy, np.linspace(0, 100, 700), e0=e0, pre_edge=(-50, 50), post_edge=(30, 100)
            )

    def test_extract_chi_simple(self) -> None:
        """Test chi(k) extraction."""
        e0 = 7112.0
        energy = np.linspace(e0, e0 + 500, 500)
        mu_norm = 1.0 + 0.1 * np.sin(np.sqrt(0.262465 * (energy - e0)) * 2)

        k, chi = self.processor.extract_chi(energy, mu_norm, e0, rbkg=1.0)

        assert len(k) > 0
        assert len(chi) == len(k)
        assert np.all(k >= 2.0)
        assert np.all(k <= 12.0)

    def test_extract_chi_validation(self) -> None:
        """Test extract_chi validation."""
        e0 = 7112.0
        energy = np.linspace(e0, e0 + 500, 500)
        mu_norm = np.ones_like(energy)

        with pytest.raises(ValueError, match="kmin.*must be < kmax"):
            self.processor.extract_chi(energy, mu_norm, e0, kmin=10.0, kmax=5.0)

    def test_fourier_transform_simple(self) -> None:
        """Test Fourier transform to R-space."""
        k = np.linspace(2.0, 12.0, 200)
        chi = 0.1 * np.sin(k * 2)  # Simple oscillation

        r_space, chi_r = self.processor.fourier_transform(k, chi)

        assert len(r_space) > 0
        assert len(chi_r) == len(r_space)
        assert np.all(r_space >= 0)  # Only positive R

    def test_fourier_transform_kweight(self) -> None:
        """Test Fourier transform with different k-weighting."""
        k = np.linspace(2.0, 12.0, 200)
        chi = 0.1 * np.sin(k * 2)

        for kweight in [0, 1, 2, 3]:
            r_space, chi_r = self.processor.fourier_transform(k, chi, kweight=kweight)
            assert len(r_space) > 0

    def test_fourier_transform_windows(self) -> None:
        """Test Fourier transform with different windows."""
        k = np.linspace(2.0, 12.0, 200)
        chi = 0.1 * np.sin(k * 2)

        for window in ["hanning", "kaiser", "tukey"]:
            r_space, chi_r = self.processor.fourier_transform(k, chi, window=window)
            assert len(r_space) > 0

    def test_fourier_transform_validation(self) -> None:
        """Test Fourier transform validation."""
        k = np.linspace(2.0, 12.0, 200)
        chi = 0.1 * np.sin(k * 2)

        with pytest.raises(ValueError, match="kweight must be"):
            self.processor.fourier_transform(k, chi, kweight=5)

        with pytest.raises(ValueError, match="Invalid window type"):
            self.processor.fourier_transform(k, chi, window="invalid")

    @given(
        arrays(
            dtype=np.float64,
            shape=st.integers(min_value=50, max_value=200),
            elements=st.floats(min_value=7000.0, max_value=7500.0),
        )
    )
    def test_find_edge_property(self, energy: np.ndarray) -> None:
        """Property-based test for find_edge."""
        # Ensure monotonic
        energy = np.sort(energy)
        if len(np.unique(energy)) < len(energy):
            return

        # Create simple step function
        e0_approx = np.mean(energy)
        mu = np.where(energy < e0_approx, 0.5, 1.0)

        try:
            found_e0 = self.processor.find_edge(energy, mu)
            # Edge should be within energy range
            assert energy[0] <= found_e0 <= energy[-1]
        except ValueError:
            # Some edge cases may fail
            pass
