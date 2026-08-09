from __future__ import annotations
from PyQt5.QtWidgets import QMainWindow, QTabWidget, QStatusBar, QAction, QMessageBox
from Storage import DataBase
from UiConfig import ConfigTab
from UiSteps import StepsTab
from UiRecord import RecordTab
from UiAssertions import AssertionsTab
from UiScenarios import ScenariosTab
from UiModules import ModulesTab
from UiDataSets import DataSetsTab
from UiRunner import RunnerTab


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ERP Test Automation Framework v7")
        self.setMinimumSize(1200, 800)
        self.db = DataBase()
        tabs = QTabWidget()

        # Tab 1: Configuration
        self.config_tab = ConfigTab(self.db)
        tabs.addTab(self.config_tab, "⚙ Configuration")

        # Tab 2: Steps (view/edit only — no recording)
        self.steps_tab = StepsTab(self.db)
        tabs.addTab(self.steps_tab, "📋 Steps")

        # Tab 3: Record (dedicated recording tab)
        self.record_tab = RecordTab(self.db)
        tabs.addTab(self.record_tab, "🎥 Record")

        # Tab 4: Assertions
        self.assertions_tab = AssertionsTab(self.db)
        tabs.addTab(self.assertions_tab, "✅ Assertions")

        # Tab 5: Scenarios
        self.scenarios_tab = ScenariosTab(self.db)
        tabs.addTab(self.scenarios_tab, "📁 Scenarios")

        # Tab 6: Modules
        self.modules_tab = ModulesTab(self.db)
        tabs.addTab(self.modules_tab, "🏷 Modules")

        # Tab 7: Data Sets
        self.datasets_tab = DataSetsTab(self.db)
        tabs.addTab(self.datasets_tab, "📊 Data Sets")

        # Tab 8: Runner
        self.runner_tab = RunnerTab(self.db, self.config_tab)
        tabs.addTab(self.runner_tab, "▶ Test Runner")

        self.setCentralWidget(tabs)
        self.setStatusBar(QStatusBar())

        mb = self.menuBar()
        fm = mb.addMenu("File")
        ra = QAction("Refresh All", self)
        ra.triggered.connect(self._refresh)
        fm.addAction(ra)
        fm.addSeparator()
        ex = QAction("Exit", self)
        ex.triggered.connect(self.close)
        fm.addAction(ex)

        hm = mb.addMenu("Help")
        aa = QAction("About", self)
        aa.triggered.connect(lambda: QMessageBox.about(self, "About",
            "ERP Test Automation Framework v7\n\n"
            "SQLite · Global variables · Data-driven testing\n"
            "Module categorization · Conditional branching\n"
            "PyQt5 + Playwright"))
        hm.addAction(aa)

    def _refresh(self):
        for tab in [self.config_tab, self.steps_tab, self.record_tab,
                    self.assertions_tab, self.scenarios_tab, self.modules_tab,
                    self.datasets_tab, self.runner_tab]:
            if hasattr(tab, 'refresh'):
                tab.refresh()
        self.statusBar().showMessage("All tabs refreshed", 3000)

