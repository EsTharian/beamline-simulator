"""X-ray diffraction (XRD) analysis utilities."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np
from numpy.typing import NDArray
from scipy import optimize, signal


@dataclass
class Peak:
    """Represents a diffraction peak.

    Attributes:
        position: Peak position in two-theta degrees
        intensity: Peak intensity (maximum value)
        fwhm: Full width at half maximum in degrees
        hkl_indices: Optional Miller indices (h, k, l)
    """

    position: float
    intensity: float
    fwhm: float
    hkl_indices: tuple[int, int, int] | None = None


@dataclass
class FitResult:
    """Results from peak profile fitting.

    Attributes:
        center: Fitted peak center in degrees
        amplitude: Fitted peak amplitude
        width: Fitted peak width (FWHM) in degrees
        background: Fitted background level
        model_type: Profile model used
        chi_squared: Reduced chi-squared value
        uncertainties: Dictionary of parameter uncertainties
    """

    center: float
    amplitude: float
    width: float
    background: float
    model_type: Literal["gaussian", "lorentzian", "pseudo_voigt"]
    chi_squared: float
    uncertainties: dict[str, float]


class XRDAnalyzer:
    """Powder X-ray diffraction analysis utilities.

    Stateless class with functional methods for peak detection,
    profile fitting, and physical property calculations.
    """

    def find_peaks(
        self,
        two_theta: NDArray[np.float64],
        intensity: NDArray[np.float64],
        prominence: float = 0.1,
        height: float | None = None,
        distance: int | None = None,
        width: float | None = None,
    ) -> list[Peak]:
        """Identify diffraction peaks using scipy.signal.find_peaks.

        Uses prominence-based detection to find peaks that stand out
        relative to their surroundings, suitable for noisy XRD data.

        Args:
            two_theta: Two-theta angles in degrees (monotonically increasing)
            intensity: Diffracted intensity values
            prominence: Minimum peak prominence (relative to surrounding)
            height: Minimum peak height (absolute)
            distance: Minimum distance between peaks (samples)
            width: Minimum peak width at half-height (samples)

        Returns:
            List of Peak objects sorted by position

        Raises:
            ValueError: If arrays have different lengths or invalid ranges
            ValueError: If two_theta is not monotonically increasing
        """
        # Input validation
        if len(two_theta) != len(intensity):
            raise ValueError(
                f"Arrays must have same length: two_theta={len(two_theta)}, "
                f"intensity={len(intensity)}"
            )

        if len(two_theta) == 0:
            return []

        # Check for finite values
        if not np.all(np.isfinite(two_theta)) or not np.all(np.isfinite(intensity)):
            raise ValueError("Arrays must contain only finite values")

        # Check monotonicity
        if not np.all(np.diff(two_theta) > 0):
            raise ValueError("two_theta must be monotonically increasing")

        # Validate parameters
        if prominence <= 0:
            raise ValueError(f"prominence must be > 0, got {prominence}")
        if height is not None and height <= 0:
            raise ValueError(f"height must be > 0, got {height}")
        if distance is not None and distance < 1:
            raise ValueError(f"distance must be >= 1, got {distance}")
        if width is not None and width <= 0:
            raise ValueError(f"width must be > 0, got {width}")

        # Build find_peaks parameters
        peak_kwargs: dict[str, float | int] = {"prominence": prominence}
        if height is not None:
            peak_kwargs["height"] = height
        if distance is not None:
            peak_kwargs["distance"] = distance
        if width is not None:
            peak_kwargs["width"] = width

        # Find peaks
        peak_indices, _properties = signal.find_peaks(intensity, **peak_kwargs)  # type: ignore[arg-type]

        if len(peak_indices) == 0:
            return []

        # Calculate FWHM for each peak
        peaks: list[Peak] = []
        for idx in peak_indices:
            peak_pos = two_theta[idx]
            peak_intensity = intensity[idx]

            # Calculate FWHM using interpolation
            fwhm = self._calculate_fwhm(two_theta, intensity, int(idx))

            peaks.append(
                Peak(
                    position=float(peak_pos),
                    intensity=float(peak_intensity),
                    fwhm=fwhm,
                    hkl_indices=None,
                )
            )

        # Sort by position
        peaks.sort(key=lambda p: p.position)
        return peaks

    def _calculate_fwhm(
        self,
        two_theta: NDArray[np.float64],
        intensity: NDArray[np.float64],
        peak_idx: int,
    ) -> float:
        """Calculate FWHM for a peak using interpolation.

        Args:
            two_theta: Two-theta array
            intensity: Intensity array
            peak_idx: Index of peak center

        Returns:
            FWHM in degrees
        """
        peak_intensity = intensity[peak_idx]
        half_max = peak_intensity / 2.0

        # Find left half-maximum point
        left_idx = peak_idx
        while left_idx > 0 and intensity[left_idx] > half_max:
            left_idx -= 1

        if left_idx < peak_idx:
            # Interpolate left side
            if left_idx >= 0:
                left_theta = np.interp(
                    half_max,
                    intensity[left_idx : left_idx + 2],
                    two_theta[left_idx : left_idx + 2],
                )
            else:
                left_theta = two_theta[0]
        else:
            left_theta = two_theta[peak_idx]

        # Find right half-maximum point
        right_idx = peak_idx
        while right_idx < len(intensity) - 1 and intensity[right_idx] > half_max:
            right_idx += 1

        if right_idx > peak_idx:
            # Interpolate right side
            if right_idx < len(intensity):
                right_theta = np.interp(
                    half_max,
                    intensity[right_idx - 1 : right_idx + 1][::-1],
                    two_theta[right_idx - 1 : right_idx + 1][::-1],
                )
            else:
                right_theta = two_theta[-1]
        else:
            right_theta = two_theta[peak_idx]

        fwhm = abs(right_theta - left_theta)
        return float(fwhm)

    def fit_peak(
        self,
        two_theta: NDArray[np.float64],
        intensity: NDArray[np.float64],
        center: float,
        width: float = 1.0,
        model: Literal["gaussian", "lorentzian", "pseudo_voigt"] = "gaussian",
        background_order: int = 1,
    ) -> FitResult:
        """Fit peak profile using specified model.

        Models:
        - Gaussian: A * exp(-0.5 * ((x - μ) / σ)²)
        - Lorentzian: A / (1 + ((x - μ) / γ)²)
        - Pseudo-Voigt: η * Gaussian + (1 - η) * Lorentzian

        Args:
            two_theta: Two-theta angles in degrees
            intensity: Intensity values
            center: Initial guess for peak center
            width: Initial guess for peak width (FWHM)
            model: Profile model type
            background_order: Polynomial order for background (0=constant, 1=linear)

        Returns:
            FitResult with fitted parameters and uncertainties

        Raises:
            ValueError: If model type is invalid
            ValueError: If arrays have different lengths
            RuntimeError: If fitting fails to converge
        """
        # Input validation
        if len(two_theta) != len(intensity):
            raise ValueError(
                f"Arrays must have same length: two_theta={len(two_theta)}, "
                f"intensity={len(intensity)}"
            )

        if len(two_theta) == 0:
            raise ValueError("Arrays must not be empty")

        if model not in ("gaussian", "lorentzian", "pseudo_voigt"):
            raise ValueError(f"Invalid model type: {model}")

        if background_order < 0 or background_order > 2:
            raise ValueError(f"background_order must be 0, 1, or 2, got {background_order}")

        if width <= 0:
            raise ValueError(f"width must be > 0, got {width}")

        # Get model function
        if model == "gaussian":
            model_func = self._gaussian_model
        elif model == "lorentzian":
            model_func = self._lorentzian_model
        else:  # pseudo_voigt
            model_func = self._pseudo_voigt_model

        # Initial parameter guesses
        max_intensity = np.max(intensity)
        min_intensity = np.min(intensity)

        # Estimate background from edges
        n_edge = min(10, len(intensity) // 10)
        if n_edge > 0:
            left_bg = np.mean(intensity[:n_edge])
            right_bg = np.mean(intensity[-n_edge:])
            bg_slope = (right_bg - left_bg) / (two_theta[-1] - two_theta[0])
            bg_intercept = left_bg - bg_slope * two_theta[0]
        else:
            bg_slope = 0.0
            bg_intercept = np.mean(intensity)

        # Build initial parameter vector
        if model == "pseudo_voigt":
            # center, amplitude, width, eta, background...
            p0 = [center, max_intensity - bg_intercept, width, 0.5]
        else:
            # center, amplitude, width, background...
            p0 = [center, max_intensity - bg_intercept, width]

        # Add background parameters
        if background_order == 0:
            p0.append(bg_intercept)
        elif background_order == 1:
            p0.extend([bg_intercept, bg_slope])
        else:  # background_order == 2
            p0.extend([bg_intercept, bg_slope, 0.0])

        # Parameter bounds
        center_range = width * 2
        lower_bounds = [
            center - center_range,  # center
            0.0,  # amplitude
            0.1 * width,  # width
        ]
        upper_bounds = [
            center + center_range,  # center
            2 * max_intensity,  # amplitude
            10 * width,  # width
        ]

        if model == "pseudo_voigt":
            lower_bounds.insert(3, 0.0)  # eta
            upper_bounds.insert(3, 1.0)  # eta

        # Background bounds
        bg_range = max_intensity - min_intensity
        for _ in range(background_order + 1):
            lower_bounds.append(-bg_range)
            upper_bounds.append(bg_range)

        # Perform fit
        try:
            popt, pcov = optimize.curve_fit(
                lambda x, *p: model_func(x, np.array(p, dtype=np.float64), background_order),
                two_theta,
                intensity,
                p0=p0,
                bounds=(lower_bounds, upper_bounds),
                maxfev=10000,
            )
        except optimize.OptimizeWarning as e:
            raise RuntimeError(f"Peak fitting failed to converge: {e}") from e
        except Exception as e:
            raise RuntimeError(f"Peak fitting error: {e}") from e

        # Calculate uncertainties
        uncertainties_dict: dict[str, float] = {}
        param_names = ["center", "amplitude", "width"]
        if model == "pseudo_voigt":
            param_names.insert(3, "eta")

        for i, name in enumerate(param_names):
            if i < len(popt):
                uncertainties_dict[name] = float(np.sqrt(pcov[i, i]))

        # Background uncertainties
        bg_start = len(param_names)
        for i in range(background_order + 1):
            idx = bg_start + i
            if idx < len(popt):
                uncertainties_dict[f"background_{i}"] = float(np.sqrt(pcov[idx, idx]))

        # Calculate chi-squared
        y_fit = model_func(two_theta, popt, background_order)
        residuals = intensity - y_fit
        chi_squared = float(np.sum(residuals**2) / (len(intensity) - len(popt)))

        # Extract parameters
        center_fit = float(popt[0])
        amplitude_fit = float(popt[1])
        width_fit = float(popt[2])

        # Background
        bg_idx = 3 if model == "pseudo_voigt" else 3
        if background_order == 0:
            background_fit = float(popt[bg_idx])
        elif background_order == 1:
            background_fit = float(popt[bg_idx] + popt[bg_idx + 1] * np.mean(two_theta))
        else:
            background_fit = float(
                popt[bg_idx]
                + popt[bg_idx + 1] * np.mean(two_theta)
                + popt[bg_idx + 2] * np.mean(two_theta) ** 2
            )

        return FitResult(
            center=center_fit,
            amplitude=amplitude_fit,
            width=width_fit,
            background=background_fit,
            model_type=model,
            chi_squared=chi_squared,
            uncertainties=uncertainties_dict,
        )

    def _gaussian_model(
        self,
        x: NDArray[np.float64],
        params: NDArray[np.float64],
        background_order: int,
    ) -> NDArray[np.float64]:
        """Gaussian peak model: A * exp(-0.5 * ((x - μ) / σ)²).

        Args:
            x: Two-theta values
            params: [center, amplitude, width, background...]
            background_order: Background polynomial order

        Returns:
            Model intensity values
        """
        center = params[0]
        amplitude = params[1]
        width = params[2]  # FWHM

        # Convert FWHM to sigma: FWHM = 2 * sqrt(2 * ln(2)) * sigma
        sigma = width / (2 * np.sqrt(2 * np.log(2)))

        # Gaussian profile
        profile = amplitude * np.exp(-0.5 * ((x - center) / sigma) ** 2)

        # Add background
        bg_start = 3
        background = self._calculate_background(x, params, bg_start, background_order)

        result: NDArray[np.float64] = (profile + background).astype(np.float64)
        return result

    def _lorentzian_model(
        self,
        x: NDArray[np.float64],
        params: NDArray[np.float64],
        background_order: int,
    ) -> NDArray[np.float64]:
        """Lorentzian peak model: A / (1 + ((x - μ) / γ)²).

        Args:
            x: Two-theta values
            params: [center, amplitude, width, background...]
            background_order: Background polynomial order

        Returns:
            Model intensity values
        """
        center = params[0]
        amplitude = params[1]
        width = params[2]  # FWHM

        # Convert FWHM to gamma: FWHM = 2 * gamma
        gamma = width / 2.0

        # Lorentzian profile
        profile = amplitude / (1 + ((x - center) / gamma) ** 2)

        # Add background
        bg_start = 3
        background = self._calculate_background(x, params, bg_start, background_order)

        result: NDArray[np.float64] = (profile + background).astype(np.float64)
        return result

    def _pseudo_voigt_model(
        self,
        x: NDArray[np.float64],
        params: NDArray[np.float64],
        background_order: int,
    ) -> NDArray[np.float64]:
        """Pseudo-Voigt peak model: η * Gaussian + (1 - η) * Lorentzian.

        Args:
            x: Two-theta values
            params: [center, amplitude, width, eta, background...]
            background_order: Background polynomial order

        Returns:
            Model intensity values
        """
        center = params[0]
        amplitude = params[1]
        width = params[2]  # FWHM
        eta = params[3]  # Mixing parameter [0, 1]

        # Convert FWHM to sigma and gamma
        sigma = width / (2 * np.sqrt(2 * np.log(2)))
        gamma = width / 2.0

        # Gaussian component
        gaussian = amplitude * np.exp(-0.5 * ((x - center) / sigma) ** 2)

        # Lorentzian component
        lorentzian = amplitude / (1 + ((x - center) / gamma) ** 2)

        # Pseudo-Voigt: weighted combination
        profile = eta * gaussian + (1 - eta) * lorentzian

        # Add background
        bg_start = 4
        background = self._calculate_background(x, params, bg_start, background_order)

        result: NDArray[np.float64] = (profile + background).astype(np.float64)
        return result

    def _calculate_background(
        self,
        x: NDArray[np.float64],
        params: NDArray[np.float64],
        bg_start: int,
        background_order: int,
    ) -> NDArray[np.float64]:
        """Calculate polynomial background.

        Args:
            x: Two-theta values
            params: Parameter array
            bg_start: Index where background parameters start
            background_order: Polynomial order

        Returns:
            Background values
        """

        bg_result: NDArray[np.float64]

        if background_order == 0:
            bg_result = np.full_like(x, params[bg_start], dtype=np.float64)
            return bg_result
        elif background_order == 1:
            bg_result = (params[bg_start] + params[bg_start + 1] * x).astype(np.float64)
            return bg_result
        else:  # background_order == 2
            bg_result = (
                params[bg_start] + params[bg_start + 1] * x + params[bg_start + 2] * x**2
            ).astype(np.float64)
            return bg_result

    def calculate_d_spacing(
        self,
        two_theta: float,
        wavelength: float = 1.5406,
    ) -> float:
        """Calculate d-spacing using Bragg's law.

        Formula: d = λ / (2 sin θ)
        where θ = two_theta / 2

        Args:
            two_theta: Peak position in degrees
            wavelength: X-ray wavelength in Å (default: Cu Kα)

        Returns:
            d-spacing in Å

        Raises:
            ValueError: If two_theta <= 0 or >= 180
            ValueError: If wavelength <= 0
        """
        if two_theta <= 0 or two_theta >= 180:
            raise ValueError(f"two_theta must be in (0, 180) degrees, got {two_theta}")

        if wavelength <= 0:
            raise ValueError(f"wavelength must be > 0, got {wavelength}")

        # Convert two_theta to theta (half)
        theta_rad = np.deg2rad(two_theta / 2.0)

        # Apply Bragg's law: d = λ / (2 sin θ)
        d_spacing = wavelength / (2 * np.sin(theta_rad))

        return float(d_spacing)

    def estimate_crystallite_size(
        self,
        fwhm: float,
        two_theta: float,
        wavelength: float = 1.5406,
        k_factor: float = 0.9,
    ) -> float:
        """Estimate crystallite size using Scherrer equation.

        Formula: D = Kλ / (β cos θ)
        where β = FWHM in radians, θ = two_theta / 2

        Args:
            fwhm: Peak FWHM in degrees
            two_theta: Peak position in degrees
            wavelength: X-ray wavelength in Å
            k_factor: Shape factor (default: 0.9 for spherical crystallites)

        Returns:
            Crystallite size in nm

        Raises:
            ValueError: If inputs are invalid
        """
        if fwhm <= 0:
            raise ValueError(f"fwhm must be > 0, got {fwhm}")

        if two_theta <= 0 or two_theta >= 180:
            raise ValueError(f"two_theta must be in (0, 180) degrees, got {two_theta}")

        if wavelength <= 0:
            raise ValueError(f"wavelength must be > 0, got {wavelength}")

        if k_factor <= 0:
            raise ValueError(f"k_factor must be > 0, got {k_factor}")

        # Convert FWHM to radians: β = fwhm * π / 180
        beta_rad = np.deg2rad(fwhm)

        # Convert two_theta to theta
        theta_rad = np.deg2rad(two_theta / 2.0)

        # Apply Scherrer: D = Kλ / (β cos θ)
        # Result in Å
        d_angstrom = (k_factor * wavelength) / (beta_rad * np.cos(theta_rad))

        # Convert from Å to nm: divide by 10
        d_nm = d_angstrom / 10.0

        return float(d_nm)

    def calculate_lattice_parameter(
        self,
        d_spacings: list[float],
        hkl_indices: list[tuple[int, int, int]],
        crystal_system: Literal["cubic", "tetragonal", "orthorhombic", "hexagonal"] = "cubic",
    ) -> float:
        """Calculate lattice parameter from indexed peaks.

        For cubic: a = d * √(h² + k² + l²)
        For other systems, simplified calculations are used.

        Args:
            d_spacings: List of d-spacing values in Å
            hkl_indices: List of (h, k, l) Miller indices
            crystal_system: Crystal system type (only cubic fully implemented)

        Returns:
            Lattice parameter in Å

        Raises:
            ValueError: If lengths don't match or crystal system unsupported
            ValueError: If calculation fails (e.g., negative square root)
        """
        if len(d_spacings) != len(hkl_indices):
            raise ValueError(
                f"d_spacings and hkl_indices must have same length: "
                f"{len(d_spacings)} vs {len(hkl_indices)}"
            )

        if len(d_spacings) == 0:
            raise ValueError("At least one peak is required")

        # Validate hkl indices
        for hkl in hkl_indices:
            if len(hkl) != 3:
                raise ValueError(f"hkl_indices must be tuples of length 3, got {hkl}")
            if not all(isinstance(x, int) for x in hkl):
                raise ValueError(f"hkl_indices must contain integers, got {hkl}")

        if crystal_system == "cubic":
            # For cubic: a = d * √(h² + k² + l²)
            lattice_params: list[float] = []
            for d, (h, k, l_idx) in zip(d_spacings, hkl_indices, strict=True):
                hkl_sq_sum = h * h + k * k + l_idx * l_idx
                if hkl_sq_sum <= 0:
                    raise ValueError(f"Invalid hkl indices: ({h}, {k}, {l_idx})")
                a = d * np.sqrt(float(hkl_sq_sum))
                lattice_params.append(a)

            # Return average
            return float(np.mean(lattice_params))

        elif crystal_system in ("tetragonal", "orthorhombic", "hexagonal"):
            # Simplified: use first peak with non-zero h or k
            # For tetragonal: a ≈ d * √(h² + k²) (assuming c/a ≈ 1)
            # For orthorhombic: a ≈ d * h (simplified)
            # For hexagonal: a ≈ d * √(4/3 * (h² + hk + k²)) (simplified)
            raise NotImplementedError(
                f"Full implementation for {crystal_system} system not yet available. "
                "Only cubic system is fully supported."
            )
        else:
            raise ValueError(f"Unsupported crystal system: {crystal_system}")
