"""Terminal-like output window for displaying processing output."""

import sys
from io import StringIO
from typing import Optional
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QTextEdit, QPushButton, QHBoxLayout,
    QWidget, QApplication
)
from PyQt6.QtCore import Qt, pyqtSignal, QObject
from PyQt6.QtGui import QFont, QTextCursor, QColor


class OutputCapture(QObject):
    """Captures stdout/stderr and emits signals with the text."""

    text_written = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self._buffer = StringIO()

    def write(self, text):
        if text:
            self._buffer.write(text)
            self.text_written.emit(text)

    def flush(self):
        pass

    def getvalue(self):
        return self._buffer.getvalue()


class OutputWindow(QDialog):
    """Terminal-like window for displaying processing output.

    Shows stdout/stderr output in a scrolling text area with monospace font.
    Can be used for formula assignment, calibration, and other long-running tasks.
    """

    # Class-level instance for reuse
    _instance: Optional['OutputWindow'] = None

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle("Processing Output")
        self.setMinimumSize(700, 400)
        self.setWindowFlags(
            Qt.WindowType.Window |
            Qt.WindowType.WindowMinimizeButtonHint |
            Qt.WindowType.WindowMaximizeButtonHint |
            Qt.WindowType.WindowCloseButtonHint
        )

        self._original_stdout = None
        self._original_stderr = None
        self._capture = None

        self._setup_ui()

    def _setup_ui(self):
        """Set up the UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        # Output text area
        self.output_text = QTextEdit()
        self.output_text.setReadOnly(True)
        self.output_text.setFont(QFont("Monaco", 11) if sys.platform == "darwin"
                                  else QFont("Consolas", 10))

        # Dark terminal-like styling
        self.output_text.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #d4d4d4;
                border: 1px solid #3c3c3c;
                padding: 8px;
            }
        """)

        layout.addWidget(self.output_text)

        # Button row
        button_layout = QHBoxLayout()

        self.clear_btn = QPushButton("Clear")
        self.clear_btn.clicked.connect(self.clear)
        button_layout.addWidget(self.clear_btn)

        button_layout.addStretch()

        self.close_btn = QPushButton("Close")
        self.close_btn.clicked.connect(self.hide)
        button_layout.addWidget(self.close_btn)

        layout.addLayout(button_layout)

    @classmethod
    def get_instance(cls, parent=None) -> 'OutputWindow':
        """Get or create the singleton instance."""
        if cls._instance is None or not cls._instance.isVisible():
            cls._instance = cls(parent)
        return cls._instance

    def clear(self):
        """Clear the output text."""
        self.output_text.clear()

    def append_text(self, text: str, color: Optional[str] = None):
        """Append text to the output.

        Args:
            text: Text to append
            color: Optional color name or hex code
        """
        cursor = self.output_text.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)

        if color:
            # Insert colored text
            fmt = cursor.charFormat()
            fmt.setForeground(QColor(color))
            cursor.setCharFormat(fmt)
            cursor.insertText(text)
            # Reset to default color
            fmt.setForeground(QColor("#d4d4d4"))
            cursor.setCharFormat(fmt)
        else:
            cursor.insertText(text)

        # Auto-scroll to bottom
        self.output_text.setTextCursor(cursor)
        self.output_text.ensureCursorVisible()

        # Process events to update display
        QApplication.processEvents()

    def append_line(self, text: str, color: Optional[str] = None):
        """Append a line of text (with newline)."""
        self.append_text(text + "\n", color)

    def append_header(self, text: str):
        """Append a header line (cyan colored)."""
        self.append_line("=" * 60, "#569cd6")
        self.append_line(text, "#569cd6")
        self.append_line("=" * 60, "#569cd6")

    def append_success(self, text: str):
        """Append success message (green)."""
        self.append_line(text, "#4ec9b0")

    def append_warning(self, text: str):
        """Append warning message (yellow)."""
        self.append_line(text, "#dcdcaa")

    def append_error(self, text: str):
        """Append error message (red)."""
        self.append_line(text, "#f14c4c")

    def start_capture(self):
        """Start capturing stdout/stderr."""
        self._capture = OutputCapture()
        self._capture.text_written.connect(self.append_text)

        self._original_stdout = sys.stdout
        self._original_stderr = sys.stderr

        sys.stdout = self._capture
        sys.stderr = self._capture

    def stop_capture(self):
        """Stop capturing stdout/stderr."""
        if self._original_stdout:
            sys.stdout = self._original_stdout
            self._original_stdout = None

        if self._original_stderr:
            sys.stderr = self._original_stderr
            self._original_stderr = None

        self._capture = None

    def closeEvent(self, event):
        """Handle close event - stop capture if active."""
        self.stop_capture()
        super().closeEvent(event)

    def show_and_raise(self):
        """Show the window and bring it to front."""
        self.show()
        self.raise_()
        self.activateWindow()
