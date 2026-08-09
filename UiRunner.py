"""
Runner tab v7 — config selector, scenario selection, run, results.
"""
from __future__ import annotations
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QGroupBox,
    QComboBox, QPushButton, QProgressBar, QTextEdit, QListWidget, QListWidgetItem,
    QTableWidget, QTableWidgetItem, QMessageBox, QInputDialog, QLabel, QLineEdit)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QTextCursor, QColor, QFont
from Config import EnvironmentConfig
from Models import TestResult, ResultStatus
from Storage import DataBase
from Runner import TestRunner


class TestRunThread(QThread):
    log_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int)
    result_signal = pyqtSignal(object)
    step_signal = pyqtSignal(str, bool)
    assertion_signal = pyqtSignal(str, str)
    scenario_signal = pyqtSignal(str, bool)

    def __init__(self, runner, scenario_ids):
        super().__init__()
        self.runner = runner
        self.scenario_ids = scenario_ids

    def run(self):
        try:
            self.runner.log_message.connect(self.log_signal.emit)
            self.runner.progress.connect(self.progress_signal.emit)
            self.runner.step_completed.connect(self.step_signal.emit)
            self.runner.assertion_evaluated.connect(self.assertion_signal.emit)
            self.runner.scenario_completed.connect(self.scenario_signal.emit)
            self.runner.finished.connect(self.result_signal.emit)
            self.runner.run_scenarios(self.scenario_ids)
        except Exception as e:
            self.log_signal.emit(f"FATAL ERROR: {e}")
            self.result_signal.emit(None)


