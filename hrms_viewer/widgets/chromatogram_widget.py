"""Chromatogram widget for TIC/BPC display using PyQtGraph."""

from typing import Optional, Tuple
import numpy as np
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QCheckBox, QLabel, QPushButton
from PyQt6.QtCore import pyqtSignal, Qt
import pyqtgraph as pg


class ChromatogramWidget(QWidget):
    """TIC/BPC chromatogram viewer using PyQtGraph.

    Signals:
        scan_clicked: Emitted when user clicks to select a scan (scan number)
        range_selected: Emitted when user selects a time range (start_scan, end_scan)
        time_hovered: Emitted when mouse hovers over plot (time, intensity)
    """

    scan_clicked = pyqtSignal(int)
    range_selected = pyqtSignal(int, int)
    time_hovered = pyqtSignal(float, float)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)

        self._tic_data = None
        self._bpc_data = None
        self._current_scan: Optional[int] = None

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

        self.tic_checkbox = QCheckBox("TIC")
        self.tic_checkbox.setChecked(True)
        self.bpc_checkbox = QCheckBox("BPC")
        self.bpc_checkbox.setChecked(False)

        self.select_range_btn = QPushButton("Select Range")
        self.select_range_btn.setFixedWidth(90)
        self.select_range_btn.setToolTip("Click to show range selector, click again to average selected scans")

        self.info_label = QLabel("")
        self.info_label.setStyleSheet("color: gray; font-size: 10px;")

        controls.addWidget(self.tic_checkbox)
        controls.addWidget(self.bpc_checkbox)
        controls.addWidget(self.select_range_btn)
        controls.addStretch()
        controls.addWidget(self.info_label)

        layout.addLayout(controls)

        # PyQtGraph plot widget
        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setBackground('w')
        self.plot_widget.setLabel('left', 'Intensity')
        self.plot_widget.setLabel('bottom', 'Time', units='min')
        self.plot_widget.showGrid(x=True, y=True, alpha=0.3)

        # Enable mouse interaction
        self.plot_widget.setMouseEnabled(x=True, y=True)

        layout.addWidget(self.plot_widget)

        # Create plot items - thicker lines for visibility
        self.tic_curve = self.plot_widget.plot(
            pen=pg.mkPen('#2196F3', width=2.5),
            name='TIC'
        )
        self.bpc_curve = self.plot_widget.plot(
            pen=pg.mkPen('#4CAF50', width=2.5),
            name='BPC'
        )
        self.bpc_curve.setVisible(False)

        # Current scan indicator (vertical line)
        self.scan_line = pg.InfiniteLine(
            pos=0,
            angle=90,
            pen=pg.mkPen('#F44336', width=2, style=Qt.PenStyle.DashLine),
            movable=False
        )
        self.scan_line.setVisible(False)
        self.plot_widget.addItem(self.scan_line)

        # Region selector for time range - thick handles for easier grabbing
        self.region_selector = pg.LinearRegionItem(
            values=[0, 1],
            brush=pg.mkBrush(100, 100, 200, 50),
            pen=pg.mkPen('#3F51B5', width=3),
            movable=True,
            hoverPen=pg.mkPen('#3F51B5', width=5),
        )
        # Make the region lines thicker and easier to grab
        for line in self.region_selector.lines:
            line.setPen(pg.mkPen('#3F51B5', width=4))
            line.setHoverPen(pg.mkPen('#1A237E', width=6))
        self.region_selector.setVisible(False)
        self.plot_widget.addItem(self.region_selector)

        # Crosshair for hover position
        self.vLine = pg.InfiniteLine(angle=90, movable=False, pen=pg.mkPen('gray', width=1))
        self.hLine = pg.InfiniteLine(angle=0, movable=False, pen=pg.mkPen('gray', width=1))
        self.vLine.setVisible(False)
        self.hLine.setVisible(False)
        self.plot_widget.addItem(self.vLine, ignoreBounds=True)
        self.plot_widget.addItem(self.hLine, ignoreBounds=True)

    def _connect_signals(self):
        """Connect internal signals."""
        self.tic_checkbox.toggled.connect(self._on_tic_toggled)
        self.bpc_checkbox.toggled.connect(self._on_bpc_toggled)
        self.select_range_btn.clicked.connect(self._on_select_range_clicked)

        # Mouse click for scan selection
        self.plot_widget.scene().sigMouseClicked.connect(self._on_mouse_clicked)

        # Mouse move for crosshair
        self.plot_widget.scene().sigMouseMoved.connect(self._on_mouse_moved)

        # Region changed
        self.region_selector.sigRegionChangeFinished.connect(self._on_region_changed)

    def _on_tic_toggled(self, checked: bool):
        """Handle TIC checkbox toggle."""
        self.tic_curve.setVisible(checked)

    def _on_bpc_toggled(self, checked: bool):
        """Handle BPC checkbox toggle."""
        self.bpc_curve.setVisible(checked)

    def _on_select_range_clicked(self):
        """Handle Select Range button click."""
        if self._tic_data is None:
            return

        if self.region_selector.isVisible():
            # If already visible, emit the range and hide
            region = self.region_selector.getRegion()
            start_scan = self._scan_from_time(region[0])
            end_scan = self._scan_from_time(region[1])
            if start_scan is not None and end_scan is not None:
                self.range_selected.emit(min(start_scan, end_scan), max(start_scan, end_scan))
            self.region_selector.setVisible(False)
            self.select_range_btn.setText("Select Range")
        else:
            # Block signals while setting initial region to prevent premature dialog
            self.region_selector.blockSignals(True)

            # Show region selector in center of current view
            view_range = self.plot_widget.viewRange()
            center = (view_range[0][0] + view_range[0][1]) / 2
            width = (view_range[0][1] - view_range[0][0]) * 0.2
            self.region_selector.setRegion([center - width/2, center + width/2])
            self.region_selector.setVisible(True)
            self.select_range_btn.setText("Average")

            # Re-enable signals
            self.region_selector.blockSignals(False)

    def _on_mouse_clicked(self, event):
        """Handle mouse click on plot."""
        if self._tic_data is None:
            return

        pos = event.scenePos()
        if not self.plot_widget.sceneBoundingRect().contains(pos):
            return

        # Map to plot coordinates
        mouse_point = self.plot_widget.plotItem.vb.mapSceneToView(pos)
        time = mouse_point.x()

        # Find closest scan
        scan = self._scan_from_time(time)
        if scan is not None:
            # Check if right-click (for range selection mode)
            if event.button() == Qt.MouseButton.RightButton:
                self._show_region_selector(time)
            else:
                self.set_current_scan(scan)
                self.scan_clicked.emit(scan)

    def _on_mouse_moved(self, pos):
        """Handle mouse move for crosshair update."""
        if self._tic_data is None:
            return

        if self.plot_widget.sceneBoundingRect().contains(pos):
            mouse_point = self.plot_widget.plotItem.vb.mapSceneToView(pos)
            time = mouse_point.x()

            # Update crosshair position
            self.vLine.setPos(time)
            self.vLine.setVisible(True)

            # Get intensity at this position
            intensity = self._intensity_at_time(time)
            if intensity is not None:
                self.hLine.setPos(intensity)
                self.hLine.setVisible(True)
                self.info_label.setText(f"Time: {time:.2f} min, Int: {intensity:.2e}")
                self.time_hovered.emit(time, intensity)
        else:
            self.vLine.setVisible(False)
            self.hLine.setVisible(False)
            self.info_label.setText("")

    def _on_region_changed(self):
        """Handle region selection changed - update info display only."""
        if self._tic_data is None:
            return

        region = self.region_selector.getRegion()
        start_time, end_time = region

        # Update info label to show selected range
        n_scans = 0
        start_scan = self._scan_from_time(start_time)
        end_scan = self._scan_from_time(end_time)
        if start_scan is not None and end_scan is not None:
            n_scans = abs(end_scan - start_scan) + 1

        self.info_label.setText(f"Range: {start_time:.2f} - {end_time:.2f} min ({n_scans} scans)")

    def _scan_from_time(self, time: float) -> Optional[int]:
        """Find closest scan number to a time value."""
        if self._tic_data is None:
            return None

        times = np.array(self._tic_data.time)
        idx = np.argmin(np.abs(times - time))
        return self._tic_data.scans[idx]

    def _time_from_scan(self, scan: int) -> Optional[float]:
        """Get time for a scan number."""
        if self._tic_data is None:
            return None

        try:
            idx = self._tic_data.scans.index(scan)
            return self._tic_data.time[idx]
        except ValueError:
            return None

    def _intensity_at_time(self, time: float) -> Optional[float]:
        """Get intensity at a time value."""
        if self._tic_data is None:
            return None

        try:
            if self.tic_checkbox.isChecked():
                times = np.array(self._tic_data.time)
                idx = np.argmin(np.abs(times - time))
                if 0 <= idx < len(self._tic_data.tic):
                    return self._tic_data.tic[idx]
            elif self._bpc_data is not None:
                times = np.array(self._bpc_data.time)
                idx = np.argmin(np.abs(times - time))
                if 0 <= idx < len(self._bpc_data.tic):
                    return self._bpc_data.tic[idx]
        except (IndexError, ValueError):
            pass
        return None

    def _show_region_selector(self, center_time: float):
        """Show the region selector centered at a time."""
        if self._tic_data is None:
            return

        # Set region to 10% of total time range, centered at click
        times = self._tic_data.time
        total_range = max(times) - min(times)
        width = total_range * 0.1

        self.region_selector.setRegion([center_time - width/2, center_time + width/2])
        self.region_selector.setVisible(True)

    def set_tic_data(self, tic_data):
        """Set TIC data and update plot.

        Args:
            tic_data: TIC_Data object from CoreMS
        """
        self._tic_data = tic_data

        if tic_data is not None:
            self.tic_curve.setData(tic_data.time, tic_data.tic)
            self.plot_widget.autoRange()

    def set_bpc_data(self, bpc_data):
        """Set BPC data and update plot.

        Args:
            bpc_data: TIC_Data object from CoreMS (containing BPC)
        """
        self._bpc_data = bpc_data

        if bpc_data is not None:
            # Note: BPC is stored in the 'tic' attribute of BPC-type TIC_Data
            self.bpc_curve.setData(bpc_data.time, bpc_data.tic)

    def set_current_scan(self, scan: int):
        """Set and display the current scan indicator.

        Args:
            scan: Scan number to highlight
        """
        self._current_scan = scan
        time = self._time_from_scan(scan)

        if time is not None:
            self.scan_line.setPos(time)
            self.scan_line.setVisible(True)

    def get_selected_range(self) -> Optional[Tuple[int, int]]:
        """Get the currently selected scan range.

        Returns:
            Tuple of (start_scan, end_scan) or None if no selection
        """
        if not self.region_selector.isVisible() or self._tic_data is None:
            return None

        region = self.region_selector.getRegion()
        start_scan = self._scan_from_time(region[0])
        end_scan = self._scan_from_time(region[1])

        if start_scan is not None and end_scan is not None:
            return (min(start_scan, end_scan), max(start_scan, end_scan))
        return None

    def show_region_selector(self, visible: bool = True):
        """Show or hide the region selector.

        Args:
            visible: Whether to show the selector
        """
        self.region_selector.setVisible(visible)

    def clear(self):
        """Clear all data and reset the widget."""
        self._tic_data = None
        self._bpc_data = None
        self._current_scan = None

        self.tic_curve.clear()
        self.bpc_curve.clear()
        self.scan_line.setVisible(False)
        self.region_selector.setVisible(False)
        self.info_label.setText("")
