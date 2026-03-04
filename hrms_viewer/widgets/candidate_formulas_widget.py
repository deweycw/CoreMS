"""Candidate formulas widget for displaying all formula assignments for a selected peak."""

from typing import Optional, List, Any, Tuple
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QTableView, QHeaderView, QLabel,
    QAbstractItemView, QMenu
)
from PyQt6.QtCore import (
    Qt, pyqtSignal, QAbstractTableModel, QModelIndex,
    QSortFilterProxyModel
)
from PyQt6.QtGui import QColor, QAction
from math import comb
from corems.encapsulation.constant import Atoms


class CandidateFormulasModel(QAbstractTableModel):
    """Table model for candidate molecular formulas.

    Displays all candidate formulas for a selected peak with
    columns for formula, calculated m/z, error, and score.
    """

    COLUMNS = [
        ("Formula", "formula"),
        ("Calc m/z", "mz_calc"),
        ("Error (ppm)", "error"),
        ("DBE", "dbe"),
        ("H/C", "hc"),
        ("O/C", "oc"),
        ("Confidence", "confidence"),
        ("Class", "mol_class"),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._formulas: List = []
        self._peak = None

    def set_peak(self, peak):
        """Set the peak to display formulas for.

        Args:
            peak: MSPeak object with molecular_formulas attribute
        """
        self.beginResetModel()
        self._peak = peak

        if peak is not None and hasattr(peak, 'molecular_formulas'):
            self._formulas = list(peak.molecular_formulas)
        else:
            self._formulas = []

        self.endResetModel()

    def clear(self):
        """Clear the table."""
        self.beginResetModel()
        self._peak = None
        self._formulas = []
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()) -> int:
        return len(self._formulas)

    def columnCount(self, parent=QModelIndex()) -> int:
        return len(self.COLUMNS)

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return self.COLUMNS[section][0]
        return None

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid() or index.row() >= len(self._formulas):
            return None

        formula = self._formulas[index.row()]
        col_key = self.COLUMNS[index.column()][1]

        if role == Qt.ItemDataRole.DisplayRole:
            return self._get_display_value(formula, col_key, index.row())

        elif role == Qt.ItemDataRole.BackgroundRole:
            # Highlight best formula (first row, typically highest confidence)
            if index.row() == 0 and len(self._formulas) > 0:
                return QColor(200, 255, 200)  # Light green

        return None

    def _get_display_value(self, formula, col_key: str, row: int) -> str:
        """Get display value for a cell."""
        try:
            if col_key == "formula":
                # Use the string property which returns just the formula
                # Add spaces between elements for clarity (e.g., "C6 H6 O6")
                import re
                formula_str = None
                if hasattr(formula, 'string'):
                    formula_str = formula.string
                elif hasattr(formula, 'molecular_formula'):
                    formula_str = str(formula.molecular_formula)
                else:
                    formula_str = str(formula)

                # Insert space before each uppercase letter (except the first)
                if formula_str:
                    formula_str = re.sub(r'(?<!^)([A-Z])', r' \1', formula_str)
                return formula_str or ""

            elif col_key == "mz_calc":
                mz_calc = getattr(formula, 'mz_calc', None)
                if mz_calc is None:
                    mz_calc = getattr(formula, 'calculated_mz', None)
                if mz_calc is not None:
                    return f"{mz_calc:.6f}"
                return ""

            elif col_key == "error":
                error = getattr(formula, 'mz_error', None)
                if error is not None:
                    return f"{error:.4f}"
                return ""

            elif col_key == "dbe":
                dbe = getattr(formula, 'dbe', None)
                if dbe is not None:
                    return f"{dbe:.1f}"
                return ""

            elif col_key == "hc":
                hc = getattr(formula, 'H_C', None)
                if hc is not None:
                    return f"{hc:.2f}"
                return ""

            elif col_key == "oc":
                oc = getattr(formula, 'O_C', None)
                if oc is not None:
                    return f"{oc:.2f}"
                return ""

            elif col_key == "confidence":
                conf = getattr(formula, 'confidence_score', None)
                if conf is not None:
                    return f"{conf:.3f}"
                return ""

            elif col_key == "mol_class":
                mol_class = getattr(formula, 'class_label', None)
                if mol_class is None:
                    mol_class = getattr(formula, 'molecular_class', None)
                if mol_class is not None:
                    return str(mol_class)
                return ""

        except Exception:
            pass

        return ""


