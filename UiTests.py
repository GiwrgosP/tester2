"""
Tests tab v1 — clean table + separate edit window.
A Test is an ordered list of scenarios executed on a chosen environment.
The edit window is scrollable and reuses the same picker style as the
scenario edit window (scenarios list mirrors the steps list, modules
section mirrors the scenario edit window's Modules section).
"""
from __future__ import annotations
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QTableWidget, QTableWidgetItem, QLineEdit, QTextEdit, QPushButton,
    QListWidget, QListWidgetItem, QGroupBox, QMessageBox, QDialog,
    QLabel, QComboBox, QScrollArea)
from PyQt5.QtCore import Qt
from Models import Test
from Storage import DataBase
from UiScenarios import _PickerDialog


class TestEditDialog(QDialog):
    """Dialog for creating/editing a test. Opens as a separate window.
    Has scrollbars. All lists are read-only (no inline editing)."""

    def __init__(self, test, db, parent=None):
        super().__init__(parent)
        self.db = db
        self._test = test  # Test object being edited
        self._module_ids = list(test.module_Ids or [])
        self._is_new = test.test_Id == 0

        title = "New Test" if self._is_new else f"Edit Test: {test.test_Name}"
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

        # ── Test info ──────────────────────────────────────────
        info_group = QGroupBox("Test Info")
        info_layout = QFormLayout(info_group)
        self.name_input = QLineEdit(self._test.test_Name)
        info_layout.addRow("Name:", self.name_input)
        self.desc_input = QTextEdit(self._test.test_Description)
        self.desc_input.setMaximumHeight(50)
        info_layout.addRow("Description:", self.desc_input)
        layout.addWidget(info_group)

        # ── Environment ────────────────────────────────────────
        env_group = QGroupBox("Environment")
        env_layout = QFormLayout(env_group)
        self.env_combo = QComboBox()
        self.env_combo.addItem("None (choose at run time)", 0)
        for cfg in self.db.list_configs():
            self.env_combo.addItem(
                f"[{cfg.config_Id}] {cfg.config_Name} — {cfg.web_app_url}",
                cfg.config_Id)
        self._set_combo_data(self.env_combo, self._test.config_Id)
        env_layout.addRow("Run on:", self.env_combo)
        env_hint = QLabel("The test runs every selected scenario on this environment.")
        env_hint.setStyleSheet("color:#6b7280;font-size:11px;")
        env_layout.addRow("", env_hint)
        layout.addWidget(env_group)

        # ── Scenarios section (same pattern as the steps list
        #    in the scenario edit window) ───────────────────────
        scen_group = QGroupBox("Scenarios in Test")
        scen_layout = QVBoxLayout(scen_group)
        self.sel_scen = QListWidget()
        self.sel_scen.setMaximumHeight(140)
        self.sel_scen.setEditTriggers(QListWidget.NoEditTriggers)  # Read-only
        scen_layout.addWidget(self.sel_scen)
        scen_btns = QHBoxLayout()
        self.add_scen = QPushButton("Add Scenarios...")
        self.add_scen.clicked.connect(self._add_scenarios_picker)
        scen_btns.addWidget(self.add_scen)
        self.rm_scen = QPushButton("Remove")
        self.rm_scen.clicked.connect(self._rm_scen)
        scen_btns.addWidget(self.rm_scen)
        self.up_btn = QPushButton("↑ Up")
        self.up_btn.clicked.connect(lambda: self._mv(-1))
        scen_btns.addWidget(self.up_btn)
        self.dn_btn = QPushButton("↓ Down")
        self.dn_btn.clicked.connect(lambda: self._mv(1))
        scen_btns.addWidget(self.dn_btn)
        scen_btns.addStretch()
        scen_layout.addLayout(scen_btns)
        layout.addWidget(scen_group)

        # Populate scenarios
        for sid in self._test.scenario_Ids:
            sc = self.db.load_scenario(sid)
            if sc:
                branch_mark = " 🔀" if getattr(sc, 'is_Branch_Scenario', False) else ""
                item = QListWidgetItem(f"[{sc.scenario_Id}] {sc.scenario_Name}{branch_mark}")
            else:
                item = QListWidgetItem(f"[{sid}] (missing #{sid})")
            item.setData(Qt.UserRole, sid)
            self.sel_scen.addItem(item)

        # ── Modules (identical to the scenario edit window) ────
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
        self._refresh_mods()

        layout.addStretch()

        # Set the scroll area content
        scroll.setWidget(content)
        main_layout.addWidget(scroll)

        # ── Save / Cancel buttons (fixed at bottom, outside scroll) ──
        btn_row = QHBoxLayout()
        self.save_btn = QPushButton("Save Test")
        self.save_btn.setStyleSheet(
            "QPushButton{background-color:#22c55e;color:white;font-weight:bold;padding:6px 12px;border-radius:4px;}")
        self.save_btn.clicked.connect(self._save_and_close)
        btn_row.addWidget(self.save_btn)
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(self.cancel_btn)
        main_layout.addLayout(btn_row)

    # ── Helpers ─────────────────────────────────────────────

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

    def _refresh_mods(self):
        self.module_list.clear()
        for mid in self._module_ids:
            m = self.db.load_module(mid)
            name = m.module_Name if m else f"(missing #{mid})"
            item = QListWidgetItem(f"[{mid}] {name}")
            item.setData(Qt.UserRole, mid)
            self.module_list.addItem(item)

    # ── Picker handlers ─────────────────────────────────────

    def _add_scenarios_picker(self):
        all_s = self.db.list_scenarios()
        existing_ids = set(self._get_selected_ids(self.sel_scen))
        rows = []
        for s in all_s:
            if s.scenario_Id in existing_ids:
                continue
            module_names = self._module_names(s.module_Ids or [])
            branch_mark = " (branch)" if getattr(s, 'is_Branch_Scenario', False) else ""
            rows.append({
                "id": s.scenario_Id,
                "cells": [s.scenario_Id, s.scenario_Name + branch_mark,
                          len(s.step_Ids or []), s.scenario_Description, module_names],
                "module_Ids": s.module_Ids or [],
            })
        if not rows:
            QMessageBox.information(self, "None", "No scenarios available to add.")
            return
        dialog = _PickerDialog("Add Scenarios to Test",
                               ["ID", "Name", "Steps", "Description", "Module"], self)
        dialog.populate_module_filter(self.db.list_modules())
        dialog.set_rows(rows)
        if dialog.exec_() == QDialog.Accepted:
            for sid in dialog.get_selected():
                sc = self.db.load_scenario(sid)
                if sc:
                    branch_mark = " 🔀" if getattr(sc, 'is_Branch_Scenario', False) else ""
                    item = QListWidgetItem(f"[{sc.scenario_Id}] {sc.scenario_Name}{branch_mark}")
                    item.setData(Qt.UserRole, sc.scenario_Id)
                    self.sel_scen.addItem(item)

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

    def _rm_scen(self):
        i = self.sel_scen.currentItem()
        if i:
            self.sel_scen.takeItem(self.sel_scen.row(i))

    def _mv(self, d):
        r = self.sel_scen.currentRow()
        if r < 0:
            return
        if d < 0 and r > 0:
            i = self.sel_scen.takeItem(r)
            self.sel_scen.insertItem(r - 1, i)
            self.sel_scen.setCurrentRow(r - 1)
        elif d > 0 and r < self.sel_scen.count() - 1:
            i = self.sel_scen.takeItem(r)
            self.sel_scen.insertItem(r + 1, i)
            self.sel_scen.setCurrentRow(r + 1)

    def _rm_mod(self):
        item = self.module_list.currentItem()
        if item:
            mid = item.data(Qt.UserRole)
            if mid in self._module_ids:
                self._module_ids.remove(mid)
                self._refresh_mods()

    def _save_and_close(self):
        """Collect form data and save."""
        t = self._test
        t.test_Name = self.name_input.text().strip()
        t.test_Description = self.desc_input.toPlainText().strip()
        t.config_Id = self.env_combo.currentData() or 0
        t.scenario_Ids = self._get_selected_ids(self.sel_scen)
        t.module_Ids = list(self._module_ids)

        if not t.test_Name:
            QMessageBox.warning(self, "Name", "Enter a name.")
            return

        self.db.save_test(t)
        self._test = t
        self.accept()

    def get_test(self) -> Test:
        """Return the saved test (valid after accept())."""
        return self._test


