"""Calibration module for HRMS Viewer.

Implements polynomial fitting for m/z calibration using formula assignments
with prediction band filtering for outlier removal.
"""

from typing import List, Tuple, Optional, Dict, Any
from dataclasses import dataclass
import numpy as np
from scipy import stats


@dataclass
class CalibrationResult:
    """Results from calibration fitting."""

    # Fitted polynomial coefficients (highest degree first)
    coefficients: np.ndarray

    # Degree of polynomial
    degree: int

    # Number of peaks used for calibration
    n_peaks: int

    # Final standard deviation of errors (ppm)
    final_std: float

    # Calibration points: list of (mz, observed_mz, calculated_mz, error_ppm, formula)
    cal_points: List[Tuple[float, float, float, float, str]]

    # All assigned peaks before filtering: list of (mz, error_ppm, formula, confidence, is_used)
    all_assigned: List[Tuple[float, float, str, float, bool]]

    # Number of iterations used for outlier removal (internal fit iterations)
    iterations: int

    # Number of outer calibration iterations (assign -> calibrate -> apply cycles)
    calibration_iterations: int = 1

    @property
    def residual_errors(self) -> np.ndarray:
        """Get residual errors (ppm) of calibration points."""
        return np.array([p[3] for p in self.cal_points])

    @property
    def mz_values(self) -> np.ndarray:
        """Get m/z values of calibration points."""
        return np.array([p[0] for p in self.cal_points])

    def apply_correction(self, mz_array: np.ndarray) -> np.ndarray:
        """Apply calibration correction to m/z values.

        Args:
            mz_array: Array of m/z values to correct

        Returns:
            Corrected m/z values
        """
        # Calculate predicted error in ppm
        error_ppm = np.polyval(self.coefficients, mz_array)

        # Convert ppm error to absolute correction
        correction = mz_array * error_ppm / 1e6

        # Subtract the predicted error (since positive error means observed > calculated)
        return mz_array - correction


def get_prediction_interval(x: np.ndarray, y: np.ndarray, x_pred: np.ndarray,
                           coefficients: np.ndarray, alpha: float = 0.05) -> Tuple[np.ndarray, np.ndarray]:
    """Calculate prediction intervals for polynomial regression.

    Args:
        x: Observed x values
        y: Observed y values
        x_pred: X values for prediction
        coefficients: Polynomial coefficients (highest degree first)
        alpha: Significance level (default 0.05 for 95% interval)

    Returns:
        Tuple of (lower_bound, upper_bound)
    """
    n = len(x)
    degree = len(coefficients) - 1

    if n <= degree + 1:
        # Not enough points for prediction interval
        return np.full_like(x_pred, -np.inf), np.full_like(x_pred, np.inf)

    # Get fitted values
    y_fit = np.polyval(coefficients, x)

    # Calculate residual standard error
    residuals = y - y_fit
    se = np.sqrt(np.sum(residuals**2) / (n - degree - 1))

    # Calculate prediction at new points
    y_pred = np.polyval(coefficients, x_pred)

    # Build design matrix for x values
    X = np.column_stack([x**i for i in range(degree, -1, -1)])
    X_pred = np.column_stack([x_pred**i for i in range(degree, -1, -1)])

    try:
        # Calculate hat matrix diagonal elements for prediction points
        XtX_inv = np.linalg.inv(X.T @ X)
        h = np.array([x_p @ XtX_inv @ x_p.T for x_p in X_pred])

        # Prediction interval standard error
        se_pred = se * np.sqrt(1 + h)

        # t-value for confidence level
        t_val = stats.t.ppf(1 - alpha/2, n - degree - 1)

        lower = y_pred - t_val * se_pred
        upper = y_pred + t_val * se_pred

    except np.linalg.LinAlgError:
        # Singular matrix - return wide bounds
        lower = y_pred - 3 * se
        upper = y_pred + 3 * se

    return lower, upper


