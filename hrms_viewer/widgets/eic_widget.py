"""EIC (Extracted Ion Chromatogram) widget for displaying overlaid EICs."""

from typing import Optional, Dict
import numpy as np
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QListWidget, QListWidgetItem, QColorDialog
)
from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtGui import QColor
import pyqtgraph as pg


class EICWidget(QWidget):
    """EIC overlay viewer using PyQtGraph.

    Displays multiple extracted ion chromatograms overlaid on the same plot,
    with a legend showing the m/z values and colors.

    Signals:
        eic_clicked: Emitted when an EIC is clicked (m/z value)
        eic_removed: Emitted when an EIC is removed (m/z value)
        time_clicked: Emitted when user clicks on the plot (time in minutes)
    """

    eic_clicked = pyqtSignal(float)
    eic_removed = pyqtSignal(float)
    time_clicked = pyqtSignal(float)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)

        # Store EIC data and curves
        self._eics: Dict[float, object] = {}  # m/z -> EIC_Data
        self._curves: Dict[float, pg.PlotDataItem] = {}  # m/z -> curve
        self._colors: Dict[float, str] = {}  # m/z -> color

        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        """Set up the widget UI."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Left side: plot
        plot_layout = QVBoxLayout()

        # Title
        title = QLabel("Extracted Ion Chromatograms")
        title.setStyleSheet("font-weight: bold;")
        plot_layout.addWidget(title)

        # PyQtGraph plot widget
        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setBackground('w')
        self.plot_widget.setLabel('left', 'Intensity')
        self.plot_widget.setLabel('bottom', 'Time', units='min')
        self.plot_widget.showGrid(x=True, y=True, alpha=0.3)
        self.plot_widget.addLegend()

        plot_layout.addWidget(self.plot_widget)
        layout.addLayout(plot_layout, stretch=3)

        # Right side: EIC list
        list_layout = QVBoxLayout()

        list_label = QLabel("Active EICs")
        list_label.setStyleSheet("font-weight: bold;")
        list_layout.addWidget(list_label)

        self.eic_list = QListWidget()
        self.eic_list.setMaximumWidth(150)
        list_layout.addWidget(self.eic_list)

        # Buttons
        btn_layout = QHBoxLayout()

        self.clear_btn = QPushButton("Clear All")
        self.clear_btn.clicked.connect(self.clear_all)
        btn_layout.addWidget(self.clear_btn)

        self.remove_btn = QPushButton("Remove")
        self.remove_btn.clicked.connect(self._remove_selected)
        btn_layout.addWidget(self.remove_btn)

        list_layout.addLayout(btn_layout)
        layout.addLayout(list_layout, stretch=1)

        # Crosshair for hover
        self.vLine = pg.InfiniteLine(angle=90, movable=False, pen=pg.mkPen('gray', width=1))
        self.vLine.setVisible(False)
        self.plot_widget.addItem(self.vLine, ignoreBounds=True)

    def _connect_signals(self):
        """Connect internal signals."""
        # Mouse click on plot
        self.plot_widget.scene().sigMouseClicked.connect(self._on_mouse_clicked)

        # Mouse move for crosshair
        self.plot_widget.scene().sigMouseMoved.connect(self._on_mouse_moved)

        # List selection
        self.eic_list.itemDoubleClicked.connect(self._on_item_double_clicked)

    def _on_mouse_clicked(self, event):
        """Handle mouse click on plot."""
        pos = event.scenePos()
        if not self.plot_widget.sceneBoundingRect().contains(pos):
            return

        if event.button() != Qt.MouseButton.LeftButton:
            return

        # Map to plot coordinates
        mouse_point = self.plot_widget.plotItem.vb.mapSceneToView(pos)
        time = mouse_point.x()

        self.time_clicked.emit(time)

    def _on_mouse_moved(self, pos):
        """Handle mouse move for crosshair update."""
        if self.plot_widget.sceneBoundingRect().contains(pos):
            mouse_point = self.plot_widget.plotItem.vb.mapSceneToView(pos)
            self.vLine.setPos(mouse_point.x())
            self.vLine.setVisible(True)
        else:
            self.vLine.setVisible(False)

    def _on_item_double_clicked(self, item: QListWidgetItem):
        """Handle double-click on list item to change color."""
        mz = item.data(Qt.ItemDataRole.UserRole)
        if mz is None:
            return

        current_color = QColor(self._colors.get(mz, "#FF0000"))
        new_color = QColorDialog.getColor(current_color, self, f"Color for m/z {mz:.4f}")

        if new_color.isValid():
            self._update_color(mz, new_color.name())

    def _remove_selected(self):
        """Remove the selected EIC from the list."""
        current = self.eic_list.currentItem()
        if current:
            mz = current.data(Qt.ItemDataRole.UserRole)
            if mz is not None:
                self.remove_eic(mz)

    def _update_color(self, mz: float, color: str):
        """Update the color of an EIC.

        Args:
            mz: Target m/z
            color: New hex color string
        """
        self._colors[mz] = color

        # Update curve
        if mz in self._curves:
            self._curves[mz].setPen(pg.mkPen(color, width=1.5))

        # Update list item
        for i in range(self.eic_list.count()):
            item = self.eic_list.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == mz:
                item.setForeground(QColor(color))
                break

    def add_eic(self, mz: float, eic_data, color: str = "#FF0000"):
        """Add an EIC to the display.

        Args:
            mz: Target m/z value
            eic_data: EIC_Data object from CoreMS
            color: Hex color string for plotting
        """
        # Remove existing if present
        if mz in self._eics:
            self.remove_eic(mz)

        self._eics[mz] = eic_data
        self._colors[mz] = color

        # Create curve
        curve = self.plot_widget.plot(
            eic_data.time,
            eic_data.eic,
            pen=pg.mkPen(color, width=1.5),
            name=f"m/z {mz:.4f}"
        )
        self._curves[mz] = curve

        # Add to list
        item = QListWidgetItem(f"m/z {mz:.4f}")
        item.setData(Qt.ItemDataRole.UserRole, mz)
        item.setForeground(QColor(color))
        self.eic_list.addItem(item)

    def remove_eic(self, mz: float):
        """Remove an EIC from the display.

        Args:
            mz: Target m/z value to remove
        """
        if mz not in self._eics:
            return

        # Remove curve
        if mz in self._curves:
            self.plot_widget.removeItem(self._curves[mz])
            del self._curves[mz]

        # Remove from dictionaries
        del self._eics[mz]
        if mz in self._colors:
            del self._colors[mz]

        # Remove from list
        for i in range(self.eic_list.count()):
            item = self.eic_list.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == mz:
                self.eic_list.takeItem(i)
                break

        self.eic_removed.emit(mz)

    def clear_all(self):
        """Remove all EICs."""
        mz_list = list(self._eics.keys())
        for mz in mz_list:
            self.remove_eic(mz)

    def set_time_range(self, start: float, end: float):
        """Set the visible time range.

        Args:
            start: Start time in minutes
            end: End time in minutes
        """
        self.plot_widget.setXRange(start, end)

    def has_eics(self) -> bool:
        """Check if any EICs are displayed."""
        return len(self._eics) > 0

    def get_eic_mzs(self):
        """Get list of displayed m/z values."""
        return list(self._eics.keys())
