"""Isotopologue selection dialog for visualizing isotope peak positions."""

from typing import List, Dict, Tuple, Optional
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QLabel, QHeaderView, QCheckBox, QGroupBox, QSpinBox,
    QDialogButtonBox
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor

from corems.encapsulation.constant import Atoms


def get_isotope_data() -> List[Tuple[str, float, str, str, float]]:
    """Generate isotope data from CoreMS Atoms class.

    Returns:
        List of (display_name, mass_shift, element, description, abundance) tuples
    """
    isotope_data = []

    # Define the isotopes we want to show, grouped by element
    # Format: (display_name, isotope_symbol, base_element, description, count)
    isotope_definitions = [
        # Carbon isotopes
        ("13C1", "13C", "C", "One 13C substitution", 1),
        ("13C2", "13C", "C", "Two 13C substitutions", 2),
        ("13C3", "13C", "C", "Three 13C substitutions", 3),
        ("13C4", "13C", "C", "Four 13C substitutions", 4),
        ("13C5", "13C", "C", "Five 13C substitutions", 5),
        ("13C6", "13C", "C", "Six 13C substitutions", 6),

        # Nitrogen isotopes
        ("15N1", "15N", "N", "One 15N substitution", 1),
        ("15N2", "15N", "N", "Two 15N substitutions", 2),

        # Oxygen isotopes
        ("18O1", "18O", "O", "One 18O substitution", 1),
        ("17O1", "17O", "O", "One 17O substitution", 1),

        # Sulfur isotopes
        ("34S1", "34S", "S", "One 34S substitution", 1),
        ("33S1", "33S", "S", "One 33S substitution", 1),
        ("36S1", "36S", "S", "One 36S substitution", 1),

        # Iron isotopes (relative to 56Fe, most abundant)
        ("54Fe", "54Fe", "Fe", "54Fe (lighter than 56Fe)", 1),
        ("57Fe", "57Fe", "Fe", "57Fe substitution", 1),
        ("58Fe", "58Fe", "Fe", "58Fe substitution", 1),

        # Copper isotopes (relative to 63Cu, most abundant)
        ("65Cu", "65Cu", "Cu", "65Cu substitution", 1),

        # Chlorine isotopes (relative to 35Cl)
        ("37Cl1", "37Cl", "Cl", "One 37Cl substitution", 1),
        ("37Cl2", "37Cl", "Cl", "Two 37Cl substitutions", 2),

        # Bromine isotopes (relative to 79Br)
        ("81Br1", "81Br", "Br", "One 81Br substitution", 1),
        ("81Br2", "81Br", "Br", "Two 81Br substitutions", 2),

        # Silicon isotopes (relative to 28Si)
        ("29Si", "29Si", "Si", "29Si substitution", 1),
        ("30Si", "30Si", "Si", "30Si substitution", 1),

        # Magnesium isotopes
        ("25Mg", "25Mg", "Mg", "25Mg substitution", 1),
        ("26Mg", "26Mg", "Mg", "26Mg substitution", 1),

        # Nickel isotopes
        ("60Ni", "60Ni", "Ni", "60Ni substitution", 1),
        ("62Ni", "62Ni", "Ni", "62Ni substitution", 1),

        # Zinc isotopes
        ("66Zn", "66Zn", "Zn", "66Zn substitution", 1),
        ("68Zn", "68Zn", "Zn", "68Zn substitution", 1),

        # Potassium isotopes
        ("41K", "41K", "K", "41K substitution", 1),

        # Calcium isotopes
        ("44Ca", "44Ca", "Ca", "44Ca substitution", 1),

        # Hydrogen/Deuterium
        ("D1", "D", "H", "One deuterium substitution", 1),
        ("D2", "D", "H", "Two deuterium substitutions", 2),
    ]

    for display_name, isotope_symbol, base_element, description, count in isotope_definitions:
        try:
            # Get masses from CoreMS Atoms class
            isotope_mass = Atoms.atomic_masses.get(isotope_symbol)
            base_mass = Atoms.atomic_masses.get(base_element)

            if isotope_mass is None or base_mass is None:
                continue

            # Calculate mass shift (isotope - base) * count
            mass_shift = (isotope_mass - base_mass) * count

            # Get abundance of the isotope
            abundance = Atoms.isotopic_abundance.get(isotope_symbol, 0.0)

            isotope_data.append((display_name, mass_shift, base_element, description, abundance))

        except Exception as e:
            print(f"Warning: Could not get data for {display_name}: {e}")

    return isotope_data


