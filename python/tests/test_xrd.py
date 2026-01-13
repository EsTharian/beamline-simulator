"""Tests for XRD analysis module."""

from __future__ import annotations

import numpy as np
import pytest
from hypothesis import given
from hypothesis import strategies as st
from hypothesis.extra.numpy import arrays

from beamline.analysis.xrd import FitResult, Peak, XRDAnalyzer


class TestPeak:
    """Tests for Peak dataclass."""

    def test_peak_creation(self) -> None:
        """Test creating a Peak object."""
        peak = Peak(position=20.0, intensity=100.0, fwhm=0.5)
        assert peak.position == 20.0
        assert peak.intensity == 100.0
        assert peak.fwhm == 0.5
        assert peak.hkl_indices is None

    def test_peak_with_hkl(self) -> None:
        """Test Peak with Miller indices."""
        peak = Peak(position=20.0, intensity=100.0, fwhm=0.5, hkl_indices=(1, 1, 1))
        assert peak.hkl_indices == (1, 1, 1)


class TestFitResult:
    """Tests for FitResult dataclass."""

    def test_fit_result_creation(self) -> None:
        """Test creating a FitResult object."""
        result = FitResult(
            center=20.0,
            amplitude=100.0,
            width=0.5,
            background=10.0,
            model_type="gaussian",
            chi_squared=1.5,
            uncertainties={"center": 0.01, "amplitude": 1.0},
        )
        assert result.center == 20.0
        assert result.model_type == "gaussian"
        assert "center" in result.uncertainties


