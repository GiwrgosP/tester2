"""
Scenarios tab v8 — clean table + separate edit window.
Click a scenario row to open a scrollable edit dialog.
Lists in the dialog are read-only (no inline editing).
"""
from __future__ import annotations
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QSplitter,
    QTableWidget, QTableWidgetItem, QLineEdit, QTextEdit, QSpinBox, QPushButton,
    QListWidget, QListWidgetItem, QGroupBox, QMessageBox, QDialog, QDialogButtonBox,
    QLabel, QComboBox, QCheckBox, QScrollArea, QHeaderView)
from PyQt5.QtCore import Qt
from Models import Scenario, DataSet
from Storage import DataBase


class _PickerDialog(QDialog):
    """Dialog for picking items from a filtered table. Multi-select with checkboxes."""

    def __init__(self, title, columns, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumSize(700, 450)
        self._rows = []
        self._build_ui(columns)
        self._populate_table()

    def _build_ui(self, columns):
        layout = QVBoxLayout(self)
        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel("Module:"))
        self.module_filter = QComboBox()
        self.module_filter.addItem("All", "all")
        self.module_filter.addItem("No Module", "none")
        self.module_filter.currentIndexChanged.connect(self._populate_table)
        filter_row.addWidget(self.module_filter)
        filter_row.addStretch()
        layout.addLayout(filter_row)
        search_row = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Type search text and press Enter...")
        self.search_input.returnPressed.connect(self._populate_table)
        search_row.addWidget(self.search_input)
        self.search_btn = QPushButton("Search")
        self.search_btn.clicked.connect(self._populate_table)
        search_row.addWidget(self.search_btn)
        self.clear_btn = QPushButton("Clear")
        self.clear_btn.clicked.connect(self._clear_search)
        search_row.addWidget(self.clear_btn)
        search_row.addStretch()
        layout.addLayout(search_row)
        self.table = QTableWidget(0, len(columns) + 1)
        headers = [""] + columns
        self.table.setHorizontalHeaderLabels(headers)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        layout.addWidget(self.table)
        btn_row = QHBoxLayout()
        self.select_all_btn = QPushButton("Select All")
        self.select_all_btn.clicked.connect(self._select_all)
        btn_row.addWidget(self.select_all_btn)
        self.deselect_all_btn = QPushButton("Deselect All")
        self.deselect_all_btn.clicked.connect(self._deselect_all)
        btn_row.addWidget(self.deselect_all_btn)
        btn_row.addStretch()
        self.count_label = QLabel("0 selected")
        btn_row.addWidget(self.count_label)
        layout.addLayout(btn_row)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def set_rows(self, rows):
        self._rows = rows
        self._populate_table()

    def populate_module_filter(self, modules):
        for m in modules:
            self.module_filter.addItem(f"[{m.module_Id}] {m.module_Name}", m.module_Id)

    def _populate_table(self):
        self.table.setRowCount(0)
        filter_val = self.module_filter.currentData() or "all"
        search_text = self.search_input.text().strip().lower()
        selected_count = 0
        for row_data in self._rows:
            module_ids = row_data.get("module_Ids", [])
            if filter_val == "all":
                pass
            elif filter_val == "none":
                if module_ids:
                    continue
            else:
                if filter_val not in (module_ids or []):
                    continue
            if search_text:
                text_to_search = " ".join(str(c) for c in row_data.get("cells", [])).lower()
                if search_text not in text_to_search:
                    continue
            r = self.table.rowCount()
            self.table.insertRow(r)
            checkbox_item = QTableWidgetItem()
            checkbox_item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
            checkbox_item.setCheckState(Qt.Unchecked)
            self.table.setItem(r, 0, checkbox_item)
            if checkbox_item.checkState() == Qt.Checked:
                selected_count += 1
            for col_idx, cell_text in enumerate(row_data.get("cells", [])):
                self.table.setItem(r, col_idx + 1, QTableWidgetItem(str(cell_text)))
        self.count_label.setText(f"{selected_count} selected")

    def _select_all(self):
        for i in range(self.table.rowCount()):
            self.table.item(i, 0).setCheckState(Qt.Checked)
        self.count_label.setText(f"{self.table.rowCount()} selected")

    def _deselect_all(self):
        for i in range(self.table.rowCount()):
            self.table.item(i, 0).setCheckState(Qt.Unchecked)
        self.count_label.setText("0 selected")

    def _clear_search(self):
        self.search_input.clear()
        self._populate_table()

    def get_selected(self) -> list:
        selected = []
        for r in range(self.table.rowCount()):
            checkbox_item = self.table.item(r, 0)
            if checkbox_item and checkbox_item.checkState() == Qt.Checked:
                selected.append(self._rows[r]["id"])
        return selected


