"""Batch results widget for displaying time-window assignment results."""

from typing import Optional, List, Any
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableView, QHeaderView,
    QPushButton, QLabel, QFileDialog, QAbstractItemView
)
from PyQt6.QtCore import (
    Qt, pyqtSignal, QAbstractTableModel, QModelIndex
)
from PyQt6.QtGui import QColor
import csv

from hrms_viewer.core.data_model import TimeWindowResult


class BatchResultsModel(QAbstractTableModel):
    """Table model for batch assignment results.

    Displays one row per time window with summary statistics.
    """

    COLUMNS = [
        ("#", "index"),
        ("Start (min)", "start_time"),
        ("End (min)", "end_time"),
        ("Scans", "n_scans"),
        ("Peaks", "n_peaks"),
        ("Assigned", "n_assigned"),
        ("Rate %", "rate"),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._results: List[TimeWindowResult] = []

    def set_results(self, results: List[TimeWindowResult]):
        """Set the batch results to display.

        Args:
            results: List of TimeWindowResult objects
        """
        self.beginResetModel()
        self._results = results if results else []
        self.endResetModel()

    def clear(self):
        """Clear all results."""
        self.beginResetModel()
        self._results = []
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()) -> int:
        return len(self._results)

    def columnCount(self, parent=QModelIndex()) -> int:
        return len(self.COLUMNS)

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return self.COLUMNS[section][0]
        return None

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid() or index.row() >= len(self._results):
            return None

        result = self._results[index.row()]
        col_key = self.COLUMNS[index.column()][1]

        if role == Qt.ItemDataRole.DisplayRole:
            return self._get_display_value(result, col_key)

        elif role == Qt.ItemDataRole.BackgroundRole:
            if col_key == "rate":
                # Color based on assignment rate
                rate = (result.n_assigned / result.n_peaks * 100) if result.n_peaks > 0 else 0
                if rate >= 50:
                    return QColor(200, 255, 200)  # Light green
                elif rate >= 25:
                    return QColor(255, 255, 200)  # Light yellow
                else:
                    return QColor(255, 220, 220)  # Light red

        elif role == Qt.ItemDataRole.TextAlignmentRole:
            if col_key in ["n_scans", "n_peaks", "n_assigned", "rate"]:
                return Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            elif col_key in ["start_time", "end_time"]:
                return Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            return Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter

        elif role == Qt.ItemDataRole.UserRole:
            # Return the result object itself
            return result

        return None

    def _get_display_value(self, result: TimeWindowResult, col_key: str) -> str:
        """Get display value for a cell.

        Args:
            result: TimeWindowResult object
            col_key: Column key

        Returns:
            Formatted string value
        """
        if col_key == "index":
            return str(result.window_index)

        elif col_key == "start_time":
            return f"{result.start_time:.2f}"

        elif col_key == "end_time":
            return f"{result.end_time:.2f}"

        elif col_key == "n_scans":
            return str(result.n_scans)

        elif col_key == "n_peaks":
            return str(result.n_peaks)

        elif col_key == "n_assigned":
            return str(result.n_assigned)

        elif col_key == "rate":
            if result.n_peaks > 0:
                rate = (result.n_assigned / result.n_peaks) * 100
                return f"{rate:.1f}%"
            return "0%"

        return ""

    def get_result(self, row: int) -> Optional[TimeWindowResult]:
        """Get result at row index.

        Args:
            row: Row index

        Returns:
            TimeWindowResult or None
        """
        if 0 <= row < len(self._results):
            return self._results[row]
        return None

    def get_results(self) -> List[TimeWindowResult]:
        """Get all results."""
        return self._results


