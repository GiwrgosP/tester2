"""
Record tab v7 — dedicated tab for recording steps via Playwright codegen.
NEW: Select which steps to keep, assign module to all recorded steps.
Simplified form: URL, browser, device type only (no config picker).
"""
from __future__ import annotations
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLineEdit, QComboBox, QPushButton, QLabel, QGroupBox, QMessageBox,
    QTextEdit, QListWidget, QListWidgetItem, QDialog, QDialogButtonBox,
    QTableWidget, QTableWidgetItem, QCheckBox, QHeaderView)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont
from Config import DeviceType
from Storage import DataBase
from Recorder import StepRecorder


class RecordingThread(QThread):
    """Background thread for Playwright codegen recording."""
    steps_ready = pyqtSignal(list)
    error_occurred = pyqtSignal(str)
    log_message = pyqtSignal(str)

    def __init__(self, url, browser, device_type="desktop"):
        super().__init__()
        self.url = url
        self.browser = browser
        self.device_type = device_type

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


class _StepsReviewDialog(QDialog):
    """Dialog for reviewing recorded steps, selecting which to keep,
    and assigning a module to all of them."""

    def __init__(self, steps, modules, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Review Recorded Steps")
        self.setMinimumSize(800, 500)
        self._steps = steps
        self._modules = modules
        self._build_ui()
        self._populate()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        # Info
        info = QLabel(f"Recorded {len(self._steps)} steps. Select which to keep and assign a module.")
        info.setStyleSheet("padding: 5px; color: #64748b;")
        layout.addWidget(info)

        # Module assignment
        module_row = QHBoxLayout()
        module_row.addWidget(QLabel("Assign module to selected steps:"))
        self.module_combo = QComboBox()
        self.module_combo.addItem("No Module", 0)
        for m in self._modules:
            self.module_combo.addItem(f"[{m.module_Id}] {m.module_Name}", m.module_Id)
        module_row.addWidget(self.module_combo)
        module_row.addStretch()
        layout.addLayout(module_row)

        # Steps table with checkboxes
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["Keep", "Name", "Action", "Selector", "Input Value", "Description"])
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table)

        # Buttons row
        btn_row = QHBoxLayout()
        self.select_all_btn = QPushButton("Select All")
        self.select_all_btn.clicked.connect(self._select_all)
        btn_row.addWidget(self.select_all_btn)
        self.deselect_all_btn = QPushButton("Deselect All")
        self.deselect_all_btn.clicked.connect(self._deselect_all)
        btn_row.addWidget(self.deselect_all_btn)
        self.select_none_btn = QPushButton("Select None")
        self.select_none_btn.clicked.connect(self._select_none)
        btn_row.addWidget(self.select_none_btn)
        btn_row.addStretch()
        self.count_label = QLabel(f"{len(self._steps)} selected")
        btn_row.addWidget(self.count_label)
        layout.addLayout(btn_row)

        # OK / Cancel
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _populate(self):
        self.table.setRowCount(0)
        for step in self._steps:
            r = self.table.rowCount()
            self.table.insertRow(r)

            # Keep checkbox
            keep_item = QTableWidgetItem()
            keep_item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
            keep_item.setCheckState(Qt.Checked)  # all checked by default
            self.table.setItem(r, 0, keep_item)

            # Step info (read-only)
            self.table.setItem(r, 1, QTableWidgetItem(step.step_Name))
            self.table.setItem(r, 2, QTableWidgetItem(step.action_Type.value))
            self.table.setItem(r, 3, QTableWidgetItem(step.target_Selector))
            self.table.setItem(r, 4, QTableWidgetItem(step.input_Value))
            self.table.setItem(r, 5, QTableWidgetItem(step.target_Description))

        self._update_count()

    def _select_all(self):
        for i in range(self.table.rowCount()):
            self.table.item(i, 0).setCheckState(Qt.Checked)
        self._update_count()

    def _deselect_all(self):
        for i in range(self.table.rowCount()):
            self.table.item(i, 0).setCheckState(Qt.Unchecked)
        self._update_count()

    def _select_none(self):
        self._deselect_all()

    def _update_count(self):
        count = sum(1 for i in range(self.table.rowCount())
                    if self.table.item(i, 0).checkState() == Qt.Checked)
        self.count_label.setText(f"{count} selected")

    def get_selected_steps(self) -> list:
        """Return list of Step objects that are checked, with module assigned."""
        module_id = self.module_combo.currentData() or 0
        selected = []
        for i in range(self.table.rowCount()):
            if self.table.item(i, 0).checkState() == Qt.Checked:
                step = self._steps[i]
                # Assign module if selected
                if module_id > 0:
                    step.module_Ids = [module_id]
                selected.append(step)
        return selected

    def get_module_id(self) -> int:
        return self.module_combo.currentData() or 0


