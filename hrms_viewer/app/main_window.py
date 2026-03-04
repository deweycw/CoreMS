"""Main application window for HRMS Viewer."""

import os
from pathlib import Path
from typing import Optional, List

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QSplitter, QDockWidget,
    QFileDialog, QMessageBox, QStatusBar, QToolBar, QProgressBar,
    QLabel
)
from PyQt6.QtCore import Qt, QSettings
from PyQt6.QtGui import QAction, QKeySequence

from hrms_viewer.core.data_model import HRMSDataModel, DataType, TimeWindowResult
from hrms_viewer.core.workers import (
    SpectrumProcessWorker, FormulaSearchWorker, EICExtractionWorker,
    CalibrationWorker
)
from hrms_viewer.widgets.chromatogram_widget import ChromatogramWidget
from hrms_viewer.widgets.spectrum_widget import SpectrumWidget
from hrms_viewer.widgets.eic_widget import EICWidget
from hrms_viewer.widgets.peak_table_widget import PeakTableWidget
from hrms_viewer.widgets.candidate_formulas_widget import CandidateFormulasWidget
from hrms_viewer.widgets.batch_results_widget import BatchResultsWidget
from hrms_viewer.dialogs.eic_dialog import EICDialog
from hrms_viewer.dialogs.settings_dialog import SettingsDialog
from hrms_viewer.dialogs.batch_assignment_dialog import BatchAssignmentDialog


