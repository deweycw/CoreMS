"""File handling utilities for CoreMS integration."""

from typing import Optional, List, Dict, Union
from pathlib import Path
from dataclasses import dataclass

from corems.encapsulation.factory.parameters import MSParameters


@dataclass
class TIC_Data:
    """TIC data container compatible with CoreMS TIC_Data."""
    scans: List[int]
    time: List[float]
    tic: List[float]
    bpc: List[float] = None
    apexes: List[int] = None

    def __post_init__(self):
        if self.bpc is None:
            self.bpc = []
        if self.apexes is None:
            self.apexes = []


class FileHandler:
    """Handles file operations with CoreMS.

    This class wraps CoreMS file reading functionality to provide
    a clean interface for the HRMS Viewer application.
    Supports Thermo .RAW files only.
    """

    @staticmethod
    def get_supported_formats() -> str:
        """Get file dialog filter string for supported formats."""
        return "Thermo RAW Files (*.raw);;All Files (*)"

    @staticmethod
    def open_file(file_path: str):
        """Open a Thermo RAW file.

        Args:
            file_path: Path to the .RAW file

        Returns:
            Reader object (ImportMassSpectraThermoMSFileReader)

        Raises:
            FileNotFoundError: If file doesn't exist
            ValueError: If file format not supported
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        suffix = path.suffix.lower()

        if suffix == '.raw':
            return FileHandler._open_raw_file(file_path)
        else:
            raise ValueError(f"Unsupported file format: {suffix}. Only Thermo .RAW files are supported.")

    @staticmethod
    def _open_raw_file(file_path: str):
        """Open a Thermo .RAW file."""
        from corems.mass_spectra.input.rawFileReader import ImportMassSpectraThermoMSFileReader

        path = Path(file_path)
        reader = ImportMassSpectraThermoMSFileReader(
            file_location=file_path,
            analyzer="Unknown",
            instrument_label="Unknown",
            sample_name=path.stem
        )
        reader._file_type = 'raw'
        return reader

    @staticmethod
    def get_file_type(reader) -> str:
        """Get the file type of a reader."""
        return getattr(reader, '_file_type', 'raw')

    @staticmethod
    def get_tic(reader, ms_type: str = 'MS', trace_type: str = 'TIC') -> TIC_Data:
        """Get TIC or BPC data from reader.

        Args:
            reader: Open file reader
            ms_type: MS filter type
            trace_type: 'TIC' for total ion current, 'BPC' for base peak

        Returns:
            TIC_Data object with scans, time, tic/bpc values
        """
        tic_data, _ = reader.get_tic(
            ms_type=ms_type,
            peak_detection=False,
            smooth=False,
            plot=False,
            trace_type=trace_type
        )
        return tic_data

    @staticmethod
    def get_scan_df(reader):
        """Get scan metadata as DataFrame.

        Args:
            reader: Open file reader

        Returns:
            pandas DataFrame with scan metadata
        """
        return reader.get_scan_df()

    @staticmethod
    def get_spectrum(reader, scan: int, mode: str = 'profile', auto_process: bool = False):
        """Get mass spectrum for a specific scan.

        Args:
            reader: Open file reader
            scan: Scan number
            mode: 'profile' or 'centroid'
            auto_process: Whether to auto-process (peak picking)

        Returns:
            MassSpectrum object
        """
        return reader.get_mass_spectrum_from_scan(
            scan_number=scan,
            spectrum_mode=mode,
            auto_process=auto_process
        )

    @staticmethod
    def get_averaged_spectrum(reader, scan_list: List[int], mode: str = 'profile',
                              auto_process: bool = False):
        """Get averaged mass spectrum from multiple scans.

        Args:
            reader: Open file reader
            scan_list: List of scan numbers to average
            mode: 'profile' or 'centroid'
            auto_process: Whether to auto-process (peak picking)

        Returns:
            MassSpectrum object representing the average
        """
        return reader.get_average_mass_spectrum_by_scanlist(
            scans_list=scan_list,
            auto_process=auto_process
        )

    @staticmethod
    def get_eic(reader, target_mz: float, tic_data, ppm_tolerance: float = 5.0,
                ms_type: str = 'MS'):
        """Extract EIC for a target m/z.

        Args:
            reader: Open file reader
            target_mz: Target m/z value
            tic_data: TIC_Data object (needed for scan range)
            ppm_tolerance: Mass tolerance in ppm
            ms_type: MS filter type

        Returns:
            EIC_Data-like object with scans, time, eic values
        """
        reader.chromatogram_settings.eic_tolerance_ppm = ppm_tolerance
        eics, _ = reader.get_eics(
            target_mzs=[target_mz],
            tic_data=tic_data,
            ms_type=ms_type,
            peak_detection=False,
            smooth=False,
            plot=False
        )
        return eics.get(target_mz)

    @staticmethod
    def process_spectrum(spectrum, parameters: Optional[MSParameters] = None):
        """Process a spectrum (peak picking).

        Args:
            spectrum: MassSpectrum object
            parameters: Optional MSParameters to apply

        Returns:
            The same spectrum object (modified in place)
        """
        if parameters is not None:
            spectrum.parameters = parameters

        spectrum.process_mass_spec()
        return spectrum

    @staticmethod
    def assign_formulas(spectrum, find_isotopologues: bool = True):
        """Assign molecular formulas to peaks in a spectrum.

        Args:
            spectrum: MassSpectrum object (must be processed first)
            find_isotopologues: Whether to search for isotopologue patterns

        Returns:
            List of peaks that were assigned formulas
        """
        from corems.molecular_id.search.molecularFormulaSearch import SearchMolecularFormulas

        # Ensure spectrum is processed
        if not hasattr(spectrum, 'mspeaks') or len(spectrum.mspeaks) == 0:
            spectrum.process_mass_spec()

        # Run formula search
        with SearchMolecularFormulas(spectrum, find_isotopologues=find_isotopologues) as search:
            search.run_worker_mass_spectrum()

        # Return assigned peaks
        return [peak for peak in spectrum.mspeaks if peak.is_assigned]

    @staticmethod
    def close_file(reader):
        """Close a file reader."""
        try:
            reader.close()
        except:
            pass
