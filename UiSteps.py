"""
Steps tab v7 — clean UI.
Main tab shows a read-only table of steps.
Clicking a step opens a dialog for editing (not inline).
All tables are read-only.
"""
from __future__ import annotations
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QTableWidget, QTableWidgetItem, QLineEdit, QComboBox, QSpinBox, QTextEdit,
    QPushButton, QListWidget, QListWidgetItem, QGroupBox, QMessageBox, QDialog,
    QDialogButtonBox, QLabel, QInputDialog, QScrollArea, QCheckBox)
from PyQt5.QtCore import Qt
from Models import Step, ActionType
from Storage import DataBase


class _StepEditDialog(QDialog):
    """Dialog for editing a single step. Scrollable."""

    def __init__(self, db: DataBase, step: Step | None, parent=None):
        super().__init__(parent)
        self.db = db
        self._step = step or Step()
        self._module_ids = list(self._step.module_Ids or [])
        self._assertion_ids = list(self._step.assertion_Ids or [])
        self.setWindowTitle(f"Edit Step: {self._step.step_Name or 'New'}")
        self.setMinimumSize(700, 550)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)

        content = QWidget()
        form_layout = QVBoxLayout(content)
        form_layout.setSpacing(10)

        self._build_form(form_layout)
        scroll.setWidget(content)

        main_layout = QVBoxLayout(self)
        main_layout.addWidget(scroll)

        btn_row = QHBoxLayout()
        self.save_btn = QPushButton("Save")
        self.save_btn.setStyleSheet("QPushButton{background-color:#22c55e;color:white;font-weight:bold;padding:8px 20px;border-radius:4px;}")
        self.save_btn.clicked.connect(self.accept)
        btn_row.addWidget(self.save_btn)
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(self.cancel_btn)
        main_layout.addLayout(btn_row)

    def _build_form(self, layout):
        form = QFormLayout()
        self.name_input = QLineEdit(self._step.step_Name)
        form.addRow("Name:", self.name_input)
        self.action_combo = QComboBox()
        for t, lbl in ActionType.labels().items():
            self.action_combo.addItem(lbl, t.value)
        form.addRow("Action Type:", self.action_combo)
        self.selector_input = QLineEdit(self._step.target_Selector)
        form.addRow("Target Selector:", self.selector_input)
        self.input_input = QLineEdit(self._step.input_Value)
        form.addRow("Input Value:", self.input_input)
        self.desc_input = QLineEdit(self._step.target_Description)
        form.addRow("Description:", self.desc_input)
        self.wait_spin = QSpinBox()
        self.wait_spin.setRange(0, 999999)
        self.wait_spin.setSuffix(" ms")
        self.wait_spin.setValue(self._step.wait_Time_Ms)
        form.addRow("Wait After:", self.wait_spin)
        self.timeout_spin = QSpinBox()
        self.timeout_spin.setRange(1000, 300000)
        self.timeout_spin.setValue(self._step.selector_Timeout_Ms)
        self.timeout_spin.setSuffix(" ms")
        form.addRow("Selector Timeout:", self.timeout_spin)
        layout.addLayout(form)

        # Fallback selectors
        fb_group = QGroupBox("Fallback Selectors (one per line)")
        fb_layout = QVBoxLayout(fb_group)
        self.fallback_input = QTextEdit("\n".join(self._step.fallback_Selectors or []))
        self.fallback_input.setMaximumHeight(60)
        fb_layout.addWidget(self.fallback_input)
        layout.addWidget(fb_group)

        # Step assertions
        assert_group = QGroupBox("Step Assertions (evaluated after this step executes)")
        assert_layout = QVBoxLayout(assert_group)
        self.assert_list = QListWidget()
        self.assert_list.setMaximumHeight(70)
        assert_layout.addWidget(self.assert_list)
        ab = QHBoxLayout()
        self.add_assert_btn = QPushButton("Add Assertion...")
        self.add_assert_btn.clicked.connect(self._add_assertion)
        ab.addWidget(self.add_assert_btn)
        self.rm_assert_btn = QPushButton("Remove")
        self.rm_assert_btn.clicked.connect(self._rm_assertion)
        ab.addWidget(self.rm_assert_btn)
        ab.addStretch()
        assert_layout.addLayout(ab)
        layout.addWidget(assert_group)

        # Modules
        mod_group = QGroupBox("Modules")
        mod_layout = QVBoxLayout(mod_group)
        self.module_list = QListWidget()
        self.module_list.setMaximumHeight(60)
        mod_layout.addWidget(self.module_list)
        mb = QHBoxLayout()
        self.add_mod_btn = QPushButton("Add Module...")
        self.add_mod_btn.clicked.connect(self._add_module)
        mb.addWidget(self.add_mod_btn)
        self.rm_mod_btn = QPushButton("Remove")
        self.rm_mod_btn.clicked.connect(self._rm_module)
        mb.addWidget(self.rm_mod_btn)
        mb.addStretch()
        mod_layout.addLayout(mb)
        layout.addWidget(mod_group)

        self.vars_label = QLabel("Variables: none")
        self.vars_label.setStyleSheet("color:#6366f1;font-size:11px;")
        layout.addWidget(self.vars_label)

        self._load_lists()

    def _load_lists(self):
        # Load action type
        action_map = {v: k.value for k, v in ActionType.labels().items()}
        current = self._step.action_Type.value
        for i in range(self.action_combo.count()):
            if self.action_combo.itemData(i) == current:
                self.action_combo.setCurrentIndex(i)
                break

        # Load assertions
        self.assert_list.clear()
        for aid in self._assertion_ids:
            a = self.db.load_assertion(aid)
            name = a.assertion_Name if a else f"(missing #{aid})"
            item = QListWidgetItem(f"[{aid}] {name}")
            item.setData(Qt.UserRole, aid)
            self.assert_list.addItem(item)

        # Load modules
        self.module_list.clear()
        for mid in self._module_ids:
            m = self.db.load_module(mid)
            name = m.module_Name if m else f"(missing #{mid})"
            item = QListWidgetItem(f"[{mid}] {name}")
            item.setData(Qt.UserRole, mid)
            self.module_list.addItem(item)

        self._refresh_vars()

    def _refresh_vars(self):
        vars_set = set(self._step.get_Variables())
        self.vars_label.setText(f"Variables: {', '.join(sorted(vars_set)) if vars_set else 'none'}")

    def _add_assertion(self):
        all_a = self.db.list_assertions()
        existing_ids = set(self._assertion_ids)
        items = [f"[{a.assertion_Id}] {a.assertion_Name}" for a in all_a if a.assertion_Id not in existing_ids]
        if not items:
            QMessageBox.information(self, "None", "No assertions available.")
            return
        ch, ok = QInputDialog.getItem(self, "Add Assertion", "Select:", items, 0, False)
        if ok and ch:
            aid = all_a[items.index(ch)].assertion_Id
            self._assertion_ids.append(aid)
            self._load_lists()

    def _rm_assertion(self):
        item = self.assert_list.currentItem()
        if item:
            aid = item.data(Qt.UserRole)
            if aid in self._assertion_ids:
                self._assertion_ids.remove(aid)
                self._load_lists()

    def _add_module(self):
        all_m = self.db.list_modules()
        existing_ids = set(self._module_ids)
        items = [f"[{m.module_Id}] {m.module_Name}" for m in all_m if m.module_Id not in existing_ids]
        if not items:
            QMessageBox.information(self, "None", "No modules available.")
            return
        ch, ok = QInputDialog.getItem(self, "Add Module", "Select:", items, 0, False)
        if ok and ch:
            mid = all_m[items.index(ch)].module_Id
            self._module_ids.append(mid)
            self._load_lists()

    def _rm_module(self):
        item = self.module_list.currentItem()
        if item:
            mid = item.data(Qt.UserRole)
            if mid in self._module_ids:
                self._module_ids.remove(mid)
                self._load_lists()

    def get_step(self) -> Step:
        """Build and return the step from the form data."""
        s = Step()
        s.step_Id = self._step.step_Id
        s.step_Name = self.name_input.text().strip()
        s.action_Type = ActionType(self.action_combo.currentData())
        s.target_Selector = self.selector_input.text().strip()
        s.input_Value = self.input_input.text().strip()
        s.target_Description = self.desc_input.text().strip()
        s.wait_Time_Ms = self.wait_spin.value()
        s.selector_Timeout_Ms = self.timeout_spin.value()
        s.fallback_Selectors = [l.strip() for l in self.fallback_input.toPlainText().splitlines() if l.strip()]
        s.assertion_Ids = list(self._assertion_ids)
        s.module_Ids = list(self._module_ids)
        return s


