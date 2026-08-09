"""
Configuration tab — manage environment configs and global variables.
Opens a dialog with scrollbar for editing.
"""
from __future__ import annotations
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QTableWidget, QTableWidgetItem, QLineEdit, QComboBox, QCheckBox, QSpinBox,
    QPushButton, QListWidget, QListWidgetItem, QGroupBox, QMessageBox,
    QDialog, QDialogButtonBox, QLabel, QScrollArea)
from PyQt5.QtCore import Qt
from Config import EnvironmentConfig, DeviceType, BrowserType, GlobalVariable
from Storage import DataBase


class _ConfigEditDialog(QDialog):
    """Dialog for editing a single environment config with scrollbar."""

    def __init__(self, config, db, parent=None):
        super().__init__(parent)
        self.db = db
        self.config = config
        self.setWindowTitle(f"Edit Config: {config.config_Name}" if config.config_Name else "New Config")
        self.setMinimumSize(600, 500)
        self._build_ui()
        self._load_config()

    def _build_ui(self):
        # Scroll area for the form
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setFrameShape(QScrollArea.NoFrame)

        content = QWidget()
        form = QFormLayout(content)

        # Config fields
        self.name_input = QLineEdit()
        form.addRow("Config Name:", self.name_input)

        self.device_combo = QComboBox()
        self.device_combo.addItems(["Desktop", "Mobile", "Tablet"])
        form.addRow("Device:", self.device_combo)

        self.browser_combo = QComboBox()
        self.browser_combo.addItems(["Chrome", "Firefox", "Safari", "Edge"])
        form.addRow("Browser:", self.browser_combo)

        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("https://your-erp.com")
        form.addRow("App URL:", self.url_input)

        self.headless_check = QCheckBox("Headless mode")
        form.addRow("", self.headless_check)

        self.timeout_spin = QSpinBox()
        self.timeout_spin.setRange(5, 300)
        self.timeout_spin.setValue(30)
        self.timeout_spin.setSuffix(" sec")
        form.addRow("Timeout:", self.timeout_spin)

        scroll.setWidget(content)

        # Global variables section (outside scroll — table needs its own scroll)
        gv_group = QGroupBox("Global Variables — use as {{global.var_name}}")
        gv_layout = QVBoxLayout(gv_group)
        self.gv_table = QTableWidget(0, 4)
        self.gv_table.setHorizontalHeaderLabels(["Name", "Value", "Sensitive", "Description"])
        self.gv_table.setMinimumHeight(180)
        gv_layout.addWidget(self.gv_table)
        gv_btns = QHBoxLayout()
        self.add_gv_btn = QPushButton("Add Variable")
        self.add_gv_btn.clicked.connect(self._add_gv)
        gv_btns.addWidget(self.add_gv_btn)
        self.rm_gv_btn = QPushButton("Remove Selected")
        self.rm_gv_btn.clicked.connect(self._rm_gv)
        gv_btns.addWidget(self.rm_gv_btn)
        gv_layout.addLayout(gv_btns)
        self.gv_hint = QLabel("Examples: {{global.username}}, {{global.password}}, {{global.base_url}}")
        self.gv_hint.setStyleSheet("color:#6366f1;font-size:11px;")
        gv_layout.addWidget(self.gv_hint)

        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.addWidget(scroll)
        main_layout.addWidget(gv_group)

        # OK / Cancel
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        main_layout.addWidget(buttons)

    def _load_config(self):
        self.name_input.setText(self.config.config_Name)
        dm = {DeviceType.DESKTOP: "Desktop", DeviceType.MOBILE: "Mobile", DeviceType.TABLET: "Tablet"}
        bm = {BrowserType.CHROME: "Chrome", BrowserType.FIREFOX: "Firefox",
              BrowserType.SAFARI: "Safari", BrowserType.EDGE: "Edge"}
        self.device_combo.setCurrentText(dm.get(self.config.device_type, "Desktop"))
        self.browser_combo.setCurrentText(bm.get(self.config.browser_type, "Chrome"))
        self.url_input.setText(self.config.web_app_url)
        self.headless_check.setChecked(self.config.headless)
        self.timeout_spin.setValue(self.config.timeout_sec)
        self._load_gv_table()

    def _load_gv_table(self):
        self.gv_table.setRowCount(0)
        for gv in (self.config.global_Variables or []):
            if isinstance(gv, dict):
                gv = GlobalVariable.from_dict(gv)
            r = self.gv_table.rowCount()
            self.gv_table.insertRow(r)
            self.gv_table.setItem(r, 0, QTableWidgetItem(gv.var_Name))
            val_item = QTableWidgetItem("*******" if gv.is_Sensitive else gv.var_Value)
            self.gv_table.setItem(r, 1, val_item)
            self.gv_table.setItem(r, 2, QTableWidgetItem("Yes" if gv.is_Sensitive else "No"))
            self.gv_table.setItem(r, 3, QTableWidgetItem(gv.var_Description))

    def _add_gv(self):
        self.gv_table.insertRow(self.gv_table.rowCount())
        self.gv_table.setItem(self.gv_table.rowCount()-1, 0, QTableWidgetItem(""))
        self.gv_table.setItem(self.gv_table.rowCount()-1, 1, QTableWidgetItem(""))
        self.gv_table.setItem(self.gv_table.rowCount()-1, 2, QTableWidgetItem("No"))
        self.gv_table.setItem(self.gv_table.rowCount()-1, 3, QTableWidgetItem(""))

    def _rm_gv(self):
        r = self.gv_table.currentRow()
        if r >= 0:
            self.gv_table.removeRow(r)

    def get_config(self) -> EnvironmentConfig:
        """Return the edited config from the form."""
        cfg = EnvironmentConfig()
        cfg.config_Id = self.config.config_Id
        cfg.config_Name = self.name_input.text().strip()
        dm = {"Desktop": DeviceType.DESKTOP, "Mobile": DeviceType.MOBILE, "Tablet": DeviceType.TABLET}
        bm = {"Chrome": BrowserType.CHROME, "Firefox": BrowserType.FIREFOX,
              "Safari": BrowserType.SAFARI, "Edge": BrowserType.EDGE}
        cfg.device_type = dm.get(self.device_combo.currentText(), DeviceType.DESKTOP)
        cfg.browser_type = bm.get(self.browser_combo.currentText(), BrowserType.CHROME)
        cfg.web_app_url = self.url_input.text().strip()
        cfg.headless = self.headless_check.isChecked()
        cfg.timeout_sec = self.timeout_spin.value()
        cfg.global_Variables = self._collect_gv()
        return cfg

    def _collect_gv(self) -> list:
        gvs = []
        for r in range(self.gv_table.rowCount()):
            name_item = self.gv_table.item(r, 0)
            val_item = self.gv_table.item(r, 1)
            sens_item = self.gv_table.item(r, 2)
            desc_item = self.gv_table.item(r, 3)
            name = name_item.text().strip() if name_item else ""
            if not name:
                continue
            val = val_item.text() if val_item else ""
            if val == "*******":
                for gv in (self.config.global_Variables or []):
                    if isinstance(gv, dict):
                        gv_obj = GlobalVariable.from_dict(gv)
                    else:
                        gv_obj = gv
                    if gv_obj.var_Name == name:
                        val = gv_obj.var_Value
                        break
            is_sens = (sens_item.text() == "Yes") if sens_item else False
            desc = desc_item.text() if desc_item else ""
            gvs.append(GlobalVariable(var_Name=name, var_Value=val, var_Description=desc, is_Sensitive=is_sens))
        return gvs


