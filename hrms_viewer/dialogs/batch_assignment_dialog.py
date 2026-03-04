"""Batch time-window assignment dialog."""

from typing import Optional, List, Callable
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QGroupBox,
    QLabel, QPushButton, QDoubleSpinBox, QProgressBar,
    QDialogButtonBox, QApplication
)
from PyQt6.QtCore import Qt, pyqtSignal

from hrms_viewer.dialogs.calibration_dialog import AssignmentParametersDialog


class BatchAssignmentDialog(QDialog):
    """Dialog for batch time-window formula assignment.

    Allows user to specify time range and window size for batch processing.
    """

    # Signal emitted when processing should start
    start_processing = pyqtSignal(float, float, float, dict)  # start, end, window_size, params

    def __init__(self, time_range: tuple, has_calibration: bool = False, parent=None):
        """Initialize batch assignment dialog.

        Args:
            time_range: (min_time, max_time) tuple from data
            has_calibration: Whether a calibration is available to apply
            parent: Parent widget
        """
        super().__init__(parent)

        self.time_range = time_range
        self.has_calibration = has_calibration
        self._assignment_params: Optional[dict] = None
        self._is_processing = False
        self._cancelled = False

        self.setWindowTitle("Batch Time-Window Assignment")
        self.setMinimumWidth(450)
        self.setModal(True)

        self._setup_ui()
        self._update_preview()

    def _setup_ui(self):
        """Set up the dialog UI."""
        layout = QVBoxLayout(self)

        # Time Range group
        time_group = QGroupBox("Time Range")
        time_layout = QFormLayout(time_group)

        # Start time
        self.start_time_spin = QDoubleSpinBox()
        self.start_time_spin.setRange(0.0, 999.0)
        self.start_time_spin.setValue(self.time_range[0] if self.time_range else 0.0)
        self.start_time_spin.setSingleStep(1.0)
        self.start_time_spin.setDecimals(2)
        self.start_time_spin.setSuffix(" min")
        self.start_time_spin.valueChanged.connect(self._update_preview)
        time_layout.addRow("Start Time:", self.start_time_spin)

        # End time
        self.end_time_spin = QDoubleSpinBox()
        self.end_time_spin.setRange(0.0, 999.0)
        self.end_time_spin.setValue(self.time_range[1] if self.time_range else 30.0)
        self.end_time_spin.setSingleStep(1.0)
        self.end_time_spin.setDecimals(2)
        self.end_time_spin.setSuffix(" min")
        self.end_time_spin.valueChanged.connect(self._update_preview)
        time_layout.addRow("End Time:", self.end_time_spin)

        # Window size
        self.window_size_spin = QDoubleSpinBox()
        self.window_size_spin.setRange(0.1, 60.0)
        self.window_size_spin.setValue(2.0)
        self.window_size_spin.setSingleStep(0.5)
        self.window_size_spin.setDecimals(2)
        self.window_size_spin.setSuffix(" min")
        self.window_size_spin.valueChanged.connect(self._update_preview)
        time_layout.addRow("Window Size:", self.window_size_spin)

        layout.addWidget(time_group)

        # Preview section
        preview_group = QGroupBox("Preview")
        preview_layout = QVBoxLayout(preview_group)

        self.preview_label = QLabel()
        self.preview_label.setWordWrap(True)
        preview_layout.addWidget(self.preview_label)

        self.windows_detail_label = QLabel()
        self.windows_detail_label.setStyleSheet("color: #666; font-size: 11px;")
        self.windows_detail_label.setWordWrap(True)
        preview_layout.addWidget(self.windows_detail_label)

        layout.addWidget(preview_group)

        # Calibration status section
        if self.has_calibration:
            cal_group = QGroupBox("Calibration")
            cal_layout = QVBoxLayout(cal_group)
            cal_label = QLabel("Calibration will be applied to each window")
            cal_label.setStyleSheet("color: #4CAF50; font-weight: bold;")
            cal_layout.addWidget(cal_label)
            layout.addWidget(cal_group)

        # Assignment Parameters section
        params_group = QGroupBox("Assignment Parameters")
        params_layout = QVBoxLayout(params_group)

        self.params_status_label = QLabel("Using default parameters")
        self.params_status_label.setStyleSheet("color: #666;")
        params_layout.addWidget(self.params_status_label)

        self.configure_params_btn = QPushButton("Configure Assignment Parameters...")
        self.configure_params_btn.clicked.connect(self._configure_parameters)
        params_layout.addWidget(self.configure_params_btn)

        layout.addWidget(params_group)

        # Progress section (initially hidden)
        self.progress_group = QGroupBox("Progress")
        progress_layout = QVBoxLayout(self.progress_group)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        progress_layout.addWidget(self.progress_bar)

        self.progress_label = QLabel("")
        progress_layout.addWidget(self.progress_label)

        self.progress_group.setVisible(False)
        layout.addWidget(self.progress_group)

        # Buttons
        button_layout = QHBoxLayout()

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self._on_cancel)
        button_layout.addWidget(self.cancel_btn)

        button_layout.addStretch()

        self.start_btn = QPushButton("Start")
        self.start_btn.setDefault(True)
        self.start_btn.clicked.connect(self._on_start)
        button_layout.addWidget(self.start_btn)

        layout.addLayout(button_layout)

    def _update_preview(self):
        """Update the preview text based on current settings."""
        start = self.start_time_spin.value()
        end = self.end_time_spin.value()
        window = self.window_size_spin.value()

        if end <= start:
            self.preview_label.setText("Invalid range: end time must be greater than start time")
            self.windows_detail_label.setText("")
            self.start_btn.setEnabled(False)
            return

        total_time = end - start
        n_windows = int(total_time / window)
        if n_windows == 0:
            n_windows = 1

        self.preview_label.setText(f"<b>{n_windows} windows</b> to process")

        # Show first few and last window ranges
        if n_windows <= 5:
            windows_text = []
            for i in range(n_windows):
                w_start = start + i * window
                w_end = min(start + (i + 1) * window, end)
                windows_text.append(f"{w_start:.1f}-{w_end:.1f}")
            self.windows_detail_label.setText("Windows: " + ", ".join(windows_text) + " min")
        else:
            # Show first 3 and last one
            windows_text = []
            for i in range(3):
                w_start = start + i * window
                w_end = min(start + (i + 1) * window, end)
                windows_text.append(f"{w_start:.1f}-{w_end:.1f}")
            last_start = start + (n_windows - 1) * window
            last_end = min(start + n_windows * window, end)
            self.windows_detail_label.setText(
                f"Windows: {', '.join(windows_text)}, ... {last_start:.1f}-{last_end:.1f} min"
            )

        self.start_btn.setEnabled(True)

    def _configure_parameters(self):
        """Open assignment parameters dialog."""
        params = AssignmentParametersDialog.get_assignment_params(self)
        if params:
            self._assignment_params = params
            self.params_status_label.setText("Custom parameters configured")
            self.params_status_label.setStyleSheet("color: #4CAF50;")

    def _on_start(self):
        """Handle start button click."""
        if self._is_processing:
            return

        start = self.start_time_spin.value()
        end = self.end_time_spin.value()
        window = self.window_size_spin.value()

        # Use default parameters if not configured
        if self._assignment_params is None:
            # Get default parameters from the dialog
            dialog = AssignmentParametersDialog(self)
            self._assignment_params = dialog.get_parameters()

        self._is_processing = True
        self._cancelled = False

        # Show progress
        self.progress_group.setVisible(True)
        self.start_btn.setEnabled(False)
        self.configure_params_btn.setEnabled(False)
        self.start_time_spin.setEnabled(False)
        self.end_time_spin.setEnabled(False)
        self.window_size_spin.setEnabled(False)

        # Emit signal to start processing
        self.start_processing.emit(start, end, window, self._assignment_params)

    def _on_cancel(self):
        """Handle cancel button click."""
        if self._is_processing:
            self._cancelled = True
            self.progress_label.setText("Cancelling...")
        else:
            self.reject()

    def is_cancelled(self) -> bool:
        """Check if processing was cancelled."""
        return self._cancelled

    def update_progress(self, current: int, total: int, message: str = ""):
        """Update progress bar.

        Args:
            current: Current window number (1-based)
            total: Total number of windows
            message: Optional progress message
        """
        percent = int((current / total) * 100) if total > 0 else 0
        self.progress_bar.setValue(percent)

        if message:
            self.progress_label.setText(message)
        else:
            self.progress_label.setText(f"Processing window {current}/{total}")

        # Process events to update UI
        QApplication.processEvents()

    def processing_complete(self, success: bool = True):
        """Called when processing is complete.

        Args:
            success: Whether processing completed successfully
        """
        self._is_processing = False

        if success and not self._cancelled:
            self.progress_bar.setValue(100)
            self.progress_label.setText("Complete!")
            self.accept()
        elif self._cancelled:
            self.progress_label.setText("Cancelled")
            self.reject()
        else:
            self.progress_label.setText("Failed")
            # Re-enable controls for retry
            self.start_btn.setEnabled(True)
            self.configure_params_btn.setEnabled(True)
            self.start_time_spin.setEnabled(True)
            self.end_time_spin.setEnabled(True)
            self.window_size_spin.setEnabled(True)

    def get_parameters(self) -> dict:
        """Get all batch parameters.

        Returns:
            Dict with start_time, end_time, window_size, assignment_params
        """
        return {
            'start_time': self.start_time_spin.value(),
            'end_time': self.end_time_spin.value(),
            'window_size': self.window_size_spin.value(),
            'assignment_params': self._assignment_params
        }

    def get_window_count(self) -> int:
        """Get the number of windows that will be processed."""
        start = self.start_time_spin.value()
        end = self.end_time_spin.value()
        window = self.window_size_spin.value()
        total_time = end - start
        return max(1, int(total_time / window))