class RecordTab(QWidget):
    """Dedicated tab for recording steps via Playwright codegen.
    After recording, shows a review dialog to select steps and assign module."""

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
            "Close the browser when done. You'll review the captured steps and "
            "choose which ones to keep.")
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

        # Device type
        self.device_combo = QComboBox()
        self.device_combo.addItem("Desktop", "desktop")
        self.device_combo.addItem("Mobile", "mobile")
        self.device_combo.addItem("Tablet", "tablet")
        form_layout.addRow("Device Type:", self.device_combo)

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
        # No config combo to refresh — just clear and go
        pass

    def _start_recording(self):
        url = self.url_input.text().strip()
        if not url:
            QMessageBox.warning(self, "URL", "Enter the ERP URL first.")
            return
        if not url.startswith("http"):
            url = "https://" + url

        browser = self.browser_combo.currentData()
        device_type = self.device_combo.currentData()

        self.record_btn.setEnabled(False)
        self.record_btn.setText("🎥 Recording... (close browser to stop)")
        self.status_label.setText("Recording in progress — interact with the browser")
        self.status_label.setStyleSheet("color:#ef4444;font-weight:bold;padding:5px;")
        self.log_output.clear()
        self.steps_list.clear()

        self._thread = RecordingThread(url, browser, device_type)
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

        # Show review dialog
        modules = self.db.list_modules()
        dialog = _StepsReviewDialog(steps, modules, self)

        if dialog.exec_() == QDialog.Accepted:
            selected_steps = dialog.get_selected_steps()
            module_id = dialog.get_module_id()

            if not selected_steps:
                self.log_output.append("No steps selected. Nothing saved.")
                self.steps_list.clear()
                return

            # Save selected steps to database
            count = 0
            self.steps_list.clear()
            for step in selected_steps:
                self.db.save_step(step)
                count += 1
                module_info = f" | Module: #{module_id}" if module_id > 0 else ""
                self.steps_list.addItem(
                    f"[{step.step_Id}] {step.step_Name} - {step.action_Type.value}{module_info}")

            module_name = "None"
            if module_id > 0:
                m = self.db.load_module(module_id)
                module_name = m.module_Name if m else f"#{module_id}"

            self.log_output.append(f"Saved {count} steps to database (module: {module_name}).")
            QMessageBox.information(self, "Recording Complete",
                                    f"{count} steps recorded and saved (module: {module_name}).\n"
                                    f"Go to the Steps tab to edit them.")
        else:
            self.log_output.append("Recording cancelled — no steps saved.")
            self.steps_list.clear()

    def _on_error(self, error):
        self.record_btn.setEnabled(True)
        self.record_btn.setText("🎥 Start Recording")
        self.status_label.setText("Recording failed")
        self.status_label.setStyleSheet("color:#ef4444;font-weight:bold;padding:5px;")
        self.log_output.append(f"ERROR: {error}")
        QMessageBox.critical(self, "Recording Error", error)