class ConfigTab(QWidget):
    """Configuration tab — list of configs with Add/Edit/Delete."""

    def __init__(self, db: DataBase):
        super().__init__()
        self.db = db
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        # Toolbar
        btn_row = QHBoxLayout()
        self.add_btn = QPushButton("New Config")
        self.add_btn.clicked.connect(self._add_config)
        btn_row.addWidget(self.add_btn)
        self.edit_btn = QPushButton("Edit")
        self.edit_btn.clicked.connect(self._edit_config)
        btn_row.addWidget(self.edit_btn)
        self.del_btn = QPushButton("Delete")
        self.del_btn.clicked.connect(self._delete_config)
        btn_row.addWidget(self.del_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        # Config list
        self.config_list = QListWidget()
        layout.addWidget(self.config_list)

    def refresh(self):
        self.config_list.clear()
        for cfg in self.db.list_configs():
            gvars = cfg.global_Variables or []
            item = QListWidgetItem(
                f"[{cfg.config_Id}] {cfg.config_Name} — "
                f"{cfg.browser_type.value} | {len(gvars)} global vars | {cfg.web_app_url}")
            item.setData(Qt.UserRole, cfg.config_Id)
            self.config_list.addItem(item)

    def _add_config(self):
        cfg = EnvironmentConfig()
        dialog = _ConfigEditDialog(cfg, self.db, self)
        if dialog.exec_() == QDialog.Accepted:
            cfg = dialog.get_config()
            if not cfg.config_Name:
                QMessageBox.warning(self, "Name", "Enter a config name.")
                return
            self.db.save_config(cfg)
            self.refresh()

    def _edit_config(self):
        item = self.config_list.currentItem()
        if not item:
            QMessageBox.information(self, "Select", "Select a config to edit.")
            return
        cid = item.data(Qt.UserRole)
        cfg = self.db.load_config_by_id(cid)
        if cfg is None:
            return
        dialog = _ConfigEditDialog(cfg, self.db, self)
        if dialog.exec_() == QDialog.Accepted:
            cfg = dialog.get_config()
            self.db.save_config(cfg)
            self.refresh()

    def _delete_config(self):
        item = self.config_list.currentItem()
        if not item:
            QMessageBox.information(self, "Select", "Select a config to delete.")
            return
        cid = item.data(Qt.UserRole)
        name = item.text().split("] ")[1].split(" —")[0] if "] " in item.text() else item.text()
        if QMessageBox.question(self, "Delete", f"Delete config '{name}'?") == QMessageBox.Yes:
            self.db.delete_config(cid)
            self.refresh()

    def get_current_config(self) -> EnvironmentConfig | None:
        """Called by Runner tab to get the selected config."""
        item = self.config_list.currentItem()
        if not item:
            configs = self.db.list_configs()
            return configs[0] if configs else None
        cid = item.data(Qt.UserRole)
        return self.db.load_config_by_id(cid)