class CandidateFormulasWidget(QWidget):
    """Widget for displaying candidate molecular formulas for a selected peak.

    Shows all formula candidates from CoreMS assignment results,
    not just the best match.
    """

    formula_selected = pyqtSignal(int, object)  # row index, formula object
    # Signal: base_mz, list of (name, mass_shift, relative_intensity)
    isotopologues_requested = pyqtSignal(float, list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_peak = None
        self._setup_ui()

    def _setup_ui(self):
        """Set up the widget UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Header
        self.header_label = QLabel("Candidate Formulas")
        self.header_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(self.header_label)

        # Peak info label
        self.peak_info_label = QLabel("Select a peak to view candidates")
        self.peak_info_label.setStyleSheet("color: gray;")
        layout.addWidget(self.peak_info_label)

        # Table
        self.model = CandidateFormulasModel(self)
        self.proxy_model = QSortFilterProxyModel(self)
        self.proxy_model.setSourceModel(self.model)

        self.table = QTableView()
        self.table.setModel(self.proxy_model)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setAlternatingRowColors(True)
        self.table.setSortingEnabled(True)
        self.table.verticalHeader().setVisible(False)

        # Set column sizing
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)  # Formula
        for i in range(1, len(CandidateFormulasModel.COLUMNS)):
            header.setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)

        layout.addWidget(self.table)

        # Connect selection signal
        self.table.selectionModel().selectionChanged.connect(self._on_selection_changed)

        # Context menu
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)

    def set_peak(self, peak):
        """Set the peak to display formulas for.

        Args:
            peak: MSPeak object from CoreMS
        """
        self._current_peak = peak
        self.model.set_peak(peak)

        if peak is not None:
            mz = getattr(peak, 'mz_exp', 0)
            n_formulas = len(peak.molecular_formulas) if hasattr(peak, 'molecular_formulas') else 0
            self.peak_info_label.setText(f"m/z {mz:.4f} - {n_formulas} candidate(s)")
            self.peak_info_label.setStyleSheet("color: black;")
        else:
            self.peak_info_label.setText("Select a peak to view candidates")
            self.peak_info_label.setStyleSheet("color: gray;")

    def clear(self):
        """Clear the widget."""
        self._current_peak = None
        self.model.clear()
        self.peak_info_label.setText("Select a peak to view candidates")
        self.peak_info_label.setStyleSheet("color: gray;")

    def _on_selection_changed(self, selected, deselected):
        """Handle formula selection change."""
        indexes = self.table.selectionModel().selectedRows()
        if indexes:
            proxy_index = indexes[0]
            source_index = self.proxy_model.mapToSource(proxy_index)
            row = source_index.row()
            if row < len(self.model._formulas):
                formula = self.model._formulas[row]
                self.formula_selected.emit(row, formula)

    def _show_context_menu(self, pos):
        """Show context menu for formula actions."""
        index = self.table.indexAt(pos)
        if not index.isValid():
            return

        source_index = self.proxy_model.mapToSource(index)
        row = source_index.row()
        if row >= len(self.model._formulas):
            return

        formula = self.model._formulas[row]

        menu = QMenu(self)

        # Get formula string for display
        if hasattr(formula, 'string'):
            formula_str = formula.string
        else:
            formula_str = str(formula)

        # Show isotopologues action
        isotope_action = QAction(f"Show expected isotopologues for {formula_str}", self)
        isotope_action.triggered.connect(lambda: self._show_isotopologues(formula))
        menu.addAction(isotope_action)

        menu.exec(self.table.viewport().mapToGlobal(pos))

    def _show_isotopologues(self, formula):
        """Calculate and emit isotopologue pattern for a formula.

        If the selected formula is itself an isotopologue, this will calculate
        the monoisotopic m/z and show all isotopologues with the selected one highlighted.

        Args:
            formula: MolecularFormula object
        """
        print(f"[DEBUG] _show_isotopologues called with formula: {formula}")

        if self._current_peak is None:
            print("[DEBUG] No current peak set")
            return

        # Get the formula's calculated m/z
        formula_mz = getattr(formula, 'mz_calc', None)
        if formula_mz is None:
            formula_mz = getattr(formula, 'calculated_mz', None)
        if formula_mz is None:
            formula_mz = self._current_peak.mz_exp

        # Check if this formula is an isotopologue
        is_isotopologue = getattr(formula, 'is_isotopologue', False)

        # Also check if the formula dict contains isotope atoms (13C, 15N, etc.)
        isotope_mass_shift = self._get_isotope_mass_shift(formula)

        if is_isotopologue or isotope_mass_shift > 0.5:
            # This is an isotopologue - calculate monoisotopic m/z
            mono_mz = formula_mz - isotope_mass_shift
            selected_shift = isotope_mass_shift
            print(f"[DEBUG] Formula is isotopologue, mono_mz={mono_mz:.4f}, shift={isotope_mass_shift:.4f}")
        else:
            # This is the monoisotopic formula
            mono_mz = formula_mz
            selected_shift = 0.0
            print(f"[DEBUG] Formula is monoisotopic, mono_mz={mono_mz:.4f}")

        # Calculate isotopologue pattern from the monoisotopic formula
        # We need to get the monoisotopic atom counts
        mono_atom_dict = self._get_monoisotopic_atom_dict(formula)
        isotopologues = self._calculate_isotopologue_pattern_from_dict(mono_atom_dict)

        print(f"[DEBUG] Calculated {len(isotopologues)} isotopologues")

        # Add info about which isotopologue is selected (mass shift closest to selected_shift)
        # The spectrum widget will use this to highlight the selected one
        # We encode this by adding a 4th element to the tuple for the selected one
        isotopologues_with_selection = []
        for name, mass_shift, rel_intensity in isotopologues:
            # Check if this is the selected isotopologue (within 0.1 Da tolerance)
            is_selected = abs(mass_shift - selected_shift) < 0.1
            isotopologues_with_selection.append((name, mass_shift, rel_intensity, is_selected))

        # Emit signal with monoisotopic m/z and isotopologue list
        self.isotopologues_requested.emit(mono_mz, isotopologues_with_selection)
        print(f"[DEBUG] Signal emitted for mono_mz={mono_mz:.4f}, selected_shift={selected_shift:.4f}")

    def _get_isotope_mass_shift(self, formula) -> float:
        """Calculate the mass shift from monoisotopic for a formula containing isotopes.

        Args:
            formula: MolecularFormula object

        Returns:
            Mass shift in Da (0 if monoisotopic)
        """
        import re

        # Get the formula dictionary
        if hasattr(formula, '_d_molecular_formula'):
            atom_dict = formula._d_molecular_formula
        elif hasattr(formula, 'to_dict'):
            atom_dict = formula.to_dict()
        else:
            return 0.0

        total_shift = 0.0

        for atom, count in atom_dict.items():
            if not isinstance(count, (int, float)) or count <= 0:
                continue

            # Check if this is an isotope (has number prefix like 13C, 15N, 18O)
            match = re.match(r'^(\d+)([A-Z][a-z]?)$', str(atom))
            if match:
                mass_number = match.group(1)
                base_element = match.group(2)

                # Get mass difference between isotope and base element
                isotope_mass = Atoms.atomic_masses.get(atom)
                base_mass = Atoms.atomic_masses.get(base_element)

                if isotope_mass is not None and base_mass is not None:
                    mass_diff = isotope_mass - base_mass
                    total_shift += mass_diff * count

            # Handle deuterium specially
            elif atom == 'D':
                h_mass = Atoms.atomic_masses.get('H')
                d_mass = Atoms.atomic_masses.get('D')
                if h_mass is not None and d_mass is not None:
                    total_shift += (d_mass - h_mass) * count

        return total_shift

    def _get_monoisotopic_atom_dict(self, formula) -> dict:
        """Convert a formula to its monoisotopic equivalent.

        Replaces isotope atoms (13C, 15N, etc.) with their base elements.

        Args:
            formula: MolecularFormula object

        Returns:
            Dictionary with monoisotopic atom counts
        """
        import re

        # Get the formula dictionary
        if hasattr(formula, '_d_molecular_formula'):
            atom_dict = dict(formula._d_molecular_formula)
        elif hasattr(formula, 'to_dict'):
            atom_dict = dict(formula.to_dict())
        else:
            return {}

        mono_dict = {}

        for atom, count in atom_dict.items():
            if not isinstance(count, (int, float)):
                # Keep non-numeric entries (like ion_type)
                mono_dict[atom] = count
                continue

            if count <= 0:
                continue

            # Check if this is an isotope
            match = re.match(r'^(\d+)([A-Z][a-z]?)$', str(atom))
            if match:
                # Convert isotope to base element
                base_element = match.group(2)
                mono_dict[base_element] = mono_dict.get(base_element, 0) + count
            elif atom == 'D':
                # Deuterium -> Hydrogen
                mono_dict['H'] = mono_dict.get('H', 0) + count
            else:
                # Already a base element
                mono_dict[atom] = mono_dict.get(atom, 0) + count

        return mono_dict

    def _calculate_isotopologue_pattern_from_dict(self, atom_dict: dict) -> List[Tuple[str, float, float]]:
        """Calculate isotopologue pattern from an atom dictionary.

        Args:
            atom_dict: Dictionary of atom counts (monoisotopic)

        Returns:
            List of (name, mass_shift, relative_intensity) tuples
        """
        import re
        isotopologues = []

        # Build mapping of base elements to their isotopes
        element_isotopes = {}

        for symbol, abundance in Atoms.isotopic_abundance.items():
            match = re.match(r'^(\d+)([A-Z][a-z]?)$', symbol)
            if match:
                base_element = match.group(2)
                if base_element not in element_isotopes:
                    element_isotopes[base_element] = []
                element_isotopes[base_element].append((symbol, abundance))
            elif symbol == 'D':
                if 'H' not in element_isotopes:
                    element_isotopes['H'] = []
                element_isotopes['H'].append(('D', abundance))

        # Process each element
        for base_element, n_atoms in atom_dict.items():
            if not isinstance(n_atoms, (int, float)) or n_atoms <= 0:
                continue
            if base_element not in Atoms.atomic_masses:
                continue

            n_atoms = int(n_atoms)
            base_abundance = Atoms.isotopic_abundance.get(base_element, 1.0)
            base_mass = Atoms.atomic_masses.get(base_element)

            if base_mass is None or base_abundance == 0:
                continue

            isotopes = element_isotopes.get(base_element, [])

            for isotope_symbol, isotope_abundance in isotopes:
                if isotope_abundance == 0:
                    continue

                isotope_mass = Atoms.atomic_masses.get(isotope_symbol)
                if isotope_mass is None:
                    continue

                mass_shift_per_atom = isotope_mass - base_mass
                total_abundance = base_abundance + sum(a for _, a in isotopes)
                p = isotope_abundance / total_abundance if total_abundance > 0 else 0

                if p == 0:
                    continue

                p_mono = (1 - p) ** n_atoms
                max_subs = min(n_atoms, 6)

                for k in range(1, max_subs + 1):
                    p_k = comb(n_atoms, k) * (p ** k) * ((1 - p) ** (n_atoms - k))
                    rel_intensity = p_k / p_mono if p_mono > 0 else 0

                    if rel_intensity > 0.005:
                        if k == 1:
                            name = isotope_symbol
                        else:
                            name = f"{isotope_symbol}×{k}"
                        mass_shift = mass_shift_per_atom * k
                        isotopologues.append((name, mass_shift, rel_intensity))

        isotopologues.sort(key=lambda x: x[1])
        return isotopologues

    def _calculate_isotopologue_pattern(self, formula) -> List[Tuple[str, float, float]]:
        """Calculate expected isotopologue pattern for a molecular formula.

        This is a wrapper that extracts the atom dictionary from the formula
        and delegates to _calculate_isotopologue_pattern_from_dict.

        Args:
            formula: MolecularFormula object with atom composition

        Returns:
            List of (name, mass_shift, relative_intensity) tuples
        """
        # Get the formula dictionary (atom counts)
        if hasattr(formula, '_d_molecular_formula'):
            atom_dict = formula._d_molecular_formula
        elif hasattr(formula, 'to_dict'):
            atom_dict = formula.to_dict()
        else:
            return []

        return self._calculate_isotopologue_pattern_from_dict(atom_dict)
