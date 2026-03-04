"""Calibration dialog for visualizing and applying mass calibration."""

from typing import Optional, Tuple
import re
import numpy as np
from scipy import stats
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QGroupBox,
    QLabel, QPushButton, QDialogButtonBox, QSpinBox, QDoubleSpinBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QCheckBox, QSplitter,
    QWidget, QTabWidget
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor
import pyqtgraph as pg

from hrms_viewer.core.calibration import CalibrationResult


class CalibrationDialog(QDialog):
    """Dialog for mass calibration with visualization.

    Shows calibration parameters, error distribution plot, and calibration points table.
    """

    calibration_accepted = pyqtSignal(object)  # CalibrationResult

    def __init__(self, calibration: CalibrationResult, parent=None):
        super().__init__(parent)
        self.calibration = calibration

        self.setWindowTitle("Mass Calibration Results")
        self.setMinimumSize(900, 700)

        self._setup_ui()
        self._populate_data()

    def _setup_ui(self):
        """Set up the dialog UI."""
        layout = QVBoxLayout(self)

        # Summary section
        summary_group = QGroupBox("Calibration Summary")
        summary_layout = QFormLayout(summary_group)

        self.n_peaks_label = QLabel()
        self.final_std_label = QLabel()
        self.cal_iterations_label = QLabel()
        self.fit_iterations_label = QLabel()
        self.degree_label = QLabel()

        summary_layout.addRow("Calibration Points:", self.n_peaks_label)
        summary_layout.addRow("Final Std Dev (ppm):", self.final_std_label)
        summary_layout.addRow("Polynomial Degree:", self.degree_label)
        summary_layout.addRow("Calibration Iterations:", self.cal_iterations_label)
        summary_layout.addRow("Fit Iterations:", self.fit_iterations_label)

        layout.addWidget(summary_group)

        # Tabs for different views
        tabs = QTabWidget()

        # Error distribution tab
        error_tab = QWidget()
        error_layout = QVBoxLayout(error_tab)

        # Error plot
        self.error_plot = pg.PlotWidget()
        self.error_plot.setBackground('w')
        self.error_plot.setLabel('left', 'Error (ppm)')
        self.error_plot.setLabel('bottom', 'm/z')
        self.error_plot.showGrid(x=True, y=True, alpha=0.3)
        # Disable SI prefix (scientific notation) on axes
        self.error_plot.getAxis('bottom').enableAutoSIPrefix(False)
        self.error_plot.getAxis('left').enableAutoSIPrefix(False)
        error_layout.addWidget(self.error_plot)

        # Legend
        legend_layout = QHBoxLayout()
        legend_layout.addWidget(QLabel("Legend:"))

        used_label = QLabel("  Used in calibration")
        used_label.setStyleSheet("color: #2196F3;")
        legend_layout.addWidget(used_label)

        excluded_label = QLabel("  Excluded (outliers)")
        excluded_label.setStyleSheet("color: #F44336;")
        legend_layout.addWidget(excluded_label)

        fit_label = QLabel("  Polynomial fit")
        fit_label.setStyleSheet("color: #4CAF50;")
        legend_layout.addWidget(fit_label)

        band_label = QLabel("  Prediction band (95%)")
        band_label.setStyleSheet("color: #FF9800;")
        legend_layout.addWidget(band_label)

        legend_layout.addStretch()
        error_layout.addLayout(legend_layout)

        tabs.addTab(error_tab, "Error Distribution")

        # Histogram tab
        hist_tab = QWidget()
        hist_layout = QVBoxLayout(hist_tab)

        self.hist_plot = pg.PlotWidget()
        self.hist_plot.setBackground('w')
        self.hist_plot.setLabel('left', 'Count')
        self.hist_plot.setLabel('bottom', 'Error (ppm)')
        self.hist_plot.showGrid(x=True, y=True, alpha=0.3)
        # Disable SI prefix (scientific notation) on axes
        self.hist_plot.getAxis('bottom').enableAutoSIPrefix(False)
        self.hist_plot.getAxis('left').enableAutoSIPrefix(False)
        hist_layout.addWidget(self.hist_plot)

        tabs.addTab(hist_tab, "Error Histogram")

        # KDE by formula class tab
        kde_tab = QWidget()
        kde_layout = QVBoxLayout(kde_tab)

        self.kde_plot = pg.PlotWidget()
        self.kde_plot.setBackground('w')
        self.kde_plot.setLabel('left', 'Density')
        self.kde_plot.setLabel('bottom', 'Error (ppm)')
        self.kde_plot.showGrid(x=True, y=True, alpha=0.3)
        # Disable SI prefix (scientific notation) on axes
        self.kde_plot.getAxis('bottom').enableAutoSIPrefix(False)
        self.kde_plot.getAxis('left').enableAutoSIPrefix(False)
        self.kde_plot.addLegend()
        kde_layout.addWidget(self.kde_plot)

        # KDE statistics
        self.kde_stats_label = QLabel()
        self.kde_stats_label.setStyleSheet("font-family: monospace;")
        kde_layout.addWidget(self.kde_stats_label)

        tabs.addTab(kde_tab, "Error KDE by Class")

        # Calibration table tab
        table_tab = QWidget()
        table_layout = QVBoxLayout(table_tab)

        self.cal_table = QTableWidget()
        self.cal_table.setColumnCount(5)
        self.cal_table.setHorizontalHeaderLabels([
            "m/z (obs)", "m/z (calc)", "Error (ppm)", "Formula", "Used"
        ])

        header = self.cal_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        self.cal_table.setColumnWidth(4, 60)

        table_layout.addWidget(self.cal_table)

        # Table statistics
        self.table_stats = QLabel()
        table_layout.addWidget(self.table_stats)

        tabs.addTab(table_tab, "Calibration Points")

        # Polynomial coefficients tab
        coef_tab = QWidget()
        coef_layout = QVBoxLayout(coef_tab)

        self.coef_label = QLabel()
        self.coef_label.setStyleSheet("font-family: monospace;")
        coef_layout.addWidget(self.coef_label)

        coef_layout.addStretch()

        tabs.addTab(coef_tab, "Polynomial Coefficients")

        layout.addWidget(tabs)

        # Dialog buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self._on_accept)
        button_box.rejected.connect(self.reject)

        layout.addWidget(button_box)

    def _populate_data(self):
        """Populate the dialog with calibration data."""
        cal = self.calibration

        # Summary
        self.n_peaks_label.setText(f"{cal.n_peaks}")
        self.final_std_label.setText(f"{cal.final_std:.4f}")
        self.degree_label.setText(f"{cal.degree}")
        self.cal_iterations_label.setText(f"{cal.calibration_iterations}")
        self.fit_iterations_label.setText(f"{cal.iterations}")

        # Error plot
        self._plot_errors()

        # Histogram
        self._plot_histogram()

        # KDE by formula class
        self._plot_kde_by_class()

        # Table
        self._populate_table()

        # Coefficients
        self._display_coefficients()

    def _plot_errors(self):
        """Plot error distribution with fit and prediction bands."""
        from hrms_viewer.core.calibration import get_prediction_interval

        cal = self.calibration
        plot = self.error_plot

        # Get all assigned points
        mz_used = []
        errors_used = []
        mz_excluded = []
        errors_excluded = []

        for mz, error, formula, conf, is_used in cal.all_assigned:
            if is_used:
                mz_used.append(mz)
                errors_used.append(error)
            else:
                mz_excluded.append(mz)
                errors_excluded.append(error)

        # Plot excluded points (red)
        if mz_excluded:
            plot.plot(
                mz_excluded, errors_excluded,
                pen=None,
                symbol='o',
                symbolSize=8,
                symbolBrush='#F44336',
                symbolPen=None,
                name='Excluded'
            )

        # Plot used points (blue)
        if mz_used:
            plot.plot(
                mz_used, errors_used,
                pen=None,
                symbol='o',
                symbolSize=8,
                symbolBrush='#2196F3',
                symbolPen=None,
                name='Used'
            )

        # Plot polynomial fit and prediction bands
        if len(mz_used) > 0:
            all_mz = mz_used + mz_excluded
            mz_range = np.linspace(min(all_mz), max(all_mz), 200)
            fit_errors = np.polyval(cal.coefficients, mz_range)

            # Plot fit line (green)
            plot.plot(
                mz_range, fit_errors,
                pen=pg.mkPen('#4CAF50', width=2),
                name='Fit'
            )

            # Calculate and plot prediction bands (orange)
            mz_arr = np.array(mz_used)
            errors_arr = np.array(errors_used)
            lpb, upb = get_prediction_interval(mz_arr, errors_arr, mz_arr, cal.coefficients, alpha=0.05)

            # Sort for proper line plotting
            sort_idx = np.argsort(mz_arr)
            plot.plot(
                mz_arr[sort_idx], lpb[sort_idx],
                pen=pg.mkPen('#FF9800', width=1.5, style=Qt.PenStyle.DashLine),
                name='Prediction Band'
            )
            plot.plot(
                mz_arr[sort_idx], upb[sort_idx],
                pen=pg.mkPen('#FF9800', width=1.5, style=Qt.PenStyle.DashLine)
            )

        # Add zero line
        all_mz = mz_used + mz_excluded
        if all_mz:
            plot.plot(
                [min(all_mz), max(all_mz)], [0, 0],
                pen=pg.mkPen('gray', width=1, style=Qt.PenStyle.DashLine)
            )

    def _plot_histogram(self):
        """Plot error histogram."""
        cal = self.calibration
        plot = self.hist_plot

        # Get errors for used points
        errors_used = [error for mz, error, formula, conf, is_used in cal.all_assigned if is_used]
        errors_all = [error for mz, error, formula, conf, is_used in cal.all_assigned]

        if not errors_all:
            return

        # Calculate histogram bins
        all_errors = np.array(errors_all)
        bins = np.linspace(all_errors.min() - 0.1, all_errors.max() + 0.1, 30)

        # Plot all errors (light red)
        hist_all, bin_edges = np.histogram(errors_all, bins=bins)
        bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2
        bar_width = (bin_edges[1] - bin_edges[0]) * 0.8

        for i, (center, count) in enumerate(zip(bin_centers, hist_all)):
            bar = pg.BarGraphItem(
                x=[center], height=[count], width=bar_width,
                brush='#FFCDD2', pen=None
            )
            plot.addItem(bar)

        # Plot used errors (blue, overlaid)
        if errors_used:
            hist_used, _ = np.histogram(errors_used, bins=bins)

            for i, (center, count) in enumerate(zip(bin_centers, hist_used)):
                bar = pg.BarGraphItem(
                    x=[center], height=[count], width=bar_width * 0.6,
                    brush='#2196F3', pen=None
                )
                plot.addItem(bar)

        # Add vertical line at zero
        plot.addItem(pg.InfiniteLine(
            pos=0, angle=90,
            pen=pg.mkPen('#4CAF50', width=2, style=Qt.PenStyle.DashLine)
        ))

        # Add vertical line at mean
        if errors_used:
            mean_error = np.mean(errors_used)
            plot.addItem(pg.InfiniteLine(
                pos=mean_error, angle=90,
                pen=pg.mkPen('#F44336', width=2)
            ))

    def _classify_formula(self, formula: str) -> str:
        """Classify a molecular formula as CHO or CHON.

        Args:
            formula: Molecular formula string (e.g., "C10H20O5", "C10H20O5N2")

        Returns:
            "CHO" if formula contains only C, H, O (and optionally charge/adduct)
            "CHON" if formula contains N
            "Other" for other formulas
        """
        if not formula:
            return "Other"

        # Remove charge indicators and common adducts
        clean = re.sub(r'[+-]$', '', formula)
        clean = re.sub(r'\[.*?\]', '', clean)

        # Extract element symbols (uppercase letter followed by optional lowercase)
        elements = set(re.findall(r'[A-Z][a-z]?', clean))

        # Remove H (hydrogen) and check remaining elements
        elements.discard('H')

        if elements == {'C', 'O'}:
            return "CHO"
        elif elements == {'C', 'O', 'N'}:
            return "CHON"
        elif 'N' in elements and 'C' in elements and 'O' in elements:
            return "CHON"
        elif 'C' in elements and 'O' in elements:
            return "CHO"
        else:
            return "Other"

    def _plot_kde_by_class(self):
        """Plot KDE of m/z errors separated by formula class (CHO vs CHON)."""
        cal = self.calibration
        plot = self.kde_plot

        # Separate errors by formula class (only used points)
        cho_errors = []
        chon_errors = []

        for mz, error, formula, conf, is_used in cal.all_assigned:
            if not is_used:
                continue

            formula_class = self._classify_formula(formula)
            if formula_class == "CHO":
                cho_errors.append(error)
            elif formula_class == "CHON":
                chon_errors.append(error)

        # Need at least 2 points for KDE
        if len(cho_errors) < 2 and len(chon_errors) < 2:
            self.kde_stats_label.setText("Insufficient data for KDE plot")
            return

        # Determine x-axis range
        all_errors = cho_errors + chon_errors
        if not all_errors:
            return

        x_min = min(all_errors) - 0.5
        x_max = max(all_errors) + 0.5
        x_vals = np.linspace(x_min, x_max, 200)

        # Plot CHO KDE (blue)
        if len(cho_errors) >= 2:
            cho_kde = stats.gaussian_kde(cho_errors)
            cho_density = cho_kde(x_vals)
            plot.plot(
                x_vals, cho_density,
                pen=pg.mkPen('#2196F3', width=2),
                name=f'CHO (n={len(cho_errors)})'
            )
            # Add rug plot for CHO
            for err in cho_errors:
                plot.plot(
                    [err, err], [0, max(cho_density) * 0.02],
                    pen=pg.mkPen('#2196F3', width=1)
                )

        # Plot CHON KDE (orange)
        if len(chon_errors) >= 2:
            chon_kde = stats.gaussian_kde(chon_errors)
            chon_density = chon_kde(x_vals)
            plot.plot(
                x_vals, chon_density,
                pen=pg.mkPen('#FF9800', width=2),
                name=f'CHON (n={len(chon_errors)})'
            )
            # Add rug plot for CHON
            max_density = chon_density.max() if len(chon_errors) >= 2 else 0
            if len(cho_errors) >= 2:
                max_density = max(max_density, cho_kde(x_vals).max())
            for err in chon_errors:
                plot.plot(
                    [err, err], [0, max_density * 0.02],
                    pen=pg.mkPen('#FF9800', width=1)
                )

        # Add zero line
        plot.addItem(pg.InfiniteLine(
            pos=0, angle=90,
            pen=pg.mkPen('gray', width=1, style=Qt.PenStyle.DashLine)
        ))

        # Calculate and display statistics
        stats_lines = []
        if cho_errors:
            cho_mean = np.mean(cho_errors)
            cho_std = np.std(cho_errors) if len(cho_errors) > 1 else 0
            stats_lines.append(f"CHO:  n={len(cho_errors):3d}  mean={cho_mean:+.3f} ppm  std={cho_std:.3f} ppm")
        if chon_errors:
            chon_mean = np.mean(chon_errors)
            chon_std = np.std(chon_errors) if len(chon_errors) > 1 else 0
            stats_lines.append(f"CHON: n={len(chon_errors):3d}  mean={chon_mean:+.3f} ppm  std={chon_std:.3f} ppm")

        self.kde_stats_label.setText("\n".join(stats_lines))

    def _populate_table(self):
        """Populate the calibration points table."""
        cal = self.calibration

        self.cal_table.setRowCount(len(cal.all_assigned))

        n_used = 0
        for row, (mz, error, formula, conf, is_used) in enumerate(cal.all_assigned):
            # m/z observed
            mz_item = QTableWidgetItem(f"{mz:.5f}")
            mz_item.setFlags(mz_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.cal_table.setItem(row, 0, mz_item)

            # m/z calculated (find from cal_points if used)
            mz_calc = mz  # placeholder
            for cp in cal.cal_points:
                if abs(cp[0] - mz) < 0.0001:
                    mz_calc = cp[2]
                    break
            calc_item = QTableWidgetItem(f"{mz_calc:.5f}")
            calc_item.setFlags(calc_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.cal_table.setItem(row, 1, calc_item)

            # Error
            error_item = QTableWidgetItem(f"{error:+.4f}")
            error_item.setFlags(error_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.cal_table.setItem(row, 2, error_item)

            # Formula
            formula_item = QTableWidgetItem(formula)
            formula_item.setFlags(formula_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.cal_table.setItem(row, 3, formula_item)

            # Used checkbox
            used_item = QTableWidgetItem()
            used_item.setFlags(used_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            if is_used:
                used_item.setCheckState(Qt.CheckState.Checked)
                n_used += 1
            else:
                used_item.setCheckState(Qt.CheckState.Unchecked)
            self.cal_table.setItem(row, 4, used_item)

            # Color row based on used status
            color = QColor(232, 245, 233) if is_used else QColor(255, 235, 238)
            for col in range(5):
                item = self.cal_table.item(row, col)
                if item:
                    item.setBackground(color)

        # Update stats
        self.table_stats.setText(
            f"Total assigned: {len(cal.all_assigned)}, "
            f"Used for calibration: {n_used}, "
            f"Excluded: {len(cal.all_assigned) - n_used}"
        )

    def _display_coefficients(self):
        """Display polynomial coefficients."""
        cal = self.calibration

        lines = ["Polynomial coefficients (highest degree first):", ""]

        for i, coef in enumerate(cal.coefficients):
            power = cal.degree - i
            lines.append(f"  x^{power}: {coef:+.10e}")

        lines.append("")
        lines.append("Polynomial equation (error in ppm):")
        lines.append("")

        terms = []
        for i, coef in enumerate(cal.coefficients):
            power = cal.degree - i
            if power == 0:
                terms.append(f"{coef:+.6e}")
            elif power == 1:
                terms.append(f"{coef:+.6e} * m/z")
            else:
                terms.append(f"{coef:+.6e} * m/z^{power}")

        lines.append("  error = " + " ".join(terms))

        self.coef_label.setText("\n".join(lines))

    def _on_accept(self):
        """Handle accept button."""
        self.calibration_accepted.emit(self.calibration)
        self.accept()


class CalibrationParametersDialog(QDialog):
    """Dialog for setting calibration parameters before running calibration."""

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle("Calibration Parameters")
        self.setMinimumWidth(450)

        self._setup_ui()

    def _setup_ui(self):
        """Set up the dialog UI."""
        layout = QVBoxLayout(self)

        # Formula search info (read-only)
        formula_group = QGroupBox("Molecular Formula Search (Fixed)")
        formula_layout = QVBoxLayout(formula_group)

        info_text = (
            "Search criteria:\n"
            "  • Atoms: C(1-40), H(4-80), O(1-12), N(0-2)\n"
            "  • DBE: 0-16\n"
            "  • Ion type: [M+H]+ / [M-H]-\n"
            "  • m/z range: 200-900\n"
            "  • Filters: H/C ≤ 3, O/C ≤ 1.2"
        )
        info_label = QLabel(info_text)
        info_label.setStyleSheet("font-family: monospace; color: #555;")
        formula_layout.addWidget(info_label)

        layout.addWidget(formula_group)

        # m/z Error Range group
        error_group = QGroupBox("m/z Error Range for Assignment")
        error_layout = QFormLayout(error_group)

        # Min ppm error
        self.min_ppm_spin = QDoubleSpinBox()
        self.min_ppm_spin.setRange(-100.0, 0.0)
        self.min_ppm_spin.setValue(-2.0)
        self.min_ppm_spin.setSingleStep(0.5)
        self.min_ppm_spin.setDecimals(2)
        self.min_ppm_spin.setToolTip("Minimum m/z error (ppm) for formula search")
        error_layout.addRow("Min Error (ppm):", self.min_ppm_spin)

        # Max ppm error
        self.max_ppm_spin = QDoubleSpinBox()
        self.max_ppm_spin.setRange(0.0, 100.0)
        self.max_ppm_spin.setValue(4.0)
        self.max_ppm_spin.setSingleStep(0.5)
        self.max_ppm_spin.setDecimals(2)
        self.max_ppm_spin.setToolTip("Maximum m/z error (ppm) for formula search")
        error_layout.addRow("Max Error (ppm):", self.max_ppm_spin)

        layout.addWidget(error_group)

        # Calibration Parameters group
        params_group = QGroupBox("Calibration Fitting")
        params_layout = QFormLayout(params_group)

        # Polynomial degree
        self.degree_spin = QSpinBox()
        self.degree_spin.setRange(1, 5)
        self.degree_spin.setValue(2)
        self.degree_spin.setToolTip("Degree of polynomial fit (1=linear, 2=quadratic, 3=cubic)")
        params_layout.addRow("Polynomial Degree:", self.degree_spin)

        # Min confidence
        self.confidence_spin = QDoubleSpinBox()
        self.confidence_spin.setRange(0.0, 1.0)
        self.confidence_spin.setValue(0.6)
        self.confidence_spin.setSingleStep(0.1)
        self.confidence_spin.setDecimals(2)
        self.confidence_spin.setToolTip("Minimum confidence score for calibration points")
        params_layout.addRow("Min Confidence Score:", self.confidence_spin)

        # Min S/N
        self.sn_spin = QDoubleSpinBox()
        self.sn_spin.setRange(0.0, 1000.0)
        self.sn_spin.setValue(10.0)
        self.sn_spin.setSingleStep(5.0)
        self.sn_spin.setDecimals(1)
        self.sn_spin.setToolTip("Minimum signal-to-noise ratio for calibration points")
        params_layout.addRow("Min S/N:", self.sn_spin)

        # Target std
        self.std_spin = QDoubleSpinBox()
        self.std_spin.setRange(0.01, 10.0)
        self.std_spin.setValue(0.5)
        self.std_spin.setSingleStep(0.1)
        self.std_spin.setDecimals(2)
        self.std_spin.setToolTip("Target standard deviation (ppm) for stopping iteration")
        params_layout.addRow("Target Std Dev (ppm):", self.std_spin)

        layout.addWidget(params_group)

        # Options group
        options_group = QGroupBox("Options")
        options_layout = QVBoxLayout(options_group)

        self.apply_checkbox = QCheckBox("Apply calibration to spectrum")
        self.apply_checkbox.setChecked(True)
        self.apply_checkbox.setToolTip("Apply the calibration correction to m/z values")
        options_layout.addWidget(self.apply_checkbox)

        self.show_output_checkbox = QCheckBox("Show processing output")
        self.show_output_checkbox.setChecked(True)
        self.show_output_checkbox.setToolTip("Show terminal-like window with assignment output")
        options_layout.addWidget(self.show_output_checkbox)

        layout.addWidget(options_group)

        # Info
        info_label = QLabel(
            "Calibration will:\n"
            "1. Assign molecular formulas using the specified m/z error range\n"
            "2. Filter by confidence and S/N thresholds\n"
            "3. Fit polynomial to error vs m/z\n"
            "4. Iteratively remove outliers until target std is reached"
        )
        info_label.setStyleSheet("color: gray; font-size: 10px;")
        layout.addWidget(info_label)

        # Dialog buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)

        layout.addWidget(button_box)

    def get_parameters(self) -> dict:
        """Get the selected parameters.

        Returns:
            Dict with calibration parameters
        """
        return {
            # m/z error range (user-configurable)
            'min_ppm_error': self.min_ppm_spin.value(),
            'max_ppm_error': self.max_ppm_spin.value(),
            # Calibration fitting parameters
            'degree': self.degree_spin.value(),
            'min_confidence': self.confidence_spin.value(),
            'min_sn': self.sn_spin.value(),
            'target_std': self.std_spin.value(),
            'apply_correction': self.apply_checkbox.isChecked(),
            'show_output': self.show_output_checkbox.isChecked()
        }

    @staticmethod
    def get_calibration_params(parent=None) -> Optional[dict]:
        """Show dialog and return parameters.

        Returns:
            Dict with parameters or None if cancelled
        """
        dialog = CalibrationParametersDialog(parent)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            return dialog.get_parameters()
        return None


class AssignmentParametersDialog(QDialog):
    """Dialog for setting molecular formula assignment parameters."""

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle("Formula Assignment Parameters")
        self.setMinimumWidth(500)

        self._setup_ui()

    def _setup_ui(self):
        """Set up the dialog UI."""
        layout = QVBoxLayout(self)

        # Molecular Formula Search Criteria group
        formula_group = QGroupBox("Molecular Formula Search Criteria")
        formula_layout = QVBoxLayout(formula_group)

        # Atom ranges - grid layout
        atoms_layout = QHBoxLayout()

        # Left column - common atoms
        left_atoms = QFormLayout()

        self.c_min_spin = QSpinBox()
        self.c_min_spin.setRange(1, 200)
        self.c_min_spin.setValue(1)
        self.c_max_spin = QSpinBox()
        self.c_max_spin.setRange(1, 200)
        self.c_max_spin.setValue(40)
        c_layout = QHBoxLayout()
        c_layout.addWidget(self.c_min_spin)
        c_layout.addWidget(QLabel("-"))
        c_layout.addWidget(self.c_max_spin)
        left_atoms.addRow("C:", c_layout)

        self.h_min_spin = QSpinBox()
        self.h_min_spin.setRange(0, 400)
        self.h_min_spin.setValue(4)
        self.h_max_spin = QSpinBox()
        self.h_max_spin.setRange(0, 400)
        self.h_max_spin.setValue(80)
        h_layout = QHBoxLayout()
        h_layout.addWidget(self.h_min_spin)
        h_layout.addWidget(QLabel("-"))
        h_layout.addWidget(self.h_max_spin)
        left_atoms.addRow("H:", h_layout)

        self.o_min_spin = QSpinBox()
        self.o_min_spin.setRange(0, 50)
        self.o_min_spin.setValue(1)
        self.o_max_spin = QSpinBox()
        self.o_max_spin.setRange(0, 50)
        self.o_max_spin.setValue(12)
        o_layout = QHBoxLayout()
        o_layout.addWidget(self.o_min_spin)
        o_layout.addWidget(QLabel("-"))
        o_layout.addWidget(self.o_max_spin)
        left_atoms.addRow("O:", o_layout)

        atoms_layout.addLayout(left_atoms)

        # Right column - heteroatoms
        right_atoms = QFormLayout()

        self.n_min_spin = QSpinBox()
        self.n_min_spin.setRange(0, 20)
        self.n_min_spin.setValue(0)
        self.n_max_spin = QSpinBox()
        self.n_max_spin.setRange(0, 20)
        self.n_max_spin.setValue(2)
        n_layout = QHBoxLayout()
        n_layout.addWidget(self.n_min_spin)
        n_layout.addWidget(QLabel("-"))
        n_layout.addWidget(self.n_max_spin)
        right_atoms.addRow("N:", n_layout)

        self.s_min_spin = QSpinBox()
        self.s_min_spin.setRange(0, 10)
        self.s_min_spin.setValue(0)
        self.s_max_spin = QSpinBox()
        self.s_max_spin.setRange(0, 10)
        self.s_max_spin.setValue(2)
        s_layout = QHBoxLayout()
        s_layout.addWidget(self.s_min_spin)
        s_layout.addWidget(QLabel("-"))
        s_layout.addWidget(self.s_max_spin)
        right_atoms.addRow("S:", s_layout)

        self.p_min_spin = QSpinBox()
        self.p_min_spin.setRange(0, 10)
        self.p_min_spin.setValue(0)
        self.p_max_spin = QSpinBox()
        self.p_max_spin.setRange(0, 10)
        self.p_max_spin.setValue(1)
        p_layout = QHBoxLayout()
        p_layout.addWidget(self.p_min_spin)
        p_layout.addWidget(QLabel("-"))
        p_layout.addWidget(self.p_max_spin)
        right_atoms.addRow("P:", p_layout)

        atoms_layout.addLayout(right_atoms)
        formula_layout.addLayout(atoms_layout)

        # DBE range
        dbe_layout_row = QHBoxLayout()
        dbe_layout_row.addWidget(QLabel("DBE:"))
        self.dbe_min_spin = QSpinBox()
        self.dbe_min_spin.setRange(0, 50)
        self.dbe_min_spin.setValue(0)
        self.dbe_max_spin = QSpinBox()
        self.dbe_max_spin.setRange(0, 50)
        self.dbe_max_spin.setValue(16)
        dbe_layout_row.addWidget(self.dbe_min_spin)
        dbe_layout_row.addWidget(QLabel("-"))
        dbe_layout_row.addWidget(self.dbe_max_spin)
        dbe_layout_row.addStretch()
        formula_layout.addLayout(dbe_layout_row)

        # Expandable section for additional elements
        self.additional_elements_btn = QPushButton("Additional Elements ▶")
        self.additional_elements_btn.setStyleSheet("text-align: left; padding: 5px;")
        self.additional_elements_btn.setFlat(True)
        self.additional_elements_btn.clicked.connect(self._toggle_additional_elements)
        formula_layout.addWidget(self.additional_elements_btn)

        # Container for additional elements (initially hidden)
        self.additional_elements_widget = QWidget()
        additional_layout = QHBoxLayout(self.additional_elements_widget)
        additional_layout.setContentsMargins(20, 0, 0, 0)

        # Left column of additional elements
        add_left = QFormLayout()

        self.fe_min_spin = QSpinBox()
        self.fe_min_spin.setRange(0, 5)
        self.fe_min_spin.setValue(0)
        self.fe_max_spin = QSpinBox()
        self.fe_max_spin.setRange(0, 5)
        self.fe_max_spin.setValue(0)
        fe_layout = QHBoxLayout()
        fe_layout.addWidget(self.fe_min_spin)
        fe_layout.addWidget(QLabel("-"))
        fe_layout.addWidget(self.fe_max_spin)
        add_left.addRow("Fe:", fe_layout)

        self.cu_min_spin = QSpinBox()
        self.cu_min_spin.setRange(0, 5)
        self.cu_min_spin.setValue(0)
        self.cu_max_spin = QSpinBox()
        self.cu_max_spin.setRange(0, 5)
        self.cu_max_spin.setValue(0)
        cu_layout = QHBoxLayout()
        cu_layout.addWidget(self.cu_min_spin)
        cu_layout.addWidget(QLabel("-"))
        cu_layout.addWidget(self.cu_max_spin)
        add_left.addRow("Cu:", cu_layout)

        self.na_min_spin = QSpinBox()
        self.na_min_spin.setRange(0, 5)
        self.na_min_spin.setValue(0)
        self.na_max_spin = QSpinBox()
        self.na_max_spin.setRange(0, 5)
        self.na_max_spin.setValue(0)
        na_layout = QHBoxLayout()
        na_layout.addWidget(self.na_min_spin)
        na_layout.addWidget(QLabel("-"))
        na_layout.addWidget(self.na_max_spin)
        add_left.addRow("Na:", na_layout)

        self.k_min_spin = QSpinBox()
        self.k_min_spin.setRange(0, 5)
        self.k_min_spin.setValue(0)
        self.k_max_spin = QSpinBox()
        self.k_max_spin.setRange(0, 5)
        self.k_max_spin.setValue(0)
        k_layout = QHBoxLayout()
        k_layout.addWidget(self.k_min_spin)
        k_layout.addWidget(QLabel("-"))
        k_layout.addWidget(self.k_max_spin)
        add_left.addRow("K:", k_layout)

        additional_layout.addLayout(add_left)

        # Right column of additional elements
        add_right = QFormLayout()

        self.cl_min_spin = QSpinBox()
        self.cl_min_spin.setRange(0, 5)
        self.cl_min_spin.setValue(0)
        self.cl_max_spin = QSpinBox()
        self.cl_max_spin.setRange(0, 5)
        self.cl_max_spin.setValue(0)
        cl_layout = QHBoxLayout()
        cl_layout.addWidget(self.cl_min_spin)
        cl_layout.addWidget(QLabel("-"))
        cl_layout.addWidget(self.cl_max_spin)
        add_right.addRow("Cl:", cl_layout)

        self.br_min_spin = QSpinBox()
        self.br_min_spin.setRange(0, 5)
        self.br_min_spin.setValue(0)
        self.br_max_spin = QSpinBox()
        self.br_max_spin.setRange(0, 5)
        self.br_max_spin.setValue(0)
        br_layout = QHBoxLayout()
        br_layout.addWidget(self.br_min_spin)
        br_layout.addWidget(QLabel("-"))
        br_layout.addWidget(self.br_max_spin)
        add_right.addRow("Br:", br_layout)

        self.i_min_spin = QSpinBox()
        self.i_min_spin.setRange(0, 5)
        self.i_min_spin.setValue(0)
        self.i_max_spin = QSpinBox()
        self.i_max_spin.setRange(0, 5)
        self.i_max_spin.setValue(0)
        i_layout = QHBoxLayout()
        i_layout.addWidget(self.i_min_spin)
        i_layout.addWidget(QLabel("-"))
        i_layout.addWidget(self.i_max_spin)
        add_right.addRow("I:", i_layout)

        additional_layout.addLayout(add_right)

        self.additional_elements_widget.setVisible(False)
        formula_layout.addWidget(self.additional_elements_widget)

        # Ion type options
        ion_layout = QHBoxLayout()

        self.protonated_checkbox = QCheckBox("[M+H]+ / [M-H]-")
        self.protonated_checkbox.setChecked(True)
        self.protonated_checkbox.setToolTip("Search for protonated/deprotonated ions")
        ion_layout.addWidget(self.protonated_checkbox)

        self.radical_checkbox = QCheckBox("[M]+/[M]-")
        self.radical_checkbox.setChecked(False)
        self.radical_checkbox.setToolTip("Search for radical ions")
        ion_layout.addWidget(self.radical_checkbox)

        self.adduct_checkbox = QCheckBox("Adducts")
        self.adduct_checkbox.setChecked(False)
        self.adduct_checkbox.setToolTip("Search for adduct ions (Na, K, Cl, Br)")
        ion_layout.addWidget(self.adduct_checkbox)

        formula_layout.addLayout(ion_layout)

        # Filters
        filter_layout = QHBoxLayout()

        filter_layout.addWidget(QLabel("H/C ≤"))
        self.hc_filter_spin = QDoubleSpinBox()
        self.hc_filter_spin.setRange(0.1, 10.0)
        self.hc_filter_spin.setValue(3.0)
        self.hc_filter_spin.setSingleStep(0.1)
        self.hc_filter_spin.setDecimals(1)
        filter_layout.addWidget(self.hc_filter_spin)

        filter_layout.addWidget(QLabel("   O/C ≤"))
        self.oc_filter_spin = QDoubleSpinBox()
        self.oc_filter_spin.setRange(0.1, 5.0)
        self.oc_filter_spin.setValue(1.2)
        self.oc_filter_spin.setSingleStep(0.1)
        self.oc_filter_spin.setDecimals(1)
        filter_layout.addWidget(self.oc_filter_spin)

        filter_layout.addStretch()
        formula_layout.addLayout(filter_layout)

        layout.addWidget(formula_group)

        # m/z Error Range group
        error_group = QGroupBox("m/z Error Range")
        error_layout = QFormLayout(error_group)

        # Min ppm error
        self.min_ppm_spin = QDoubleSpinBox()
        self.min_ppm_spin.setRange(-100.0, 0.0)
        self.min_ppm_spin.setValue(-2.0)
        self.min_ppm_spin.setSingleStep(0.5)
        self.min_ppm_spin.setDecimals(2)
        self.min_ppm_spin.setToolTip("Minimum m/z error (ppm) for formula search")
        error_layout.addRow("Min Error (ppm):", self.min_ppm_spin)

        # Max ppm error
        self.max_ppm_spin = QDoubleSpinBox()
        self.max_ppm_spin.setRange(0.0, 100.0)
        self.max_ppm_spin.setValue(4.0)
        self.max_ppm_spin.setSingleStep(0.5)
        self.max_ppm_spin.setDecimals(2)
        self.max_ppm_spin.setToolTip("Maximum m/z error (ppm) for formula search")
        error_layout.addRow("Max Error (ppm):", self.max_ppm_spin)

        layout.addWidget(error_group)

        # Options group
        options_group = QGroupBox("Options")
        options_layout = QVBoxLayout(options_group)

        self.isotopologue_checkbox = QCheckBox("Find isotopologues")
        self.isotopologue_checkbox.setChecked(True)
        self.isotopologue_checkbox.setToolTip("Search for isotopologue patterns")
        options_layout.addWidget(self.isotopologue_checkbox)

        self.show_output_checkbox = QCheckBox("Show processing output")
        self.show_output_checkbox.setChecked(True)
        self.show_output_checkbox.setToolTip("Show terminal-like window with assignment output")
        options_layout.addWidget(self.show_output_checkbox)

        layout.addWidget(options_group)

        # Dialog buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)

        layout.addWidget(button_box)

    def _toggle_additional_elements(self):
        """Toggle visibility of additional elements section."""
        visible = not self.additional_elements_widget.isVisible()
        self.additional_elements_widget.setVisible(visible)
        if visible:
            self.additional_elements_btn.setText("Additional Elements ▼")
        else:
            self.additional_elements_btn.setText("Additional Elements ▶")

    def get_parameters(self) -> dict:
        """Get the selected parameters.

        Returns:
            Dict with assignment parameters
        """
        # Build usedAtoms dict - only include elements with max > 0
        usedAtoms = {
            'C': (self.c_min_spin.value(), self.c_max_spin.value()),
            'H': (self.h_min_spin.value(), self.h_max_spin.value()),
            'O': (self.o_min_spin.value(), self.o_max_spin.value()),
        }

        # Add N, S, P if max > 0
        if self.n_max_spin.value() > 0:
            usedAtoms['N'] = (self.n_min_spin.value(), self.n_max_spin.value())
        if self.s_max_spin.value() > 0:
            usedAtoms['S'] = (self.s_min_spin.value(), self.s_max_spin.value())
        if self.p_max_spin.value() > 0:
            usedAtoms['P'] = (self.p_min_spin.value(), self.p_max_spin.value())

        # Add additional elements if max > 0
        if self.fe_max_spin.value() > 0:
            usedAtoms['Fe'] = (self.fe_min_spin.value(), self.fe_max_spin.value())
        if self.cu_max_spin.value() > 0:
            usedAtoms['Cu'] = (self.cu_min_spin.value(), self.cu_max_spin.value())
        if self.na_max_spin.value() > 0:
            usedAtoms['Na'] = (self.na_min_spin.value(), self.na_max_spin.value())
        if self.k_max_spin.value() > 0:
            usedAtoms['K'] = (self.k_min_spin.value(), self.k_max_spin.value())
        if self.cl_max_spin.value() > 0:
            usedAtoms['Cl'] = (self.cl_min_spin.value(), self.cl_max_spin.value())
        if self.br_max_spin.value() > 0:
            usedAtoms['Br'] = (self.br_min_spin.value(), self.br_max_spin.value())
        if self.i_max_spin.value() > 0:
            usedAtoms['I'] = (self.i_min_spin.value(), self.i_max_spin.value())

        return {
            'usedAtoms': usedAtoms,
            'min_dbe': self.dbe_min_spin.value(),
            'max_dbe': self.dbe_max_spin.value(),
            'isProtonated': self.protonated_checkbox.isChecked(),
            'isRadical': self.radical_checkbox.isChecked(),
            'isAdduct': self.adduct_checkbox.isChecked(),
            'max_hc_filter': self.hc_filter_spin.value(),
            'max_oc_filter': self.oc_filter_spin.value(),
            'min_ppm_error': self.min_ppm_spin.value(),
            'max_ppm_error': self.max_ppm_spin.value(),
            'find_isotopologues': self.isotopologue_checkbox.isChecked(),
            'show_output': self.show_output_checkbox.isChecked()
        }

    @staticmethod
    def get_assignment_params(parent=None) -> Optional[dict]:
        """Show dialog and return parameters.

        Returns:
            Dict with parameters or None if cancelled
        """
        dialog = AssignmentParametersDialog(parent)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            return dialog.get_parameters()
        return None
