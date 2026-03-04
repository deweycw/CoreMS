#!/usr/bin/env python3
"""HRMS Viewer - Main application entry point."""

# CRITICAL: Configure Mono runtime BEFORE any other imports
# This must happen before PyQt6 or CoreMS to avoid threading conflicts
import sys
import platform

if platform.system() == "Darwin":  # macOS
    try:
        from clr_loader import get_mono
        from pythonnet import set_runtime
        mono_runtime = get_mono()
        set_runtime(mono_runtime)

        # Pre-load Thermo libraries on main thread
        import clr
        from pathlib import Path
        import importlib.util
        spec = importlib.util.find_spec('corems')
        if spec and spec.origin:
            dll_path = str(Path(spec.origin).parent.parent / "ext_lib" / "dotnet")
            sys.path.append(dll_path)
            clr.AddReference("ThermoFisher.CommonCore.RawFileReader")
            clr.AddReference("ThermoFisher.CommonCore.Data")
            clr.AddReference("ThermoFisher.CommonCore.MassPrecisionEstimator")
    except Exception as e:
        print(f"Warning: Could not configure Mono runtime: {e}")

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt

from hrms_viewer.app.main_window import MainWindow


def main():
    """Launch the HRMS Viewer application."""
    # Enable high DPI scaling
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName("HRMS Viewer")
    app.setOrganizationName("CoreMS")
    app.setApplicationVersion("0.1.0")

    # Set application style
    app.setStyle("Fusion")

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