class ScenarioEditDialog(QDialog):
    """Dialog for editing a scenario. Opens as a separate window.
    Has scrollbars. All lists are read-only (no inline editing)."""

    def __init__(self, scenario, db, parent=None):
        super().__init__(parent)
        self.db = db
        self._scenario = scenario  # Scenario object being edited
        self._module_ids = list(scenario.module_Ids or [])
        self._is_new = scenario.scenario_Id == 0

        title = "New Scenario" if self._is_new else f"Edit Scenario: {scenario.scenario_Name}"
        self.setWindowTitle(title)
        self.setMinimumSize(800, 600)
        self._build_ui()

    def _build_ui(self):
        # ── Main layout with scroll area ─────────────────────────
        main_layout = QVBoxLayout(self)

        # Scroll area wraps the entire form
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        content = QWidget()
        layout = QVBoxLayout(content)

        # ── Scenario info ──────────────────────────────────────
        info_group = QGroupBox("Scenario Info")
        info_layout = QFormLayout(info_group)
        self.name_input = QLineEdit(self._scenario.scenario_Name)
        info_layout.addRow("Name:", self.name_input)
        self.desc_input = QTextEdit(self._scenario.scenario_Description)
        self.desc_input.setMaximumHeight(50)
        info_layout.addRow("Description:", self.desc_input)
        self.order_spin = QSpinBox()
        self.order_spin.setValue(self._scenario.execution_Order)
        info_layout.addRow("Order:", self.order_spin)
        self.branch_check = QCheckBox("Branch scenario (helper — hidden from Runner)")
        self.branch_check.setChecked(getattr(self._scenario, 'is_Branch_Scenario', False))
        info_layout.addRow("", self.branch_check)
        self.dataset_combo = QComboBox()
        self.dataset_combo.addItem("None (run once)", 0)
        for ds in self.db.list_data_sets():
            self.dataset_combo.addItem(
                f"[{ds.data_Set_Id}] {ds.data_Set_Name} ({len(ds.rows)} rows)", ds.data_Set_Id)
        for i in range(self.dataset_combo.count()):
            if self.dataset_combo.itemData(i) == self._scenario.data_Set_Id:
                self.dataset_combo.setCurrentIndex(i)
                break
        info_layout.addRow("Data Set:", self.dataset_combo)
        layout.addWidget(info_group)

        self.vars_label = QLabel("Variables: none")
        self.vars_label.setStyleSheet("color:#6366f1;font-size:11px;")
        layout.addWidget(self.vars_label)

        # ── Steps section ──────────────────────────────────────
        steps_group = QGroupBox("Steps in Scenario")
        steps_layout = QVBoxLayout(steps_group)
        self.sel_steps = QListWidget()
        self.sel_steps.setMaximumHeight(120)
        self.sel_steps.setEditTriggers(QListWidget.NoEditTriggers)  # Read-only
        steps_layout.addWidget(self.sel_steps)
        step_btns = QHBoxLayout()
        self.add_s = QPushButton("Add Steps...")
        self.add_s.clicked.connect(self._add_steps_picker)
        step_btns.addWidget(self.add_s)
        self.rm_s = QPushButton("Remove")
        self.rm_s.clicked.connect(self._rm_s)
        step_btns.addWidget(self.rm_s)
        self.up_btn = QPushButton("↑ Up")
        self.up_btn.clicked.connect(lambda: self._mv(-1))
        step_btns.addWidget(self.up_btn)
        self.dn_btn = QPushButton("↓ Down")
        self.dn_btn.clicked.connect(lambda: self._mv(1))
        step_btns.addWidget(self.dn_btn)
        step_btns.addStretch()
        steps_layout.addLayout(step_btns)
        layout.addWidget(steps_group)

        # Populate steps
        for sid in self._scenario.step_Ids:
            st = self.db.load_step(sid)
            if st:
                item = QListWidgetItem(f"[{st.step_Id}] {st.step_Name} - {st.action_Type.value}")
                item.setData(Qt.UserRole, st.step_Id)
                self.sel_steps.addItem(item)

        # ── Assertions section ─────────────────────────────────
        assert_group = QGroupBox("Assertions in Scenario")
        assert_layout = QVBoxLayout(assert_group)
        self.sel_a = QListWidget()
        self.sel_a.setMaximumHeight(90)
        self.sel_a.setEditTriggers(QListWidget.NoEditTriggers)  # Read-only
        assert_layout.addWidget(self.sel_a)
        assert_btns = QHBoxLayout()
        self.add_a = QPushButton("Add Assertions...")
        self.add_a.clicked.connect(self._add_assertions_picker)
        assert_btns.addWidget(self.add_a)
        self.rm_a = QPushButton("Remove")
        self.rm_a.clicked.connect(self._rm_a)
        assert_btns.addWidget(self.rm_a)
        assert_btns.addStretch()
        assert_layout.addLayout(assert_btns)
        layout.addWidget(assert_group)

        # Populate assertions
        for aid in self._scenario.assertion_Ids:
            a = self.db.load_assertion(aid)
            if a:
                item = QListWidgetItem(f"[{a.assertion_Id}] {a.assertion_Name} - {a.assertion_Type.value}")
                item.setData(Qt.UserRole, a.assertion_Id)
                self.sel_a.addItem(item)

        # ── Nested scenarios section ───────────────────────────
        nested_group = QGroupBox("Nested Scenarios")
        nested_layout = QVBoxLayout(nested_group)
        self.sel_n = QListWidget()
        self.sel_n.setMaximumHeight(70)
        self.sel_n.setEditTriggers(QListWidget.NoEditTriggers)  # Read-only
        nested_layout.addWidget(self.sel_n)
        nested_btns = QHBoxLayout()
        self.add_n = QPushButton("Add Nested Scenarios...")
        self.add_n.clicked.connect(self._add_nested_picker)
        nested_btns.addWidget(self.add_n)
        self.rm_n = QPushButton("Remove")
        self.rm_n.clicked.connect(self._rm_n)
        nested_btns.addWidget(self.rm_n)
        nested_btns.addStretch()
        nested_layout.addLayout(nested_btns)
        layout.addWidget(nested_group)

        # Populate nested
        for nid in self._scenario.nested_Scenario_Ids:
            ns = self.db.load_scenario(nid)
            nm = ns.scenario_Name if ns else f"(missing #{nid})"
            item = QListWidgetItem(f"[{nid}] {nm}")
            item.setData(Qt.UserRole, nid)
            self.sel_n.addItem(item)

        # ── Pre-condition ──────────────────────────────────────
        pre_group = QGroupBox("Pre-Condition (evaluate BEFORE main scenario)")
        pre_layout = QFormLayout(pre_group)
        self.pre_assertion_combo = QComboBox()
        self.pre_assertion_combo.addItem("None (no pre-condition)", 0)
        for a in self.db.list_assertions():
            self.pre_assertion_combo.addItem(f"[{a.assertion_Id}] {a.assertion_Name}", a.assertion_Id)
        self._set_combo_data(self.pre_assertion_combo, getattr(self._scenario, 'pre_Condition_Assertion_Id', 0))
        pre_layout.addRow("Evaluate assertion:", self.pre_assertion_combo)
        self.pre_true_combo = QComboBox()
        self.pre_true_combo.addItem("None (continue)", 0)
        for s in self.db.list_scenarios():
            if s.scenario_Id != self._scenario.scenario_Id:
                self.pre_true_combo.addItem(f"[{s.scenario_Id}] {s.scenario_Name}", s.scenario_Id)
        self._set_combo_data(self.pre_true_combo, getattr(self._scenario, 'pre_On_True_Scenario_Id', 0))
        pre_layout.addRow("If PASSES, run scenario:", self.pre_true_combo)
        self.pre_false_combo = QComboBox()
        self.pre_false_combo.addItem("None (continue)", 0)
        for s in self.db.list_scenarios():
            if s.scenario_Id != self._scenario.scenario_Id:
                self.pre_false_combo.addItem(f"[{s.scenario_Id}] {s.scenario_Name}", s.scenario_Id)
        self._set_combo_data(self.pre_false_combo, getattr(self._scenario, 'pre_On_False_Scenario_Id', 0))
        pre_layout.addRow("If FAILS, run scenario:", self.pre_false_combo)
        self.pre_stop_check = QCheckBox("Stop main scenario if pre-condition passes")
        self.pre_stop_check.setChecked(getattr(self._scenario, 'pre_Stop_If_True', False))
        pre_layout.addRow("", self.pre_stop_check)
        layout.addWidget(pre_group)

        # ── Post-condition ─────────────────────────────────────
        post_group = QGroupBox("Post-Condition (evaluate AFTER all steps)")
        post_layout = QFormLayout(post_group)
        self.post_assertion_combo = QComboBox()
        self.post_assertion_combo.addItem("None (no post-condition)", 0)
        for a in self.db.list_assertions():
            self.post_assertion_combo.addItem(f"[{a.assertion_Id}] {a.assertion_Name}", a.assertion_Id)
        self._set_combo_data(self.post_assertion_combo, getattr(self._scenario, 'post_Condition_Assertion_Id', 0))
        post_layout.addRow("Evaluate assertion:", self.post_assertion_combo)
        self.post_true_combo = QComboBox()
        self.post_true_combo.addItem("None (continue)", 0)
        for s in self.db.list_scenarios():
            if s.scenario_Id != self._scenario.scenario_Id:
                self.post_true_combo.addItem(f"[{s.scenario_Id}] {s.scenario_Name}", s.scenario_Id)
        self._set_combo_data(self.post_true_combo, getattr(self._scenario, 'post_On_True_Scenario_Id', 0))
        post_layout.addRow("If PASSES, run scenario:", self.post_true_combo)
        self.post_false_combo = QComboBox()
        self.post_false_combo.addItem("None (continue)", 0)
        for s in self.db.list_scenarios():
            if s.scenario_Id != self._scenario.scenario_Id:
                self.post_false_combo.addItem(f"[{s.scenario_Id}] {s.scenario_Name}", s.scenario_Id)
        self._set_combo_data(self.post_false_combo, getattr(self._scenario, 'post_On_False_Scenario_Id', 0))
        post_layout.addRow("If FAILS, run scenario:", self.post_false_combo)
        layout.addWidget(post_group)

        # ── Modules ────────────────────────────────────────────
        mg = QGroupBox("Modules")
        ml = QVBoxLayout(mg)
        self.module_list = QListWidget()
        self.module_list.setMaximumHeight(70)
        self.module_list.setEditTriggers(QListWidget.NoEditTriggers)  # Read-only
        ml.addWidget(self.module_list)
        mb = QHBoxLayout()
        self.add_mod_btn = QPushButton("Add Module...")
        self.add_mod_btn.clicked.connect(self._add_mod_picker)
        mb.addWidget(self.add_mod_btn)
        self.rm_mod_btn = QPushButton("Remove")
        self.rm_mod_btn.clicked.connect(self._rm_mod)
        mb.addWidget(self.rm_mod_btn)
        ml.addLayout(mb)
        layout.addWidget(mg)

        # Populate modules
        for mid in self._module_ids:
            m = self.db.load_module(mid)
            name = m.module_Name if m else f"(missing #{mid})"
            item = QListWidgetItem(f"[{mid}] {name}")
            item.setData(Qt.UserRole, mid)
            self.module_list.addItem(item)

        layout.addStretch()

        # Set the scroll area content
        scroll.setWidget(content)
        main_layout.addWidget(scroll)

        # ── Save / Cancel buttons (fixed at bottom, outside scroll) ──
        btn_row = QHBoxLayout()
        self.save_btn = QPushButton("Save Scenario")
        self.save_btn.setStyleSheet(
            "QPushButton{background-color:#22c55e;color:white;font-weight:bold;padding:6px 12px;border-radius:4px;}")
        self.save_btn.clicked.connect(self._save_and_close)
        btn_row.addWidget(self.save_btn)
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(self.cancel_btn)
        main_layout.addLayout(btn_row)

        # Refresh variables label
        self._refresh_vars()

    def _set_combo_data(self, combo, value):
        for i in range(combo.count()):
            if combo.itemData(i) == value:
                combo.setCurrentIndex(i)
                return
        combo.setCurrentIndex(0)

    def _get_selected_ids(self, list_widget):
        return [list_widget.item(i).data(Qt.UserRole) for i in range(list_widget.count())]

    def _module_names(self, module_ids):
        if not module_ids:
            return "(none)"
        names = []
        for mid in module_ids:
            m = self.db.load_module(mid)
            names.append(m.module_Name if m else f"#{mid}")
        return ", ".join(names)

    def _refresh_vars(self):
        vars_set = set()
        for i in range(self.sel_steps.count()):
            sid = self.sel_steps.item(i).data(Qt.UserRole)
            st = self.db.load_step(sid)
            if st:
                vars_set.update(st.get_Variables())
        for i in range(self.sel_a.count()):
            aid = self.sel_a.item(i).data(Qt.UserRole)
            a = self.db.load_assertion(aid)
            if a:
                vars_set.update(a.get_Variables())
        self.vars_label.setText(f"Variables: {', '.join(sorted(vars_set)) if vars_set else 'none'}")

    def _refresh_mods(self):
        self.module_list.clear()
        for mid in self._module_ids:
            m = self.db.load_module(mid)
            name = m.module_Name if m else f"(missing #{mid})"
            item = QListWidgetItem(f"[{mid}] {name}")
            item.setData(Qt.UserRole, mid)
            self.module_list.addItem(item)

    # ── Picker handlers ─────────────────────────────────────

    def _make_picker(self, title, columns):
        dialog = _PickerDialog(title, columns, self)
        dialog.populate_module_filter(self.db.list_modules())
        return dialog

    def _add_steps_picker(self):
        all_steps = self.db.list_steps()
        existing_ids = set(self._get_selected_ids(self.sel_steps))
        rows = []
        for s in all_steps:
            if s.step_Id in existing_ids:
                continue
            module_names = self._module_names(s.module_Ids or [])
            rows.append({
                "id": s.step_Id,
                "cells": [s.step_Id, s.step_Name, s.action_Type.value, module_names],
                "module_Ids": s.module_Ids or [],
            })
        if not rows:
            QMessageBox.information(self, "None", "No steps available to add.")
            return
        dialog = self._make_picker("Add Steps to Scenario", ["ID", "Name", "Action", "Module"])
        dialog.set_rows(rows)
        if dialog.exec_() == QDialog.Accepted:
            for sid in dialog.get_selected():
                st = self.db.load_step(sid)
                if st:
                    item = QListWidgetItem(f"[{st.step_Id}] {st.step_Name} - {st.action_Type.value}")
                    item.setData(Qt.UserRole, st.step_Id)
                    self.sel_steps.addItem(item)
            self._refresh_vars()

    def _add_assertions_picker(self):
        all_a = self.db.list_assertions()
        existing_ids = set(self._get_selected_ids(self.sel_a))
        rows = []
        for a in all_a:
            if a.assertion_Id in existing_ids:
                continue
            module_names = self._module_names(a.module_Ids or [])
            rows.append({
                "id": a.assertion_Id,
                "cells": [a.assertion_Id, a.assertion_Name, a.assertion_Type.value,
                          a.target_Selector, module_names],
                "module_Ids": a.module_Ids or [],
            })
        if not rows:
            QMessageBox.information(self, "None", "No assertions available to add.")
            return
        dialog = self._make_picker("Add Assertions to Scenario",
                                   ["ID", "Name", "Type", "Selector", "Module"])
        dialog.set_rows(rows)
        if dialog.exec_() == QDialog.Accepted:
            for aid in dialog.get_selected():
                a = self.db.load_assertion(aid)
                if a:
                    item = QListWidgetItem(f"[{a.assertion_Id}] {a.assertion_Name} - {a.assertion_Type.value}")
                    item.setData(Qt.UserRole, a.assertion_Id)
                    self.sel_a.addItem(item)
            self._refresh_vars()

    def _add_nested_picker(self):
        all_s = self.db.list_scenarios()
        existing_ids = set(self._get_selected_ids(self.sel_n))
        rows = []
        for s in all_s:
            if s.scenario_Id == self._scenario.scenario_Id or s.scenario_Id in existing_ids:
                continue
            module_names = self._module_names(s.module_Ids or [])
            branch_mark = " (branch)" if getattr(s, 'is_Branch_Scenario', False) else ""
            rows.append({
                "id": s.scenario_Id,
                "cells": [s.scenario_Id, s.scenario_Name + branch_mark, s.scenario_Description, module_names],
                "module_Ids": s.module_Ids or [],
            })
        if not rows:
            QMessageBox.information(self, "None", "No scenarios available to add.")
            return
        dialog = self._make_picker("Add Nested Scenarios", ["ID", "Name", "Description", "Module"])
        dialog.set_rows(rows)
        if dialog.exec_() == QDialog.Accepted:
            for sid in dialog.get_selected():
                ns = self.db.load_scenario(sid)
                if ns:
                    item = QListWidgetItem(f"[{ns.scenario_Id}] {ns.scenario_Name}")
                    item.setData(Qt.UserRole, ns.scenario_Id)
                    self.sel_n.addItem(item)

    def _add_mod_picker(self):
        all_m = self.db.list_modules()
        existing_ids = set(self._module_ids)
        rows = []
        for m in all_m:
            if m.module_Id in existing_ids:
                continue
            parent_name = "None"
            if m.parent_Module_Id and m.parent_Module_Id > 0:
                p = self.db.load_module(m.parent_Module_Id)
                parent_name = p.module_Name if p else f"(missing #{m.parent_Module_Id})"
            rows.append({
                "id": m.module_Id,
                "cells": [m.module_Id, m.module_Name, m.module_Description, parent_name],
                "module_Ids": [],
            })
        if not rows:
            QMessageBox.information(self, "None", "No modules available.")
            return
        dialog = _PickerDialog("Add Modules", ["ID", "Name", "Description", "Parent"], self)
        dialog.set_rows(rows)
        if dialog.exec_() == QDialog.Accepted:
            for mid in dialog.get_selected():
                self._module_ids.append(mid)
            self._refresh_mods()

    # ── Standard handlers ───────────────────────────────────

    def _rm_s(self):
        i = self.sel_steps.currentItem()
        if i:
            self.sel_steps.takeItem(self.sel_steps.row(i))
            self._refresh_vars()

    def _mv(self, d):
        r = self.sel_steps.currentRow()
        if r < 0:
            return
        if d < 0 and r > 0:
            i = self.sel_steps.takeItem(r)
            self.sel_steps.insertItem(r - 1, i)
            self.sel_steps.setCurrentRow(r - 1)
        elif d > 0 and r < self.sel_steps.count() - 1:
            i = self.sel_steps.takeItem(r)
            self.sel_steps.insertItem(r + 1, i)
            self.sel_steps.setCurrentRow(r + 1)

    def _rm_a(self):
        i = self.sel_a.currentItem()
        if i:
            self.sel_a.takeItem(self.sel_a.row(i))
            self._refresh_vars()

    def _rm_n(self):
        i = self.sel_n.currentItem()
        if i:
            self.sel_n.takeItem(self.sel_n.row(i))

    def _rm_mod(self):
        item = self.module_list.currentItem()
        if item:
            mid = item.data(Qt.UserRole)
            if mid in self._module_ids:
                self._module_ids.remove(mid)
                self._refresh_mods()

    def _save_and_close(self):
        """Collect form data and save. Called on OK."""
        s = self._scenario
        s.scenario_Name = self.name_input.text().strip()
        s.scenario_Description = self.desc_input.toPlainText().strip()
        s.execution_Order = self.order_spin.value()
        s.step_Ids = self._get_selected_ids(self.sel_steps)
        s.assertion_Ids = self._get_selected_ids(self.sel_a)
        s.nested_Scenario_Ids = self._get_selected_ids(self.sel_n)
        s.module_Ids = list(self._module_ids)
        s.data_Set_Id = self.dataset_combo.currentData() or 0
        s.is_Branch_Scenario = self.branch_check.isChecked()
        s.pre_Condition_Assertion_Id = self.pre_assertion_combo.currentData() or 0
        s.pre_On_True_Scenario_Id = self.pre_true_combo.currentData() or 0
        s.pre_On_False_Scenario_Id = self.pre_false_combo.currentData() or 0
        s.pre_Stop_If_True = self.pre_stop_check.isChecked()
        s.post_Condition_Assertion_Id = self.post_assertion_combo.currentData() or 0
        s.post_On_True_Scenario_Id = self.post_true_combo.currentData() or 0
        s.post_On_False_Scenario_Id = self.post_false_combo.currentData() or 0

        if not s.scenario_Name:
            QMessageBox.warning(self, "Name", "Enter a name.")
            return

        self.db.save_scenario(s)
        self._scenario = s
        self.accept()

    def get_scenario(self) -> Scenario:
        """Return the saved scenario (valid after accept())."""
        return self._scenario


