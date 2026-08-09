"""
Record tab — dedicated tab for recording steps via Playwright codegen.
"""
from __future__ import annotations
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLineEdit, QComboBox, QPushButton, QLabel, QGroupBox, QMessageBox,
    QTextEdit, QListWidget, QListWidgetItem)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont
from Config import EnvironmentConfig
from Storage import DataBase
from Recorder import StepRecorder


class RecordingThread(QThread):
    """Background thread for Playwright codegen recording."""
    steps_ready = pyqtSignal(list)
    error_occurred = pyqtSignal(str)
    log_message = pyqtSignal(str)

    def __init__(self, url, browser):
        super().__init__()
        self.url = url
        self.browser = browser

    def run(self):
        try:
            self.log_message.emit(f"Starting recording: url={self.url}, browser={self.browser}")
            recorder = StepRecorder()
            steps = recorder.start_recording(self.url, self.browser)
            self.log_message.emit(f"Recording finished: {len(steps)} steps captured")
            self.steps_ready.emit(steps)
        except Exception as e:
            import traceback
            traceback.print_exc()
            self.error_occurred.emit(str(e))


class RecordTab(QWidget):
    """Dedicated tab for recording steps via Playwright codegen."""

    def __init__(self, db: DataBase):
        super().__init__()
        self.db = db
        self._thread = None
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        # Title
        title = QLabel("Record Steps")
        title.setStyleSheet("font-size:18px;font-weight:bold;padding:10px;")
        layout.addWidget(title)

        desc = QLabel(
            "Enter the ERP URL and click 'Start Recording'. "
            "A browser will open — interact with the ERP normally. "
            "Close the browser when done and your steps will be captured automatically.")
        desc.setWordWrap(True)
        desc.setStyleSheet("color:#64748b;padding:0 10px 10px 10px;")
        layout.addWidget(desc)

        # Recording form
        form_group = QGroupBox("Recording Settings")
        form_layout = QFormLayout(form_group)

        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("https://your-erp.com")
        form_layout.addRow("App URL:", self.url_input)

        self.browser_combo = QComboBox()
        self.browser_combo.addItem("Chrome", "chromium")
        self.browser_combo.addItem("Firefox", "firefox")
        self.browser_combo.addItem("Safari (WebKit)", "webkit")
        self.browser_combo.addItem("Edge", "edge")
        form_layout.addRow("Browser:", self.browser_combo)

        # Config picker for global variables
        self.config_combo = QComboBox()
        form_layout.addRow("Config (for {{global.vars}}):", self.config_combo)

        layout.addWidget(form_group)

        # Record button
        self.record_btn = QPushButton("🎥 Start Recording")
        self.record_btn.setMinimumHeight(50)
        self.record_btn.setStyleSheet(
            "QPushButton{background-color:#ef4444;color:white;font-weight:bold;"
            "font-size:16px;border-radius:6px;}QPushButton:disabled{background-color:#9ca3af;}")
        self.record_btn.clicked.connect(self._start_recording)
        layout.addWidget(self.record_btn)

        # Status / log
        self.status_label = QLabel("Ready to record")
        self.status_label.setStyleSheet("color:#22c55e;font-weight:bold;padding:5px;")
        layout.addWidget(self.status_label)

        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setFont(QFont("Consolas", 9))
        self.log_output.setMaximumHeight(200)
        layout.addWidget(self.log_output)

        # Recorded steps preview
        self.steps_list = QListWidget()
        self.steps_list.setMaximumHeight(200)
        layout.addWidget(QLabel("Recorded steps (auto-saved):"))
        layout.addWidget(self.steps_list)

    def refresh(self):
        self.config_combo.clear()
        for cfg in self.db.list_configs():
            gvars = cfg.global_Variables or []
            self.config_combo.addItem(
                f"[{cfg.config_Id}] {cfg.config_Name} ({len(gvars)} vars)", cfg.config_Id)

    def _start_recording(self):
        url = self.url_input.text().strip()
        if not url:
            QMessageBox.warning(self, "URL", "Enter the ERP URL first.")
            return
        if not url.startswith("http"):
            url = "https://" + url

        browser = self.browser_combo.currentData()

        self.record_btn.setEnabled(False)
        self.record_btn.setText("🎥 Recording... (close browser to stop)")
        self.status_label.setText("Recording in progress — interact with the browser")
        self.status_label.setStyleSheet("color:#ef4444;font-weight:bold;padding:5px;")
        self.log_output.clear()
        self.steps_list.clear()

        self._thread = RecordingThread(url, browser)
        self._thread.log_message.connect(self._log)
        self._thread.steps_ready.connect(self._on_steps_ready)
        self._thread.error_occurred.connect(self._on_error)
        self._thread.start()

    def _log(self, text):
        self.log_output.append(text)
        c = self.log_output.textCursor()
        c.movePosition(__import__('PyQt5.QtGui', fromlist=['QTextCursor']).QTextCursor.End)
        self.log_output.setTextCursor(c)

    def _on_steps_ready(self, steps):
        self.record_btn.setEnabled(True)
        self.record_btn.setText("🎥 Start Recording")
        self.status_label.setText(f"Recording complete — {len(steps)} steps captured")
        self.status_label.setStyleSheet("color:#22c55e;font-weight:bold;padding:5px;")

        if not steps:
            self.log_output.append("No steps were captured. Did you interact with the browser?")
            return

        # Save steps to database
        count = 0
        for step in steps:
            self.db.save_step(step)
            count += 1
            self.steps_list.addItem(f"[{step.step_Id}] {step.step_Name} - {step.action_Type.value}")

        self.log_output.append(f"Saved {count} steps to database.")
        QMessageBox.information(self, "Recording Complete",
                                f"{count} steps recorded and saved.\n"
                                f"Go to the Steps tab to edit them.")

    def _on_error(self, error):
        self.record_btn.setEnabled(True)
        self.record_btn.setText("🎥 Start Recording")
        self.status_label.setText("Recording failed")
        self.status_label.setStyleSheet("color:#ef4444;font-weight:bold;padding:5px;")
        self.log_output.append(f"ERROR: {error}")
        QMessageBox.critical(self, "Recording Error", error)