def filter_by_prediction_band(mz: np.ndarray, errors: np.ndarray,
                              coefficients: np.ndarray, alpha: float = 0.05) -> np.ndarray:
    """Filter points based on prediction band.

    Args:
        mz: m/z values
        errors: Error values (ppm)
        coefficients: Current polynomial coefficients
        alpha: Significance level for prediction band

    Returns:
        Boolean mask where True = point is within prediction band
    """
    lower, upper = get_prediction_interval(mz, errors, mz, coefficients, alpha)
    return (errors >= lower) & (errors <= upper)


def fit_calibration(mz: np.ndarray, errors: np.ndarray, degree: int = 3,
                   max_iterations: int = 20, target_std: float = 0.5,
                   alpha: float = 0.05) -> Tuple[np.ndarray, np.ndarray, int]:
    """Iteratively fit polynomial with outlier removal using prediction bands.

    Args:
        mz: m/z values
        errors: Error values (ppm)
        degree: Polynomial degree (default 3 for cubic)
        max_iterations: Maximum iterations for outlier removal
        target_std: Target standard deviation (ppm) to stop iterations
        alpha: Significance level for prediction band (default 0.05 for 95%)

    Returns:
        Tuple of (coefficients, mask of used points, number of iterations)
    """
    mask = np.ones(len(mz), dtype=bool)
    iteration = 0

    for iteration in range(max_iterations):
        # Fit polynomial to current points
        mz_curr = mz[mask]
        errors_curr = errors[mask]

        if len(mz_curr) < degree + 2:
            # Not enough points
            break

        coefficients = np.polyfit(mz_curr, errors_curr, degree)

        # Filter by prediction band
        new_mask = filter_by_prediction_band(mz_curr, errors_curr, coefficients, alpha)

        # Count points removed
        n_removed = np.sum(~new_mask)

        # Update global mask
        current_indices = np.where(mask)[0]
        removed_indices = current_indices[~new_mask]
        mask[removed_indices] = False

        # Calculate std on remaining points
        mz_filtered = mz[mask]
        errors_filtered = errors[mask]

        if len(mz_filtered) < degree + 2:
            break

        coefficients = np.polyfit(mz_filtered, errors_filtered, degree)
        predicted = np.polyval(coefficients, mz_filtered)
        residuals = errors_filtered - predicted
        std = np.std(residuals)

        # Stop if no points removed (converged) or std target met
        if n_removed == 0:
            if std <= target_std:
                break
            else:
                # Can't improve further without removing more points
                break

    # Final fit
    mz_final = mz[mask]
    errors_final = errors[mask]

    if len(mz_final) >= degree + 1:
        coefficients = np.polyfit(mz_final, errors_final, degree)
    else:
        coefficients = np.zeros(degree + 1)

    return coefficients, mask, iteration + 1


def extract_calibration_data(spectrum, min_confidence: float = 0.6,
                            min_sn: float = 10.0) -> List[Dict[str, Any]]:
    """Extract calibration data from assigned peaks.

    Args:
        spectrum: Processed and assigned spectrum
        min_confidence: Minimum confidence score for inclusion
        min_sn: Minimum S/N ratio for inclusion

    Returns:
        List of dicts with keys: mz_obs, mz_calc, error_ppm, formula, confidence, sn
    """
    cal_data = []

    if not hasattr(spectrum, 'mspeaks'):
        return cal_data

    for peak in spectrum.mspeaks:
        if not peak.is_assigned:
            continue

        # Get best molecular formula
        if not peak.molecular_formulas:
            continue

        # Get the best formula (highest confidence or first)
        best_formula = None
        best_confidence = 0

        for mf in peak.molecular_formulas:
            conf = getattr(mf, 'confidence_score', 0) or 0
            if conf > best_confidence:
                best_confidence = conf
                best_formula = mf

        if best_formula is None:
            best_formula = peak.molecular_formulas[0]
            best_confidence = getattr(best_formula, 'confidence_score', 0) or 0

        # Check confidence threshold
        if best_confidence < min_confidence:
            continue

        # Check S/N threshold
        sn = getattr(peak, 'signal_to_noise', 0) or 0
        if sn < min_sn:
            continue

        # Get m/z values
        mz_obs = peak.mz_exp
        mz_calc = best_formula.mz_calc if hasattr(best_formula, 'mz_calc') else best_formula.calculated_mz

        # Calculate error in ppm
        error_ppm = (mz_obs - mz_calc) / mz_calc * 1e6

        # Get formula string
        formula_str = str(best_formula.molecular_formula) if hasattr(best_formula, 'molecular_formula') else str(best_formula)

        cal_data.append({
            'mz_obs': mz_obs,
            'mz_calc': mz_calc,
            'error_ppm': error_ppm,
            'formula': formula_str,
            'confidence': best_confidence,
            'sn': sn
        })

    return cal_data


