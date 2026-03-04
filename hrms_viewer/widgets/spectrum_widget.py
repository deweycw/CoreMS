"""Mass spectrum widget for displaying MS data using PyQtGraph."""

from typing import Optional, List, Tuple
import numpy as np
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QCheckBox, QLabel, QMenu, QPushButton,
    QDoubleSpinBox
)
from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtGui import QAction
import pyqtgraph as pg


class SpectrumWidget(QWidget):
    """Mass spectrum viewer using PyQtGraph.

    Displays profile and/or centroid mass spectrum data with interactive
    peak selection and zoom capabilities.

    Signals:
        mz_clicked: Emitted when user clicks on spectrum (m/z value)
        peak_clicked: Emitted when user clicks on a peak (peak index)
        eic_requested: Emitted when user requests EIC extraction (m/z value)
        assign_requested: Emitted when user requests formula assignment (peak index)
    """

    mz_clicked = pyqtSignal(float)
    peak_clicked = pyqtSignal(int)
    eic_requested = pyqtSignal(float)
    assign_requested = pyqtSignal(int)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)

        self._spectrum = None
        self._highlighted_peak: Optional[int] = None

        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        """Set up the widget UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        # Controls row
        controls = QHBoxLayout()
        controls.setContentsMargins(5, 2, 5, 2)

        self.profile_checkbox = QCheckBox("Profile")
        self.profile_checkbox.setChecked(True)
        self.peaks_checkbox = QCheckBox("Peaks")
        self.peaks_checkbox.setChecked(True)
        self.labels_checkbox = QCheckBox("m/z")
        self.labels_checkbox.setChecked(False)
        self.labels_checkbox.setEnabled(False)  # Disabled until processed
        self.labels_checkbox.setToolTip("Show m/z labels (5 decimal places) - requires processing")
        self.sn_checkbox = QCheckBox("S/N")
        self.sn_checkbox.setChecked(False)
        self.sn_checkbox.setEnabled(False)  # Disabled until processed
        self.sn_checkbox.setToolTip("Show signal-to-noise ratio - requires processing")
        self.rp_checkbox = QCheckBox("RP")
        self.rp_checkbox.setChecked(False)
        self.rp_checkbox.setEnabled(False)  # Disabled until processed
        self.rp_checkbox.setToolTip("Show resolving power - requires processing")
        self.noise_checkbox = QCheckBox("Noise")
        self.noise_checkbox.setChecked(False)
        self.noise_checkbox.setEnabled(False)  # Disabled until processed
        self.noise_checkbox.setToolTip("Show noise threshold level - requires processing")

        self.noise_sigma_label = QLabel("σ:")
        self.noise_sigma_label.setVisible(False)  # Hidden until Noise is checked
        self.noise_sigma_spin = QDoubleSpinBox()
        self.noise_sigma_spin.setRange(1.0, 100.0)
        self.noise_sigma_spin.setValue(6.0)  # Default log_nsigma
        self.noise_sigma_spin.setSingleStep(1.0)
        self.noise_sigma_spin.setFixedWidth(70)
        self.noise_sigma_spin.setToolTip("Noise threshold multiplier (default: 6)")
        self.noise_sigma_spin.setVisible(False)  # Hidden until Noise is checked

        self.reset_zoom_btn = QPushButton("Reset Zoom")
        self.reset_zoom_btn.setFixedWidth(80)
        self.reset_zoom_btn.setToolTip("Reset view to show full spectrum (or double-click)")

        self.info_label = QLabel("")
        self.info_label.setStyleSheet("color: gray; font-size: 10px;")

        controls.addWidget(self.profile_checkbox)
        controls.addWidget(self.peaks_checkbox)
        controls.addWidget(self.labels_checkbox)
        controls.addWidget(self.sn_checkbox)
        controls.addWidget(self.rp_checkbox)
        controls.addWidget(self.noise_checkbox)
        controls.addWidget(self.noise_sigma_label)
        controls.addWidget(self.noise_sigma_spin)
        controls.addWidget(self.reset_zoom_btn)
        controls.addStretch()
        controls.addWidget(self.info_label)

        layout.addLayout(controls)

        # PyQtGraph plot widget
        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setBackground('w')
        self.plot_widget.setLabel('left', 'Intensity')
        self.plot_widget.setLabel('bottom', 'm/z')
        self.plot_widget.showGrid(x=True, y=True, alpha=0.3)

        # Enable mouse interaction
        self.plot_widget.setMouseEnabled(x=True, y=True)

        # Enable rectangle zoom mode (left-click drag to zoom)
        self.plot_widget.getViewBox().setMouseMode(pg.ViewBox.RectMode)

        # Enable scroll wheel zoom
        self.plot_widget.getViewBox().setMouseEnabled(x=True, y=True)
        self.plot_widget.getViewBox().enableAutoRange(enable=False)

        layout.addWidget(self.plot_widget)

        # Profile curve - thicker line for visibility
        self.profile_curve = self.plot_widget.plot(
            pen=pg.mkPen('#2196F3', width=2),
            name='Profile'
        )

        # Peaks scatter plot (for detected peaks)
        self.peaks_scatter = pg.ScatterPlotItem(
            size=8,
            pen=pg.mkPen('#F44336', width=1),
            brush=pg.mkBrush('#F44336'),
            symbol='o'
        )
        self.plot_widget.addItem(self.peaks_scatter)

        # Highlighted peak indicator
        self.highlight_scatter = pg.ScatterPlotItem(
            size=14,
            pen=pg.mkPen('#4CAF50', width=2),
            brush=pg.mkBrush(76, 175, 80, 100),
            symbol='o'
        )
        self.plot_widget.addItem(self.highlight_scatter)

        # Peak labels (text items)
        self.peak_labels: List[pg.TextItem] = []

        # Isotopologue markers (vertical lines showing predicted isotope positions)
        self.isotope_markers: List = []  # Can be InfiniteLine or PlotDataItem
        self.isotope_labels: List[pg.TextItem] = []
        self._isotope_base_mz: Optional[float] = None  # The m/z of the selected peak
        self._isotope_data: List[Tuple] = []  # Store isotope data for updates
        self._isotope_colors: List[str] = []  # Store colors for consistency

        # Noise threshold line - thick orange line for visibility
        self.noise_line = pg.InfiniteLine(
            pos=0,
            angle=0,
            pen=pg.mkPen('#FF5722', width=3, style=Qt.PenStyle.DashLine),
            movable=False,
            label='Noise',
            labelOpts={'color': '#FF5722', 'position': 0.02, 'fill': (255, 255, 255, 180)}
        )
        self.noise_line.setVisible(False)
        self.plot_widget.addItem(self.noise_line)

        # Crosshair for hover
        self.vLine = pg.InfiniteLine(angle=90, movable=False, pen=pg.mkPen('gray', width=1))
        self.vLine.setVisible(False)
        self.plot_widget.addItem(self.vLine, ignoreBounds=True)

        # Legend for peak colors (hidden until peaks are processed)
        self.peak_legend = pg.LegendItem(offset=(70, 10))
        self.peak_legend.setParentItem(self.plot_widget.getPlotItem())

        # Create dummy scatter items for legend entries
        self._legend_assigned = pg.ScatterPlotItem(
            size=8, brush=pg.mkBrush('#4CAF50'), symbol='o'
        )
        self._legend_unassigned = pg.ScatterPlotItem(
            size=8, brush=pg.mkBrush('#F44336'), symbol='o'
        )
        self.peak_legend.addItem(self._legend_assigned, 'Assigned')
        self.peak_legend.addItem(self._legend_unassigned, 'Unassigned')
        self.peak_legend.setVisible(False)

        # Context menu
        self.plot_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)

    def _connect_signals(self):
        """Connect internal signals."""
        self.profile_checkbox.toggled.connect(self._on_profile_toggled)
        self.peaks_checkbox.toggled.connect(self._on_peaks_toggled)
        self.labels_checkbox.toggled.connect(self._update_peak_labels)
        self.sn_checkbox.toggled.connect(self._update_peak_labels)
        self.rp_checkbox.toggled.connect(self._update_peak_labels)
        self.noise_checkbox.toggled.connect(self._on_noise_toggled)
        self.noise_sigma_spin.valueChanged.connect(self._on_noise_sigma_changed)
        self.reset_zoom_btn.clicked.connect(self.reset_zoom)

        # Mouse click for peak selection
        self.plot_widget.scene().sigMouseClicked.connect(self._on_mouse_clicked)

        # Mouse move for crosshair
        self.plot_widget.scene().sigMouseMoved.connect(self._on_mouse_moved)

        # Update labels when view range changes (zoom/pan)
        self.plot_widget.sigRangeChanged.connect(self._on_range_changed)

        # Context menu
        self.plot_widget.customContextMenuRequested.connect(self._show_context_menu)

    def _on_range_changed(self):
        """Handle view range change (zoom/pan) - update peak labels and isotope labels."""
        self._update_peak_labels()
        self._update_isotope_label_positions()

    def _on_profile_toggled(self, checked: bool):
        """Handle profile checkbox toggle."""
        self.profile_curve.setVisible(checked)

    def _on_peaks_toggled(self, checked: bool):
        """Handle peaks checkbox toggle."""
        self.peaks_scatter.setVisible(checked)

    def _on_noise_toggled(self, checked: bool):
        """Handle noise checkbox toggle."""
        if checked and self._spectrum is not None:
            self._update_noise_line()
        self.noise_line.setVisible(checked)
        self.noise_sigma_label.setVisible(checked)
        self.noise_sigma_spin.setVisible(checked)

    def _on_noise_sigma_changed(self, value: float):
        """Handle noise sigma spinbox change."""
        if self.noise_checkbox.isChecked():
            self._update_noise_line()

    def _update_noise_line(self):
        """Update noise threshold line position based on baseline_noise_std * sigma."""
        if self._spectrum is None:
            return

        try:
            # Get baseline noise std from spectrum (property, not private attr)
            noise_std = self._spectrum.baseline_noise_std

            if noise_std is not None and noise_std > 0:
                # Calculate threshold: baseline_noise_std * log_nsigma
                log_nsigma = self.noise_sigma_spin.value()
                noise_threshold = noise_std * log_nsigma

                self.noise_line.setPos(noise_threshold)
                self.noise_line.setVisible(True)
                # Update label with threshold value
                self.noise_line.label.setFormat(f'Noise: {noise_threshold:.2e} ({log_nsigma}σ)')
                print(f"Noise threshold set to {noise_threshold:.2e} (noise_std={noise_std:.2e} × σ={log_nsigma})")
            else:
                print(f"Warning: baseline_noise_std is {noise_std} - spectrum may not be processed")
                self.noise_line.setVisible(False)
        except Exception as e:
            print(f"Error updating noise line: {e}")
            import traceback
            traceback.print_exc()

    def _on_mouse_clicked(self, event):
        """Handle mouse click on plot."""
        if self._spectrum is None:
            return

        pos = event.scenePos()
        if not self.plot_widget.sceneBoundingRect().contains(pos):
            return

        # Double-click to reset zoom
        if event.double():
            self.reset_zoom()
            return

        if event.button() != Qt.MouseButton.LeftButton:
            return

        # Map to plot coordinates
        mouse_point = self.plot_widget.plotItem.vb.mapSceneToView(pos)
        mz = mouse_point.x()

        self.mz_clicked.emit(mz)

        # Check if click is near a peak
        peak_idx = self._find_nearest_peak(mz)
        if peak_idx is not None:
            self.highlight_peak(peak_idx)
            self.peak_clicked.emit(peak_idx)

    def _on_mouse_moved(self, pos):
        """Handle mouse move for crosshair update."""
        if self._spectrum is None:
            return

        if self.plot_widget.sceneBoundingRect().contains(pos):
            mouse_point = self.plot_widget.plotItem.vb.mapSceneToView(pos)
            mz = mouse_point.x()

            self.vLine.setPos(mz)
            self.vLine.setVisible(True)

            # Show m/z in info label
            intensity = self._intensity_at_mz(mz)
            if intensity is not None:
                self.info_label.setText(f"m/z: {mz:.4f}, Int: {intensity:.2e}")
            else:
                self.info_label.setText(f"m/z: {mz:.4f}")
        else:
            self.vLine.setVisible(False)
            self.info_label.setText("")

    def _show_context_menu(self, pos):
        """Show context menu at position."""
        if self._spectrum is None:
            return

        # Map to plot coordinates
        scene_pos = self.plot_widget.mapToScene(pos)
        view_pos = self.plot_widget.plotItem.vb.mapSceneToView(scene_pos)
        mz = view_pos.x()

        menu = QMenu(self)

        # Reset zoom action
        reset_action = QAction("Reset Zoom", self)
        reset_action.triggered.connect(self.reset_zoom)
        menu.addAction(reset_action)

        menu.addSeparator()

        # EIC action
        eic_action = QAction(f"Extract EIC at m/z {mz:.4f}", self)
        eic_action.triggered.connect(lambda: self.eic_requested.emit(mz))
        menu.addAction(eic_action)

        # If near a peak, add peak-specific actions
        peak_idx = self._find_nearest_peak(mz)
        if peak_idx is not None:
            peak = self._spectrum.mspeaks[peak_idx]
            menu.addSeparator()

            assign_action = QAction(f"Assign formula to peak {peak.mz_exp:.4f}", self)
            assign_action.triggered.connect(lambda: self.assign_requested.emit(peak_idx))
            menu.addAction(assign_action)

            # Isotopologue action
            isotope_action = QAction(f"Show isotopologues for {peak.mz_exp:.4f}", self)
            isotope_action.triggered.connect(lambda: self._show_isotopologue_dialog(peak.mz_exp))
            menu.addAction(isotope_action)

            # Show peak info
            info_text = f"m/z: {peak.mz_exp:.4f}, Int: {peak.abundance:.2e}"
            if hasattr(peak, 'signal_to_noise') and peak.signal_to_noise:
                info_text += f", S/N: {peak.signal_to_noise:.1f}"
            info_action = QAction(info_text, self)
            info_action.setEnabled(False)
            menu.addAction(info_action)

            # Show measured (uncalibrated) m/z if peak has been calibrated
            if hasattr(peak, 'mz_cal') and peak.mz_cal is not None:
                # _mz_exp holds the original measured value before calibration
                # mz_exp property returns mz_cal after calibration
                measured_mz = peak._mz_exp
                calibrated_mz = peak.mz_cal
                delta_ppm = ((calibrated_mz - measured_mz) / calibrated_mz) * 1e6
                measured_action = QAction(f"Measured m/z: {measured_mz:.6f} ({delta_ppm:+.2f} ppm)", self)
                measured_action.setEnabled(False)
                menu.addAction(measured_action)
        else:
            # Allow isotopologue selection at any m/z position
            menu.addSeparator()
            isotope_action = QAction(f"Show isotopologues at m/z {mz:.4f}", self)
            isotope_action.triggered.connect(lambda: self._show_isotopologue_dialog(mz))
            menu.addAction(isotope_action)

        # Clear isotopologues action (if any are shown)
        if self.isotope_markers:
            menu.addSeparator()
            clear_isotopes_action = QAction("Clear isotopologue markers", self)
            clear_isotopes_action.triggered.connect(self.clear_isotope_markers)
            menu.addAction(clear_isotopes_action)

        menu.exec(self.plot_widget.mapToGlobal(pos))

    def _find_nearest_peak(self, mz: float, tolerance_ppm: float = 50.0) -> Optional[int]:
        """Find the peak nearest to a m/z value.

        Args:
            mz: Target m/z
            tolerance_ppm: Maximum distance in ppm

        Returns:
            Peak index or None if no peak within tolerance
        """
        if self._spectrum is None or not hasattr(self._spectrum, 'mspeaks'):
            return None

        if len(self._spectrum.mspeaks) == 0:
            return None

        peak_mzs = np.array([p.mz_exp for p in self._spectrum.mspeaks])
        distances = np.abs(peak_mzs - mz) / mz * 1e6  # ppm

        min_idx = np.argmin(distances)
        if distances[min_idx] < tolerance_ppm:
            return int(min_idx)
        return None

    def _intensity_at_mz(self, mz: float) -> Optional[float]:
        """Get intensity at a m/z value (interpolated from profile)."""
        if self._spectrum is None:
            return None

        try:
            mz_profile = self._spectrum.mz_exp_profile
            abund_profile = self._spectrum.abundance_profile

            # Find nearest point
            idx = np.argmin(np.abs(np.array(mz_profile) - mz))
            return abund_profile[idx]
        except:
            return None

    def _update_peak_labels(self, _=None):
        """Update peak labels display based on selected options."""
        # Clear existing labels
        for label in self.peak_labels:
            self.plot_widget.removeItem(label)
        self.peak_labels.clear()

        if self._spectrum is None:
            return

        if not hasattr(self._spectrum, 'mspeaks') or len(self._spectrum.mspeaks) == 0:
            print(f"No peaks to label (mspeaks count: {len(self._spectrum.mspeaks) if hasattr(self._spectrum, 'mspeaks') else 0})")
            return

        # Check if any label option is selected
        show_mz = self.labels_checkbox.isChecked()
        show_sn = self.sn_checkbox.isChecked()
        show_rp = self.rp_checkbox.isChecked()

        if not (show_mz or show_sn or show_rp):
            return

        # Get visible range to only label peaks in view
        view_range = self.plot_widget.viewRange()
        mz_min, mz_max = view_range[0]

        # Limit number of labels to avoid clutter (show top peaks by abundance)
        visible_peaks = [(i, p) for i, p in enumerate(self._spectrum.mspeaks)
                         if mz_min <= p.mz_exp <= mz_max]

        # Sort by abundance and take top 50
        visible_peaks.sort(key=lambda x: x[1].abundance, reverse=True)
        visible_peaks = visible_peaks[:50]

        print(f"Labeling {len(visible_peaks)} peaks (mz range: {mz_min:.2f}-{mz_max:.2f}, show_mz={show_mz}, show_sn={show_sn}, show_rp={show_rp})")

        # Add labels for peaks
        labels_added = 0
        for i, peak in visible_peaks:
            # Build label text with selected info
            parts = []

            if show_mz:
                # Show m/z with 5 decimal places
                parts.append(f"{peak.mz_exp:.5f}")

            if show_sn:
                # Show signal-to-noise ratio
                sn = getattr(peak, 'signal_to_noise', None)
                if sn is not None and sn > 0:
                    parts.append(f"S/N:{sn:.0f}")

            if show_rp:
                # Show resolving power
                rp = getattr(peak, 'resolving_power', None)
                if rp is not None and rp > 0:
                    if rp >= 1000:
                        parts.append(f"RP:{rp/1000:.1f}k")
                    else:
                        parts.append(f"RP:{rp:.0f}")

            if not parts:
                continue

            text = "\n".join(parts)

            label = pg.TextItem(
                text=text,
                color='k',
                anchor=(0.5, 1),
                angle=0  # Horizontal for better readability with multiple lines
            )
            label.setPos(peak.mz_exp, peak.abundance)
            self.plot_widget.addItem(label)
            self.peak_labels.append(label)
            labels_added += 1

        print(f"Added {labels_added} peak labels")

    def set_spectrum(self, spectrum):
        """Set and display a mass spectrum.

        Args:
            spectrum: MassSpectrum object from CoreMS
        """
        self._spectrum = spectrum
        self._highlighted_peak = None

        if spectrum is None:
            self.clear()
            return

        # Plot profile data
        try:
            mz = spectrum.mz_exp_profile
            abundance = spectrum.abundance_profile
            self.profile_curve.setData(mz, abundance)
        except Exception:
            # May be centroid-only spectrum
            self.profile_curve.clear()

        # Check if spectrum is already processed (has peaks)
        has_peaks = hasattr(spectrum, 'mspeaks') and len(spectrum.mspeaks) > 0
        self._enable_processing_options(has_peaks)

        # Plot peaks if available
        self._update_peaks_display()

        # Hide noise line and uncheck processing boxes for unprocessed spectrum
        if not has_peaks:
            self.labels_checkbox.setChecked(False)
            self.sn_checkbox.setChecked(False)
            self.rp_checkbox.setChecked(False)
            self.noise_checkbox.setChecked(False)
            self.noise_line.setVisible(False)

        # Auto-range
        self.plot_widget.autoRange()

    def _update_peaks_display(self):
        """Update the peaks scatter plot."""
        self.peaks_scatter.clear()
        self.highlight_scatter.clear()

        if self._spectrum is None or not hasattr(self._spectrum, 'mspeaks'):
            return

        if len(self._spectrum.mspeaks) == 0:
            return

        peak_mz = [p.mz_exp for p in self._spectrum.mspeaks]
        peak_abund = [p.abundance for p in self._spectrum.mspeaks]

        # Color based on assignment status
        brushes = []
        for peak in self._spectrum.mspeaks:
            if peak.is_assigned:
                brushes.append(pg.mkBrush('#4CAF50'))  # Green for assigned
            else:
                brushes.append(pg.mkBrush('#F44336'))  # Red for unassigned

        self.peaks_scatter.setData(
            peak_mz, peak_abund,
            brush=brushes,
            pen=pg.mkPen('k', width=0.5)
        )

        # Show legend if there are any assigned peaks
        has_assigned = any(p.is_assigned for p in self._spectrum.mspeaks)
        self.peak_legend.setVisible(has_assigned)

        # Update labels
        self._update_peak_labels()

    def highlight_peak(self, peak_index: int):
        """Highlight a specific peak.

        Args:
            peak_index: Index of peak to highlight
        """
        self._highlighted_peak = peak_index

        if self._spectrum is None or not hasattr(self._spectrum, 'mspeaks'):
            return

        if peak_index < 0 or peak_index >= len(self._spectrum.mspeaks):
            self.highlight_scatter.clear()
            return

        peak = self._spectrum.mspeaks[peak_index]
        self.highlight_scatter.setData([peak.mz_exp], [peak.abundance])

    def zoom_to_mz(self, mz: float, window: float = 2.0):
        """Zoom the view to center on a m/z value.

        Args:
            mz: Center m/z value
            window: Width of view in m/z units
        """
        self.plot_widget.setXRange(mz - window/2, mz + window/2)

    def zoom_to_peak(self, peak_index: int, window: float = 2.0):
        """Zoom to a specific peak.

        Args:
            peak_index: Index of peak to zoom to
            window: Width of view in m/z units
        """
        if self._spectrum is None or not hasattr(self._spectrum, 'mspeaks'):
            return

        if peak_index < 0 or peak_index >= len(self._spectrum.mspeaks):
            return

        peak = self._spectrum.mspeaks[peak_index]
        self.zoom_to_mz(peak.mz_exp, window)
        self.highlight_peak(peak_index)

    def get_visible_range(self) -> Tuple[float, float]:
        """Get the current visible m/z range.

        Returns:
            Tuple of (min_mz, max_mz)
        """
        view_range = self.plot_widget.viewRange()
        return (view_range[0][0], view_range[0][1])

    def reset_zoom(self):
        """Reset zoom to show the full spectrum."""
        self.plot_widget.autoRange()

    def refresh_peaks(self):
        """Refresh the peaks display after processing."""
        self._update_peaks_display()
        # Enable processing-dependent controls now that peaks are available
        self._enable_processing_options(True)
        # Also update noise line since processing calculates noise values
        if self.noise_checkbox.isChecked():
            self._update_noise_line()

    def _enable_processing_options(self, enabled: bool):
        """Enable or disable controls that require a processed spectrum."""
        self.labels_checkbox.setEnabled(enabled)
        self.sn_checkbox.setEnabled(enabled)
        self.rp_checkbox.setEnabled(enabled)
        self.noise_checkbox.setEnabled(enabled)

    # ===== Isotopologue Methods =====

    def _show_isotopologue_dialog(self, base_mz: float):
        """Show dialog for selecting isotopologues to visualize.

        Args:
            base_mz: The m/z value of the selected peak
        """
        from hrms_viewer.dialogs.isotopologue_dialog import IsotopologueDialog

        dialog = IsotopologueDialog(base_mz, parent=self)
        dialog.isotopes_selected.connect(
            lambda isotopes: self.show_isotope_markers(base_mz, isotopes)
        )
        dialog.exec()

    def show_isotope_markers(self, base_mz: float, isotopes: List[Tuple], show_intensities: bool = True):
        """Show vertical markers at predicted isotopologue positions.

        Args:
            base_mz: The m/z of the monoisotopic peak
            isotopes: List of tuples:
                - (name, mass_shift, rel_intensity) or
                - (name, mass_shift, rel_intensity, is_selected)
                The is_selected flag indicates which isotopologue was originally selected
            show_intensities: If True and intensities are provided, show intensity bars
        """
        # Clear existing markers
        self.clear_isotope_markers()

        if not isotopes:
            return

        self._isotope_base_mz = base_mz
        # Store isotope data for label position updates
        self._isotope_data = isotopes

        # Color palette for different isotope markers
        self._isotope_colors = [
            '#E91E63',  # Pink
            '#9C27B0',  # Purple
            '#673AB7',  # Deep Purple
            '#3F51B5',  # Indigo
            '#2196F3',  # Blue
            '#00BCD4',  # Cyan
            '#009688',  # Teal
            '#4CAF50',  # Green
            '#8BC34A',  # Light Green
            '#CDDC39',  # Lime
        ]

        # Check if we have intensity and selection information
        has_intensities = len(isotopes) > 0 and len(isotopes[0]) >= 3
        has_selection = len(isotopes) > 0 and len(isotopes[0]) >= 4

        # Check if the monoisotopic peak is selected (no isotopologue has is_selected=True)
        mono_is_selected = True
        if has_selection:
            mono_is_selected = not any(iso[3] for iso in isotopes if len(iso) >= 4)

        # Find the max intensity in actual spectrum data near these m/z values for scaling
        max_spectrum_intensity = self._get_max_intensity_in_range(base_mz, isotopes)

        # Add marker for base peak (M, monoisotopic)
        # Use thicker line and different style if selected
        if mono_is_selected:
            base_pen = pg.mkPen('#FF5722', width=3, style=Qt.PenStyle.SolidLine)  # Orange, solid, thick
            base_color = '#FF5722'
            base_label_prefix = "★ "  # Star to indicate selected
        else:
            base_pen = pg.mkPen('#000000', width=2, style=Qt.PenStyle.DashLine)
            base_color = 'k'
            base_label_prefix = ""

        base_line = pg.InfiniteLine(
            pos=base_mz,
            angle=90,
            pen=base_pen,
            movable=False
        )
        self.plot_widget.addItem(base_line)
        self.isotope_markers.append(base_line)

        # Add label for base peak
        base_label = pg.TextItem(
            text=f"{base_label_prefix}M\n{base_mz:.4f}\n100%",
            color=base_color,
            anchor=(0.5, 0)  # Anchor at top-center so text extends downward
        )
        self.plot_widget.addItem(base_label)
        self.isotope_labels.append(base_label)
        # Store mz for position updates (key=0 for custom data)
        base_label.setData(0, base_mz)

        # Add markers for each isotopologue
        for i, isotope_data in enumerate(isotopes):
            name = isotope_data[0]
            mass_shift = isotope_data[1]
            rel_intensity = isotope_data[2] if has_intensities else None
            is_selected = isotope_data[3] if has_selection and len(isotope_data) >= 4 else False

            isotope_mz = base_mz + mass_shift

            # Use different styling for selected isotopologue
            if is_selected:
                color = '#FF5722'  # Orange for selected
                line_width = 3
                line_style = Qt.PenStyle.SolidLine
                label_prefix = "★ "  # Star to indicate selected
            else:
                color = self._isotope_colors[i % len(self._isotope_colors)]
                line_width = 2
                line_style = Qt.PenStyle.DashLine
                label_prefix = ""

            # Create vertical line marker
            line = pg.InfiniteLine(
                pos=isotope_mz,
                angle=90,
                pen=pg.mkPen(color, width=line_width, style=line_style),
                movable=False
            )
            self.plot_widget.addItem(line)
            self.isotope_markers.append(line)

            # Create label with intensity and m/z
            if rel_intensity is not None:
                label_text = f"{label_prefix}{name}\n{isotope_mz:.4f}\n{rel_intensity*100:.1f}%"
            else:
                label_text = f"{label_prefix}{name}\n{isotope_mz:.4f}"

            label = pg.TextItem(
                text=label_text,
                color=color,
                anchor=(0.5, 0)  # Anchor at top-center so text extends downward
            )
            self.plot_widget.addItem(label)
            self.isotope_labels.append(label)
            # Store mz for position updates (key=0 for custom data)
            label.setData(0, isotope_mz)

            # If intensities provided, add a bar showing expected relative intensity
            if has_intensities and rel_intensity is not None and show_intensities and max_spectrum_intensity > 0:
                # Scale bar height relative to max spectrum intensity
                bar_height = max_spectrum_intensity * min(rel_intensity, 1.0)
                bar_width = 8 if is_selected else 6
                bar = pg.PlotDataItem(
                    [isotope_mz, isotope_mz],
                    [0, bar_height],
                    pen=pg.mkPen(color, width=bar_width, style=Qt.PenStyle.SolidLine)
                )
                self.plot_widget.addItem(bar)
                self.isotope_markers.append(bar)

        # Update label positions to be at top of current view
        self._update_isotope_label_positions()

        print(f"Showing {len(isotopes)} isotopologue markers for m/z {base_mz:.5f}")

    def _get_max_intensity_in_range(self, base_mz: float, isotopes: List[Tuple]) -> float:
        """Get the maximum spectrum intensity in the range of isotopologue peaks."""
        if self._spectrum is None:
            return 1.0

        # Find the m/z range we're interested in
        if isotopes:
            max_shift = max(iso[1] for iso in isotopes)
            min_shift = min(iso[1] for iso in isotopes) if isotopes else 0
        else:
            max_shift = 5.0
            min_shift = 0

        mz_min = base_mz + min_shift - 0.5
        mz_max = base_mz + max_shift + 0.5

        # Get max intensity from spectrum data in this range
        if hasattr(self._spectrum, 'mz_exp') and hasattr(self._spectrum, 'abundance'):
            mz_array = self._spectrum.mz_exp
            abund_array = self._spectrum.abundance
            mask = (mz_array >= mz_min) & (mz_array <= mz_max)
            if mask.any():
                return float(abund_array[mask].max())

        return 1.0

    def _update_isotope_label_positions(self):
        """Update isotopologue label positions to stay at top of current view."""
        if not self.isotope_labels:
            return

        # Get current view range
        view_range = self.plot_widget.viewRange()
        y_top = view_range[1][1] * 0.95  # Position at 95% of view height

        # Update each label position
        for label in self.isotope_labels:
            mz = label.data(0)  # Retrieve stored m/z (key=0)
            if mz is not None:
                label.setPos(mz, y_top)

    def clear_isotope_markers(self):
        """Remove all isotopologue markers from the plot."""
        for marker in self.isotope_markers:
            self.plot_widget.removeItem(marker)
        self.isotope_markers.clear()

        for label in self.isotope_labels:
            self.plot_widget.removeItem(label)
        self.isotope_labels.clear()

        self._isotope_base_mz = None
        self._isotope_data = []
        self._isotope_colors = []

    def clear(self):
        """Clear all data and reset the widget."""
        self._spectrum = None
        self._highlighted_peak = None

        self.profile_curve.clear()
        self.peaks_scatter.clear()
        self.highlight_scatter.clear()

        for label in self.peak_labels:
            self.plot_widget.removeItem(label)
        self.peak_labels.clear()

        # Clear isotope markers
        self.clear_isotope_markers()

        # Hide the peak legend
        self.peak_legend.setVisible(False)

        # Disable and reset processing-dependent controls
        self._enable_processing_options(False)
        self.labels_checkbox.setChecked(False)
        self.sn_checkbox.setChecked(False)
        self.rp_checkbox.setChecked(False)
        self.noise_checkbox.setChecked(False)
        self.noise_line.setVisible(False)

        self.info_label.setText("")
