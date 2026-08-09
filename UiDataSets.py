"""
Data Sets tab — view/edit data sets. Opens a dialog with scrollbar for editing.
"""
from __future__ import annotations
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QTableWidget, QTableWidgetItem, QLineEdit, QPushButton, QListWidget,
    QListWidgetItem, QGroupBox, QMessageBox, QDialog, QDialogButtonBox,
    QLabel, QScrollArea, QTextEdit)
from PyQt5.QtCore import Qt
from Models import DataSet
from Storage import DataBase


class _DataSetEditDialog(QDialog):
    """Dialog for editing a single data set with scrollbar."""

    def __init__(self, data_set, db, parent=None):
        super().__init__(parent)
        self.db = db
        self.data_set = data_set
        self.setWindowTitle(f"Edit Data Set: {data_set.data_Set_Name}" if data_set.data_Set_Name else "New Data Set")
        self.setMinimumSize(700, 550)
        self._module_ids = list(data_set.module_Ids or [])
        self._build_ui()
        self._load_data_set()

    def _build_ui(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setFrameShape(QScrollArea.NoFrame)

        content = QWidget()
        layout = QVBoxLayout(content)

        # Basic fields
        form = QFormLayout()
        self.name_input = QLineEdit()
        form.addRow("Data Set Name:", self.name_input)
        self.desc_input = QTextEdit()
        self.desc_input.setMaximumHeight(60)
        form.addRow("Description:", self.desc_input)
        layout.addLayout(form)

        # Columns
        col_group = QGroupBox("Columns (variable names — use as {{var}} in steps)")
        col_layout = QVBoxLayout(col_group)
        self.columns_list = QListWidget()
        self.columns_list.setMaximumHeight(100)
        col_layout.addWidget(self.columns_list)
        col_btns = QHBoxLayout()
        self.add_col_btn = QPushButton("Add Column")
        self.add_col_btn.clicked.connect(self._add_col)
        col_btns.addWidget(self.add_col_btn)
        self.rm_col_btn = QPushButton("Remove")
        self.rm_col_btn.clicked.connect(self._rm_col)
        col_btns.addWidget(self.rm_col_btn)
        col_btns.addStretch()
        col_layout.addLayout(col_btns)
        layout.addWidget(col_group)

        # Rows
        row_group = QGroupBox("Data Rows")
        row_layout = QVBoxLayout(row_group)
        self.rows_table = QTableWidget(0, 1)
        self.rows_table.setMinimumHeight(200)
        row_layout.addWidget(self.rows_table)
        row_btns = QHBoxLayout()
        self.add_row_btn = QPushButton("Add Row")
        self.add_row_btn.clicked.connect(self._add_row)
        row_btns.addWidget(self.add_row_btn)
        self.rm_row_btn = QPushButton("Remove Row")
        self.rm_row_btn.clicked.connect(self._rm_row)
        row_btns.addWidget(self.rm_row_btn)
        row_btns.addStretch()
        row_layout.addLayout(row_btns)
        layout.addWidget(row_group)

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
        layout.addWidget(mg)

        scroll.setWidget(content)

        main_layout = QVBoxLayout(self)
        main_layout.addWidget(scroll)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        main_layout.addWidget(buttons)

    def _load_data_set(self):
        ds = self.data_set
        self.name_input.setText(ds.data_Set_Name)
        self.desc_input.setPlainText(ds.data_Set_Description)
        self.columns_list.clear()
        for col in (ds.columns or []):
            self.columns_list.addItem(col)
        self._rebuild_table()
        self._refresh_mod_list()

    def _rebuild_table(self):
        cols = self._get_columns()
        self.rows_table.setRowCount(0)
        self.rows_table.setColumnCount(len(cols))
        self.rows_table.setHorizontalHeaderLabels(cols)
        for row_data in (self.data_set.rows or []):
            r = self.rows_table.rowCount()
            self.rows_table.insertRow(r)
            for c, col in enumerate(cols):
                val = row_data.get(col, "") if isinstance(row_data, dict) else ""
                self.rows_table.setItem(r, c, QTableWidgetItem(str(val)))

    def _get_columns(self):
        return [self.columns_list.item(i).text() for i in range(self.columns_list.count())]

    def _add_col(self):
        col_name, ok = __import__('PyQt5.QtWidgets', fromlist=['QInputDialog']).QInputDialog.getText(
            self, "Add Column", "Column name (use as {{name}}):")
        if ok and col_name.strip():
            self.columns_list.addItem(col_name.strip())
            self._rebuild_table()

    def _rm_col(self):
        item = self.columns_list.currentItem()
        if item:
            self.columns_list.takeItem(self.columns_list.row(item))
            self._rebuild_table()

    def _add_row(self):
        r = self.rows_table.rowCount()
        self.rows_table.insertRow(r)
        for c in range(self.rows_table.columnCount()):
            self.rows_table.setItem(r, c, QTableWidgetItem(""))

    def _rm_row(self):
        r = self.rows_table.currentRow()
        if r >= 0:
            self.rows_table.removeRow(r)

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

    def get_data_set(self) -> DataSet:
        """Return the edited data set from the form."""
        ds = DataSet()
        ds.data_Set_Id = self.data_set.data_Set_Id
        ds.data_Set_Name = self.name_input.text().strip()
        ds.data_Set_Description = self.desc_input.toPlainText().strip()
        ds.columns = self._get_columns()
        ds.rows = []
        for r in range(self.rows_table.rowCount()):
            row = {}
            for c, col in enumerate(ds.columns):
                item = self.rows_table.item(r, c)
                row[col] = item.text() if item else ""
            ds.rows.append(row)
        ds.module_Ids = list(self._module_ids)
        return ds


class DataSetsTab(QWidget):
    """Data Sets tab — view/edit data sets with dialog-based editing."""

    def __init__(self, db: DataBase):
        super().__init__()
        self.db = db
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        btn_row = QHBoxLayout()
        self.add_btn = QPushButton("New Data Set")
        self.add_btn.clicked.connect(self._add_data_set)
        btn_row.addWidget(self.add_btn)
        self.edit_btn = QPushButton("Edit")
        self.edit_btn.clicked.connect(self._edit_data_set)
        btn_row.addWidget(self.edit_btn)
        self.del_btn = QPushButton("Delete")
        self.del_btn.clicked.connect(self._delete_data_set)
        btn_row.addWidget(self.del_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["ID", "Name", "Columns", "Rows", "Modules"])
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        layout.addWidget(self.table)

    def refresh(self):
        self.table.setRowCount(0)
        for ds in self.db.list_data_sets():
            r = self.table.rowCount()
            self.table.insertRow(r)
            self.table.setItem(r, 0, QTableWidgetItem(str(ds.data_Set_Id)))
            self.table.setItem(r, 1, QTableWidgetItem(ds.data_Set_Name))
            self.table.setItem(r, 2, QTableWidgetItem(", ".join(ds.columns or [])))
            self.table.setItem(r, 3, QTableWidgetItem(str(len(ds.rows or []))))
            self.table.setItem(r, 4, QTableWidgetItem(str(len(ds.module_Ids or []))))

    def _add_data_set(self):
        ds = DataSet()
        dialog = _DataSetEditDialog(ds, self.db, self)
        if dialog.exec_() == QDialog.Accepted:
            ds = dialog.get_data_set()
            if not ds.data_Set_Name:
                QMessageBox.warning(self, "Name", "Enter a data set name.")
                return
            self.db.save_data_set(ds)
            self.refresh()

    def _edit_data_set(self):
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.information(self, "Select", "Select a data set to edit.")
            return
        dsid = int(self.table.item(row, 0).text())
        ds = self.db.load_data_set(dsid)
        if ds is None:
            return
        dialog = _DataSetEditDialog(ds, self.db, self)
        if dialog.exec_() == QDialog.Accepted:
            ds = dialog.get_data_set()
            self.db.save_data_set(ds)
            self.refresh()

    def _delete_data_set(self):
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.information(self, "Select", "Select a data set to delete.")
            return
        dsid = int(self.table.item(row, 0).text())
        name = self.table.item(row, 1).text()
        if QMessageBox.question(self, "Delete", f"Delete data set '{name}'?") == QMessageBox.Yes:
            self.db.delete_data_set(dsid)
            self.refresh()

