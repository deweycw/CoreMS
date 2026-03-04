"""Background worker threads for HRMS Viewer."""

import sys
import io
from typing import Optional, List
from PyQt6.QtCore import QThread, pyqtSignal

from hrms_viewer.core.file_handler import FileHandler
from corems.encapsulation.factory.parameters import MSParameters


class OutputCapture:
    """Context manager to capture stdout/stderr and emit via Qt signal.

    This allows capturing all CoreMS output (print statements, progress bars, etc.)
    and displaying it in the terminal-like output window.
    """

    def __init__(self, output_signal):
        """Initialize with the pyqtSignal to emit captured output.

        Args:
            output_signal: A pyqtSignal(str) to emit captured text
        """
        self.output_signal = output_signal
        self._stdout = None
        self._stderr = None
        self._capture_stdout = None
        self._capture_stderr = None

    def __enter__(self):
        """Start capturing stdout and stderr."""
        self._stdout = sys.stdout
        self._stderr = sys.stderr

        # Create custom stream that emits to signal
        self._capture_stdout = SignalStream(self.output_signal)
        self._capture_stderr = SignalStream(self.output_signal)

        sys.stdout = self._capture_stdout
        sys.stderr = self._capture_stderr

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Restore original stdout and stderr."""
        sys.stdout = self._stdout
        sys.stderr = self._stderr
        return False


class SignalStream(io.StringIO):
    """A stream that writes to a Qt signal."""

    def __init__(self, signal):
        super().__init__()
        self.signal = signal
        self._buffer = ""

    def write(self, text):
        """Write text and emit via signal."""
        if text:
            # Buffer partial lines, emit on newline or carriage return
            self._buffer += text
            # Check for line endings or carriage returns (for progress bars)
            if '\n' in self._buffer or '\r' in self._buffer:
                # Emit the buffer
                self.signal.emit(self._buffer)
                self._buffer = ""

    def flush(self):
        """Flush any remaining buffer content."""
        if self._buffer:
            self.signal.emit(self._buffer)
            self._buffer = ""

    def isatty(self):
        """Return False - this is not a TTY."""
        return False


class FileLoadWorker(QThread):
    """Background worker for loading mass spec files (RAW or mzML).

    Signals:
        finished: Emits (reader, tic_data, bpc_data, scan_df) on success
        error: Emits error message string on failure
        progress: Emits (percent, message) during loading
    """

    finished = pyqtSignal(object, object, object, object)  # reader, tic, bpc, scan_df
    error = pyqtSignal(str)
    progress = pyqtSignal(int, str)

    def __init__(self, file_path: str, parent=None):
        super().__init__(parent)
        self.file_path = file_path

    def run(self):
        try:
            self.progress.emit(10, "Opening file...")
            reader = FileHandler.open_file(self.file_path)

            self.progress.emit(30, "Loading TIC...")
            tic_data = FileHandler.get_tic(reader, trace_type='TIC')

            self.progress.emit(50, "Loading BPC...")
            try:
                bpc_data = FileHandler.get_tic(reader, trace_type='BPC')
            except:
                bpc_data = tic_data  # Some formats don't support BPC

            self.progress.emit(70, "Loading scan info...")
            scan_df = FileHandler.get_scan_df(reader)

            self.progress.emit(100, "Complete")
            self.finished.emit(reader, tic_data, bpc_data, scan_df)

        except Exception as e:
            self.error.emit(str(e))


class SpectrumLoadWorker(QThread):
    """Background worker for loading a single spectrum.

    Signals:
        finished: Emits (scan, spectrum) on success
        error: Emits error message string on failure
    """

    finished = pyqtSignal(int, object)  # scan, spectrum
    error = pyqtSignal(str)

    def __init__(self, reader, scan: int, mode: str = 'profile', parent=None):
        super().__init__(parent)
        self.reader = reader
        self.scan = scan
        self.mode = mode

    def run(self):
        try:
            spectrum = FileHandler.get_spectrum(
                self.reader,
                self.scan,
                mode=self.mode,
                auto_process=False
            )
            self.finished.emit(self.scan, spectrum)

        except Exception as e:
            self.error.emit(str(e))


class AveragedSpectrumWorker(QThread):
    """Background worker for averaging spectra over a scan range.

    Signals:
        finished: Emits (start_scan, end_scan, spectrum) on success
        error: Emits error message string on failure
        progress: Emits (percent, message) during processing
    """

    finished = pyqtSignal(int, int, object)  # start_scan, end_scan, spectrum
    error = pyqtSignal(str)
    progress = pyqtSignal(int, str)

    def __init__(self, reader, scan_list: List[int], mode: str = 'profile', parent=None):
        super().__init__(parent)
        self.reader = reader
        self.scan_list = scan_list
        self.mode = mode

    def run(self):
        try:
            n_scans = len(self.scan_list)
            self.progress.emit(10, f"Averaging {n_scans} scans...")

            spectrum = FileHandler.get_averaged_spectrum(
                self.reader,
                self.scan_list,
                mode=self.mode,
                auto_process=False
            )

            start_scan = min(self.scan_list)
            end_scan = max(self.scan_list)

            self.progress.emit(100, "Complete")
            self.finished.emit(start_scan, end_scan, spectrum)

        except Exception as e:
            self.error.emit(str(e))


class SpectrumProcessWorker(QThread):
    """Background worker for processing a spectrum (peak picking).

    Signals:
        finished: Emits processed spectrum on success
        error: Emits error message string on failure
        progress: Emits (percent, message) during processing
    """

    finished = pyqtSignal(object)  # spectrum
    error = pyqtSignal(str)
    progress = pyqtSignal(int, str)

    def __init__(self, spectrum, parameters: Optional[MSParameters] = None, parent=None):
        super().__init__(parent)
        self.spectrum = spectrum
        self.parameters = parameters

    def run(self):
        try:
            self.progress.emit(20, "Processing spectrum...")

            if self.parameters is not None:
                self.spectrum.parameters = self.parameters

            self.spectrum.process_mass_spec()

            n_peaks = len(self.spectrum.mspeaks) if hasattr(self.spectrum, 'mspeaks') else 0
            self.progress.emit(100, f"Found {n_peaks} peaks")
            self.finished.emit(self.spectrum)

        except Exception as e:
            self.error.emit(str(e))


class FormulaSearchWorker(QThread):
    """Background worker for molecular formula assignment.

    Signals:
        finished: Emits (spectrum, assigned_peaks) on success
        error: Emits error message string on failure
        progress: Emits (percent, message) during search
        output: Emits text for display in output window
    """

    # Default CoreMS database URL
    DEFAULT_DB_URL = "postgresql+psycopg2://coremsappdb:coremsapppnnl@localhost:5432/coremsapp"

    finished = pyqtSignal(object, list)  # spectrum, assigned_peaks list
    error = pyqtSignal(str)
    progress = pyqtSignal(int, str)
    output = pyqtSignal(str)  # Text for output window

    def __init__(self, spectrum, parameters: Optional[MSParameters] = None,
                 find_isotopologues: bool = True,
                 min_ppm_error: float = -2.0, max_ppm_error: float = 4.0,
                 db_url: str = None,
                 usedAtoms: dict = None,
                 min_dbe: float = 0, max_dbe: float = 16,
                 isProtonated: bool = True, isRadical: bool = False, isAdduct: bool = False,
                 max_hc_filter: float = 3.0, max_oc_filter: float = 1.2,
                 parent=None):
        super().__init__(parent)
        self.spectrum = spectrum
        self.parameters = parameters
        self.find_isotopologues = find_isotopologues
        self.min_ppm_error = min_ppm_error
        self.max_ppm_error = max_ppm_error
        self.db_url = db_url or self.DEFAULT_DB_URL
        # User-configurable molecular formula search criteria
        self.usedAtoms = usedAtoms or {
            'C': (1, 40), 'H': (4, 80), 'O': (1, 12), 'N': (0, 2)
        }
        self.min_dbe = min_dbe
        self.max_dbe = max_dbe
        self.isProtonated = isProtonated
        self.isRadical = isRadical
        self.isAdduct = isAdduct
        self.max_hc_filter = max_hc_filter
        self.max_oc_filter = max_oc_filter

    def run(self):
        try:
            from corems.molecular_id.search.molecularFormulaSearch import SearchMolecularFormulas

            # Capture all stdout/stderr from CoreMS
            with OutputCapture(self.output):
                print("Setting up formula search parameters...")

                # Apply parameters if provided
                if self.parameters is not None:
                    self.spectrum.parameters = self.parameters

                # Set database URL
                self.spectrum.molecular_search_settings.url_database = self.db_url
                print(f"Database: {self.db_url}")

                # Enable verbose processing to see all CoreMS output
                self.spectrum.molecular_search_settings.verbose_processing = True

                # User-configurable molecular formula search criteria
                self.spectrum.molecular_search_settings.min_dbe = self.min_dbe
                self.spectrum.molecular_search_settings.max_dbe = self.max_dbe
                self.spectrum.molecular_search_settings.usedAtoms = self.usedAtoms
                self.spectrum.molecular_search_settings.isProtonated = self.isProtonated
                self.spectrum.molecular_search_settings.isRadical = self.isRadical
                self.spectrum.molecular_search_settings.isAdduct = self.isAdduct
                self.spectrum.molecular_search_settings.max_oc_filter = self.max_oc_filter
                self.spectrum.molecular_search_settings.max_hc_filter = self.max_hc_filter

                # Set m/z error range
                self.spectrum.molecular_search_settings.min_ppm_error = self.min_ppm_error
                self.spectrum.molecular_search_settings.max_ppm_error = self.max_ppm_error

                print(f"\nMolecular Formula Search Criteria:")
                print(f"  usedAtoms: {self.usedAtoms}")
                print(f"  DBE: {self.min_dbe}-{self.max_dbe}")
                print(f"  isProtonated: {self.isProtonated}")
                print(f"  isRadical: {self.isRadical}")
                print(f"  isAdduct: {self.isAdduct}")
                print(f"  Filters: H/C <= {self.max_hc_filter}, O/C <= {self.max_oc_filter}")
                print(f"  m/z error range: {self.min_ppm_error:.2f} to {self.max_ppm_error:.2f} ppm")
                sys.stdout.flush()

                # Ensure spectrum is processed
                if not hasattr(self.spectrum, 'mspeaks') or len(self.spectrum.mspeaks) == 0:
                    self.progress.emit(10, "Processing spectrum...")
                    print("\nProcessing spectrum (peak picking)...")
                    sys.stdout.flush()
                    self.spectrum.process_mass_spec()

                n_peaks = len(self.spectrum.mspeaks)
                self.progress.emit(30, f"Searching formulas for {n_peaks} peaks...")
                print(f"\n{'='*50}")
                print(f"MOLECULAR FORMULA ASSIGNMENT")
                print(f"{'='*50}")
                print(f"Searching formulas for {n_peaks} peaks...")
                print(f"Find isotopologues: {self.find_isotopologues}")
                print("-" * 50)
                sys.stdout.flush()

                # Run formula search - this will print progress from CoreMS
                # This is a BLOCKING call - it will not return until assignment is complete
                with SearchMolecularFormulas(
                    self.spectrum,
                    find_isotopologues=self.find_isotopologues
                ) as search:
                    search.run_worker_mass_spectrum()

                # Flush output to ensure all assignment output is shown
                sys.stdout.flush()
                sys.stderr.flush()

                # Count assigned peaks
                assigned_peaks = [peak for peak in self.spectrum.mspeaks if peak.is_assigned]
                n_assigned = len(assigned_peaks)

                print("-" * 50)
                print(f"\nAssigned {n_assigned}/{n_peaks} peaks ({100*n_assigned/n_peaks:.1f}%)")
                print(f"\n{'='*50}")
                print(f"FORMULA ASSIGNMENT COMPLETE!")
                print(f"{'='*50}")
                sys.stdout.flush()

            self.progress.emit(100, f"Assigned {n_assigned}/{n_peaks} peaks")
            self.finished.emit(self.spectrum, assigned_peaks)

        except Exception as e:
            self.output.emit(f"\nERROR: {str(e)}\n")
            self.error.emit(str(e))


class EICExtractionWorker(QThread):
    """Background worker for EIC extraction.

    Signals:
        finished: Emits (mz, eic_data) on success
        error: Emits error message string on failure
    """

    finished = pyqtSignal(float, object)  # mz, eic_data
    error = pyqtSignal(str)

    def __init__(self, reader, target_mz: float, tic_data,
                 ppm_tolerance: float = 5.0, parent=None):
        super().__init__(parent)
        self.reader = reader
        self.target_mz = target_mz
        self.tic_data = tic_data
        self.ppm_tolerance = ppm_tolerance

    def run(self):
        try:
            eic_data = FileHandler.get_eic(
                self.reader,
                self.target_mz,
                self.tic_data,
                ppm_tolerance=self.ppm_tolerance
            )

            if eic_data is not None:
                self.finished.emit(self.target_mz, eic_data)
            else:
                self.error.emit(f"No data found for m/z {self.target_mz:.4f}")

        except Exception as e:
            self.error.emit(str(e))


class SinglePeakAssignWorker(QThread):
    """Background worker for assigning formula to a single peak.

    Signals:
        finished: Emits (peak_index, peak) on success
        error: Emits error message string on failure
    """

    finished = pyqtSignal(int, object)  # peak_index, peak
    error = pyqtSignal(str)

    def __init__(self, spectrum, peak_index: int,
                 parameters: Optional[MSParameters] = None, parent=None):
        super().__init__(parent)
        self.spectrum = spectrum
        self.peak_index = peak_index
        self.parameters = parameters

    def run(self):
        try:
            from corems.molecular_id.search.molecularFormulaSearch import SearchMolecularFormulas

            if self.parameters is not None:
                self.spectrum.parameters = self.parameters

            # Get the specific peak
            peak = self.spectrum.mspeaks[self.peak_index]

            # Run formula search on spectrum
            with SearchMolecularFormulas(
                self.spectrum,
                find_isotopologues=False
            ) as search:
                # Search just for this peak's m/z
                search.run_worker_ms_peaks([peak])

            self.finished.emit(self.peak_index, peak)

        except Exception as e:
            self.error.emit(str(e))


class CalibrationWorker(QThread):
    """Background worker for mass calibration.

    Performs formula assignment and polynomial fitting with outlier removal.

    Signals:
        finished: Emits (spectrum, calibration_result) on success
        error: Emits error message string on failure
        progress: Emits (percent, message) during calibration
        output: Emits text for display in output window
    """

    # Default CoreMS database URL
    DEFAULT_DB_URL = "postgresql+psycopg2://coremsappdb:coremsapppnnl@localhost:5432/coremsapp"

    finished = pyqtSignal(object, object)  # spectrum, CalibrationResult
    error = pyqtSignal(str)
    progress = pyqtSignal(int, str)
    output = pyqtSignal(str)  # Text for output window

    def __init__(self, spectrum, parameters: Optional[MSParameters] = None,
                 degree: int = 2, min_confidence: float = 0.6,
                 min_sn: float = 10.0, target_std: float = 0.5,
                 min_ppm_error: float = -2.0, max_ppm_error: float = 4.0,
                 apply_correction: bool = True, db_url: str = None,
                 parent=None):
        super().__init__(parent)
        self.spectrum = spectrum
        self.parameters = parameters
        self.degree = degree
        self.min_confidence = min_confidence
        self.min_sn = min_sn
        self.target_std = target_std
        self.min_ppm_error = min_ppm_error
        self.max_ppm_error = max_ppm_error
        self.apply_correction = apply_correction
        self.db_url = db_url or self.DEFAULT_DB_URL

    def run(self):
        try:
            from corems.molecular_id.search.molecularFormulaSearch import SearchMolecularFormulas
            from hrms_viewer.core.calibration import run_calibration, apply_calibration_to_spectrum

            # Capture all stdout/stderr from CoreMS
            with OutputCapture(self.output):
                print("Setting up calibration parameters...")

                # Apply fixed MSParameters for calibration
                from corems.encapsulation.factory.parameters import MSParameters as CoreMSParams

                # Mass spectrum settings
                CoreMSParams.mass_spectrum.calib_pol_order = 2
                CoreMSParams.mass_spectrum.min_picking_mz = 200
                CoreMSParams.mass_spectrum.max_picking_mz = 900
                CoreMSParams.mass_spectrum.noise_threshold_method = 'log'
                CoreMSParams.mass_spectrum.noise_threshold_log_nsigma = 20

                # MS peak settings
                CoreMSParams.ms_peak.peak_min_prominence_percent = 0.02
                CoreMSParams.ms_peak.legacy_resolving_power = False

                # Molecular search settings (fixed)
                CoreMSParams.molecular_search.db_chunk_size = 1000
                CoreMSParams.molecular_search.mz_error_score_weight = 0.6
                CoreMSParams.molecular_search.isotopologue_score_weight = 0.4
                CoreMSParams.molecular_search.output_score_method = "prob_score"

                # Set database URL
                self.spectrum.molecular_search_settings.url_database = self.db_url
                print(f"Database: {self.db_url}")

                # Enable verbose processing to see all CoreMS output
                self.spectrum.molecular_search_settings.verbose_processing = True

                # Fixed molecular formula search criteria
                self.spectrum.molecular_search_settings.min_dbe = 0
                self.spectrum.molecular_search_settings.max_dbe = 16

                self.spectrum.molecular_search_settings.usedAtoms = {
                    'C': (1, 40),
                    'H': (4, 80),
                    'O': (1, 12),
                    'N': (0, 2),
                }

                self.spectrum.molecular_search_settings.isProtonated = True
                self.spectrum.molecular_search_settings.isRadical = False
                self.spectrum.molecular_search_settings.isAdduct = False

                self.spectrum.molecular_search_settings.max_oc_filter = 1.2
                self.spectrum.molecular_search_settings.max_hc_filter = 3

                self.spectrum.molecular_search_settings.used_atom_valences = {
                    'C': 4,
                    '13C': 4,
                    'H': 1,
                    'O': 2,
                    'N': 3
                }

                # User-configurable m/z error range
                self.spectrum.molecular_search_settings.min_ppm_error = self.min_ppm_error
                self.spectrum.molecular_search_settings.max_ppm_error = self.max_ppm_error

                print(f"\nMolecular Formula Search Criteria (Fixed):")
                print(f"  usedAtoms: C(1-40), H(4-80), O(1-12), N(0-2)")
                print(f"  DBE: 0-16")
                print(f"  Ion type: [M+H]+ / [M-H]-")
                print(f"  m/z range: 200-900")
                print(f"  Filters: H/C <= 3, O/C <= 1.2")
                print(f"\nUser-configurable:")
                print(f"  m/z error range: {self.min_ppm_error:.2f} to {self.max_ppm_error:.2f} ppm")
                sys.stdout.flush()

                # Ensure spectrum is processed
                if not hasattr(self.spectrum, 'mspeaks') or len(self.spectrum.mspeaks) == 0:
                    self.progress.emit(10, "Processing spectrum...")
                    print("\nProcessing spectrum (peak picking)...")
                    sys.stdout.flush()
                    self.spectrum.process_mass_spec()

                n_peaks = len(self.spectrum.mspeaks)
                self.progress.emit(20, f"Assigning formulas to {n_peaks} peaks...")
                print(f"\n{'='*50}")
                print(f"STEP 1: MOLECULAR FORMULA ASSIGNMENT")
                print(f"{'='*50}")
                print(f"Assigning formulas to {n_peaks} peaks...")
                print("-" * 50)
                sys.stdout.flush()

                # Run formula search - this will print progress from CoreMS
                # This is a BLOCKING call - it will not return until assignment is complete
                with SearchMolecularFormulas(
                    self.spectrum,
                    find_isotopologues=True
                ) as search:
                    search.run_worker_mass_spectrum()

                # Flush output to ensure all assignment output is shown
                sys.stdout.flush()
                sys.stderr.flush()

                # Count assigned peaks
                assigned_peaks = [peak for peak in self.spectrum.mspeaks if peak.is_assigned]
                n_assigned = len(assigned_peaks)

                print("-" * 50)
                print(f"Formula assignment COMPLETE: {n_assigned}/{n_peaks} peaks ({100*n_assigned/n_peaks:.1f}%)")
                print(f"{'='*50}\n")
                sys.stdout.flush()

                self.progress.emit(60, f"Assigned {n_assigned} peaks, running calibration...")

                # Check if we have enough assigned peaks
                if n_assigned == 0:
                    print("\nERROR: No peaks were assigned molecular formulas!")
                    print("Cannot proceed with calibration.")
                    sys.stdout.flush()
                    self.error.emit("No peaks were assigned molecular formulas. Check database connection and settings.")
                    return

                # Run calibration
                print(f"{'='*50}")
                print(f"STEP 2: CALIBRATION FITTING")
                print(f"{'='*50}")
                print(f"Parameters:")
                print(f"  Polynomial degree: {self.degree}")
                print(f"  Min confidence: {self.min_confidence}")
                print(f"  Min S/N: {self.min_sn}")
                print(f"  Target std: {self.target_std} ppm")
                print("-" * 50)
                sys.stdout.flush()

                calibration = run_calibration(
                    self.spectrum,
                    degree=self.degree,
                    min_confidence=self.min_confidence,
                    min_sn=self.min_sn,
                    target_std=self.target_std
                )

                sys.stdout.flush()

                if calibration is None:
                    print("\nERROR: Not enough assigned peaks for calibration")
                    sys.stdout.flush()
                    self.error.emit("Not enough assigned peaks for calibration")
                    return

                self.progress.emit(80, f"Calibration fit using {calibration.n_peaks} peaks...")
                print(f"\nCalibration fit COMPLETE:")
                print(f"  Points used: {calibration.n_peaks}")
                print(f"  Iterations: {calibration.iterations}")
                print(f"  Final std: {calibration.final_std:.4f} ppm")
                sys.stdout.flush()

                # Apply correction if requested
                if self.apply_correction:
                    self.progress.emit(90, "Applying calibration correction...")
                    print(f"\nApplying calibration correction to spectrum...")
                    sys.stdout.flush()
                    apply_calibration_to_spectrum(self.spectrum, calibration)

                self.progress.emit(100, f"Calibration complete: std={calibration.final_std:.3f} ppm")
                print(f"\n{'='*50}")
                print(f"CALIBRATION COMPLETE!")
                print(f"{'='*50}")
                sys.stdout.flush()

            self.finished.emit(self.spectrum, calibration)

        except Exception as e:
            self.output.emit(f"\nERROR: {str(e)}\n")
            self.error.emit(str(e))