class StepsTab(QWidget):
    """Tab for managing steps. Shows a read-only table.
    Click Edit to open a dialog."""

    def __init__(self, db: DataBase):
        super().__init__()
        self.db = db
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        # Filter by module (same logic as the Test Runner tab's test filter)
        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel("Filter by module:"))
        self.module_filter = QComboBox()
        self.module_filter.currentIndexChanged.connect(lambda *_: self.refresh())
        filter_row.addWidget(self.module_filter)
        filter_row.addStretch()
        layout.addLayout(filter_row)

        # Table
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["ID", "Name", "Action", "Selector", "Input", "Assertions"])
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)  # READ-ONLY
        self.table.doubleClicked.connect(self._edit_selected)
        layout.addWidget(self.table)

        # Buttons
        btn_row = QHBoxLayout()
        self.edit_btn = QPushButton("Edit")
        self.edit_btn.clicked.connect(self._edit_selected)
        btn_row.addWidget(self.edit_btn)
        self.del_btn = QPushButton("Delete")
        self.del_btn.clicked.connect(self._delete)
        btn_row.addWidget(self.del_btn)
        self.new_btn = QPushButton("New Step")
        self.new_btn.clicked.connect(self._new_step)
        btn_row.addWidget(self.new_btn)
        self.ref_btn = QPushButton("Refresh")
        self.ref_btn.clicked.connect(self.refresh)
        btn_row.addWidget(self.ref_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

    def refresh(self):
        # Rebuild the module filter, keeping the current selection
        self.module_filter.blockSignals(True)
        cur = self.module_filter.currentData() if self.module_filter.count() > 0 else "all"
        self.module_filter.clear()
        self.module_filter.addItem("All", "all")
        self.module_filter.addItem("No Module", "none")
        for m in self.db.list_modules():
            self.module_filter.addItem(f"[{m.module_Id}] {m.module_Name}", m.module_Id)
        for i in range(self.module_filter.count()):
            if self.module_filter.itemData(i) == cur:
                self.module_filter.setCurrentIndex(i)
                break
        self.module_filter.blockSignals(False)

        filter_val = self.module_filter.currentData() if self.module_filter.count() > 0 else "all"
        all_steps = self.db.list_steps()
        if filter_val == "all":
            steps = all_steps
        elif filter_val == "none":
            steps = [s for s in all_steps if not s.module_Ids]
        else:
            mid = int(filter_val)
            steps = [s for s in all_steps if mid in (s.module_Ids or [])]

        self.table.setRowCount(0)
        for s in steps:
            r = self.table.rowCount()
            self.table.insertRow(r)
            self.table.setItem(r, 0, QTableWidgetItem(str(s.step_Id)))
            self.table.setItem(r, 1, QTableWidgetItem(s.step_Name))
            self.table.setItem(r, 2, QTableWidgetItem(s.action_Type.value))
            self.table.setItem(r, 3, QTableWidgetItem(s.target_Selector))
            self.table.setItem(r, 4, QTableWidgetItem(s.input_Value))
            self.table.setItem(r, 5, QTableWidgetItem(str(len(s.assertion_Ids))))

    def _get_selected_step(self):
        row = self.table.currentRow()
        if row < 0:
            return None
        sid = int(self.table.item(row, 0).text())
        return self.db.load_step(sid)

    def _edit_selected(self):
        s = self._get_selected_step()
        if s is None:
            QMessageBox.information(self, "Select", "Select a step to edit.")
            return
        dialog = _StepEditDialog(self.db, s, self)
        if dialog.exec_() == QDialog.Accepted:
            updated = dialog.get_step()
            self.db.save_step(updated)
            self.refresh()

    def _new_step(self):
        dialog = _StepEditDialog(self.db, None, self)
        if dialog.exec_() == QDialog.Accepted:
            new_step = dialog.get_step()
            self.db.save_step(new_step)
            self.refresh()

    def _delete(self):
        s = self._get_selected_step()
        if s is None:
            return
        result = self.db.delete_step(s.step_Id)
        if result.get("blocked"):
            deps = "\n".join(result.get("dependents", []))
            QMessageBox.warning(self, "Cannot Delete", f"This step is used by:\n\n{deps}")
            return
        self.refresh()