class BatchResultsWidget(QWidget):
    """Widget for displaying batch time-window assignment results.

    Shows a table of results with export functionality.
    Emits signals when user selects a window to view.
    """

    # Signal emitted when user wants to view a window's spectrum
    window_selected = pyqtSignal(int)  # row index
    window_double_clicked = pyqtSignal(int)  # row index

    def __init__(self, parent=None):
        super().__init__(parent)

        self._model = BatchResultsModel(self)

        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        """Set up the widget UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Header with stats and export button
        header_layout = QHBoxLayout()

        self.stats_label = QLabel("No batch results")
        header_layout.addWidget(self.stats_label)

        header_layout.addStretch()

        self.export_summary_btn = QPushButton("Export Summary")
        self.export_summary_btn.setEnabled(False)
        self.export_summary_btn.clicked.connect(self._export_summary_csv)
        header_layout.addWidget(self.export_summary_btn)

        self.export_detailed_btn = QPushButton("Export Detailed")
        self.export_detailed_btn.setEnabled(False)
        self.export_detailed_btn.clicked.connect(self._export_detailed_csv)
        header_layout.addWidget(self.export_detailed_btn)

        layout.addLayout(header_layout)

        # Table view
        self.table_view = QTableView()
        self.table_view.setModel(self._model)
        self.table_view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table_view.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table_view.setAlternatingRowColors(True)
        self.table_view.setSortingEnabled(False)
        self.table_view.verticalHeader().setVisible(False)

        # Set column resize modes
        header = self.table_view.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)  # #
        header.resizeSection(0, 40)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)  # Start
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)  # End
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Interactive)  # Scans
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Interactive)  # Peaks
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Interactive)  # Assigned
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.Stretch)  # Rate

        layout.addWidget(self.table_view)

        # Hint label
        self.hint_label = QLabel("Click a row to load that window's spectrum")
        self.hint_label.setStyleSheet("color: #666; font-size: 11px;")
        layout.addWidget(self.hint_label)

    def _connect_signals(self):
        """Connect internal signals."""
        self.table_view.clicked.connect(self._on_row_clicked)
        self.table_view.doubleClicked.connect(self._on_row_double_clicked)

    def set_results(self, results: List[TimeWindowResult]):
        """Set the batch results to display.

        Args:
            results: List of TimeWindowResult objects
        """
        self._model.set_results(results)
        self._update_stats()

        has_results = len(results) > 0
        self.export_summary_btn.setEnabled(has_results)
        self.export_detailed_btn.setEnabled(has_results)

    def clear(self):
        """Clear all results."""
        self._model.clear()
        self._update_stats()
        self.export_summary_btn.setEnabled(False)
        self.export_detailed_btn.setEnabled(False)

    def _update_stats(self):
        """Update the statistics label."""
        results = self._model.get_results()
        if not results:
            self.stats_label.setText("No batch results")
            return

        total_windows = len(results)
        total_peaks = sum(r.n_peaks for r in results)
        total_assigned = sum(r.n_assigned for r in results)
        overall_rate = (total_assigned / total_peaks * 100) if total_peaks > 0 else 0

        self.stats_label.setText(
            f"{total_windows} windows | {total_peaks} peaks | "
            f"{total_assigned} assigned ({overall_rate:.1f}%)"
        )

    def _on_row_clicked(self, index: QModelIndex):
        """Handle row click."""
        if index.isValid():
            self.window_selected.emit(index.row())

    def _on_row_double_clicked(self, index: QModelIndex):
        """Handle row double-click."""
        if index.isValid():
            self.window_double_clicked.emit(index.row())

    def get_selected_result(self) -> Optional[TimeWindowResult]:
        """Get the currently selected result.

        Returns:
            TimeWindowResult or None if nothing selected
        """
        indexes = self.table_view.selectionModel().selectedRows()
        if indexes:
            return self._model.get_result(indexes[0].row())
        return None

    def _export_summary_csv(self):
        """Export summary to CSV file."""
        results = self._model.get_results()
        if not results:
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Summary CSV",
            "batch_summary.csv",
            "CSV Files (*.csv);;All Files (*)"
        )

        if not file_path:
            return

        try:
            with open(file_path, 'w', newline='') as f:
                writer = csv.writer(f)

                # Header
                writer.writerow([
                    "Window", "Start_RT", "End_RT", "Scans",
                    "Peaks", "Assigned", "Rate_Percent", "Top_Formulas"
                ])

                # Data rows
                for result in results:
                    rate = (result.n_assigned / result.n_peaks * 100) if result.n_peaks > 0 else 0
                    top_formulas = ", ".join(result.formulas[:5]) if result.formulas else ""

                    writer.writerow([
                        result.window_index,
                        f"{result.start_time:.2f}",
                        f"{result.end_time:.2f}",
                        result.n_scans,
                        result.n_peaks,
                        result.n_assigned,
                        f"{rate:.1f}",
                        top_formulas
                    ])

        except Exception as e:
            print(f"Error exporting summary: {e}")

    def _export_detailed_csv(self):
        """Export detailed peak data to CSV file."""
        results = self._model.get_results()
        if not results:
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Detailed CSV",
            "batch_detailed.csv",
            "CSV Files (*.csv);;All Files (*)"
        )

        if not file_path:
            return

        try:
            with open(file_path, 'w', newline='') as f:
                writer = csv.writer(f)

                # Header
                writer.writerow([
                    "Window", "Start_RT", "End_RT", "m/z", "Abundance",
                    "Formula", "Calc_m/z", "Error_ppm", "DBE", "Class"
                ])

                # Data rows - iterate through all peaks in all windows
                for result in results:
                    if result.spectrum is None:
                        continue

                    if not hasattr(result.spectrum, 'mspeaks'):
                        continue

                    for peak in result.spectrum.mspeaks:
                        if not peak.is_assigned:
                            continue

                        # Get best formula
                        formula = peak.best_molecular_formula_candidate
                        if formula is None:
                            continue

                        writer.writerow([
                            result.window_index,
                            f"{result.start_time:.2f}",
                            f"{result.end_time:.2f}",
                            f"{peak.mz_exp:.6f}",
                            f"{peak.abundance:.2e}",
                            formula.string,
                            f"{formula.mz_calc:.6f}",
                            f"{formula.mz_error:.2f}",
                            f"{formula.dbe:.1f}" if hasattr(formula, 'dbe') else "",
                            formula.class_label if hasattr(formula, 'class_label') else ""
                        ])

        except Exception as e:
            print(f"Error exporting detailed: {e}")

    def get_result(self, index: int) -> Optional[TimeWindowResult]:
        """Get result by index.

        Args:
            index: Row index

        Returns:
            TimeWindowResult or None
        """
        return self._model.get_result(index)