class ScenariosTab(QWidget):
    """Tab for listing scenarios. Click a row to open the edit dialog."""

    def __init__(self, db: DataBase):
        super().__init__()
        self.db = db
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        # Scenario table — read-only, click to edit
        self.table = QTableWidget(0, 8)
        self.table.setHorizontalHeaderLabels(
            ["ID", "Name", "Description", "Steps", "Assertions", "Nested", "Data Set", "Branch"])
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)  # Read-only table
        self.table.cellClicked.connect(self._on_row_click)
        layout.addWidget(self.table)

        # Buttons
        br = QHBoxLayout()
        self.new_btn = QPushButton("New Scenario")
        self.new_btn.setStyleSheet(
            "QPushButton{background-color:#22c55e;color:white;font-weight:bold;padding:6px 12px;border-radius:4px;}")
        self.new_btn.clicked.connect(self._new_scenario)
        br.addWidget(self.new_btn)
        self.del_btn = QPushButton("Delete Selected")
        self.del_btn.clicked.connect(self._delete_scenario)
        br.addWidget(self.del_btn)
        self.ref_btn = QPushButton("Refresh")
        self.ref_btn.clicked.connect(self.refresh)
        br.addWidget(self.ref_btn)
        br.addStretch()
        layout.addLayout(br)

    def refresh(self):
        self.table.setRowCount(0)
        for s in self.db.list_scenarios():
            r = self.table.rowCount()
            self.table.insertRow(r)
            self.table.setItem(r, 0, QTableWidgetItem(str(s.scenario_Id)))
            branch_mark = " 🔀" if getattr(s, 'is_Branch_Scenario', False) else ""
            self.table.setItem(r, 1, QTableWidgetItem(s.scenario_Name + branch_mark))
            self.table.setItem(r, 2, QTableWidgetItem(s.scenario_Description))
            self.table.setItem(r, 3, QTableWidgetItem(str(len(s.step_Ids))))
            self.table.setItem(r, 4, QTableWidgetItem(str(len(s.assertion_Ids))))
            self.table.setItem(r, 5, QTableWidgetItem(str(len(s.nested_Scenario_Ids))))
            ds_name = "None"
            if s.data_Set_Id and s.data_Set_Id > 0:
                ds = self.db.load_data_set(s.data_Set_Id)
                ds_name = ds.data_Set_Name if ds else f"(missing #{s.data_Set_Id})"
            self.table.setItem(r, 6, QTableWidgetItem(ds_name))
            branch_val = "Yes" if getattr(s, 'is_Branch_Scenario', False) else "No"
            self.table.setItem(r, 7, QTableWidgetItem(branch_val))

    def _on_row_click(self, row, col):
        """Open the edit dialog for the clicked scenario."""
        sid = int(self.table.item(row, 0).text())
        scenario = self.db.load_scenario(sid)
        if scenario is None:
            return
        dialog = ScenarioEditDialog(scenario, self.db, self)
        if dialog.exec_() == QDialog.Accepted:
            self.refresh()

    def _new_scenario(self):
        """Open the edit dialog for a new scenario."""
        scenario = Scenario()
        dialog = ScenarioEditDialog(scenario, self.db, self)
        if dialog.exec_() == QDialog.Accepted:
            self.refresh()

    def _delete_scenario(self):
        """Delete the selected scenario."""
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Select", "Select a scenario to delete.")
            return
        sid = int(self.table.item(row, 0).text())
        result = self.db.delete_scenario(sid)
        if result.get("blocked"):
            deps = "\n".join(result.get("dependents", []))
            QMessageBox.warning(self, "Cannot Delete", f"This scenario is used by:\n\n{deps}")
            return
        self.refresh()

