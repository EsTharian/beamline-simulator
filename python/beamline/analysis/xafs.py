"""X-ray absorption fine structure (XAFS) data processing utilities."""

from __future__ import annotations

from typing import Literal

import numpy as np
from numpy.typing import NDArray
from scipy import fft, interpolate, signal


class XAFSProcessor:
    """XAFS/EXAFS data processing utilities.

    Stateless class for absorption edge finding, normalization,
    chi(k) extraction, and Fourier transform analysis.
    """

    def find_edge(
        self,
        energy: NDArray[np.float64],
        mu: NDArray[np.float64],
    ) -> float:
        """Determine absorption edge energy (E₀).

        Uses maximum of first derivative method, which is standard
        for K-edges. For L-edges, alternative methods may be needed.

        Formula: E₀ = energy[argmax(dμ/dE)]

        Args:
            energy: Energy values in eV (monotonically increasing)
            mu: Absorption coefficient μ(E)

        Returns:
            Edge energy E₀ in eV

        Raises:
            ValueError: If arrays have different lengths
            ValueError: If energy is not monotonically increasing
            ValueError: If no clear edge is found
        """
        # Input validation
        if len(energy) != len(mu):
            raise ValueError(f"Arrays must have same length: energy={len(energy)}, mu={len(mu)}")

        if len(energy) == 0:
            raise ValueError("Arrays must not be empty")

        # Check for finite values
        if not np.all(np.isfinite(energy)) or not np.all(np.isfinite(mu)):
            raise ValueError("Arrays must contain only finite values")

        # Check monotonicity
        if not np.all(np.diff(energy) > 0):
            raise ValueError("energy must be monotonically increasing")

        # Calculate first derivative: dμ/dE
        dmu = np.gradient(mu, energy)

        # Find maximum of derivative (edge position)
        edge_idx = int(np.argmax(dmu))

        # Optional: Refine using interpolation for sub-sample accuracy
        # Use quadratic interpolation around maximum
        if edge_idx > 0 and edge_idx < len(dmu) - 1:
            # Fit quadratic to 3 points around maximum
            x_local = energy[edge_idx - 1 : edge_idx + 2]
            y_local = dmu[edge_idx - 1 : edge_idx + 2]

            # Quadratic fit: y = ax² + bx + c
            coeffs = np.polyfit(x_local, y_local, 2)

            # Find maximum of quadratic: x = -b / (2a)
            if abs(coeffs[0]) > 1e-10:  # Avoid division by zero
                edge_energy = -coeffs[1] / (2 * coeffs[0])
                # Clamp to valid range
                edge_energy = np.clip(edge_energy, energy[0], energy[-1])
                return float(edge_energy)

        # Fallback to direct value
        return float(energy[edge_idx])

    def normalize(
        self,
        energy: NDArray[np.float64],
        mu: NDArray[np.float64],
        e0: float | None = None,
        pre_edge: tuple[float, float] = (-150, -30),
        post_edge: tuple[float, float] = (50, 300),
    ) -> NDArray[np.float64]:
        """Perform edge-step normalization.

        Process:
        1. Fit linear baseline to pre-edge region
        2. Subtract pre-edge baseline from entire spectrum
        3. Fit linear/polynomial to post-edge region
        4. Normalize so edge step = 1

        Args:
            energy: Energy values in eV
            mu: Absorption coefficient μ(E)
            e0: Edge energy (if None, will be found automatically)
            pre_edge: (start, stop) eV relative to E₀ for pre-edge fit
            post_edge: (start, stop) eV relative to E₀ for post-edge fit

        Returns:
            Normalized absorption coefficient μ_norm(E)

        Raises:
            ValueError: If pre_edge or post_edge ranges are invalid
            ValueError: If insufficient data in ranges
        """
        # Input validation
        if len(energy) != len(mu):
            raise ValueError(f"Arrays must have same length: energy={len(energy)}, mu={len(mu)}")

        if len(energy) == 0:
            raise ValueError("Arrays must not be empty")

        # Check for finite values
        if not np.all(np.isfinite(energy)) or not np.all(np.isfinite(mu)):
            raise ValueError("Arrays must contain only finite values")

        # Check monotonicity
        if not np.all(np.diff(energy) > 0):
            raise ValueError("energy must be monotonically increasing")

        # Validate pre_edge and post_edge ranges
        if pre_edge[1] >= post_edge[0]:
            raise ValueError(
                f"pre_edge and post_edge must not overlap: "
                f"pre_edge[1]={pre_edge[1]} >= post_edge[0]={post_edge[0]}"
            )

        # Find E₀ if not provided
        if e0 is None:
            e0 = self.find_edge(energy, mu)

        # Define pre-edge range: [E₀ + pre_edge[0], E₀ + pre_edge[1]]
        pre_start = e0 + pre_edge[0]
        pre_stop = e0 + pre_edge[1]

        # Select pre-edge data
        pre_mask = (energy >= pre_start) & (energy <= pre_stop)
        energy_pre = energy[pre_mask]
        mu_pre = mu[pre_mask]

        if len(energy_pre) < 2:
            raise ValueError(
                f"Insufficient data in pre-edge range [{pre_start:.1f}, {pre_stop:.1f}] eV. "
                f"Found {len(energy_pre)} points, need at least 2."
            )

        # Fit linear baseline to pre-edge
        pre_coeffs = np.polyfit(energy_pre, mu_pre, 1)
        # Extrapolate to all energies
        pre_baseline = np.polyval(pre_coeffs, energy)

        # Subtract pre-edge baseline
        mu_subtracted = mu - pre_baseline

        # Define post-edge range: [E₀ + post_edge[0], E₀ + post_edge[1]]
        post_start = e0 + post_edge[0]
        post_stop = e0 + post_edge[1]

        # Select post-edge data
        post_mask = (energy >= post_start) & (energy <= post_stop)
        energy_post = energy[post_mask]
        mu_post = mu_subtracted[post_mask]

        if len(energy_post) < 2:
            raise ValueError(
                f"Insufficient data in post-edge range [{post_start:.1f}, {post_stop:.1f}] eV. "
                f"Found {len(energy_post)} points, need at least 2."
            )

        # Fit linear to post-edge
        post_coeffs = np.polyfit(energy_post, mu_post, 1)

        # Calculate edge step: Δμ₀ = post_edge_line(E₀) - pre_edge_line(E₀)
        # Pre-edge line at E₀ is already subtracted (baseline), so it's 0
        # Post-edge line at E₀: post_coeffs[0] * e0 + post_coeffs[1]
        edge_step = np.polyval(post_coeffs, e0)

        if edge_step <= 0:
            raise ValueError(
                f"Edge step must be > 0, got {edge_step:.6f}. Check pre_edge and post_edge ranges."
            )

        # Normalize: μ_norm = μ_subtracted / Δμ₀
        mu_norm = mu_subtracted / edge_step

        result: NDArray[np.float64] = mu_norm.astype(np.float64)
        return result

    def extract_chi(
        self,
        energy: NDArray[np.float64],
        mu_norm: NDArray[np.float64],
        e0: float,
        rbkg: float = 1.0,
        kmin: float = 2.0,
        kmax: float = 12.0,
    ) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
        """Extract χ(k) from normalized μ(E).

        Process:
        1. Convert E to k: k = √(0.262465 * (E - E₀))
        2. Select k range: [kmin, kmax]
        3. Fit spline background: μ₀(k) using UnivariateSpline
        4. Calculate chi: χ(k) = (μ_norm(k) - μ₀(k)) / μ₀(k)

        Args:
            energy: Energy values in eV
            mu_norm: Normalized absorption coefficient
            e0: Edge energy in eV
            rbkg: Spline node spacing in Å (controls flexibility)
            kmin: Minimum k value in Å⁻¹
            kmax: Maximum k value in Å⁻¹

        Returns:
            Tuple of (k, chi) arrays

        Raises:
            ValueError: If kmin >= kmax or invalid ranges
            ValueError: If insufficient data in k range
        """
        # Input validation
        if len(energy) != len(mu_norm):
            raise ValueError(
                f"Arrays must have same length: energy={len(energy)}, mu_norm={len(mu_norm)}"
            )

        if len(energy) == 0:
            raise ValueError("Arrays must not be empty")

        if kmin >= kmax:
            raise ValueError(f"kmin ({kmin}) must be < kmax ({kmax})")

        if rbkg <= 0:
            raise ValueError(f"rbkg must be > 0, got {rbkg}")

        # Convert E to k: k = √(0.262465 * (E - E₀))
        # 0.262465 = 2m_e / ℏ² conversion factor for eV -> Å⁻¹
        k = np.sqrt(0.262465 * (energy - e0))

        # Mask k range: [kmin, kmax]
        k_mask = (k >= kmin) & (k <= kmax)
        k_sel = k[k_mask]
        mu_norm_sel = mu_norm[k_mask]

        if len(k_sel) < 3:
            raise ValueError(
                f"Insufficient data in k range [{kmin:.1f}, {kmax:.1f}] Å⁻¹. "
                f"Found {len(k_sel)} points, need at least 3 for spline fitting."
            )

        # Fit spline background
        # Smoothing parameter s: larger s = smoother spline
        # Approximate: s ≈ len(k) * rbkg for reasonable smoothing
        smoothing = len(k_sel) * rbkg * 0.1  # Scale factor for reasonable smoothing

        try:
            spline = interpolate.UnivariateSpline(
                k_sel, mu_norm_sel, s=smoothing, ext="extrapolate"
            )
        except Exception as e:
            raise ValueError(f"Spline fitting failed: {e}") from e

        # Calculate background: μ₀(k)
        mu0 = spline(k_sel)

        # Avoid division by zero
        mu0 = np.maximum(mu0, 1e-10)

        # Calculate chi: χ(k) = (μ_norm(k) - μ₀(k)) / μ₀(k)
        chi = (mu_norm_sel - mu0) / mu0

        return (k_sel.astype(np.float64), chi.astype(np.float64))

    def fourier_transform(
        self,
        k: NDArray[np.float64],
        chi: NDArray[np.float64],
        kmin: float = 2.0,
        kmax: float = 12.0,
        kweight: int = 2,
        window: Literal["hanning", "kaiser", "tukey"] = "hanning",
        dk: float = 0.05,
    ) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
        """Fourier transform χ(k) to R-space.

        Process:
        1. Apply k-weighting: k^n * χ(k)
        2. Apply windowing function
        3. Interpolate to uniform k-grid
        4. Zero-pad for FFT
        5. FFT to R-space
        6. Calculate magnitude: |χ(R)|

        Args:
            k: Wavenumber array in Å⁻¹
            chi: χ(k) array
            kmin: Minimum k for transform
            kmax: Maximum k for transform
            kweight: k-weighting exponent (0, 1, 2, or 3)
            window: Windowing function type
            dk: k-grid spacing for interpolation (Å⁻¹)

        Returns:
            Tuple of (R, chi_R_magnitude) arrays

        Raises:
            ValueError: If kweight not in [0, 1, 2, 3]
            ValueError: If window type invalid
        """
        # Input validation
        if len(k) != len(chi):
            raise ValueError(f"Arrays must have same length: k={len(k)}, chi={len(chi)}")

        if len(k) == 0:
            raise ValueError("Arrays must not be empty")

        if kweight not in (0, 1, 2, 3):
            raise ValueError(f"kweight must be 0, 1, 2, or 3, got {kweight}")

        if window not in ("hanning", "kaiser", "tukey"):
            raise ValueError(f"Invalid window type: {window}")

        if dk <= 0:
            raise ValueError(f"dk must be > 0, got {dk}")

        # Mask k range
        k_mask = (k >= kmin) & (k <= kmax)
        k_sel = k[k_mask]
        chi_sel = chi[k_mask]

        if len(k_sel) < 2:
            raise ValueError(
                f"Insufficient data in k range [{kmin:.1f}, {kmax:.1f}] Å⁻¹. "
                f"Found {len(k_sel)} points, need at least 2."
            )

        # Apply k-weighting: chi_weighted = k^n * chi
        chi_weighted = k_sel**kweight * chi_sel

        # Create and apply window
        window_func = self._get_window_function(window, len(chi_weighted))
        chi_windowed = chi_weighted * window_func

        # Interpolate to uniform k-grid
        k_grid = np.arange(kmin, kmax + dk, dk)
        chi_interp = np.interp(k_grid, k_sel, chi_windowed)

        # Zero-pad for better FFT resolution
        # Pad to next power of 2 for efficiency
        n_pad = 2 ** int(np.ceil(np.log2(len(chi_interp))))
        chi_padded = np.pad(chi_interp, (0, n_pad - len(chi_interp)), mode="constant")

        # FFT to R-space
        chi_r_complex = fft.fft(chi_padded)

        # Calculate r: r = fftfreq * 2π / dk
        # dk is the spacing in k-space
        r_space = np.fft.fftfreq(len(chi_padded), dk) * 2 * np.pi

        # Calculate magnitude: |χ(R)|
        chi_r_mag = np.abs(chi_r_complex)

        # Return only positive R values
        r_positive = r_space >= 0
        r_out = r_space[r_positive]
        chi_r_out = chi_r_mag[r_positive]

        return (r_out.astype(np.float64), chi_r_out.astype(np.float64))

    def _get_window_function(
        self, window_type: Literal["hanning", "kaiser", "tukey"], length: int
    ) -> NDArray[np.float64]:
        """Get windowing function for XAFS Fourier transform.

        Args:
            window_type: Type of window
            length: Length of window array

        Returns:
            Window function array
        """
        if window_type == "hanning":
            return signal.windows.hann(length).astype(np.float64)
        elif window_type == "kaiser":
            # Beta parameter for Kaiser window (typical: 5-10)
            return signal.windows.kaiser(length, beta=8.0).astype(np.float64)
        elif window_type == "tukey":
            # Alpha parameter for Tukey window (typical: 0.1-0.2)
            return signal.windows.tukey(length, alpha=0.1).astype(np.float64)
        else:
            raise ValueError(f"Unknown window type: {window_type}")