class RunnerTab(QWidget):
    GREEN = QColor(34, 197, 94)
    RED = QColor(239, 68, 68)
    ORANGE = QColor(249, 115, 22)

    def __init__(self, db: DataBase, config_tab=None):
        super().__init__()
        self.db = db
        self.config_tab = config_tab
        self.current_result = None
        self.run_thread = None
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        # Config selector
        cg = QGroupBox("Environment Configuration")
        cl = QHBoxLayout(cg)
        cl.addWidget(QLabel("Select config:"))
        self.config_combo = QComboBox()
        cl.addWidget(self.config_combo)
        self.refresh_cfg_btn = QPushButton("↻ Refresh")
        self.refresh_cfg_btn.clicked.connect(self._refresh_configs)
        cl.addWidget(self.refresh_cfg_btn)
        layout.addWidget(cg)

        # Scenarios
        sg = QGroupBox("Scenario Selection")
        sl = QVBoxLayout(sg)
        sf = QHBoxLayout()
        sf.addWidget(QLabel("Filter by module:"))
        self.scenario_module_filter = QComboBox()
        self.scenario_module_filter.currentIndexChanged.connect(lambda: self.refresh())
        sf.addWidget(self.scenario_module_filter)
        sf.addStretch()
        sl.addLayout(sf)
        self.scenario_list = QListWidget()
        sl.addWidget(self.scenario_list)
        sb = QHBoxLayout()
        self.select_all_btn = QPushButton("Select All")
        self.select_all_btn.clicked.connect(self._sel_all)
        sb.addWidget(self.select_all_btn)
        self.deselect_all_btn = QPushButton("Deselect All")
        self.deselect_all_btn.clicked.connect(self._desel_all)
        sb.addWidget(self.deselect_all_btn)
        sl.addLayout(sb)
        layout.addWidget(sg)

        # Execution
        eg = QGroupBox("Execution")
        el = QVBoxLayout(eg)
        self.run_btn = QPushButton("Run Tests")
        self.run_btn.setMinimumHeight(40)
        self.run_btn.setStyleSheet(
            "QPushButton{background-color:#22c55e;color:white;font-weight:bold;"
            "font-size:14px;border-radius:6px;}QPushButton:disabled{background-color:#9ca3af;}")
        self.run_btn.clicked.connect(self._run)
        el.addWidget(self.run_btn)
        self.progress_bar = QProgressBar()
        el.addWidget(self.progress_bar)
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setFont(QFont("Consolas", 9))
        self.log_output.setMaximumHeight(150)
        el.addWidget(self.log_output)
        layout.addWidget(eg)

        # Results
        rg = QGroupBox("Results")
        rl = QVBoxLayout(rg)
        sr = QHBoxLayout()
        self.scenario_summary = QLineEdit("Scenarios: 0/0")
        self.scenario_summary.setReadOnly(True)
        self.step_summary = QLineEdit("Steps: 0/0")
        self.step_summary.setReadOnly(True)
        self.assertion_summary = QLineEdit("Assertions: 0/0")
        self.assertion_summary.setReadOnly(True)
        for w in [self.scenario_summary, self.step_summary, self.assertion_summary]:
            sr.addWidget(w)
        rl.addLayout(sr)
        self.results_table = QTableWidget(0, 7)
        self.results_table.setHorizontalHeaderLabels(
            ["Assertion", "Scope", "Step", "Row", "Status", "Expected", "Actual"])
        self.results_table.setEditTriggers(QTableWidget.NoEditTriggers)
        rl.addWidget(self.results_table)
        rb = QHBoxLayout()
        self.save_res_btn = QPushButton("Save Results")
        self.save_res_btn.clicked.connect(self._save_res)
        rb.addWidget(self.save_res_btn)
        self.load_res_btn = QPushButton("Load Previous")
        self.load_res_btn.clicked.connect(self._load_res)
        rb.addWidget(self.load_res_btn)
        rl.addLayout(rb)
        layout.addWidget(rg)

    def _refresh_configs(self):
        self.config_combo.clear()
        for cfg in self.db.list_configs():
            self.config_combo.addItem(
                f"[{cfg.config_Id}] {cfg.config_Name} ({len(cfg.global_Variables or [])} vars)",
                cfg.config_Id)

    def refresh(self):
        self._refresh_configs()
        self.scenario_module_filter.blockSignals(True)
        cur = self.scenario_module_filter.currentData() if self.scenario_module_filter.count() > 0 else "all"
        self.scenario_module_filter.clear()
        self.scenario_module_filter.addItem("All", "all")
        self.scenario_module_filter.addItem("No Module", "none")
        for m in self.db.list_modules():
            self.scenario_module_filter.addItem(f"[{m.module_Id}] {m.module_Name}", m.module_Id)
        for i in range(self.scenario_module_filter.count()):
            if self.scenario_module_filter.itemData(i) == cur:
                self.scenario_module_filter.setCurrentIndex(i)
                break
        self.scenario_module_filter.blockSignals(False)

        filter_val = self.scenario_module_filter.currentData() if self.scenario_module_filter.count() > 0 else "all"
        all_s = self.db.list_scenarios()
        if filter_val == "all":
            scenarios = all_s
        elif filter_val == "none":
            scenarios = [s for s in all_s if not s.module_Ids]
        else:
            mid = int(filter_val)
            scenarios = [s for s in all_s if mid in (s.module_Ids or [])]

        self.scenario_list.clear()
        for s in scenarios:
            ds_info = ""
            if s.data_Set_Id and s.data_Set_Id > 0:
                ds = self.db.load_data_set(s.data_Set_Id)
                if ds:
                    ds_info = f" | Data: {ds.data_Set_Name} ({len(ds.rows)} rows)"
            item = QListWidgetItem(f"[{s.scenario_Id}] {s.scenario_Name}{ds_info}")
            item.setCheckState(Qt.Unchecked)
            item.setData(Qt.UserRole, s.scenario_Id)
            self.scenario_list.addItem(item)

    def _sel_all(self):
        for i in range(self.scenario_list.count()):
            self.scenario_list.item(i).setCheckState(Qt.Checked)

    def _desel_all(self):
        for i in range(self.scenario_list.count()):
            self.scenario_list.item(i).setCheckState(Qt.Unchecked)

    def _run(self):
        ids = [self.scenario_list.item(i).data(Qt.UserRole)
               for i in range(self.scenario_list.count())
               if self.scenario_list.item(i).checkState() == Qt.Checked]
        if not ids:
            QMessageBox.warning(self, "None", "Select at least one scenario.")
            return

        cfg = None
        cid = self.config_combo.currentData()
        if cid:
            cfg = self.db.load_config_by_id(cid)
        if cfg is None and self.config_tab:
            cfg = self.config_tab.get_current_config()
        if cfg is None:
            QMessageBox.warning(self, "No Config", "Create a configuration in the Configuration tab first.")
            return

        self.run_btn.setEnabled(False)
        self.run_btn.setText("Running...")
        self.progress_bar.setValue(0)
        self.log_output.clear()
        runner = TestRunner(cfg, self.db)
        self.run_thread = TestRunThread(runner, ids)
        self.run_thread.log_signal.connect(self._log)
        self.run_thread.progress_signal.connect(self.progress_bar.setValue)
        self.run_thread.result_signal.connect(self._finished)
        self.run_thread.step_signal.connect(
            lambda n, ok: self._log(f"  Step: {n} -> {'PASSED' if ok else 'FAILED'}"))
        self.run_thread.assertion_signal.connect(
            lambda n, s: self._log(f"  Assertion: {n} -> {s}"))
        self.run_thread.scenario_signal.connect(
            lambda n, ok: self._log(f"Scenario: {n} -> {'PASSED' if ok else 'FAILED'}"))
        self.run_thread.start()

    def _log(self, text):
        self.log_output.append(text)
        c = self.log_output.textCursor()
        c.movePosition(QTextCursor.End)
        self.log_output.setTextCursor(c)

    def _finished(self, result):
        self.run_btn.setEnabled(True)
        self.run_btn.setText("Run Tests")
        if result is None:
            QMessageBox.critical(self, "Error", "Test execution failed.")
            return
        self.current_result = result
        self.scenario_summary.setText(f"Scenarios: {result.passed_Scenarios}/{result.total_Scenarios}")
        self.step_summary.setText(f"Steps: {result.passed_Steps}/{result.total_Steps}")
        self.assertion_summary.setText(f"Assertions: {result.passed_Assertions}/{result.total_Assertions}")
        self.results_table.setRowCount(0)
        for ar in result.assertion_Results:
            row = self.results_table.rowCount()
            self.results_table.insertRow(row)
            self.results_table.setItem(row, 0, QTableWidgetItem(ar.assertion_Name))
            self.results_table.setItem(row, 1, QTableWidgetItem(getattr(ar, 'scope', '')))
            self.results_table.setItem(row, 2, QTableWidgetItem(getattr(ar, 'step_Name', '')))
            row_label = str(ar.data_Row_Index + 1) if ar.data_Row_Index >= 0 else "-"
            self.results_table.setItem(row, 3, QTableWidgetItem(row_label))
            si = QTableWidgetItem(ar.status.value.upper())
            if ar.status == ResultStatus.PASSED:
                si.setForeground(self.GREEN)
            elif ar.status == ResultStatus.FAILED:
                si.setForeground(self.RED)
            else:
                si.setForeground(self.ORANGE)
            self.results_table.setItem(row, 4, si)
            self.results_table.setItem(row, 5, QTableWidgetItem(ar.expected_Value))
            self.results_table.setItem(row, 6, QTableWidgetItem(ar.actual_Value))
        QMessageBox.information(self, "Complete",
                                f"Status: {result.status.value.upper()}\n"
                                f"Assertions: {result.passed_Assertions}/{result.total_Assertions} passed")

    def _save_res(self):
        if self.current_result:
            self.db.save_result(self.current_result)
            QMessageBox.information(self, "Saved", "Results saved.")

    def _load_res(self):
        results = self.db.list_results()
        if not results:
            QMessageBox.information(self, "None", "No saved results.")
            return
        names = [f"{r.test_Name} ({r.status.value})" for r in results]
        ch, ok = QInputDialog.getItem(self, "Load", "Select:", names, 0, False)
        if ok and ch:
            self._finished(results[names.index(ch)])

