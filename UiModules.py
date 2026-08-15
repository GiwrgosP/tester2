"""
Modules tab — browse entities by module, create/edit/delete modules.
Opens a dialog with scrollbar for editing.
"""
from __future__ import annotations
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QTableWidget, QTableWidgetItem, QLineEdit, QComboBox, QPushButton,
    QListWidget, QListWidgetItem, QGroupBox, QMessageBox, QDialog,
    QDialogButtonBox, QLabel, QScrollArea, QTabWidget, QSplitter)
from PyQt5.QtCore import Qt
from Models import Module
from Storage import DataBase


class _ModuleEditDialog(QDialog):
    """Dialog for editing a single module with scrollbar."""

    def __init__(self, module, db, parent=None):
        super().__init__(parent)
        self.db = db
        self.module = module
        self.setWindowTitle(f"Edit Module: {module.module_Name}" if module.module_Name else "New Module")
        self.setMinimumSize(500, 400)
        self._build_ui()
        self._load_module()

    def _build_ui(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setFrameShape(QScrollArea.NoFrame)

        content = QWidget()
        form = QFormLayout(content)

        self.name_input = QLineEdit()
        form.addRow("Module Name:", self.name_input)

        self.desc_input = QLineEdit()
        form.addRow("Description:", self.desc_input)

        self.color_input = QLineEdit()
        self.color_input.setPlaceholderText("#3B82F6")
        form.addRow("Color:", self.color_input)

        self.parent_combo = QComboBox()
        self.parent_combo.addItem("None (top level)", 0)
        form.addRow("Parent Module:", self.parent_combo)

        scroll.setWidget(content)

        main_layout = QVBoxLayout(self)
        main_layout.addWidget(scroll)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        main_layout.addWidget(buttons)

    def _load_module(self):
        m = self.module
        self.name_input.setText(m.module_Name)
        self.desc_input.setText(m.module_Description)
        self.color_input.setText(m.module_Color or "#3B82F6")
        # Load parent modules
        all_m = self.db.list_modules()
        for i, mod in enumerate(all_m):
            if mod.module_Id != m.module_Id:
                self.parent_combo.addItem(f"[{mod.module_Id}] {mod.module_Name}", mod.module_Id)
        # Set current parent
        if m.parent_Module_Id and m.parent_Module_Id > 0:
            for i in range(self.parent_combo.count()):
                if self.parent_combo.itemData(i) == m.parent_Module_Id:
                    self.parent_combo.setCurrentIndex(i)
                    break

    def get_module(self) -> Module:
        """Return the edited module from the form."""
        m = Module()
        m.module_Id = self.module.module_Id
        m.module_Name = self.name_input.text().strip()
        m.module_Description = self.desc_input.text().strip()
        m.module_Color = self.color_input.text().strip() or "#3B82F6"
        m.parent_Module_Id = self.parent_combo.currentData() or 0
        m.created_At = self.module.created_At
        return m


class ModulesTab(QWidget):
    """Modules tab — browse entities by module + module CRUD."""

    def __init__(self, db: DataBase):
        super().__init__()
        self.db = db
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        # Toolbar
        btn_row = QHBoxLayout()
        self.add_btn = QPushButton("New Module")
        self.add_btn.clicked.connect(self._add_module)
        btn_row.addWidget(self.add_btn)
        self.edit_btn = QPushButton("Edit")
        self.edit_btn.clicked.connect(self._edit_module)
        btn_row.addWidget(self.edit_btn)
        self.del_btn = QPushButton("Delete")
        self.del_btn.clicked.connect(self._delete_module)
        btn_row.addWidget(self.del_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        # Splitter: module list on left, entity browser on right
        sp = QSplitter(Qt.Horizontal)

        # Left: module list
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.addWidget(QLabel("Modules (click to browse entities):"))
        self.module_list = QListWidget()
        self.module_list.currentRowChanged.connect(self._on_module_sel)
        left_layout.addWidget(self.module_list)
        sp.addWidget(left_widget)

        # Right: entity browser
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.addWidget(QLabel("Entities in selected module:"))

        self.entity_tabs = QTabWidget()

        # Steps table
        self.steps_table = QTableWidget(0, 4)
        self.steps_table.setHorizontalHeaderLabels(["ID", "Name", "Action", "Selector"])
        self.steps_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.entity_tabs.addTab(self.steps_table, "Steps")

        # Assertions table
        self.assertions_table = QTableWidget(0, 3)
        self.assertions_table.setHorizontalHeaderLabels(["ID", "Name", "Type"])
        self.assertions_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.entity_tabs.addTab(self.assertions_table, "Assertions")

        # Scenarios table
        self.scenarios_table = QTableWidget(0, 3)
        self.scenarios_table.setHorizontalHeaderLabels(["ID", "Name", "Steps"])
        self.scenarios_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.entity_tabs.addTab(self.scenarios_table, "Scenarios")

        # Data Sets table
        self.datasets_table = QTableWidget(0, 3)
        self.datasets_table.setHorizontalHeaderLabels(["ID", "Name", "Rows"])
        self.datasets_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.entity_tabs.addTab(self.datasets_table, "Data Sets")

        right_layout.addWidget(self.entity_tabs)
        sp.addWidget(right_widget)
        sp.setStretchFactor(0, 1)
        sp.setStretchFactor(1, 2)

        layout.addWidget(sp)

    def refresh(self):
        self.module_list.clear()
        # Add "All" and "No Module" virtual entries
        all_item = QListWidgetItem("📋 All Entities")
        all_item.setData(Qt.UserRole, "all")
        self.module_list.addItem(all_item)
        none_item = QListWidgetItem("❓ No Module Assigned")
        none_item.setData(Qt.UserRole, "none")
        self.module_list.addItem(none_item)
        for m in self.db.list_modules():
            item = QListWidgetItem(f"[{m.module_Id}] {m.module_Name}")
            item.setData(Qt.UserRole, m.module_Id)
            self.module_list.addItem(item)

    def _on_module_sel(self, row):
        if row < 0:
            return
        item = self.module_list.item(row)
        module_id = item.data(Qt.UserRole)

        self.steps_table.setRowCount(0)
        self.assertions_table.setRowCount(0)
        self.scenarios_table.setRowCount(0)
        self.datasets_table.setRowCount(0)

        if module_id == "all":
            steps = self.db.list_steps()
            assertions = self.db.list_assertions()
            scenarios = self.db.list_scenarios()
            datasets = self.db.list_data_sets()
        elif module_id == "none":
            steps = [s for s in self.db.list_steps() if not s.module_Ids]
            assertions = [a for a in self.db.list_assertions() if not a.module_Ids]
            scenarios = [s for s in self.db.list_scenarios() if not s.module_Ids]
            datasets = [d for d in self.db.list_data_sets() if not d.module_Ids]
        else:
            steps = self.db.get_By_Module("step", module_id)
            assertions = self.db.get_By_Module("assertion", module_id)
            scenarios = self.db.get_By_Module("scenario", module_id)
            datasets = self.db.get_By_Module("data_set", module_id)

        # Populate steps
        for s in steps:
            r = self.steps_table.rowCount()
            self.steps_table.insertRow(r)
            self.steps_table.setItem(r, 0, QTableWidgetItem(str(s.step_Id)))
            self.steps_table.setItem(r, 1, QTableWidgetItem(s.step_Name))
            self.steps_table.setItem(r, 2, QTableWidgetItem(s.action_Type.value))
            self.steps_table.setItem(r, 3, QTableWidgetItem(s.target_Selector))

        # Populate assertions
        for a in assertions:
            r = self.assertions_table.rowCount()
            self.assertions_table.insertRow(r)
            self.assertions_table.setItem(r, 0, QTableWidgetItem(str(a.assertion_Id)))
            self.assertions_table.setItem(r, 1, QTableWidgetItem(a.assertion_Name))
            self.assertions_table.setItem(r, 2, QTableWidgetItem(a.assertion_Type.value))

        # Populate scenarios
        for s in scenarios:
            r = self.scenarios_table.rowCount()
            self.scenarios_table.insertRow(r)
            self.scenarios_table.setItem(r, 0, QTableWidgetItem(str(s.scenario_Id)))
            self.scenarios_table.setItem(r, 1, QTableWidgetItem(s.scenario_Name))
            self.scenarios_table.setItem(r, 2, QTableWidgetItem(str(len(s.step_Ids or []))))

        # Populate data sets
        for ds in datasets:
            r = self.datasets_table.rowCount()
            self.datasets_table.insertRow(r)
            self.datasets_table.setItem(r, 0, QTableWidgetItem(str(ds.data_Set_Id)))
            self.datasets_table.setItem(r, 1, QTableWidgetItem(ds.data_Set_Name))
            self.datasets_table.setItem(r, 2, QTableWidgetItem(str(len(ds.rows or []))))

    def _add_module(self):
        m = Module()
        dialog = _ModuleEditDialog(m, self.db, self)
        if dialog.exec_() == QDialog.Accepted:
            m = dialog.get_module()
            if not m.module_Name:
                QMessageBox.warning(self, "Name", "Enter a module name.")
                return
            self.db.save_module(m)
            self.refresh()

    def _edit_module(self):
        item = self.module_list.currentItem()
        if not item:
            QMessageBox.information(self, "Select", "Select a module to edit.")
            return
        mid = item.data(Qt.UserRole)
        if mid in ("all", "none"):
            QMessageBox.information(self, "Virtual", "This is a virtual entry — cannot edit.")
            return
        m = self.db.load_module(mid)
        if m is None:
            return
        dialog = _ModuleEditDialog(m, self.db, self)
        if dialog.exec_() == QDialog.Accepted:
            m = dialog.get_module()
            self.db.save_module(m)
            self.refresh()

    def _delete_module(self):
        item = self.module_list.currentItem()
        if not item:
            QMessageBox.information(self, "Select", "Select a module to delete.")
            return
        mid = item.data(Qt.UserRole)
        if mid in ("all", "none"):
            QMessageBox.information(self, "Virtual", "This is a virtual entry — cannot delete.")
            return
        name = item.text().split("] ")[1] if "] " in item.text() else item.text()
        if QMessageBox.question(self, "Delete", f"Delete module '{name}'?") == QMessageBox.Yes:
            self.db.delete_module(mid)
            self.refresh()