def run_calibration(spectrum, degree: int = 3, min_confidence: float = 0.6,
                   min_sn: float = 10.0, target_std: float = 0.5,
                   max_iterations: int = 20, alpha: float = 0.05) -> Optional[CalibrationResult]:
    """Run calibration on an assigned spectrum.

    Args:
        spectrum: Processed and assigned spectrum
        degree: Polynomial degree (default 3 = cubic)
        min_confidence: Minimum confidence score threshold
        min_sn: Minimum S/N threshold
        target_std: Target standard deviation for stopping criterion
        max_iterations: Maximum iterations for outlier removal
        alpha: Significance level for prediction bands (default 0.05 for 95%)

    Returns:
        CalibrationResult or None if not enough data
    """
    # Extract calibration data
    cal_data = extract_calibration_data(spectrum, min_confidence, min_sn)

    if len(cal_data) < degree + 2:
        return None

    # Prepare arrays
    mz = np.array([d['mz_obs'] for d in cal_data])
    errors = np.array([d['error_ppm'] for d in cal_data])
    formulas = [d['formula'] for d in cal_data]
    confidences = [d['confidence'] for d in cal_data]
    mz_calc = np.array([d['mz_calc'] for d in cal_data])

    # Fit calibration with outlier removal
    coefficients, mask, iterations = fit_calibration(
        mz, errors, degree, max_iterations, target_std, alpha
    )

    # Build calibration points list
    cal_points = []
    for i in np.where(mask)[0]:
        cal_points.append((
            mz[i],           # observed m/z
            mz[i],           # same for now
            mz_calc[i],      # calculated m/z
            errors[i],       # error ppm
            formulas[i]      # formula
        ))

    # Build all assigned points list
    all_assigned = []
    for i, d in enumerate(cal_data):
        all_assigned.append((
            d['mz_obs'],
            d['error_ppm'],
            d['formula'],
            d['confidence'],
            mask[i]
        ))

    # Calculate final std
    final_std = np.std(errors[mask]) if np.any(mask) else 0.0

    return CalibrationResult(
        coefficients=coefficients,
        degree=degree,
        n_peaks=int(np.sum(mask)),
        final_std=final_std,
        cal_points=cal_points,
        all_assigned=all_assigned,
        iterations=iterations
    )


def apply_calibration_to_spectrum(spectrum, calibration: CalibrationResult):
    """Apply calibration correction to spectrum peaks.

    Args:
        spectrum: Spectrum with mspeaks
        calibration: CalibrationResult from run_calibration
    """
    if not hasattr(spectrum, 'mspeaks'):
        return

    for peak in spectrum.mspeaks:
        # Apply correction to experimental m/z
        corrected_mz = calibration.apply_correction(np.array([peak.mz_exp]))[0]

        # Store original and set corrected
        if not hasattr(peak, 'mz_exp_original'):
            peak.mz_exp_original = peak.mz_exp

        peak.mz_exp = corrected_mz
