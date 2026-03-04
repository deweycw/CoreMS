"""Peak table widget for displaying detected peaks and assignments."""

from typing import Optional, List, Any
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableView, QHeaderView,
    QPushButton, QCheckBox, QLabel, QLineEdit, QFileDialog,
    QAbstractItemView, QMenu
)
from PyQt6.QtCore import (
    Qt, pyqtSignal, QAbstractTableModel, QModelIndex,
    QSortFilterProxyModel
)
from PyQt6.QtGui import QColor, QAction
import csv


class PeakTableModel(QAbstractTableModel):
    """Table model for MS peaks.

    Displays peak data with columns for m/z, abundance, S/N,
    resolving power, assignment status, and molecular formula.
    """

    COLUMNS = [
        ("Index", "index"),
        ("m/z", "mz"),
        ("Abundance", "abundance"),
        ("S/N", "sn"),
        ("RP", "rp"),
        ("Assigned", "assigned"),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._peaks: List = []
        self._spectrum = None

    def set_peaks(self, spectrum):
        """Set peaks from a spectrum.

        Args:
            spectrum: MassSpectrum object with mspeaks attribute
        """
        self.beginResetModel()
        self._spectrum = spectrum

        if spectrum is not None and hasattr(spectrum, 'mspeaks'):
            self._peaks = list(spectrum.mspeaks)
        else:
            self._peaks = []

        self.endResetModel()

    def rowCount(self, parent=QModelIndex()) -> int:
        return len(self._peaks)

    def columnCount(self, parent=QModelIndex()) -> int:
        return len(self.COLUMNS)

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return self.COLUMNS[section][0]
        return None

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid() or index.row() >= len(self._peaks):
            return None

        peak = self._peaks[index.row()]
        col_key = self.COLUMNS[index.column()][1]

        if role == Qt.ItemDataRole.DisplayRole:
            return self._get_display_value(peak, col_key, index.row())

        elif role == Qt.ItemDataRole.BackgroundRole:
            if col_key == "assigned":
                if peak.is_assigned:
                    return QColor(200, 255, 200)  # Light green
                else:
                    return QColor(255, 220, 220)  # Light red

        elif role == Qt.ItemDataRole.TextAlignmentRole:
            if col_key in ["mz", "abundance", "sn", "rp", "error"]:
                return Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            return Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter

        elif role == Qt.ItemDataRole.UserRole:
            # Return the peak object itself
            return peak

        return None

    def _get_display_value(self, peak, col_key: str, row: int) -> str:
        """Get display value for a cell.

        Args:
            peak: MSPeak object
            col_key: Column key
            row: Row index

        Returns:
            Formatted string value
        """
        if col_key == "index":
            return str(row)

        elif col_key == "mz":
            return f"{peak.mz_exp:.6f}"

        elif col_key == "abundance":
            return f"{peak.abundance:.2e}"

        elif col_key == "sn":
            if hasattr(peak, 'signal_to_noise') and peak.signal_to_noise:
                return f"{peak.signal_to_noise:.1f}"
            return "-"

        elif col_key == "rp":
            if hasattr(peak, 'resolving_power') and peak.resolving_power:
                return f"{peak.resolving_power:.0f}"
            return "-"

        elif col_key == "assigned":
            return "Yes" if peak.is_assigned else "No"

        return ""

    def get_peak(self, row: int):
        """Get peak at row index.

        Args:
            row: Row index

        Returns:
            MSPeak object or None
        """
        if 0 <= row < len(self._peaks):
            return self._peaks[row]
        return None

    def get_peaks(self) -> List:
        """Get all peaks."""
        return self._peaks


class PeakFilterProxyModel(QSortFilterProxyModel):
    """Proxy model for filtering peaks."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._filter_assigned_only = False
        self._filter_text = ""

    def set_filter_assigned_only(self, assigned_only: bool):
        """Set whether to show only assigned peaks."""
        self._filter_assigned_only = assigned_only
        self.invalidateFilter()

    def set_filter_text(self, text: str):
        """Set text filter for formula column."""
        self._filter_text = text.lower()
        self.invalidateFilter()

    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:
        source_model = self.sourceModel()

        # Get peak from source model
        index = source_model.index(source_row, 0)
        peak = source_model.data(index, Qt.ItemDataRole.UserRole)

        if peak is None:
            return False

        # Filter by assignment status
        if self._filter_assigned_only and not peak.is_assigned:
            return False

        # Filter by formula text
        if self._filter_text:
            if not peak.is_assigned:
                return False
            formula = peak.best_molecular_formula_candidate
            if formula:
                if self._filter_text not in str(formula).lower():
                    return False
            else:
                return False

        return True


class PeakTableWidget(QWidget):
    """Peak table widget with sorting and filtering.

    Displays detected peaks from a mass spectrum with their
    properties and molecular formula assignments.

    Signals:
        peak_selected: Emitted when a peak is selected (peak index)
        peak_double_clicked: Emitted on double-click (peak index)
        assign_requested: Emitted when user requests assignment (peak index)
        eic_requested: Emitted when user requests EIC extraction (m/z value)
    """

    peak_selected = pyqtSignal(int)
    peak_double_clicked = pyqtSignal(int)
    assign_requested = pyqtSignal(int)
    eic_requested = pyqtSignal(float)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        """Set up the widget UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)

        # Title and stats
        header_layout = QHBoxLayout()

        title = QLabel("Peaks")
        title.setStyleSheet("font-weight: bold;")
        header_layout.addWidget(title)

        self.stats_label = QLabel("No peaks")
        self.stats_label.setStyleSheet("color: gray;")
        header_layout.addStretch()
        header_layout.addWidget(self.stats_label)

        layout.addLayout(header_layout)

        # Filter controls
        filter_layout = QHBoxLayout()

        self.filter_input = QLineEdit()
        self.filter_input.setPlaceholderText("Filter by formula...")
        self.filter_input.setMaximumWidth(150)
        filter_layout.addWidget(self.filter_input)

        self.assigned_checkbox = QCheckBox("Assigned only")
        filter_layout.addWidget(self.assigned_checkbox)

        filter_layout.addStretch()

        self.export_btn = QPushButton("Export CSV")
        filter_layout.addWidget(self.export_btn)

        layout.addLayout(filter_layout)

        # Table view
        self.table_view = QTableView()
        self.table_view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table_view.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table_view.setSortingEnabled(True)
        self.table_view.setAlternatingRowColors(True)
        self.table_view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)

        # Model and proxy
        self.model = PeakTableModel()
        self.proxy_model = PeakFilterProxyModel()
        self.proxy_model.setSourceModel(self.model)
        self.table_view.setModel(self.proxy_model)

        # Configure header
        header = self.table_view.horizontalHeader()
        header.setStretchLastSection(True)
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)

        layout.addWidget(self.table_view)

    def _connect_signals(self):
        """Connect internal signals."""
        self.filter_input.textChanged.connect(self._on_filter_changed)
        self.assigned_checkbox.toggled.connect(self._on_assigned_filter_changed)
        self.export_btn.clicked.connect(self._export_csv)

        self.table_view.selectionModel().selectionChanged.connect(self._on_selection_changed)
        self.table_view.doubleClicked.connect(self._on_double_clicked)
        self.table_view.customContextMenuRequested.connect(self._show_context_menu)

    def _on_filter_changed(self, text: str):
        """Handle filter text change."""
        self.proxy_model.set_filter_text(text)
        self._update_stats()

    def _on_assigned_filter_changed(self, checked: bool):
        """Handle assigned-only filter change."""
        self.proxy_model.set_filter_assigned_only(checked)
        self._update_stats()

    def _on_selection_changed(self, selected, deselected):
        """Handle row selection change."""
        indexes = self.table_view.selectionModel().selectedRows()
        if indexes:
            source_index = self.proxy_model.mapToSource(indexes[0])
            self.peak_selected.emit(source_index.row())

    def _on_double_clicked(self, index: QModelIndex):
        """Handle double-click on row."""
        source_index = self.proxy_model.mapToSource(index)
        self.peak_double_clicked.emit(source_index.row())

    def _show_context_menu(self, pos):
        """Show context menu."""
        index = self.table_view.indexAt(pos)
        if not index.isValid():
            return

        source_index = self.proxy_model.mapToSource(index)
        peak = self.model.get_peak(source_index.row())

        if peak is None:
            return

        menu = QMenu(self)

        # Assign action
        assign_action = QAction(f"Assign formula to m/z {peak.mz_exp:.4f}", self)
        assign_action.triggered.connect(lambda: self.assign_requested.emit(source_index.row()))
        menu.addAction(assign_action)

        # EIC action
        eic_action = QAction(f"Extract EIC at m/z {peak.mz_exp:.4f}", self)
        eic_action.triggered.connect(lambda: self.eic_requested.emit(peak.mz_exp))
        menu.addAction(eic_action)

        # Show formula details if assigned
        if peak.is_assigned and peak.molecular_formulas:
            menu.addSeparator()
            formula = peak.best_molecular_formula_candidate
            if formula:
                info_action = QAction(f"Formula: {formula}", self)
                info_action.setEnabled(False)
                menu.addAction(info_action)

        menu.exec(self.table_view.viewport().mapToGlobal(pos))

    def _update_stats(self):
        """Update the stats label."""
        total = self.model.rowCount()
        visible = self.proxy_model.rowCount()
        assigned = sum(1 for p in self.model.get_peaks() if p.is_assigned)

        if total == 0:
            self.stats_label.setText("No peaks")
        elif visible == total:
            self.stats_label.setText(f"{total} peaks ({assigned} assigned)")
        else:
            self.stats_label.setText(f"Showing {visible}/{total} peaks ({assigned} assigned)")

    def _export_csv(self):
        """Export visible peaks to CSV."""
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Peaks to CSV",
            "",
            "CSV Files (*.csv);;All Files (*)"
        )

        if not file_path:
            return

        try:
            with open(file_path, 'w', newline='') as f:
                writer = csv.writer(f)

                # Header
                writer.writerow([col[0] for col in PeakTableModel.COLUMNS])

                # Data
                for row in range(self.proxy_model.rowCount()):
                    row_data = []
                    for col in range(self.proxy_model.columnCount()):
                        index = self.proxy_model.index(row, col)
                        row_data.append(self.proxy_model.data(index, Qt.ItemDataRole.DisplayRole))
                    writer.writerow(row_data)

        except Exception as e:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.critical(self, "Export Error", f"Failed to export: {e}")

    def set_peaks(self, spectrum):
        """Set peaks from a spectrum.

        Args:
            spectrum: MassSpectrum object with mspeaks attribute
        """
        self.model.set_peaks(spectrum)
        self._update_stats()

    def select_peak(self, peak_index: int):
        """Select a peak by index.

        Args:
            peak_index: Index in the source model
        """
        source_index = self.model.index(peak_index, 0)
        proxy_index = self.proxy_model.mapFromSource(source_index)

        if proxy_index.isValid():
            self.table_view.selectRow(proxy_index.row())
            self.table_view.scrollTo(proxy_index)

    def get_selected_peak(self):
        """Get the currently selected peak.

        Returns:
            MSPeak object or None
        """
        indexes = self.table_view.selectionModel().selectedRows()
        if indexes:
            source_index = self.proxy_model.mapToSource(indexes[0])
            return self.model.get_peak(source_index.row())
        return None

    def clear(self):
        """Clear all peaks."""
        self.model.set_peaks(None)
        self._update_stats()

    def refresh(self):
        """Refresh the table (call after peak data changes)."""
        self.model.layoutChanged.emit()
        self._update_stats()
