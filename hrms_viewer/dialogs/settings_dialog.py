"""Settings dialog for CoreMS parameters."""

from typing import Optional
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QWidget,
    QFormLayout, QDoubleSpinBox, QSpinBox, QCheckBox,
    QGroupBox, QPushButton, QLabel, QLineEdit
)
from PyQt6.QtCore import Qt

from corems.encapsulation.factory.parameters import MSParameters


class SettingsDialog(QDialog):
    """Dialog for editing CoreMS processing parameters.

    Organized into tabs for different parameter categories.
    """

    def __init__(self, parameters: Optional[MSParameters] = None, parent=None):
        super().__init__(parent)

        self.setWindowTitle("Processing Settings")
        self.setMinimumSize(500, 600)

        # Use provided parameters or create new
        self._parameters = parameters if parameters else MSParameters()

        self._setup_ui()
        self._load_parameters()

    def _setup_ui(self):
        """Set up the dialog UI."""
        layout = QVBoxLayout(self)

        # Tab widget
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)

        # Create tabs
        self._create_mass_spectrum_tab()
        self._create_peak_picking_tab()
        self._create_molecular_search_tab()

        # Buttons
        btn_layout = QHBoxLayout()

        reset_btn = QPushButton("Reset to Defaults")
        reset_btn.clicked.connect(self._reset_defaults)
        btn_layout.addWidget(reset_btn)

        btn_layout.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        apply_btn = QPushButton("Apply")
        apply_btn.setDefault(True)
        apply_btn.clicked.connect(self.accept)
        btn_layout.addWidget(apply_btn)

        layout.addLayout(btn_layout)

    def _create_mass_spectrum_tab(self):
        """Create mass spectrum settings tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # Noise threshold group
        noise_group = QGroupBox("Noise Threshold")
        noise_layout = QFormLayout(noise_group)

        self.noise_threshold_spin = QDoubleSpinBox()
        self.noise_threshold_spin.setRange(1.0, 100.0)
        self.noise_threshold_spin.setDecimals(1)
        self.noise_threshold_spin.setSuffix(" sigma")
        noise_layout.addRow("Log N-sigma:", self.noise_threshold_spin)

        layout.addWidget(noise_group)

        # m/z range group
        mz_group = QGroupBox("m/z Range")
        mz_layout = QFormLayout(mz_group)

        self.min_mz_spin = QDoubleSpinBox()
        self.min_mz_spin.setRange(0.0, 10000.0)
        self.min_mz_spin.setDecimals(2)
        mz_layout.addRow("Minimum m/z:", self.min_mz_spin)

        self.max_mz_spin = QDoubleSpinBox()
        self.max_mz_spin.setRange(0.0, 10000.0)
        self.max_mz_spin.setDecimals(2)
        mz_layout.addRow("Maximum m/z:", self.max_mz_spin)

        layout.addWidget(mz_group)

        # Calibration group
        calib_group = QGroupBox("Calibration")
        calib_layout = QFormLayout(calib_group)

        self.min_calib_ppm_spin = QDoubleSpinBox()
        self.min_calib_ppm_spin.setRange(-10.0, 10.0)
        self.min_calib_ppm_spin.setDecimals(2)
        self.min_calib_ppm_spin.setSuffix(" ppm")
        calib_layout.addRow("Min Error:", self.min_calib_ppm_spin)

        self.max_calib_ppm_spin = QDoubleSpinBox()
        self.max_calib_ppm_spin.setRange(-10.0, 10.0)
        self.max_calib_ppm_spin.setDecimals(2)
        self.max_calib_ppm_spin.setSuffix(" ppm")
        calib_layout.addRow("Max Error:", self.max_calib_ppm_spin)

        self.calib_order_spin = QSpinBox()
        self.calib_order_spin.setRange(1, 5)
        calib_layout.addRow("Polynomial Order:", self.calib_order_spin)

        layout.addWidget(calib_group)

        layout.addStretch()
        self.tabs.addTab(tab, "Mass Spectrum")

    def _create_peak_picking_tab(self):
        """Create peak picking settings tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # Peak detection group
        peak_group = QGroupBox("Peak Detection")
        peak_layout = QFormLayout(peak_group)

        self.prominence_spin = QDoubleSpinBox()
        self.prominence_spin.setRange(0.001, 1.0)
        self.prominence_spin.setDecimals(3)
        self.prominence_spin.setSuffix(" %")
        peak_layout.addRow("Min Prominence:", self.prominence_spin)

        layout.addWidget(peak_group)

        layout.addStretch()
        self.tabs.addTab(tab, "Peak Picking")

    def _create_molecular_search_tab(self):
        """Create molecular formula search settings tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # Error tolerance group
        error_group = QGroupBox("Error Tolerance")
        error_layout = QFormLayout(error_group)

        self.min_ppm_spin = QDoubleSpinBox()
        self.min_ppm_spin.setRange(-10.0, 0.0)
        self.min_ppm_spin.setDecimals(2)
        self.min_ppm_spin.setSuffix(" ppm")
        error_layout.addRow("Min ppm Error:", self.min_ppm_spin)

        self.max_ppm_spin = QDoubleSpinBox()
        self.max_ppm_spin.setRange(0.0, 10.0)
        self.max_ppm_spin.setDecimals(2)
        self.max_ppm_spin.setSuffix(" ppm")
        error_layout.addRow("Max ppm Error:", self.max_ppm_spin)

        layout.addWidget(error_group)

        # Database group
        db_group = QGroupBox("Database")
        db_layout = QFormLayout(db_group)

        self.db_url_edit = QLineEdit()
        self.db_url_edit.setPlaceholderText("postgresql+psycopg2://...")
        db_layout.addRow("Database URL:", self.db_url_edit)

        self.db_chunk_spin = QSpinBox()
        self.db_chunk_spin.setRange(100, 10000)
        db_layout.addRow("Chunk Size:", self.db_chunk_spin)

        layout.addWidget(db_group)

        # Score method group
        score_group = QGroupBox("Scoring")
        score_layout = QFormLayout(score_group)

        self.isotopologue_check = QCheckBox("Find Isotopologues")
        score_layout.addRow("", self.isotopologue_check)

        layout.addWidget(score_group)

        layout.addStretch()
        self.tabs.addTab(tab, "Formula Search")

    def _load_parameters(self):
        """Load current parameter values into UI."""
        ms = self._parameters.mass_spectrum
        peak = self._parameters.ms_peak
        search = self._parameters.molecular_search

        # Mass spectrum tab
        self.noise_threshold_spin.setValue(ms.noise_threshold_log_nsigma)
        self.min_mz_spin.setValue(ms.min_picking_mz)
        self.max_mz_spin.setValue(ms.max_picking_mz)
        self.min_calib_ppm_spin.setValue(ms.min_calib_ppm_error)
        self.max_calib_ppm_spin.setValue(ms.max_calib_ppm_error)
        self.calib_order_spin.setValue(ms.calib_pol_order)

        # Peak picking tab
        self.prominence_spin.setValue(peak.peak_min_prominence_percent)

        # Molecular search tab
        self.min_ppm_spin.setValue(search.min_ppm_error)
        self.max_ppm_spin.setValue(search.max_ppm_error)
        self.db_url_edit.setText(search.url_database or "")
        self.db_chunk_spin.setValue(search.db_chunk_size)

    def _save_parameters(self):
        """Save UI values to parameters."""
        ms = self._parameters.mass_spectrum
        peak = self._parameters.ms_peak
        search = self._parameters.molecular_search

        # Mass spectrum tab
        ms.noise_threshold_log_nsigma = self.noise_threshold_spin.value()
        ms.min_picking_mz = self.min_mz_spin.value()
        ms.max_picking_mz = self.max_mz_spin.value()
        ms.min_calib_ppm_error = self.min_calib_ppm_spin.value()
        ms.max_calib_ppm_error = self.max_calib_ppm_spin.value()
        ms.calib_pol_order = self.calib_order_spin.value()

        # Peak picking tab
        peak.peak_min_prominence_percent = self.prominence_spin.value()

        # Molecular search tab
        search.min_ppm_error = self.min_ppm_spin.value()
        search.max_ppm_error = self.max_ppm_spin.value()
        search.url_database = self.db_url_edit.text() or None
        search.db_chunk_size = self.db_chunk_spin.value()

    def _reset_defaults(self):
        """Reset to default parameter values."""
        self._parameters = MSParameters()
        self._load_parameters()

    def accept(self):
        """Handle dialog accept."""
        self._save_parameters()
        super().accept()

    def get_parameters(self) -> MSParameters:
        """Get the current parameters.

        Returns:
            MSParameters object with current settings
        """
        return self._parameters

    @staticmethod
    def edit_parameters(parameters: Optional[MSParameters] = None,
                        parent=None) -> Optional[MSParameters]:
        """Static method to show dialog and get parameters.

        Args:
            parameters: Initial parameters (optional)
            parent: Parent widget

        Returns:
            MSParameters if accepted, None if cancelled
        """
        dialog = SettingsDialog(parameters, parent=parent)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            return dialog.get_parameters()
        return None
