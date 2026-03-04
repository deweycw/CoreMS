"""EIC extraction dialog."""

from typing import Optional, Tuple
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QDoubleSpinBox, QSpinBox, QPushButton, QColorDialog, QLabel
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor


class EICDialog(QDialog):
    """Dialog for EIC extraction parameters.

    Allows user to specify target m/z, tolerance, and color
    for extracting an ion chromatogram.
    """

    def __init__(self, default_mz: float = 500.0,
                 default_ppm: float = 5.0,
                 default_color: str = "#E91E63",
                 parent=None):
        super().__init__(parent)

        self.setWindowTitle("Extract Ion Chromatogram")
        self.setMinimumWidth(300)

        self._color = default_color

        self._setup_ui(default_mz, default_ppm)

    def _setup_ui(self, default_mz: float, default_ppm: float):
        """Set up the dialog UI."""
        layout = QVBoxLayout(self)

        # Form layout for inputs
        form = QFormLayout()

        # m/z input
        self.mz_spin = QDoubleSpinBox()
        self.mz_spin.setRange(0.0, 10000.0)
        self.mz_spin.setDecimals(4)
        self.mz_spin.setValue(default_mz)
        self.mz_spin.setSingleStep(0.0001)
        form.addRow("Target m/z:", self.mz_spin)

        # Tolerance input
        self.ppm_spin = QDoubleSpinBox()
        self.ppm_spin.setRange(0.1, 100.0)
        self.ppm_spin.setDecimals(1)
        self.ppm_spin.setValue(default_ppm)
        self.ppm_spin.setSuffix(" ppm")
        form.addRow("Tolerance:", self.ppm_spin)

        # Color picker
        color_layout = QHBoxLayout()
        self.color_label = QLabel()
        self.color_label.setFixedSize(40, 20)
        self._update_color_label()
        color_layout.addWidget(self.color_label)

        self.color_btn = QPushButton("Choose...")
        self.color_btn.clicked.connect(self._choose_color)
        color_layout.addWidget(self.color_btn)
        color_layout.addStretch()

        form.addRow("Color:", color_layout)

        layout.addLayout(form)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        ok_btn = QPushButton("Extract")
        ok_btn.setDefault(True)
        ok_btn.clicked.connect(self.accept)
        btn_layout.addWidget(ok_btn)

        layout.addLayout(btn_layout)

    def _update_color_label(self):
        """Update the color preview label."""
        self.color_label.setStyleSheet(
            f"background-color: {self._color}; border: 1px solid gray;"
        )

    def _choose_color(self):
        """Open color chooser dialog."""
        color = QColorDialog.getColor(QColor(self._color), self, "Choose EIC Color")
        if color.isValid():
            self._color = color.name()
            self._update_color_label()

    def get_values(self) -> Tuple[float, float, str]:
        """Get the entered values.

        Returns:
            Tuple of (mz, ppm_tolerance, color_hex)
        """
        return (
            self.mz_spin.value(),
            self.ppm_spin.value(),
            self._color
        )

    @staticmethod
    def get_eic_params(default_mz: float = 500.0,
                       default_ppm: float = 5.0,
                       parent=None) -> Optional[Tuple[float, float, str]]:
        """Static method to show dialog and get values.

        Args:
            default_mz: Default m/z value
            default_ppm: Default ppm tolerance
            parent: Parent widget

        Returns:
            Tuple of (mz, ppm, color) if accepted, None if cancelled
        """
        dialog = EICDialog(default_mz, default_ppm, parent=parent)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            return dialog.get_values()
        return None