# Default commonly used isotopes
DEFAULT_ISOTOPES = ["13C1", "13C2", "15N1", "18O1", "34S1"]

# Element groups for display
ELEMENT_GROUPS = {
    "C": "Carbon",
    "N": "Nitrogen",
    "O": "Oxygen",
    "S": "Sulfur",
    "Fe": "Iron",
    "Cu": "Copper",
    "Cl": "Chlorine",
    "Br": "Bromine",
    "Si": "Silicon",
    "H": "Hydrogen",
}


class IsotopologueDialog(QDialog):
    """Dialog for selecting isotopologues to visualize on the spectrum.

    Signals:
        isotopes_selected: Emitted with list of (name, mass_shift) tuples
    """

    isotopes_selected = pyqtSignal(list)  # List of (name, mass_shift) tuples

    def __init__(self, peak_mz: float, parent=None):
        super().__init__(parent)
        self.peak_mz = peak_mz
        self.selected_isotopes: List[Tuple[str, float]] = []
        self.isotope_data = get_isotope_data()

        self.setWindowTitle(f"Isotopologue Peaks - m/z {peak_mz:.5f}")
        self.setMinimumSize(600, 650)

        self._setup_ui()
        self._load_defaults()

    def _setup_ui(self):
        """Set up the dialog UI."""
        layout = QVBoxLayout(self)

        # Peak info
        info_label = QLabel(f"Selected peak: m/z {self.peak_mz:.5f}")
        info_label.setStyleSheet("font-weight: bold; font-size: 12px;")
        layout.addWidget(info_label)

        # Instructions
        instructions = QLabel(
            "Select isotopologues to show their expected positions on the spectrum.\n"
            "Mass shifts calculated from CoreMS atomic masses (NIST values)."
        )
        instructions.setStyleSheet("color: gray; font-size: 10px;")
        layout.addWidget(instructions)

        # Table with isotopes
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels([
            "Show", "Isotope", "Mass Shift (Da)", "Expected m/z", "Element", "Abundance"
        ])

        # Set up table properties
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        self.table.setColumnWidth(0, 50)
        self.table.setColumnWidth(4, 70)

        self._populate_table()
        layout.addWidget(self.table)

        # Quick select buttons
        button_row = QHBoxLayout()

        select_all_btn = QPushButton("Select All")
        select_all_btn.clicked.connect(self._select_all)
        button_row.addWidget(select_all_btn)

        select_none_btn = QPushButton("Select None")
        select_none_btn.clicked.connect(self._select_none)
        button_row.addWidget(select_none_btn)

        select_defaults_btn = QPushButton("Select Defaults")
        select_defaults_btn.clicked.connect(self._load_defaults)
        button_row.addWidget(select_defaults_btn)

        button_row.addStretch()
        layout.addLayout(button_row)

        # Element filter buttons
        filter_group = QGroupBox("Quick Select by Element")
        filter_layout = QHBoxLayout(filter_group)

        for element in ["C", "N", "O", "S", "Cl", "Br", "Fe", "Cu"]:
            btn = QPushButton(element)
            btn.setFixedWidth(40)
            btn.setToolTip(f"Toggle {ELEMENT_GROUPS.get(element, element)} isotopes")
            btn.clicked.connect(lambda checked, e=element: self._select_element(e))
            filter_layout.addWidget(btn)

        filter_layout.addStretch()
        layout.addWidget(filter_group)

        # Dialog buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel |
            QDialogButtonBox.StandardButton.Apply
        )
        button_box.accepted.connect(self._on_accept)
        button_box.rejected.connect(self.reject)
        button_box.button(QDialogButtonBox.StandardButton.Apply).clicked.connect(self._on_apply)
        layout.addWidget(button_box)

    def _populate_table(self):
        """Populate the table with isotope data."""
        self.table.setRowCount(len(self.isotope_data))
        self.checkboxes = {}

        for row, (name, mass_shift, element, description, abundance) in enumerate(self.isotope_data):
            # Checkbox
            checkbox = QCheckBox()
            checkbox.setToolTip(description)
            self.checkboxes[name] = checkbox

            checkbox_widget = QTableWidgetItem()
            self.table.setItem(row, 0, checkbox_widget)
            self.table.setCellWidget(row, 0, checkbox)

            # Isotope name
            name_item = QTableWidgetItem(name)
            name_item.setFlags(name_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            name_item.setToolTip(description)
            self.table.setItem(row, 1, name_item)

            # Mass shift
            shift_item = QTableWidgetItem(f"{mass_shift:+.6f}")
            shift_item.setFlags(shift_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, 2, shift_item)

            # Expected m/z
            expected_mz = self.peak_mz + mass_shift
            mz_item = QTableWidgetItem(f"{expected_mz:.5f}")
            mz_item.setFlags(mz_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, 3, mz_item)

            # Element
            element_item = QTableWidgetItem(element)
            element_item.setFlags(element_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, 4, element_item)

            # Abundance (as percentage)
            abundance_str = f"{abundance * 100:.2f}%" if abundance > 0 else "trace"
            abundance_item = QTableWidgetItem(abundance_str)
            abundance_item.setFlags(abundance_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, 5, abundance_item)

            # Alternate row colors
            if row % 2 == 1:
                for col in range(6):
                    item = self.table.item(row, col)
                    if item:
                        item.setBackground(QColor(245, 245, 245))

    def _load_defaults(self):
        """Load default isotope selections."""
        for name, checkbox in self.checkboxes.items():
            checkbox.setChecked(name in DEFAULT_ISOTOPES)

    def _select_all(self):
        """Select all isotopes."""
        for checkbox in self.checkboxes.values():
            checkbox.setChecked(True)

    def _select_none(self):
        """Deselect all isotopes."""
        for checkbox in self.checkboxes.values():
            checkbox.setChecked(False)

    def _select_element(self, element: str):
        """Toggle all isotopes of a specific element."""
        # Check if any are selected
        any_selected = any(
            self.checkboxes[name].isChecked()
            for name, _, elem, _, _ in self.isotope_data
            if elem == element
        )

        # Toggle all isotopes of this element
        for name, _, elem, _, _ in self.isotope_data:
            if elem == element:
                self.checkboxes[name].setChecked(not any_selected)

    def _get_selected_isotopes(self) -> List[Tuple[str, float]]:
        """Get list of selected isotopes with their mass shifts."""
        selected = []
        for name, mass_shift, element, _, _ in self.isotope_data:
            if self.checkboxes[name].isChecked():
                selected.append((name, mass_shift))
        return selected

    def _on_apply(self):
        """Apply current selection without closing dialog."""
        selected = self._get_selected_isotopes()
        self.isotopes_selected.emit(selected)

    def _on_accept(self):
        """Accept and close dialog."""
        selected = self._get_selected_isotopes()
        self.isotopes_selected.emit(selected)
        self.accept()

    def get_selected_isotopes(self) -> List[Tuple[str, float]]:
        """Get the list of selected isotopes.

        Returns:
            List of (name, mass_shift) tuples
        """
        return self._get_selected_isotopes()
