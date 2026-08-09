"""
Assertions tab — view/edit assertions. Opens a dialog with scrollbar for editing.
"""
from __future__ import annotations
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QTableWidget, QTableWidgetItem, QLineEdit, QComboBox, QSpinBox,
    QPushButton, QListWidget, QListWidgetItem, QGroupBox, QMessageBox,
    QDialog, QDialogButtonBox, QLabel, QScrollArea)
from PyQt5.QtCore import Qt
from Models import Assertion, AssertionType, ComparisonOperator
from Storage import DataBase


class _AssertionEditDialog(QDialog):
    """Dialog for editing a single assertion with scrollbar."""

    def __init__(self, assertion, db, parent=None):
        super().__init__(parent)
        self.db = db
        self.assertion = assertion
        self.setWindowTitle(f"Edit Assertion: {assertion.assertion_Name}" if assertion.assertion_Name else "New Assertion")
        self.setMinimumSize(600, 500)
        self._module_ids = list(assertion.module_Ids or [])
        self._build_ui()
        self._load_assertion()

    def _build_ui(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setFrameShape(QScrollArea.NoFrame)

        content = QWidget()
        form = QFormLayout(content)

        self.name_input = QLineEdit()
        form.addRow("Assertion Name:", self.name_input)

        self.type_combo = QComboBox()
        for t, lbl in AssertionType.labels().items():
            self.type_combo.addItem(lbl, t.value)
        form.addRow("Assertion Type:", self.type_combo)

        self.selector_input = QLineEdit()
        self.selector_input.setPlaceholderText("e.g. label=Username or #my-element or (empty for page-level)")
        form.addRow("Target Selector:", self.selector_input)

        self.expected_input = QLineEdit()
        self.expected_input.setPlaceholderText("Expected value or {{global.var}} or {{var}}")
        form.addRow("Expected Value:", self.expected_input)

        self.comparison_combo = QComboBox()
        for op, lbl in ComparisonOperator.labels().items():
            self.comparison_combo.addItem(lbl, op.value)
        form.addRow("Comparison:", self.comparison_combo)

        self.timeout_spin = QSpinBox()
        self.timeout_spin.setRange(1000, 60000)
        self.timeout_spin.setValue(5000)
        self.timeout_spin.setSuffix(" ms")
        form.addRow("Timeout:", self.timeout_spin)

        scroll.setWidget(content)

        main_layout = QVBoxLayout(self)
        main_layout.addWidget(scroll)

        # Variables hint
        self.vars_label = QLabel("Variables: none")
        self.vars_label.setStyleSheet("color:#6366f1;font-size:11px;")
        main_layout.addWidget(self.vars_label)

        # Modules
        mg = QGroupBox("Modules")
        ml = QVBoxLayout(mg)
        self.module_list = QListWidget()
        self.module_list.setMaximumHeight(80)
        ml.addWidget(self.module_list)
        mb = QHBoxLayout()
        self.add_mod_btn = QPushButton("Add Module...")
        self.add_mod_btn.clicked.connect(self._add_module)
        mb.addWidget(self.add_mod_btn)
        self.rm_mod_btn = QPushButton("Remove")
        self.rm_mod_btn.clicked.connect(self._rm_module)
        mb.addWidget(self.rm_mod_btn)
        mb.addStretch()
        ml.addLayout(mb)
        main_layout.addWidget(mg)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        main_layout.addWidget(buttons)

    def _load_assertion(self):
        a = self.assertion
        self.name_input.setText(a.assertion_Name)
        am = {t.value: lbl for t, lbl in AssertionType.labels().items()}
        self.type_combo.setCurrentText(am.get(a.assertion_Type.value, "Element Visible"))
        self.selector_input.setText(a.target_Selector)
        self.expected_input.setText(a.expected_Value)
        cm = {op.value: lbl for op, lbl in ComparisonOperator.labels().items()}
        self.comparison_combo.setCurrentText(cm.get(a.comparison_Operator.value, "Equals"))
        self.timeout_spin.setValue(a.timeout_Ms)
        self._refresh_mod_list()
        self._refresh_vars()

    def _refresh_vars(self):
        import re
        vars_set = set()
        for text in [self.expected_input.text(), self.selector_input.text()]:
            for m in re.findall(r'\{\{(global\.\w+|\w+)\}\}', text or ""):
                vars_set.add(m)
        self.vars_label.setText(f"Variables: {', '.join(sorted(vars_set)) if vars_set else 'none'}")

    def _refresh_mod_list(self):
        self.module_list.clear()
        for mid in self._module_ids:
            m = self.db.load_module(mid)
            name = m.module_Name if m else f"(missing #{mid})"
            item = QListWidgetItem(f"[{mid}] {name}")
            item.setData(Qt.UserRole, mid)
            self.module_list.addItem(item)

    def _add_module(self):
        from UiScenarios import _PickerDialog
        all_m = self.db.list_modules()
        existing = set(self._module_ids)
        items = [(m.module_Id, f"[{m.module_Id}] {m.module_Name}", []) for m in all_m
                 if m.module_Id not in existing]
        if not items:
            QMessageBox.information(self, "None", "No modules available.")
            return
        dialog = _PickerDialog("Add Modules", ["ID", "Name", "Description", "Parent"], self)
        dialog.set_rows([{"id": m.module_Id, "cells": [m.module_Id, m.module_Name,
                         m.module_Description, "None"], "module_Ids": []} for m in all_m])
        if dialog.exec_() == QDialog.Accepted:
            for mid in dialog.get_selected():
                if mid not in self._module_ids:
                    self._module_ids.append(mid)
            self._refresh_mod_list()

    def _rm_module(self):
        item = self.module_list.currentItem()
        if item:
            self._module_ids.remove(item.data(Qt.UserRole))
            self._refresh_mod_list()

    def get_assertion(self) -> Assertion:
        """Return the edited assertion from the form."""
        am = {lbl: t.value for t, lbl in AssertionType.labels().items()}
        cm = {lbl: op.value for op, lbl in ComparisonOperator.labels().items()}
        a = Assertion()
        a.assertion_Id = self.assertion.assertion_Id
        a.assertion_Name = self.name_input.text().strip()
        a.assertion_Type = AssertionType(am.get(self.type_combo.currentText(), "element_visible"))
        a.target_Selector = self.selector_input.text().strip()
        a.expected_Value = self.expected_input.text().strip()
        a.comparison_Operator = ComparisonOperator(cm.get(self.comparison_combo.currentText(), "equals"))
        a.timeout_Ms = self.timeout_spin.value()
        a.module_Ids = list(self._module_ids)
        return a


class AssertionsTab(QWidget):
    """Assertions tab — view/edit assertions with dialog-based editing."""

    def __init__(self, db: DataBase):
        super().__init__()
        self.db = db
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        btn_row = QHBoxLayout()
        self.add_btn = QPushButton("New Assertion")
        self.add_btn.clicked.connect(self._add_assertion)
        btn_row.addWidget(self.add_btn)
        self.edit_btn = QPushButton("Edit")
        self.edit_btn.clicked.connect(self._edit_assertion)
        btn_row.addWidget(self.edit_btn)
        self.del_btn = QPushButton("Delete")
        self.del_btn.clicked.connect(self._delete_assertion)
        btn_row.addWidget(self.del_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(
            ["ID", "Name", "Type", "Selector", "Expected", "Comparison", "Modules"])
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        layout.addWidget(self.table)

    def refresh(self):
        self.table.setRowCount(0)
        for a in self.db.list_assertions():
            r = self.table.rowCount()
            self.table.insertRow(r)
            self.table.setItem(r, 0, QTableWidgetItem(str(a.assertion_Id)))
            self.table.setItem(r, 1, QTableWidgetItem(a.assertion_Name))
            self.table.setItem(r, 2, QTableWidgetItem(a.assertion_Type.value))
            self.table.setItem(r, 3, QTableWidgetItem(a.target_Selector))
            self.table.setItem(r, 4, QTableWidgetItem(a.expected_Value))
            self.table.setItem(r, 5, QTableWidgetItem(a.comparison_Operator.value))
            self.table.setItem(r, 6, QTableWidgetItem(str(len(a.module_Ids or []))))

    def _add_assertion(self):
        a = Assertion()
        dialog = _AssertionEditDialog(a, self.db, self)
        if dialog.exec_() == QDialog.Accepted:
            a = dialog.get_assertion()
            if not a.assertion_Name:
                QMessageBox.warning(self, "Name", "Enter an assertion name.")
                return
            self.db.save_assertion(a)
            self.refresh()

    def _edit_assertion(self):
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.information(self, "Select", "Select an assertion to edit.")
            return
        aid = int(self.table.item(row, 0).text())
        a = self.db.load_assertion(aid)
        if a is None:
            return
        dialog = _AssertionEditDialog(a, self.db, self)
        if dialog.exec_() == QDialog.Accepted:
            a = dialog.get_assertion()
            self.db.save_assertion(a)
            self.refresh()

    def _delete_assertion(self):
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.information(self, "Select", "Select an assertion to delete.")
            return
        aid = int(self.table.item(row, 0).text())
        name = self.table.item(row, 1).text()
        if QMessageBox.question(self, "Delete", f"Delete assertion '{name}'?") == QMessageBox.Yes:
            self.db.delete_assertion(aid)
            self.refresh()