class TestsTab(QWidget):
    """Tab listing all tests, with New / Edit Selected / Delete Selected."""

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

        # Tests table — read-only
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(
            ["ID", "Name", "Description", "Environment", "Scenarios", "Modules"])
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)  # Read-only table
        self.table.doubleClicked.connect(lambda *_: self._edit_test())
        layout.addWidget(self.table)

        # Buttons
        br = QHBoxLayout()
        self.new_btn = QPushButton("New Test")
        self.new_btn.setStyleSheet(
            "QPushButton{background-color:#22c55e;color:white;font-weight:bold;padding:6px 12px;border-radius:4px;}")
        self.new_btn.clicked.connect(self._new_test)
        br.addWidget(self.new_btn)
        self.edit_btn = QPushButton("Edit Selected")
        self.edit_btn.clicked.connect(self._edit_test)
        br.addWidget(self.edit_btn)
        self.del_btn = QPushButton("Delete Selected")
        self.del_btn.clicked.connect(self._delete_test)
        br.addWidget(self.del_btn)
        self.ref_btn = QPushButton("Refresh")
        self.ref_btn.clicked.connect(self.refresh)
        br.addWidget(self.ref_btn)
        br.addStretch()
        layout.addLayout(br)

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
        all_t = self.db.list_tests()
        if filter_val == "all":
            tests = all_t
        elif filter_val == "none":
            tests = [t for t in all_t if not t.module_Ids]
        else:
            mid = int(filter_val)
            tests = [t for t in all_t if mid in (t.module_Ids or [])]

        self.table.setRowCount(0)
        for t in tests:
            r = self.table.rowCount()
            self.table.insertRow(r)
            self.table.setItem(r, 0, QTableWidgetItem(str(t.test_Id)))
            self.table.setItem(r, 1, QTableWidgetItem(t.test_Name))
            self.table.setItem(r, 2, QTableWidgetItem(t.test_Description))
            env_name = "(choose at run time)"
            if t.config_Id and t.config_Id > 0:
                cfg = self.db.load_config_by_id(t.config_Id)
                env_name = cfg.config_Name if cfg else f"(missing #{t.config_Id})"
            self.table.setItem(r, 3, QTableWidgetItem(env_name))
            self.table.setItem(r, 4, QTableWidgetItem(str(len(t.scenario_Ids or []))))
            mod_names = []
            for mid in (t.module_Ids or []):
                m = self.db.load_module(mid)
                mod_names.append(m.module_Name if m else f"#{mid}")
            self.table.setItem(r, 5, QTableWidgetItem(", ".join(mod_names) or "(none)"))

    def _selected_test_id(self):
        row = self.table.currentRow()
        if row < 0:
            return None
        return int(self.table.item(row, 0).text())

    def _new_test(self):
        """Open the edit window for a new test."""
        dialog = TestEditDialog(Test(), self.db, self)
        if dialog.exec_() == QDialog.Accepted:
            self.refresh()

    def _edit_test(self):
        """Open the edit window for the selected test."""
        tid = self._selected_test_id()
        if tid is None:
            QMessageBox.warning(self, "Select", "Select a test to edit.")
            return
        test = self.db.load_test(tid)
        if test is None:
            return
        dialog = TestEditDialog(test, self.db, self)
        if dialog.exec_() == QDialog.Accepted:
            self.refresh()

    def _delete_test(self):
        """Delete the selected test."""
        tid = self._selected_test_id()
        if tid is None:
            QMessageBox.warning(self, "Select", "Select a test to delete.")
            return
        result = self.db.delete_test(tid)
        if result.get("blocked"):
            deps = "\n".join(result.get("dependents", []))
            QMessageBox.warning(self, "Cannot Delete", f"This test is used by:\n\n{deps}")
            return
        self.refresh()