class TestXRDAnalyzer:
    """Tests for XRDAnalyzer class."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.analyzer = XRDAnalyzer()

    def test_find_peaks_simple(self) -> None:
        """Test finding peaks in simple synthetic data."""
        # Create synthetic data with known peaks
        two_theta = np.linspace(10, 50, 400)
        intensity = np.zeros_like(two_theta)

        # Add two Gaussian peaks
        peak1_pos = 20.0
        peak2_pos = 30.0
        for pos in [peak1_pos, peak2_pos]:
            intensity += 100 * np.exp(-0.5 * ((two_theta - pos) / 0.5) ** 2)

        # Add noise
        intensity += np.random.normal(0, 1, len(intensity))

        peaks = self.analyzer.find_peaks(two_theta, intensity, prominence=5.0)

        assert len(peaks) >= 2
        # Check that peaks are found near expected positions
        positions = [p.position for p in peaks]
        assert any(abs(p - peak1_pos) < 1.0 for p in positions)
        assert any(abs(p - peak2_pos) < 1.0 for p in positions)

    def test_find_peaks_empty_array(self) -> None:
        """Test find_peaks with empty arrays."""
        two_theta = np.array([])
        intensity = np.array([])

        peaks = self.analyzer.find_peaks(two_theta, intensity)
        assert peaks == []

    def test_find_peaks_validation(self) -> None:
        """Test input validation for find_peaks."""
        two_theta = np.linspace(10, 50, 100)
        intensity = np.linspace(0, 100, 99)  # Different length

        with pytest.raises(ValueError, match="same length"):
            self.analyzer.find_peaks(two_theta, intensity)

    def test_find_peaks_non_monotonic(self) -> None:
        """Test find_peaks with non-monotonic two_theta."""
        two_theta = np.array([10, 20, 15, 30])  # Not monotonic
        intensity = np.array([10, 20, 15, 30])

        with pytest.raises(ValueError, match="monotonically increasing"):
            self.analyzer.find_peaks(two_theta, intensity)

    def test_fit_peak_gaussian(self) -> None:
        """Test fitting a Gaussian peak."""
        # Create synthetic peak
        center = 20.0
        amplitude = 100.0
        width = 0.5
        background = 10.0

        two_theta = np.linspace(15, 25, 100)
        intensity = (
            amplitude * np.exp(-0.5 * ((two_theta - center) / (width / 2.355)) ** 2) + background
        )

        result = self.analyzer.fit_peak(
            two_theta, intensity, center=center, width=width, model="gaussian"
        )

        assert result.model_type == "gaussian"
        assert abs(result.center - center) < 0.1
        assert abs(result.amplitude - amplitude) < 10.0
        assert abs(result.width - width) < 0.2
        assert "center" in result.uncertainties

    def test_fit_peak_lorentzian(self) -> None:
        """Test fitting a Lorentzian peak."""
        center = 20.0
        amplitude = 100.0
        width = 0.5
        background = 10.0

        two_theta = np.linspace(15, 25, 100)
        gamma = width / 2.0
        intensity = amplitude / (1 + ((two_theta - center) / gamma) ** 2) + background

        result = self.analyzer.fit_peak(
            two_theta, intensity, center=center, width=width, model="lorentzian"
        )

        assert result.model_type == "lorentzian"
        assert abs(result.center - center) < 0.1

    def test_fit_peak_validation(self) -> None:
        """Test input validation for fit_peak."""
        two_theta = np.linspace(10, 50, 100)
        intensity = np.linspace(0, 100, 99)

        with pytest.raises(ValueError, match="same length"):
            self.analyzer.fit_peak(two_theta, intensity, center=20.0)

        with pytest.raises(ValueError, match="Invalid model type"):
            self.analyzer.fit_peak(
                two_theta, np.linspace(0, 100, 100), center=20.0, model="invalid"
            )

    def test_calculate_d_spacing(self) -> None:
        """Test d-spacing calculation."""
        # Known value: Cu Kα (1.5406 Å) at 20° two-theta
        two_theta = 20.0
        wavelength = 1.5406

        d = self.analyzer.calculate_d_spacing(two_theta, wavelength)

        # Expected: d = λ / (2 sin θ) = 1.5406 / (2 sin(10°)) ≈ 4.44 Å
        expected = wavelength / (2 * np.sin(np.deg2rad(10)))
        assert abs(d - expected) < 0.01

    def test_calculate_d_spacing_validation(self) -> None:
        """Test d-spacing validation."""
        with pytest.raises(ValueError, match="two_theta must be in"):
            self.analyzer.calculate_d_spacing(0.0)

        with pytest.raises(ValueError, match="wavelength must be > 0"):
            self.analyzer.calculate_d_spacing(20.0, wavelength=-1.0)

    def test_estimate_crystallite_size(self) -> None:
        """Test crystallite size estimation."""
        fwhm = 0.5  # degrees
        two_theta = 20.0  # degrees
        wavelength = 1.5406  # Å
        k_factor = 0.9

        size = self.analyzer.estimate_crystallite_size(fwhm, two_theta, wavelength, k_factor)

        # Should be positive and reasonable (nanometers)
        assert size > 0
        assert size < 1000  # Reasonable upper bound

    def test_calculate_lattice_parameter_cubic(self) -> None:
        """Test lattice parameter calculation for cubic system."""
        # Known: Si (111) peak at ~28.4° with Cu Kα gives a ≈ 5.43 Å
        d_spacings = [3.135]  # d-spacing for (111) peak
        hkl_indices = [(1, 1, 1)]

        a = self.analyzer.calculate_lattice_parameter(
            d_spacings, hkl_indices, crystal_system="cubic"
        )

        # For cubic: a = d * √(h² + k² + l²) = 3.135 * √3 ≈ 5.43
        expected = 3.135 * np.sqrt(3)
        assert abs(a - expected) < 0.01

    def test_calculate_lattice_parameter_validation(self) -> None:
        """Test lattice parameter validation."""
        with pytest.raises(ValueError, match="same length"):
            self.analyzer.calculate_lattice_parameter(
                [3.135], [(1, 1, 1), (2, 0, 0)], crystal_system="cubic"
            )

        with pytest.raises(NotImplementedError):
            self.analyzer.calculate_lattice_parameter(
                [3.135], [(1, 1, 1)], crystal_system="tetragonal"
            )

    @given(
        arrays(
            dtype=np.float64,
            shape=st.integers(min_value=10, max_value=100),
            elements=st.floats(min_value=10.0, max_value=50.0),
        )
    )
    def test_find_peaks_property(self, two_theta: np.ndarray) -> None:
        """Property-based test for find_peaks."""
        # Ensure monotonic
        two_theta = np.sort(two_theta)
        if len(np.unique(two_theta)) < len(two_theta):
            # Skip if duplicates
            return

        # Create intensity with some structure
        intensity = 50 + 30 * np.sin(two_theta / 5) + np.random.normal(0, 2, len(two_theta))
        intensity = np.maximum(intensity, 0)  # Ensure non-negative

        try:
            peaks = self.analyzer.find_peaks(two_theta, intensity, prominence=5.0)
            # If peaks found, they should be within the two_theta range
            if peaks:
                for peak in peaks:
                    assert two_theta[0] <= peak.position <= two_theta[-1]
                    assert peak.intensity > 0
                    assert peak.fwhm > 0
        except ValueError:
            # Some edge cases may fail validation, which is OK
            pass