class MainWindow(QMainWindow):
    """Main application window for HRMS Viewer.

    Provides a dock-based layout with:
    - Central area: Chromatogram + Spectrum splitter
    - Right dock: Peak table
    - Bottom dock: EIC panel (collapsible)
    """

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)

        self.setWindowTitle("HRMS Viewer")
        self.setMinimumSize(1200, 800)

        # Data model
        self.data_model = HRMSDataModel(self)

        # Workers (keep references to prevent garbage collection)
        self._active_workers: List = []

        # Settings
        self.settings = QSettings("CoreMS", "HRMSViewer")

        self._setup_ui()
        self._setup_menubar()
        self._setup_toolbar()
        self._setup_statusbar()
        self._connect_signals()
        self._restore_settings()

    def _setup_ui(self):
        """Set up the main UI layout."""
        # Central widget with splitter
        central = QWidget()
        self.setCentralWidget(central)

        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)

        # Vertical splitter for chromatogram and spectrum
        self.splitter = QSplitter(Qt.Orientation.Vertical)

        # Chromatogram widget (top)
        self.chromatogram = ChromatogramWidget()
        self.splitter.addWidget(self.chromatogram)

        # Spectrum widget (bottom)
        self.spectrum = SpectrumWidget()
        self.splitter.addWidget(self.spectrum)

        # Set initial splitter sizes (40% chromatogram, 60% spectrum)
        self.splitter.setSizes([300, 500])

        layout.addWidget(self.splitter)

        # Peak table dock (right side)
        self._setup_peak_table_dock()

        # EIC dock (bottom)
        self._setup_eic_dock()

        # Candidate formulas dock (under peak table)
        self._setup_candidate_formulas_dock()

        # Batch results dock
        self._setup_batch_results_dock()

    def _setup_peak_table_dock(self):
        """Set up the peak table dock widget."""
        self.peak_table = PeakTableWidget()

        self.peak_table_dock = QDockWidget("Peaks", self)
        self.peak_table_dock.setWidget(self.peak_table)
        self.peak_table_dock.setAllowedAreas(
            Qt.DockWidgetArea.RightDockWidgetArea | Qt.DockWidgetArea.LeftDockWidgetArea
        )

        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.peak_table_dock)

    def _setup_eic_dock(self):
        """Set up the EIC dock widget."""
        self.eic_widget = EICWidget()

        self.eic_dock = QDockWidget("EIC", self)
        self.eic_dock.setWidget(self.eic_widget)
        self.eic_dock.setAllowedAreas(
            Qt.DockWidgetArea.BottomDockWidgetArea | Qt.DockWidgetArea.TopDockWidgetArea
        )

        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self.eic_dock)

        # Start collapsed
        self.eic_dock.setVisible(False)

    def _setup_candidate_formulas_dock(self):
        """Set up the candidate formulas dock widget."""
        self.candidate_formulas = CandidateFormulasWidget()

        self.candidate_formulas_dock = QDockWidget("Candidate Formulas", self)
        self.candidate_formulas_dock.setWidget(self.candidate_formulas)
        self.candidate_formulas_dock.setAllowedAreas(
            Qt.DockWidgetArea.RightDockWidgetArea | Qt.DockWidgetArea.LeftDockWidgetArea |
            Qt.DockWidgetArea.BottomDockWidgetArea
        )

        # Add below the peak table dock on the right
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.candidate_formulas_dock)

        # Stack it below the peak table dock
        self.splitDockWidget(self.peak_table_dock, self.candidate_formulas_dock, Qt.Orientation.Vertical)

        # Start hidden - only show when an assigned peak is selected
        self.candidate_formulas_dock.setVisible(False)

    def _setup_batch_results_dock(self):
        """Set up the batch results dock widget."""
        self.batch_results = BatchResultsWidget()

        self.batch_results_dock = QDockWidget("Batch Results", self)
        self.batch_results_dock.setWidget(self.batch_results)
        self.batch_results_dock.setAllowedAreas(
            Qt.DockWidgetArea.BottomDockWidgetArea |
            Qt.DockWidgetArea.RightDockWidgetArea |
            Qt.DockWidgetArea.LeftDockWidgetArea
        )

        # Add to bottom area
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self.batch_results_dock)

        # Start hidden
        self.batch_results_dock.setVisible(False)

    def _setup_menubar(self):
        """Set up the menu bar."""
        menubar = self.menuBar()

        # File menu
        file_menu = menubar.addMenu("&File")

        open_action = QAction("&Open...", self)
        open_action.setShortcut(QKeySequence.StandardKey.Open)
        open_action.triggered.connect(self._open_file_dialog)
        file_menu.addAction(open_action)

        self.recent_menu = file_menu.addMenu("Recent Files")
        self._update_recent_files_menu()

        file_menu.addSeparator()

        close_action = QAction("&Close File", self)
        close_action.setShortcut(QKeySequence("Ctrl+W"))
        close_action.triggered.connect(self._close_file)
        file_menu.addAction(close_action)

        file_menu.addSeparator()

        exit_action = QAction("E&xit", self)
        exit_action.setShortcut(QKeySequence.StandardKey.Quit)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # View menu
        view_menu = menubar.addMenu("&View")

        reset_view_action = QAction("Reset View", self)
        reset_view_action.setShortcut(QKeySequence("Ctrl+0"))
        reset_view_action.triggered.connect(self._reset_view)
        view_menu.addAction(reset_view_action)

        view_menu.addSeparator()

        # Dock visibility toggles
        self.toggle_peaks_action = self.peak_table_dock.toggleViewAction()
        self.toggle_peaks_action.setText("Show &Peaks Panel")
        view_menu.addAction(self.toggle_peaks_action)

        self.toggle_eic_action = self.eic_dock.toggleViewAction()
        self.toggle_eic_action.setText("Show &EIC Panel")
        view_menu.addAction(self.toggle_eic_action)

        self.toggle_candidates_action = self.candidate_formulas_dock.toggleViewAction()
        self.toggle_candidates_action.setText("Show &Candidate Formulas Panel")
        view_menu.addAction(self.toggle_candidates_action)

        self.toggle_batch_results_action = self.batch_results_dock.toggleViewAction()
        self.toggle_batch_results_action.setText("Show &Batch Results Panel")
        view_menu.addAction(self.toggle_batch_results_action)

        # Tools menu
        tools_menu = menubar.addMenu("&Tools")

        process_action = QAction("&Process Spectrum", self)
        process_action.setShortcut(QKeySequence("Ctrl+P"))
        process_action.triggered.connect(self._process_spectrum)
        tools_menu.addAction(process_action)

        assign_action = QAction("&Assign Formulas", self)
        assign_action.setShortcut(QKeySequence("Ctrl+A"))
        assign_action.triggered.connect(self._assign_formulas)
        tools_menu.addAction(assign_action)

        self.batch_assign_action = QAction("&Batch Time-Window Assignment...", self)
        self.batch_assign_action.setShortcut(QKeySequence("Ctrl+Shift+B"))
        self.batch_assign_action.triggered.connect(self._batch_assign_formulas)
        self.batch_assign_action.setEnabled(False)
        tools_menu.addAction(self.batch_assign_action)

        calibrate_action = QAction("&Calibrate...", self)
        calibrate_action.setShortcut(QKeySequence("Ctrl+Shift+C"))
        calibrate_action.triggered.connect(self._calibrate_spectrum)
        tools_menu.addAction(calibrate_action)

        tools_menu.addSeparator()

        # Averaging options
        self.average_all_action = QAction("Average &All Scans", self)
        self.average_all_action.setShortcut(QKeySequence("Ctrl+Shift+A"))
        self.average_all_action.triggered.connect(self._average_all_scans)
        self.average_all_action.setEnabled(False)
        tools_menu.addAction(self.average_all_action)

        tools_menu.addSeparator()

        # Data type submenu
        data_type_menu = tools_menu.addMenu("&Data Type")

        self.lc_ms_action = QAction("LC-MS (Chromatography)", self)
        self.lc_ms_action.setCheckable(True)
        self.lc_ms_action.triggered.connect(lambda: self._set_data_type(DataType.LC_MS))
        data_type_menu.addAction(self.lc_ms_action)

        self.di_ms_action = QAction("DI-MS (Direct Infusion)", self)
        self.di_ms_action.setCheckable(True)
        self.di_ms_action.triggered.connect(lambda: self._set_data_type(DataType.DI_MS))
        data_type_menu.addAction(self.di_ms_action)

        tools_menu.addSeparator()

        extract_eic_action = QAction("&Extract EIC...", self)
        extract_eic_action.setShortcut(QKeySequence("Ctrl+E"))
        extract_eic_action.triggered.connect(self._extract_eic_dialog)
        tools_menu.addAction(extract_eic_action)

        tools_menu.addSeparator()

        settings_action = QAction("&Settings...", self)
        settings_action.triggered.connect(self._show_settings)
        tools_menu.addAction(settings_action)

        # Help menu
        help_menu = menubar.addMenu("&Help")

        about_action = QAction("&About", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

    def _setup_toolbar(self):
        """Set up the toolbar."""
        toolbar = QToolBar("Main Toolbar")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        # Open
        open_action = QAction("Open", self)
        open_action.triggered.connect(self._open_file_dialog)
        toolbar.addAction(open_action)

        toolbar.addSeparator()

        # Process
        self.process_action = QAction("Process", self)
        self.process_action.triggered.connect(self._process_spectrum)
        self.process_action.setEnabled(False)
        toolbar.addAction(self.process_action)

        # Assign
        self.assign_action = QAction("Assign", self)
        self.assign_action.triggered.connect(self._assign_formulas)
        self.assign_action.setEnabled(False)
        toolbar.addAction(self.assign_action)

        # Calibrate
        self.calibrate_action = QAction("Calibrate", self)
        self.calibrate_action.triggered.connect(self._calibrate_spectrum)
        self.calibrate_action.setEnabled(False)
        toolbar.addAction(self.calibrate_action)

        toolbar.addSeparator()

        # Average selection
        self.average_action = QAction("Average Range", self)
        self.average_action.triggered.connect(self._average_selected_range)
        self.average_action.setEnabled(False)
        toolbar.addAction(self.average_action)

        # Average all (useful for DI-MS)
        self.average_all_toolbar_action = QAction("Average All", self)
        self.average_all_toolbar_action.triggered.connect(self._average_all_scans)
        self.average_all_toolbar_action.setEnabled(False)
        self.average_all_toolbar_action.setToolTip("Average all scans (useful for direct infusion)")
        toolbar.addAction(self.average_all_toolbar_action)

        toolbar.addSeparator()

        # Data type indicator
        self.data_type_label = QLabel("  ")
        self.data_type_label.setStyleSheet("font-weight: bold; color: #666;")
        toolbar.addWidget(self.data_type_label)

    def _setup_statusbar(self):
        """Set up the status bar."""
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        # File label
        self.file_label = QLabel("No file loaded")
        self.status_bar.addWidget(self.file_label)

        # Scan info label
        self.scan_label = QLabel("")
        self.status_bar.addWidget(self.scan_label)

        # Progress bar (hidden by default)
        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximumWidth(200)
        self.progress_bar.setVisible(False)
        self.status_bar.addPermanentWidget(self.progress_bar)

    def _connect_signals(self):
        """Connect data model and widget signals."""
        # Data model signals
        self.data_model.file_loaded.connect(self._on_file_loaded)
        self.data_model.file_closed.connect(self._on_file_closed)
        self.data_model.tic_data_changed.connect(self._on_tic_data_changed)
        self.data_model.spectrum_changed.connect(self._on_spectrum_changed)
        self.data_model.spectrum_processed.connect(self._on_spectrum_processed)
        self.data_model.processing_started.connect(self._on_processing_started)
        self.data_model.data_type_changed.connect(self._on_data_type_changed)
        self.data_model.processing_finished.connect(self._on_processing_finished)
        self.data_model.processing_error.connect(self._on_processing_error)
        self.data_model.eic_added.connect(self._on_eic_added)

        # Chromatogram signals
        self.chromatogram.scan_clicked.connect(self._load_spectrum_at_scan)
        self.chromatogram.range_selected.connect(self._on_range_selected)

        # Spectrum signals
        self.spectrum.eic_requested.connect(self._extract_eic)
        self.spectrum.assign_requested.connect(self._assign_single_peak)
        self.spectrum.peak_clicked.connect(self._on_peak_clicked)

        # Peak table signals
        self.peak_table.peak_selected.connect(self._on_peak_table_selected)
        self.peak_table.peak_selected.connect(self._on_peak_selected_for_candidates)
        self.peak_table.peak_double_clicked.connect(self._on_peak_table_double_clicked)
        self.peak_table.eic_requested.connect(self._extract_eic)
        self.peak_table.assign_requested.connect(self._assign_single_peak)

        # Candidate formulas signals
        self.candidate_formulas.isotopologues_requested.connect(self._on_isotopologues_requested)

        # EIC widget signals
        self.eic_widget.time_clicked.connect(self._on_eic_time_clicked)

        # Batch results widget signals
        self.batch_results.window_selected.connect(self._on_batch_window_selected)
        self.batch_results.window_double_clicked.connect(self._on_batch_window_double_clicked)

        # Batch results data model signal
        self.data_model.batch_results_changed.connect(self._on_batch_results_changed)

    def _restore_settings(self):
        """Restore window settings."""
        geometry = self.settings.value("geometry")
        if geometry:
            self.restoreGeometry(geometry)

        state = self.settings.value("windowState")
        if state:
            self.restoreState(state)

    def _save_settings(self):
        """Save window settings."""
        self.settings.setValue("geometry", self.saveGeometry())
        self.settings.setValue("windowState", self.saveState())

    def closeEvent(self, event):
        """Handle window close event."""
        self._save_settings()
        self.data_model.close_file()
        super().closeEvent(event)

    # ===== File Operations =====

    def _open_file_dialog(self):
        """Show file open dialog."""
        from hrms_viewer.core.file_handler import FileHandler

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Open Mass Spec File",
            "",
            FileHandler.get_supported_formats()
        )

        if file_path:
            self._open_file(file_path)

    def _open_file(self, file_path: str):
        """Open a file.

        Args:
            file_path: Path to the .RAW or .mzML file
        """
        if not os.path.exists(file_path):
            QMessageBox.warning(self, "Error", f"File not found: {file_path}")
            return

        # Close current file if any
        if self.data_model.is_file_loaded:
            self.data_model.close_file()

        # Show progress
        self.data_model.processing_started.emit("Loading file...")
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(True)

        # Load RAW file on main thread due to Mono/PyQt6 threading issues
        self._load_raw_file_sync(file_path)

    def _load_raw_file_sync(self, file_path: str):
        """Load a RAW file synchronously on the main thread.

        Required because Mono runtime doesn't work well with PyQt6 QThreads.
        """
        from PyQt6.QtWidgets import QApplication
        from hrms_viewer.core.file_handler import FileHandler

        try:
            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)

            self.status_bar.showMessage("Opening RAW file...")
            self.progress_bar.setValue(10)
            QApplication.processEvents()

            reader = FileHandler.open_file(file_path)

            self.status_bar.showMessage("Loading TIC...")
            self.progress_bar.setValue(30)
            QApplication.processEvents()

            tic_data = FileHandler.get_tic(reader, trace_type='TIC')

            self.status_bar.showMessage("Loading BPC...")
            self.progress_bar.setValue(50)
            QApplication.processEvents()

            try:
                bpc_data = FileHandler.get_tic(reader, trace_type='BPC')
            except:
                bpc_data = tic_data

            self.status_bar.showMessage("Loading scan info...")
            self.progress_bar.setValue(70)
            QApplication.processEvents()

            scan_df = FileHandler.get_scan_df(reader)

            self.progress_bar.setValue(100)
            QApplication.processEvents()

            self._on_file_load_finished(file_path, reader, tic_data, bpc_data, scan_df)

        except Exception as e:
            self._on_file_load_error(str(e))
        finally:
            QApplication.restoreOverrideCursor()

    def _on_file_load_finished(self, file_path, reader, tic_data, bpc_data, scan_df):
        """Handle file loading completion."""
        self.data_model.set_file_data(file_path, reader, tic_data, bpc_data, scan_df)
        self._add_to_recent_files(file_path)

        # Load first spectrum
        if tic_data and len(tic_data.scans) > 0:
            self._load_spectrum_at_scan(tic_data.scans[0])

    def _on_file_load_error(self, error_msg: str):
        """Handle file loading error."""
        self.data_model.processing_finished.emit()
        QMessageBox.critical(self, "Error Loading File", error_msg)

    def _on_load_progress(self, percent: int, message: str):
        """Handle loading progress update."""
        self.progress_bar.setValue(percent)
        self.status_bar.showMessage(message, 2000)

    def _close_file(self):
        """Close the current file."""
        self.data_model.close_file()

    def _add_to_recent_files(self, file_path: str):
        """Add file to recent files list."""
        recent = self.settings.value("recentFiles", [])
        if not isinstance(recent, list):
            recent = []

        if file_path in recent:
            recent.remove(file_path)
        recent.insert(0, file_path)
        recent = recent[:10]  # Keep only 10 recent files

        self.settings.setValue("recentFiles", recent)
        self._update_recent_files_menu()

    def _update_recent_files_menu(self):
        """Update the recent files menu."""
        self.recent_menu.clear()

        recent = self.settings.value("recentFiles", [])
        if not isinstance(recent, list):
            recent = []

        for file_path in recent:
            if os.path.exists(file_path):
                action = QAction(Path(file_path).name, self)
                action.setToolTip(file_path)
                action.triggered.connect(lambda checked, fp=file_path: self._open_file(fp))
                self.recent_menu.addAction(action)

        if not recent:
            action = QAction("No recent files", self)
            action.setEnabled(False)
            self.recent_menu.addAction(action)

    # ===== Data Model Event Handlers =====

    def _on_file_loaded(self, file_path: str):
        """Handle file loaded event."""
        self.file_label.setText(Path(file_path).name)
        self.process_action.setEnabled(True)
        self.calibrate_action.setEnabled(True)
        self.average_all_action.setEnabled(True)
        self.average_all_toolbar_action.setEnabled(True)
        self.batch_assign_action.setEnabled(True)
        self.data_model.processing_finished.emit()

    def _on_file_closed(self):
        """Handle file closed event."""
        self.file_label.setText("No file loaded")
        self.scan_label.setText("")
        self.data_type_label.setText("  ")
        self.chromatogram.clear()
        self.spectrum.clear()
        self.peak_table.clear()
        self.candidate_formulas.clear()
        self.candidate_formulas_dock.setVisible(False)
        self.eic_widget.clear_all()
        self.batch_results.clear()
        self.batch_results_dock.setVisible(False)
        self.process_action.setEnabled(False)
        self.assign_action.setEnabled(False)
        self.calibrate_action.setEnabled(False)
        self.average_action.setEnabled(False)
        self.average_all_action.setEnabled(False)
        self.average_all_toolbar_action.setEnabled(False)
        self.batch_assign_action.setEnabled(False)
        self.lc_ms_action.setChecked(False)
        self.di_ms_action.setChecked(False)

    def _on_tic_data_changed(self):
        """Handle TIC data change."""
        self.chromatogram.set_tic_data(self.data_model.tic_data)
        self.chromatogram.set_bpc_data(self.data_model.bpc_data)

    def _on_spectrum_changed(self, scan: int):
        """Handle spectrum change."""
        self.spectrum.set_spectrum(self.data_model.current_spectrum)

        # Update scan indicator in chromatogram
        self.chromatogram.set_current_scan(scan)

        # Re-enable calibration button for new spectrum
        self.calibrate_action.setEnabled(True)

        # Update status bar
        rt = self.data_model.get_retention_time(scan)
        if self.data_model.is_averaged:
            scan_range = self.data_model.averaged_scan_range
            self.scan_label.setText(f"Averaged: Scans {scan_range[0]}-{scan_range[1]}")
        elif rt is not None:
            self.scan_label.setText(f"Scan: {scan}  RT: {rt:.2f} min")
        else:
            self.scan_label.setText(f"Scan: {scan}")

    def _on_spectrum_processed(self):
        """Handle spectrum processed event."""
        print(f"Spectrum processed! Peaks: {len(self.data_model.current_spectrum.mspeaks) if hasattr(self.data_model.current_spectrum, 'mspeaks') else 0}")
        print(f"baseline_noise_std: {self.data_model.current_spectrum.baseline_noise_std}")
        self.spectrum.refresh_peaks()
        self.peak_table.set_peaks(self.data_model.current_spectrum)
        self.assign_action.setEnabled(True)

    def _on_processing_started(self, description: str):
        """Handle processing started."""
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(True)
        self.status_bar.showMessage(description)

    def _on_processing_finished(self):
        """Handle processing finished."""
        self.progress_bar.setVisible(False)
        self.status_bar.showMessage("Ready", 2000)

    def _on_processing_error(self, error_msg: str):
        """Handle processing error."""
        self.progress_bar.setVisible(False)
        QMessageBox.warning(self, "Processing Error", error_msg)

    def _on_data_type_changed(self, data_type: DataType):
        """Handle data type change.

        Args:
            data_type: The new data type (LC-MS or DI-MS)
        """
        # Update menu checkboxes
        self.lc_ms_action.setChecked(data_type == DataType.LC_MS)
        self.di_ms_action.setChecked(data_type == DataType.DI_MS)

        # Update toolbar label
        if data_type == DataType.LC_MS:
            self.data_type_label.setText("LC-MS")
            self.data_type_label.setStyleSheet("font-weight: bold; color: #2196F3;")
        elif data_type == DataType.DI_MS:
            self.data_type_label.setText("DI-MS")
            self.data_type_label.setStyleSheet("font-weight: bold; color: #4CAF50;")
        else:
            self.data_type_label.setText("  ")
            self.data_type_label.setStyleSheet("font-weight: bold; color: #666;")

        # Show info message for DI mode
        if data_type == DataType.DI_MS:
            self.status_bar.showMessage(
                "Direct infusion mode: Use 'Average All Scans' to combine all scans", 5000
            )

    def _set_data_type(self, data_type: DataType):
        """Manually set the data type.

        Args:
            data_type: The data type to set
        """
        if self.data_model.is_file_loaded:
            self.data_model.data_type = data_type

    def _average_all_scans(self):
        """Average all scans in the file.

        This is particularly useful for direct infusion data where all scans
        are essentially replicates of the same sample.
        """
        if not self.data_model.is_file_loaded:
            return

        tic_data = self.data_model.tic_data
        if tic_data is None or len(tic_data.scans) == 0:
            return

        # Get all scans
        all_scans = tic_data.scans
        start_scan = min(all_scans)
        end_scan = max(all_scans)

        # Show confirmation for large number of scans
        n_scans = len(all_scans)
        if n_scans > 100:
            reply = QMessageBox.question(
                self,
                "Average All Scans",
                f"This will average {n_scans} scans.\n\n"
                f"Scan range: {start_scan} to {end_scan}\n\n"
                "Continue?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

        # Use the existing average method
        self._average_scans(start_scan, end_scan)

    # ===== Spectrum Loading =====

    def _load_spectrum_at_scan(self, scan: int):
        """Load spectrum for a specific scan.

        Args:
            scan: Scan number
        """
        if not self.data_model.is_file_loaded:
            return

        self.data_model.processing_started.emit("Loading spectrum...")

        # Load on main thread due to Mono/PyQt6 threading issues
        self._load_spectrum_sync(scan)

    def _load_spectrum_sync(self, scan: int):
        """Load spectrum synchronously on main thread (for RAW files)."""
        import gc
        from PyQt6.QtWidgets import QApplication
        from PyQt6.QtCore import QCoreApplication
        from hrms_viewer.core.file_handler import FileHandler

        # Wait for any active workers to finish to avoid Mono runtime conflicts
        for worker in self._active_workers[:]:
            if worker.isRunning():
                worker.wait(100)  # Brief wait

        # Force garbage collection to help Mono runtime stabilize
        gc.collect()

        # Process pending events to ensure clean state
        QCoreApplication.processEvents()

        try:
            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
            spectrum = FileHandler.get_spectrum(self.data_model.reader, scan)
            self._on_spectrum_load_finished(scan, spectrum)
        except Exception as e:
            self.data_model.processing_error.emit(str(e))
        finally:
            QApplication.restoreOverrideCursor()

    def _on_spectrum_load_finished(self, scan: int, spectrum):
        """Handle spectrum loading completion."""
        self.data_model.set_spectrum(scan, spectrum)
        self.data_model.processing_finished.emit()

    def _on_range_selected(self, start_scan: int, end_scan: int):
        """Handle time range selection from chromatogram.

        Args:
            start_scan: First scan in range
            end_scan: Last scan in range
        """
        self.average_action.setEnabled(True)

        # Get time range for display
        start_time = self.data_model.get_retention_time(start_scan)
        end_time = self.data_model.get_retention_time(end_scan)
        n_scans = end_scan - start_scan + 1

        if start_time is not None and end_time is not None:
            time_str = f"{start_time:.2f} - {end_time:.2f} min"
        else:
            time_str = f"scans {start_scan} - {end_scan}"

        # Ask if user wants to average
        reply = QMessageBox.question(
            self,
            "Average Scans",
            f"Average {n_scans} scans?\n\nTime range: {time_str}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            self._average_scans(start_scan, end_scan)

    def _average_selected_range(self):
        """Average the currently selected range in chromatogram."""
        scan_range = self.chromatogram.get_selected_range()
        if scan_range:
            self._average_scans(scan_range[0], scan_range[1])

    def _average_scans(self, start_scan: int, end_scan: int):
        """Average spectra in a range.

        Args:
            start_scan: First scan
            end_scan: Last scan
        """
        if not self.data_model.is_file_loaded:
            return

        scan_list = list(range(start_scan, end_scan + 1))
        self.data_model.processing_started.emit(f"Averaging {len(scan_list)} scans...")

        # Process on main thread due to Mono/PyQt6 threading issues
        self._average_scans_sync(scan_list, start_scan, end_scan)

    def _average_scans_sync(self, scan_list, start_scan: int, end_scan: int):
        """Average scans synchronously on main thread (for RAW files)."""
        from PyQt6.QtWidgets import QApplication
        from hrms_viewer.core.file_handler import FileHandler

        try:
            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
            self.status_bar.showMessage(f"Averaging {len(scan_list)} scans...")
            QApplication.processEvents()

            spectrum = FileHandler.get_averaged_spectrum(
                self.data_model.reader,
                scan_list,
                mode='profile',
                auto_process=False
            )
            self._on_average_finished(start_scan, end_scan, spectrum)
        except Exception as e:
            self.data_model.processing_error.emit(str(e))
        finally:
            QApplication.restoreOverrideCursor()

    def _on_average_finished(self, start_scan: int, end_scan: int, spectrum):
        """Handle averaging completion."""
        self.data_model.set_spectrum(
            start_scan, spectrum,
            is_averaged=True,
            scan_range=(start_scan, end_scan)
        )
        self.data_model.processing_finished.emit()

    # ===== Processing =====

    def _process_spectrum(self):
        """Process the current spectrum (peak picking)."""
        if not self.data_model.has_spectrum:
            return

        self.data_model.processing_started.emit("Processing spectrum...")

        worker = SpectrumProcessWorker(
            self.data_model.current_spectrum,
            self.data_model.parameters
        )
        worker.finished.connect(self._on_process_finished)
        worker.error.connect(lambda e: self.data_model.processing_error.emit(e))
        worker.progress.connect(lambda p, m: self.progress_bar.setValue(p))

        self._active_workers.append(worker)
        worker.finished.connect(lambda: self._active_workers.remove(worker) if worker in self._active_workers else None)
        worker.start()

    def _on_process_finished(self, spectrum):
        """Handle processing completion."""
        self.data_model.set_spectrum_processed()
        self.data_model.processing_finished.emit()

        n_peaks = len(spectrum.mspeaks) if hasattr(spectrum, 'mspeaks') else 0
        self.status_bar.showMessage(f"Found {n_peaks} peaks", 3000)

    def _assign_formulas(self):
        """Assign molecular formulas to all peaks."""
        if not self.data_model.has_spectrum:
            return

        # Show parameter dialog for user-configurable options
        from hrms_viewer.dialogs.calibration_dialog import AssignmentParametersDialog
        params = AssignmentParametersDialog.get_assignment_params(self)
        if params is None:
            return  # User cancelled

        # Show output window if requested
        output_window = None
        if params.get('show_output', True):
            from hrms_viewer.dialogs.output_window import OutputWindow
            output_window = OutputWindow.get_instance(self)
            output_window.clear()
            output_window.append_header("Molecular Formula Assignment")
            output_window.show_and_raise()

        # Ensure Docker container is running
        from hrms_viewer.core.docker_utils import ensure_molformdb_running
        output_cb = output_window.append_text if output_window else None
        success, msg = ensure_molformdb_running(output_callback=output_cb)
        if not success:
            QMessageBox.warning(
                self, "Database Not Available",
                f"Could not start the molecular formula database:\n\n{msg}\n\n"
                "Please ensure Docker is running and try again."
            )
            self.data_model.processing_finished.emit()
            return

        if output_window:
            output_window.append_text("\n")
        self.data_model.processing_started.emit("Assigning molecular formulas...")

        # Run assignment synchronously on main thread to avoid Mono/.NET threading issues
        self._run_assignment_sync(params=params, output_window=output_window)

    def _run_assignment_sync(self, params: dict, output_window=None):
        """Run formula assignment synchronously on main thread.

        This avoids Mono/.NET threading issues that cause crashes when
        running CoreMS in a QThread.
        """
        from PyQt6.QtWidgets import QApplication
        from PyQt6.QtCore import QCoreApplication

        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)

        try:
            from corems.molecular_id.search.molecularFormulaSearch import SearchMolecularFormulas

            spectrum = self.data_model.current_spectrum
            db_url = "postgresql+psycopg2://coremsappdb:coremsapppnnl@localhost:5432/coremsapp"

            def log(msg):
                if output_window:
                    output_window.append_text(msg + "\n")
                    QCoreApplication.processEvents()

            log("Setting up formula search parameters...")

            # Set database URL
            spectrum.molecular_search_settings.url_database = db_url

            # Apply user-configurable parameters
            usedAtoms = params.get('usedAtoms') or {
                'C': (1, 40), 'H': (4, 80), 'O': (1, 12), 'N': (0, 2)
            }
            spectrum.molecular_search_settings.usedAtoms = usedAtoms
            spectrum.molecular_search_settings.min_dbe = params.get('min_dbe', 0)
            spectrum.molecular_search_settings.max_dbe = params.get('max_dbe', 16)
            spectrum.molecular_search_settings.isProtonated = params.get('isProtonated', True)
            spectrum.molecular_search_settings.isRadical = params.get('isRadical', False)
            spectrum.molecular_search_settings.isAdduct = params.get('isAdduct', False)
            spectrum.molecular_search_settings.max_hc_filter = params.get('max_hc_filter', 3.0)
            spectrum.molecular_search_settings.max_oc_filter = params.get('max_oc_filter', 1.2)
            spectrum.molecular_search_settings.min_ppm_error = params.get('min_ppm_error', -2.0)
            spectrum.molecular_search_settings.max_ppm_error = params.get('max_ppm_error', 4.0)

            # Set atom valences for all elements that might be used
            # This is required for the database search to work with additional elements
            # IMPORTANT: Must set BOTH spectrum settings AND global MSParameters
            # The MolecularLookupTable uses MSParameters.molecular_search.used_atom_valences
            atom_valences = {
                'C': 4, '13C': 4,
                'H': 1, 'D': 1,
                'O': 2, '17O': 2, '18O': 2,
                'N': 3, '15N': 3,
                'S': 2, '33S': 2, '34S': 2,
                'P': 3,
                'Fe': 3,  # Can be 2 or 3
                'Cu': 2,  # Can be 1 or 2
                'Na': 1,
                'K': 1,
                'Cl': 1, '37Cl': 1,
                'Br': 1, '81Br': 1,
                'I': 1,
            }
            spectrum.molecular_search_settings.used_atom_valences = atom_valences

            # Also set on the global MSParameters (used by MolecularLookupTable)
            from corems.encapsulation.factory.parameters import MSParameters as CoreMSParams
            CoreMSParams.molecular_search.used_atom_valences = atom_valences

            # Set output_score_method to All Candidates to get all formula candidates
            spectrum.molecular_search_settings.output_score_method = "All Candidates"

            log(f"Database: {db_url}")
            log(f"usedAtoms: {usedAtoms}")
            log(f"DBE range: {params.get('min_dbe', 0)} - {params.get('max_dbe', 16)}")
            log(f"PPM error range: {params.get('min_ppm_error', -2.0)} to {params.get('max_ppm_error', 4.0)}")
            log(f"Output score method: All Candidates (returning all formula candidates)")

            # Process spectrum if needed
            if not hasattr(spectrum, 'mspeaks') or len(spectrum.mspeaks) == 0:
                log("Processing spectrum for peak picking...")
                spectrum.process_mass_spec()
                log(f"Found {len(spectrum.mspeaks)} peaks")

            QCoreApplication.processEvents()

            # Run formula search
            log("\nRunning molecular formula search...")
            find_isotopologues = params.get('find_isotopologues', True)

            with SearchMolecularFormulas(spectrum, find_isotopologues=find_isotopologues) as search:
                search.run_worker_mass_spectrum()

            QCoreApplication.processEvents()

            # Count assignments
            assigned_peaks = [p for p in spectrum.mspeaks if len(p.molecular_formulas) > 0]
            log(f"\nAssigned {len(assigned_peaks)}/{len(spectrum.mspeaks)} peaks")

            # Call the finished handler
            self._on_assign_finished(spectrum, assigned_peaks)

        except Exception as e:
            import traceback
            error_msg = f"Assignment error: {str(e)}\n{traceback.format_exc()}"
            if output_window:
                output_window.append_text(f"\nERROR: {error_msg}")
            self.data_model.processing_error.emit(str(e))

        finally:
            QApplication.restoreOverrideCursor()

    def _on_assign_finished(self, spectrum, assigned_peaks):
        """Handle formula assignment completion."""
        import gc

        self.data_model.set_spectrum_processed()
        self.data_model.processing_finished.emit()

        # Force garbage collection to clean up after worker
        gc.collect()

        n_assigned = len(assigned_peaks)
        n_total = len(spectrum.mspeaks) if hasattr(spectrum, 'mspeaks') else 0
        self.status_bar.showMessage(f"Assigned {n_assigned}/{n_total} peaks", 3000)

    def _assign_single_peak(self, peak_index: int):
        """Assign formula to a single peak.

        Args:
            peak_index: Index of the peak to assign
        """
        if not self.data_model.has_peaks:
            return

        # For now, just run full assignment
        # In a more advanced version, this could be optimized to search only one peak
        self._assign_formulas()

    # ===== EIC =====

    def _extract_eic_dialog(self):
        """Show dialog to extract EIC."""
        if not self.data_model.is_file_loaded:
            return

        result = EICDialog.get_eic_params(parent=self)
        if result:
            mz, ppm, color = result
            self._extract_eic_with_params(mz, ppm, color)

    def _extract_eic(self, mz: float):
        """Extract EIC for a target m/z with default settings.

        Args:
            mz: Target m/z value
        """
        # Generate a color
        colors = ['#E91E63', '#9C27B0', '#673AB7', '#3F51B5', '#00BCD4', '#009688', '#FF9800', '#FF5722']
        color = colors[len(self.data_model.eics) % len(colors)]
        self._extract_eic_with_params(mz, 5.0, color)

    def _extract_eic_with_params(self, mz: float, ppm: float, color: str):
        """Extract EIC with specified parameters.

        Args:
            mz: Target m/z value
            ppm: Tolerance in ppm
            color: Hex color string
        """
        if not self.data_model.is_file_loaded:
            return

        self.data_model.processing_started.emit(f"Extracting EIC at m/z {mz:.4f}...")

        # Store color for later use
        self._pending_eic_color = color

        worker = EICExtractionWorker(
            self.data_model.reader,
            mz,
            self.data_model.tic_data,
            ppm_tolerance=ppm
        )
        worker.finished.connect(self._on_eic_extracted)
        worker.error.connect(lambda e: self.data_model.processing_error.emit(e))

        self._active_workers.append(worker)
        worker.finished.connect(lambda: self._active_workers.remove(worker) if worker in self._active_workers else None)
        worker.start()

    def _on_eic_extracted(self, mz: float, eic_data):
        """Handle EIC extraction completion."""
        color = getattr(self, '_pending_eic_color', '#E91E63')
        self.data_model.add_eic(mz, eic_data, color)
        self.data_model.processing_finished.emit()

        self.status_bar.showMessage(f"Extracted EIC at m/z {mz:.4f}", 3000)

    def _on_eic_added(self, mz: float):
        """Handle EIC added to data model."""
        eic_data = self.data_model.eics.get(mz)
        color = self.data_model.eic_colors.get(mz, '#E91E63')

        if eic_data:
            self.eic_widget.add_eic(mz, eic_data, color)
            self.eic_dock.setVisible(True)

    def _on_eic_time_clicked(self, time: float):
        """Handle click on EIC at a time point."""
        scan = self.data_model.get_scan_from_time(time)
        if scan:
            self._load_spectrum_at_scan(scan)

    # ===== Peak Table Handlers =====

    def _on_peak_clicked(self, peak_index: int):
        """Handle peak click in spectrum widget."""
        self.peak_table.select_peak(peak_index)

    def _on_peak_table_selected(self, peak_index: int):
        """Handle peak selection in peak table."""
        self.spectrum.highlight_peak(peak_index)

    def _on_peak_selected_for_candidates(self, peak_index: int):
        """Handle peak selection to update candidate formulas widget."""
        if not self.data_model.has_spectrum:
            return

        spectrum = self.data_model.current_spectrum
        if hasattr(spectrum, 'mspeaks') and peak_index < len(spectrum.mspeaks):
            peak = spectrum.mspeaks[peak_index]
            self.candidate_formulas.set_peak(peak)

            # Show dock only if peak has molecular formula assignments
            if hasattr(peak, 'molecular_formulas') and len(peak.molecular_formulas) > 0:
                self.candidate_formulas_dock.setVisible(True)
            else:
                self.candidate_formulas_dock.setVisible(False)

    def _on_isotopologues_requested(self, base_mz: float, isotopologues: list):
        """Handle request to show isotopologues on spectrum.

        Args:
            base_mz: The m/z of the monoisotopic peak
            isotopologues: List of (name, mass_shift, rel_intensity) tuples
        """
        print(f"[DEBUG] MainWindow._on_isotopologues_requested: base_mz={base_mz}, {len(isotopologues)} isotopologues")
        self.spectrum.show_isotope_markers(base_mz, isotopologues, show_intensities=True)

    def _on_peak_table_double_clicked(self, peak_index: int):
        """Handle double-click on peak in table."""
        self.spectrum.zoom_to_peak(peak_index)

    # ===== View =====

    def _reset_view(self):
        """Reset all plot views to auto-range."""
        self.chromatogram.plot_widget.autoRange()
        self.spectrum.plot_widget.autoRange()

    def _show_settings(self):
        """Show settings dialog."""
        result = SettingsDialog.edit_parameters(self.data_model.parameters, parent=self)
        if result:
            self.data_model.parameters = result
            self.status_bar.showMessage("Settings updated", 2000)

    def _show_about(self):
        """Show about dialog."""
        QMessageBox.about(
            self,
            "About HRMS Viewer",
            "HRMS Viewer v0.1.0\n\n"
            "A PyQt6 application for viewing HRMS data using CoreMS.\n\n"
            "Built with:\n"
            "- PyQt6\n"
            "- PyQtGraph\n"
            "- CoreMS"
        )

    # ===== Calibration =====

    def _calibrate_spectrum(self):
        """Run mass calibration on the current spectrum."""
        if not self.data_model.has_spectrum:
            QMessageBox.warning(
                self, "No Spectrum",
                "Please load a spectrum first.\n\n"
                "Calibration works best on averaged spectra."
            )
            return

        # Check if this is an averaged spectrum (recommended)
        if not self.data_model.is_averaged:
            reply = QMessageBox.question(
                self,
                "Single Scan Spectrum",
                "Calibration typically works better on averaged spectra.\n\n"
                "Do you want to continue with this single scan?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

        # Show parameters dialog
        from hrms_viewer.dialogs.calibration_dialog import CalibrationParametersDialog
        params = CalibrationParametersDialog.get_calibration_params(parent=self)

        if params is None:
            return

        # Show output window if requested
        output_window = None
        if params.get('show_output', True):
            from hrms_viewer.dialogs.output_window import OutputWindow
            output_window = OutputWindow.get_instance(self)
            output_window.clear()
            output_window.append_header("Mass Calibration")
            output_window.show_and_raise()

        # Ensure Docker container is running
        from hrms_viewer.core.docker_utils import ensure_molformdb_running
        callback = output_window.append_text if output_window else None
        success, msg = ensure_molformdb_running(output_callback=callback)
        if not success:
            QMessageBox.warning(
                self, "Database Not Available",
                f"Could not start the molecular formula database:\n\n{msg}\n\n"
                "Please ensure Docker is running and try again."
            )
            self.data_model.processing_finished.emit()
            return

        if output_window:
            output_window.append_text("\n")

        self.data_model.processing_started.emit("Running calibration...")

        # Run calibration synchronously on main thread to avoid Mono/.NET threading issues
        self._run_calibration_sync(
            params=params,
            output_window=output_window
        )

    def _run_calibration_sync(self, params: dict, output_window=None):
        """Run calibration synchronously on main thread.

        This avoids Mono/.NET threading issues that cause crashes when
        running CoreMS in a QThread.
        """
        import sys
        from PyQt6.QtWidgets import QApplication
        from PyQt6.QtCore import QCoreApplication

        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)

        try:
            from corems.molecular_id.search.molecularFormulaSearch import SearchMolecularFormulas
            from hrms_viewer.core.calibration import run_calibration, apply_calibration_to_spectrum
            from corems.encapsulation.factory.parameters import MSParameters as CoreMSParams

            spectrum = self.data_model.current_spectrum
            db_url = "postgresql+psycopg2://coremsappdb:coremsapppnnl@localhost:5432/coremsapp"

            def log(msg):
                if output_window:
                    output_window.append_text(msg + "\n")
                    QCoreApplication.processEvents()

            log("Setting up calibration parameters...")

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
            spectrum.molecular_search_settings.url_database = db_url
            log(f"Database: {db_url}")

            # Fixed molecular formula search criteria
            spectrum.molecular_search_settings.min_dbe = 0
            spectrum.molecular_search_settings.max_dbe = 16
            spectrum.molecular_search_settings.usedAtoms = {
                'C': (1, 40),
                'H': (4, 80),
                'O': (1, 12),
                'N': (0, 2),
            }
            spectrum.molecular_search_settings.isProtonated = True
            spectrum.molecular_search_settings.isRadical = False
            spectrum.molecular_search_settings.isAdduct = False
            spectrum.molecular_search_settings.max_oc_filter = 1.2
            spectrum.molecular_search_settings.max_hc_filter = 3
            spectrum.molecular_search_settings.used_atom_valences = {
                'C': 4, '13C': 4, 'H': 1, 'O': 2, 'N': 3
            }
            spectrum.molecular_search_settings.min_ppm_error = params['min_ppm_error']
            spectrum.molecular_search_settings.max_ppm_error = params['max_ppm_error']

            log(f"\nMolecular Formula Search Criteria (Fixed):")
            log(f"  usedAtoms: C(1-40), H(4-80), O(1-12), N(0-2)")
            log(f"  DBE: 0-16")
            log(f"  Ion type: [M+H]+ / [M-H]-")
            log(f"  m/z range: 200-900")
            log(f"  Filters: H/C <= 3, O/C <= 1.2")
            log(f"\nUser-configurable:")
            log(f"  m/z error range: {params['min_ppm_error']:.2f} to {params['max_ppm_error']:.2f} ppm")

            # Step 1: Process spectrum (peak picking)
            log("\n" + "=" * 50)
            log("STEP 1: Peak Picking")
            log("=" * 50)

            if not hasattr(spectrum, 'mspeaks') or len(spectrum.mspeaks) == 0:
                log("Processing spectrum for peak picking...")
                spectrum.process_mass_spec()
                log(f"Found {len(spectrum.mspeaks)} peaks")
            else:
                log(f"Spectrum already processed: {len(spectrum.mspeaks)} peaks")

            QCoreApplication.processEvents()

            # Iterative calibration: assign -> calibrate -> apply -> re-assign until convergence
            max_calibration_iterations = 5
            calibration_result = None
            prev_n_assigned = 0

            for cal_iter in range(max_calibration_iterations):
                # Step 2: Assign molecular formulas
                log("\n" + "=" * 50)
                log(f"ITERATION {cal_iter + 1}: Molecular Formula Assignment")
                log("=" * 50)

                # Clear previous assignments before re-assigning
                if cal_iter > 0:
                    for peak in spectrum.mspeaks:
                        peak.molecular_formulas = []

                log("Running molecular formula search...")
                QCoreApplication.processEvents()

                with SearchMolecularFormulas(spectrum, find_isotopologues=True) as search:
                    search.run_worker_mass_spectrum()

                QCoreApplication.processEvents()

                # Count assignments
                assigned = [p for p in spectrum.mspeaks if len(p.molecular_formulas) > 0]
                n_assigned = len(assigned)
                log(f"\nAssigned {n_assigned}/{len(spectrum.mspeaks)} peaks")

                # Check for convergence
                if cal_iter > 0 and n_assigned == prev_n_assigned:
                    log(f"\nConverged: same number of assignments as previous iteration")
                    break

                prev_n_assigned = n_assigned

                # Step 3: Run calibration
                log("\n" + "=" * 50)
                log(f"ITERATION {cal_iter + 1}: Calibration Fitting")
                log("=" * 50)

                QCoreApplication.processEvents()

                calibration_result = run_calibration(
                    spectrum,
                    degree=params['degree'],
                    min_confidence=params['min_confidence'],
                    min_sn=params['min_sn'],
                    target_std=params['target_std']
                )

                if calibration_result is None or calibration_result.n_peaks == 0:
                    log("Not enough calibration points. Stopping.")
                    break

                log(f"\nCalibration result:")
                log(f"  Points used: {calibration_result.n_peaks}")
                log(f"  Final std: {calibration_result.final_std:.4f} ppm")
                log(f"  Iterations: {calibration_result.iterations}")

                # Check if all calibrant peaks are within prediction window
                all_within = all(is_used for _, _, _, _, is_used in calibration_result.all_assigned)
                if all_within:
                    log(f"\nAll {len(calibration_result.all_assigned)} calibrant peaks are within prediction window")
                    # Apply final calibration
                    if params['apply_correction']:
                        apply_calibration_to_spectrum(spectrum, calibration_result)
                        log("Final calibration applied")
                    break

                # Apply calibration to enable re-assignment with updated m/z values
                log("\nApplying calibration for next iteration...")
                apply_calibration_to_spectrum(spectrum, calibration_result)
                QCoreApplication.processEvents()

            else:
                # Reached max iterations
                log(f"\nReached maximum iterations ({max_calibration_iterations})")

            if calibration_result is None:
                raise ValueError("Calibration failed - not enough assigned peaks")

            # Set the outer calibration iteration count
            calibration_result.calibration_iterations = cal_iter + 1

            log("\n" + "=" * 50)
            log("CALIBRATION COMPLETE")
            log(f"Total calibration iterations: {calibration_result.calibration_iterations}")
            log("=" * 50)

            # Clear calibration assignments from peaks - assignments should only come from
            # the separate assignment step, not from calibration
            log("\nClearing calibration assignments from peaks...")
            for peak in spectrum.mspeaks:
                peak.molecular_formulas = []

            QCoreApplication.processEvents()

            # Call the finished handler
            self._on_calibration_finished(spectrum, calibration_result)

        except Exception as e:
            import traceback
            error_msg = f"Calibration error: {str(e)}\n{traceback.format_exc()}"
            if output_window:
                output_window.append_text(f"\nERROR: {error_msg}")
            self._on_calibration_error(str(e))

        finally:
            QApplication.restoreOverrideCursor()

    def _on_calibration_finished(self, spectrum, calibration_result):
        """Handle calibration completion."""
        import gc

        self.data_model.processing_finished.emit()

        # Force garbage collection to help Mono runtime stabilize
        gc.collect()

        # Show calibration results dialog
        from hrms_viewer.dialogs.calibration_dialog import CalibrationDialog
        dialog = CalibrationDialog(calibration_result, parent=self)
        dialog.calibration_accepted.connect(self._on_calibration_accepted)
        dialog.exec()

        # Cleanup after dialog closes (whether accepted or rejected)
        gc.collect()

    def _on_calibration_accepted(self, calibration_result):
        """Handle calibration acceptance."""
        import gc

        # Store calibration result for reuse in batch processing
        self.data_model.calibration_result = calibration_result

        # Update spectrum and table
        self.data_model.set_spectrum_processed()
        self.spectrum.refresh_peaks()
        self.peak_table.set_peaks(self.data_model.current_spectrum)

        # Disable calibration button - spectrum is now calibrated
        self.calibrate_action.setEnabled(False)

        # Force garbage collection to clean up Mono runtime state
        gc.collect()

        self.status_bar.showMessage(
            f"Calibration applied: {calibration_result.n_peaks} points, "
            f"std={calibration_result.final_std:.3f} ppm",
            5000
        )

    def _on_calibration_error(self, error_msg: str):
        """Handle calibration error."""
        self.data_model.processing_finished.emit()
        QMessageBox.warning(self, "Calibration Error", error_msg)

    # ===== Batch Assignment =====

    def _batch_assign_formulas(self):
        """Show batch time-window assignment dialog and run batch processing."""
        if not self.data_model.is_file_loaded:
            return

        time_range = self.data_model.time_range
        if time_range is None:
            QMessageBox.warning(self, "No Data", "No time range available in loaded file.")
            return

        # Show the batch assignment dialog
        has_calibration = self.data_model.has_calibration
        dialog = BatchAssignmentDialog(time_range, has_calibration=has_calibration, parent=self)
        dialog.start_processing.connect(self._run_batch_assignment)

        if dialog.exec():
            # Dialog was accepted (processing completed successfully)
            pass

    def _run_batch_assignment(self, start_time: float, end_time: float,
                               window_size: float, params: dict):
        """Run batch assignment across time windows.

        Args:
            start_time: Start retention time (min)
            end_time: End retention time (min)
            window_size: Size of each window (min)
            params: Assignment parameters dict
        """
        from PyQt6.QtWidgets import QApplication
        from PyQt6.QtCore import QCoreApplication

        # Get the dialog that triggered this
        dialog = self.sender()
        if not isinstance(dialog, BatchAssignmentDialog):
            return

        # Clear previous batch results
        self.data_model.clear_batch_results()
        results = []

        # Calculate windows
        current_start = start_time
        window_index = 0
        total_windows = max(1, int((end_time - start_time) / window_size))

        # Ensure Docker container is running
        from hrms_viewer.core.docker_utils import ensure_molformdb_running
        success, msg = ensure_molformdb_running()
        if not success:
            QMessageBox.warning(
                self, "Database Not Available",
                f"Could not start the molecular formula database:\n\n{msg}\n\n"
                "Please ensure Docker is running and try again."
            )
            dialog.processing_complete(success=False)
            return

        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)

        try:
            while current_start < end_time:
                window_index += 1
                current_end = min(current_start + window_size, end_time)

                # Check for cancellation
                if dialog.is_cancelled():
                    break

                # Update progress
                dialog.update_progress(
                    window_index, total_windows,
                    f"Processing window {window_index}/{total_windows} "
                    f"({current_start:.1f}-{current_end:.1f} min)"
                )
                QApplication.processEvents()

                # Process this window
                result = self._process_batch_window(
                    window_index, current_start, current_end, params
                )

                if result is not None:
                    results.append(result)
                    self.data_model.add_batch_result(result)

                current_start = current_end

            # Set all results
            self.data_model.set_batch_results(results)

            # Show batch results dock
            self.batch_results_dock.setVisible(True)

            dialog.processing_complete(success=True)

        except Exception as e:
            import traceback
            error_msg = f"Batch assignment error: {str(e)}\n{traceback.format_exc()}"
            print(error_msg)
            QMessageBox.warning(self, "Batch Assignment Error", str(e))
            dialog.processing_complete(success=False)

        finally:
            QApplication.restoreOverrideCursor()

    def _process_batch_window(self, window_index: int, start_time: float,
                               end_time: float, params: dict) -> Optional[TimeWindowResult]:
        """Process a single time window.

        Args:
            window_index: 1-based window number
            start_time: Window start time (min)
            end_time: Window end time (min)
            params: Assignment parameters

        Returns:
            TimeWindowResult or None if failed
        """
        from PyQt6.QtCore import QCoreApplication
        from corems.molecular_id.search.molecularFormulaSearch import SearchMolecularFormulas
        from hrms_viewer.core.file_handler import FileHandler

        try:
            # Get scans in this time range
            scans = self.data_model.get_scans_in_range(start_time, end_time)
            if not scans:
                return None

            start_scan = min(scans)
            end_scan = max(scans)

            # Average the scans
            spectrum = FileHandler.get_averaged_spectrum(
                self.data_model.reader,
                scans,
                mode='profile',
                auto_process=False
            )

            # Configure spectrum settings
            db_url = "postgresql+psycopg2://coremsappdb:coremsapppnnl@localhost:5432/coremsapp"
            spectrum.molecular_search_settings.url_database = db_url

            usedAtoms = params.get('usedAtoms') or {
                'C': (1, 40), 'H': (4, 80), 'O': (1, 12), 'N': (0, 2)
            }
            spectrum.molecular_search_settings.usedAtoms = usedAtoms
            spectrum.molecular_search_settings.min_dbe = params.get('min_dbe', 0)
            spectrum.molecular_search_settings.max_dbe = params.get('max_dbe', 16)
            spectrum.molecular_search_settings.isProtonated = params.get('isProtonated', True)
            spectrum.molecular_search_settings.isRadical = params.get('isRadical', False)
            spectrum.molecular_search_settings.isAdduct = params.get('isAdduct', False)
            spectrum.molecular_search_settings.max_hc_filter = params.get('max_hc_filter', 3.0)
            spectrum.molecular_search_settings.max_oc_filter = params.get('max_oc_filter', 1.2)
            spectrum.molecular_search_settings.min_ppm_error = params.get('min_ppm_error', -2.0)
            spectrum.molecular_search_settings.max_ppm_error = params.get('max_ppm_error', 4.0)

            # Set atom valences
            atom_valences = {
                'C': 4, '13C': 4, 'H': 1, 'D': 1,
                'O': 2, '17O': 2, '18O': 2, 'N': 3, '15N': 3,
                'S': 2, '33S': 2, '34S': 2, 'P': 3,
                'Fe': 3, 'Cu': 2, 'Na': 1, 'K': 1,
                'Cl': 1, '37Cl': 1, 'Br': 1, '81Br': 1, 'I': 1,
            }
            spectrum.molecular_search_settings.used_atom_valences = atom_valences
            from corems.encapsulation.factory.parameters import MSParameters as CoreMSParams
            CoreMSParams.molecular_search.used_atom_valences = atom_valences

            spectrum.molecular_search_settings.output_score_method = "All Candidates"

            # Process spectrum for peak picking
            spectrum.process_mass_spec()
            n_peaks = len(spectrum.mspeaks) if hasattr(spectrum, 'mspeaks') else 0

            # Apply calibration if available
            if self.data_model.has_calibration:
                from hrms_viewer.core.calibration import apply_calibration_to_spectrum
                apply_calibration_to_spectrum(spectrum, self.data_model.calibration_result)

            QCoreApplication.processEvents()

            # Run formula search
            find_isotopologues = params.get('find_isotopologues', True)
            with SearchMolecularFormulas(spectrum, find_isotopologues=find_isotopologues) as search:
                search.run_worker_mass_spectrum()

            QCoreApplication.processEvents()

            # Count assignments and collect unique formulas
            assigned_peaks = [p for p in spectrum.mspeaks if p.is_assigned]
            n_assigned = len(assigned_peaks)

            # Get unique formulas (top formula from each assigned peak)
            unique_formulas = set()
            for peak in assigned_peaks:
                if peak.best_molecular_formula_candidate:
                    unique_formulas.add(peak.best_molecular_formula_candidate.string)

            # Create result
            result = TimeWindowResult(
                window_index=window_index,
                start_time=start_time,
                end_time=end_time,
                start_scan=start_scan,
                end_scan=end_scan,
                n_scans=len(scans),
                spectrum=spectrum,
                n_peaks=n_peaks,
                n_assigned=n_assigned,
                formulas=sorted(list(unique_formulas))
            )

            return result

        except Exception as e:
            print(f"Error processing window {window_index}: {e}")
            return None

    def _on_batch_window_selected(self, row: int):
        """Handle batch window selection - load that spectrum.

        Args:
            row: Row index in batch results table
        """
        result = self.data_model.get_batch_result(row)
        if result is None or result.spectrum is None:
            return

        # Set the spectrum in the data model
        self.data_model.set_spectrum(
            result.start_scan,
            result.spectrum,
            is_averaged=True,
            scan_range=(result.start_scan, result.end_scan)
        )

        # Update displays
        self.spectrum.set_spectrum(result.spectrum)
        self.spectrum.refresh_peaks()
        self.peak_table.set_peaks(result.spectrum)

        # Update status bar
        self.scan_label.setText(
            f"Batch Window {result.window_index}: "
            f"{result.start_time:.1f}-{result.end_time:.1f} min "
            f"({result.n_assigned}/{result.n_peaks} assigned)"
        )

    def _on_batch_window_double_clicked(self, row: int):
        """Handle batch window double-click - load spectrum and zoom to first assigned peak.

        Args:
            row: Row index in batch results table
        """
        # First load the spectrum
        self._on_batch_window_selected(row)

        # Then zoom to first assigned peak if any
        result = self.data_model.get_batch_result(row)
        if result is None or result.spectrum is None:
            return

        if hasattr(result.spectrum, 'mspeaks'):
            for peak in result.spectrum.mspeaks:
                if peak.is_assigned:
                    self.spectrum.zoom_to_peak(peak.mz_exp)
                    break

    def _on_batch_results_changed(self):
        """Handle batch results change - update the batch results widget."""
        results = self.data_model.batch_results
        self.batch_results.set_results(results)
