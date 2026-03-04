"""Central data model for HRMS Viewer application."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Dict, List, Any
from PyQt6.QtCore import QObject, pyqtSignal

from corems.encapsulation.factory.parameters import MSParameters, LCMSParameters


@dataclass
class TimeWindowResult:
    """Result from batch assignment for a single time window."""
    window_index: int  # 1-based window number
    start_time: float  # minutes
    end_time: float  # minutes
    start_scan: int
    end_scan: int
    n_scans: int
    spectrum: Any  # MassSpectrum - averaged spectrum with assignments
    n_peaks: int
    n_assigned: int
    formulas: List[str] = field(default_factory=list)  # unique formulas found


class DataType(Enum):
    """Type of mass spectrometry data."""
    LC_MS = "LC-MS"  # Liquid chromatography - has meaningful retention times
    DI_MS = "DI-MS"  # Direct infusion - scans are essentially replicates
    UNKNOWN = "Unknown"


class HRMSDataModel(QObject):
    """Central data model managing all MS data state.

    This class holds all loaded data and emits signals when data changes,
    allowing widgets to update reactively.

    Signals:
        file_loaded: Emitted when a file is successfully loaded (file path)
        file_closed: Emitted when file is closed
        tic_data_changed: Emitted when TIC/BPC data changes
        spectrum_changed: Emitted when active spectrum changes (scan number)
        spectrum_processed: Emitted when spectrum processing completes
        eic_added: Emitted when EIC is added (m/z value)
        eic_removed: Emitted when EIC is removed (m/z value)
        peaks_updated: Emitted when peak list changes
        processing_started: Emitted when processing begins (description)
        processing_finished: Emitted when processing completes
        processing_error: Emitted on processing error (error message)
        data_type_changed: Emitted when data type changes (DataType)
    """

    # File signals
    file_loaded = pyqtSignal(str)
    file_closed = pyqtSignal()

    # Data signals
    tic_data_changed = pyqtSignal()
    spectrum_changed = pyqtSignal(int)  # scan number
    spectrum_processed = pyqtSignal()
    eic_added = pyqtSignal(float)  # m/z value
    eic_removed = pyqtSignal(float)  # m/z value
    peaks_updated = pyqtSignal()
    data_type_changed = pyqtSignal(object)  # DataType enum

    # Processing signals
    processing_started = pyqtSignal(str)  # description
    processing_finished = pyqtSignal()
    processing_error = pyqtSignal(str)  # error message

    # Batch assignment signals
    batch_results_changed = pyqtSignal()  # emitted when batch results are updated

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)

        # File and reader
        self._file_path: Optional[str] = None
        self._reader = None  # ImportMassSpectraThermoMSFileReader
        self._data_type: DataType = DataType.UNKNOWN

        # Chromatogram data
        self._tic_data = None  # TIC_Data
        self._bpc_data = None  # TIC_Data (with BPC)
        self._scan_df = None  # pandas DataFrame with scan info

        # Current spectrum
        self._current_scan: Optional[int] = None
        self._current_spectrum = None  # MassSpectrum
        self._is_averaged: bool = False
        self._averaged_scan_range: Optional[tuple] = None

        # EICs
        self._eics: Dict[float, object] = {}  # m/z -> EIC_Data
        self._eic_colors: Dict[float, str] = {}  # m/z -> color

        # Batch assignment results
        self._batch_results: List[TimeWindowResult] = []

        # Calibration result (stored for reuse in batch processing)
        self._calibration_result = None  # CalibrationResult

        # Parameters - set legacy_resolving_power to False for modern RP calculation
        self._parameters = MSParameters()
        self._parameters.mass_spectrum.legacy_resolving_power = False

    @property
    def file_path(self) -> Optional[str]:
        """Current file path."""
        return self._file_path

    @property
    def reader(self):
        """Current file reader."""
        return self._reader

    @property
    def tic_data(self):
        """TIC data."""
        return self._tic_data

    @property
    def bpc_data(self):
        """BPC data."""
        return self._bpc_data

    @property
    def scan_df(self):
        """Scan metadata DataFrame."""
        return self._scan_df

    @property
    def current_scan(self) -> Optional[int]:
        """Current scan number."""
        return self._current_scan

    @property
    def current_spectrum(self):
        """Current mass spectrum."""
        return self._current_spectrum

    @property
    def is_averaged(self) -> bool:
        """Whether current spectrum is an average."""
        return self._is_averaged

    @property
    def averaged_scan_range(self) -> Optional[tuple]:
        """Scan range if current spectrum is averaged."""
        return self._averaged_scan_range

    @property
    def eics(self) -> Dict[float, object]:
        """EIC data dictionary."""
        return self._eics

    @property
    def eic_colors(self) -> Dict[float, str]:
        """EIC color dictionary."""
        return self._eic_colors

    @property
    def parameters(self) -> MSParameters:
        """CoreMS parameters."""
        return self._parameters

    @parameters.setter
    def parameters(self, value: MSParameters):
        """Set CoreMS parameters."""
        self._parameters = value

    @property
    def is_file_loaded(self) -> bool:
        """Check if a file is currently loaded."""
        return self._reader is not None

    @property
    def has_spectrum(self) -> bool:
        """Check if a spectrum is currently loaded."""
        return self._current_spectrum is not None

    @property
    def has_peaks(self) -> bool:
        """Check if current spectrum has detected peaks."""
        if self._current_spectrum is None:
            return False
        return hasattr(self._current_spectrum, 'mspeaks') and len(self._current_spectrum.mspeaks) > 0

    @property
    def data_type(self) -> DataType:
        """Current data type (LC-MS or DI-MS)."""
        return self._data_type

    @data_type.setter
    def data_type(self, value: DataType):
        """Set the data type."""
        if self._data_type != value:
            self._data_type = value
            self.data_type_changed.emit(value)

    @property
    def is_direct_infusion(self) -> bool:
        """Check if data is direct infusion."""
        return self._data_type == DataType.DI_MS

    @property
    def is_lc_ms(self) -> bool:
        """Check if data is LC-MS."""
        return self._data_type == DataType.LC_MS

    @property
    def total_scans(self) -> int:
        """Get total number of scans."""
        if self._tic_data is None:
            return 0
        return len(self._tic_data.scans)

    @property
    def time_range(self) -> Optional[tuple]:
        """Get (min_time, max_time) in minutes."""
        if self._tic_data is None or len(self._tic_data.time) == 0:
            return None
        return (min(self._tic_data.time), max(self._tic_data.time))

    def detect_data_type(self) -> DataType:
        """Detect whether the data is LC-MS or DI-MS based on characteristics.

        Heuristics used:
        - DI-MS: Short time range (< 2 minutes) or stable TIC (low CV)
        - LC-MS: Longer time range with variable TIC

        Returns:
            Detected DataType
        """
        if self._tic_data is None:
            return DataType.UNKNOWN

        import numpy as np

        times = self._tic_data.time
        tic_values = self._tic_data.tic

        if len(times) < 2:
            return DataType.DI_MS  # Single scan = DI

        time_range = max(times) - min(times)

        # If time range is very short (< 2 minutes), likely DI
        if time_range < 2.0:
            return DataType.DI_MS

        # Calculate coefficient of variation of TIC
        # DI-MS tends to have stable TIC (low CV)
        tic_array = np.array(tic_values)
        if tic_array.mean() > 0:
            cv = tic_array.std() / tic_array.mean()
            # Low CV (< 0.3) suggests DI-MS
            if cv < 0.3 and time_range < 5.0:
                return DataType.DI_MS

        return DataType.LC_MS

    def set_file_data(self, file_path: str, reader, tic_data, bpc_data, scan_df, data_type: DataType = None):
        """Set data from a newly loaded file.

        Args:
            file_path: Path to the loaded file
            reader: ImportMassSpectraThermoMSFileReader instance
            tic_data: TIC_Data from get_tic()
            bpc_data: TIC_Data (BPC) from get_tic()
            scan_df: DataFrame from get_scan_df()
            data_type: Optional DataType override (auto-detected if None)
        """
        # Close existing reader if any
        if self._reader is not None:
            try:
                self._reader.close()
            except:
                pass

        self._file_path = file_path
        self._reader = reader
        self._tic_data = tic_data
        self._bpc_data = bpc_data
        self._scan_df = scan_df

        # Clear current spectrum and EICs
        self._current_scan = None
        self._current_spectrum = None
        self._is_averaged = False
        self._averaged_scan_range = None
        self._eics.clear()
        self._eic_colors.clear()

        # Detect or set data type
        if data_type is not None:
            self._data_type = data_type
        else:
            self._data_type = self.detect_data_type()

        self.file_loaded.emit(file_path)
        self.tic_data_changed.emit()
        self.data_type_changed.emit(self._data_type)

    def set_spectrum(self, scan: int, spectrum, is_averaged: bool = False,
                     scan_range: Optional[tuple] = None):
        """Set the current spectrum.

        Args:
            scan: Scan number (or first scan if averaged)
            spectrum: MassSpectrum object
            is_averaged: Whether this is an averaged spectrum
            scan_range: (start, end) tuple if averaged
        """
        self._current_scan = scan
        self._current_spectrum = spectrum
        self._is_averaged = is_averaged
        self._averaged_scan_range = scan_range

        self.spectrum_changed.emit(scan)

    def set_spectrum_processed(self):
        """Signal that the current spectrum has been processed."""
        self.spectrum_processed.emit()
        self.peaks_updated.emit()

    def add_eic(self, mz: float, eic_data, color: str = "#FF0000"):
        """Add an EIC to the model.

        Args:
            mz: Target m/z value
            eic_data: EIC_Data object
            color: Hex color string for plotting
        """
        self._eics[mz] = eic_data
        self._eic_colors[mz] = color
        self.eic_added.emit(mz)

    def remove_eic(self, mz: float):
        """Remove an EIC from the model.

        Args:
            mz: Target m/z value to remove
        """
        if mz in self._eics:
            del self._eics[mz]
            del self._eic_colors[mz]
            self.eic_removed.emit(mz)

    def clear_eics(self):
        """Clear all EICs."""
        mz_values = list(self._eics.keys())
        self._eics.clear()
        self._eic_colors.clear()
        for mz in mz_values:
            self.eic_removed.emit(mz)

    def close_file(self):
        """Close current file and clear all data."""
        if self._reader is not None:
            try:
                self._reader.close()
            except:
                pass

        self._file_path = None
        self._reader = None
        self._tic_data = None
        self._bpc_data = None
        self._scan_df = None
        self._current_scan = None
        self._current_spectrum = None
        self._is_averaged = False
        self._averaged_scan_range = None
        self._eics.clear()
        self._eic_colors.clear()
        self._batch_results.clear()
        self._calibration_result = None

        self.file_closed.emit()

    def get_retention_time(self, scan: int) -> Optional[float]:
        """Get retention time for a scan number.

        Args:
            scan: Scan number

        Returns:
            Retention time in minutes, or None if not found
        """
        if self._tic_data is None:
            return None

        try:
            idx = self._tic_data.scans.index(scan)
            return self._tic_data.time[idx]
        except (ValueError, IndexError):
            return None

    def get_scan_from_time(self, time: float) -> Optional[int]:
        """Get closest scan number for a retention time.

        Args:
            time: Retention time in minutes

        Returns:
            Closest scan number, or None if no data
        """
        if self._tic_data is None:
            return None

        import numpy as np
        times = np.array(self._tic_data.time)
        idx = np.argmin(np.abs(times - time))
        return self._tic_data.scans[idx]

    def get_scans_in_range(self, start_time: float, end_time: float) -> List[int]:
        """Get scan numbers within a time range.

        Args:
            start_time: Start retention time in minutes
            end_time: End retention time in minutes

        Returns:
            List of scan numbers in the range
        """
        if self._tic_data is None:
            return []

        import numpy as np
        times = np.array(self._tic_data.time)
        scans = np.array(self._tic_data.scans)
        mask = (times >= start_time) & (times <= end_time)
        return scans[mask].tolist()

    # Calibration methods
    @property
    def calibration_result(self):
        """Get stored calibration result."""
        return self._calibration_result

    @calibration_result.setter
    def calibration_result(self, value):
        """Set calibration result."""
        self._calibration_result = value

    @property
    def has_calibration(self) -> bool:
        """Check if a calibration is stored."""
        return self._calibration_result is not None

    def clear_calibration(self):
        """Clear stored calibration."""
        self._calibration_result = None

    # Batch assignment methods
    @property
    def batch_results(self) -> List[TimeWindowResult]:
        """Get batch assignment results."""
        return self._batch_results

    @property
    def has_batch_results(self) -> bool:
        """Check if batch results are available."""
        return len(self._batch_results) > 0

    def set_batch_results(self, results: List[TimeWindowResult]):
        """Set batch assignment results.

        Args:
            results: List of TimeWindowResult objects
        """
        self._batch_results = results
        self.batch_results_changed.emit()

    def add_batch_result(self, result: TimeWindowResult):
        """Add a single batch result.

        Args:
            result: TimeWindowResult to add
        """
        self._batch_results.append(result)
        self.batch_results_changed.emit()

    def clear_batch_results(self):
        """Clear all batch assignment results."""
        self._batch_results.clear()
        self.batch_results_changed.emit()

    def get_batch_result(self, index: int) -> Optional[TimeWindowResult]:
        """Get a specific batch result by index.

        Args:
            index: 0-based index into results list

        Returns:
            TimeWindowResult or None if index is out of range
        """
        if 0 <= index < len(self._batch_results):
            return self._batch_results[index]
        return None
