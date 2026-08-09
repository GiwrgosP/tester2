"""
SQLite storage for ERP Test Automation Framework v7.
Thread-safe with RLock. Dependency checking on delete.
Global variables stored as part of env_config.
"""
from __future__ import annotations
import sqlite3
import json
import os
import threading
from datetime import datetime
from Config import EnvironmentConfig
from Models import Module, DataSet, Step, Assertion, Scenario, TestResult


class DataBase:
    """SQLite-backed storage. Thread-safe. Dependency checking on delete."""

    def __init__(self, db_path: str = None):
        if db_path is None:
            # Use absolute path based on script directory to avoid CWD issues
            script_dir = os.path.dirname(os.path.abspath(__file__))
            saved_data_dir = os.path.join(script_dir, "saved_data")
            os.makedirs(saved_data_dir, exist_ok=True)
            db_path = os.path.join(saved_data_dir, "erp_test.db")
        self.db_Path = db_path
        self._conn = sqlite3.connect(self.db_Path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.RLock()
        self._init_schema()

    def _init_schema(self):
        with self._lock:
            c = self._conn.cursor()
            c.executescript("""
                CREATE TABLE IF NOT EXISTS modules (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    data TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS data_sets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    data TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS steps (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    data TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS assertions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    data TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS scenarios (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    data TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS test_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    data TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS env_config (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    data TEXT NOT NULL
                );
            """)
            self._conn.commit()

    # ── Generic save / load / list / delete ───────────────────

    def _get_table(self, entity_type: str) -> str:
        mapping = {
            "module": "modules",
            "data_set": "data_sets",
            "step": "steps",
            "assertion": "assertions",
            "scenario": "scenarios",
            "test_result": "test_results",
            "env_config": "env_config",
        }
        return mapping[entity_type]

    def _next_id(self, entity_type: str) -> int:
        with self._lock:
            table = self._get_table(entity_type)
            c = self._conn.execute(f"SELECT MAX(id) FROM {table}")
            row = c.fetchone()
            return (row[0] or 0) + 1

    def save(self, entity, entity_type: str) -> int:
        """Save an entity. Returns its ID."""
        with self._lock:
            table = self._get_table(entity_type)
            if entity is None:
                return 0

            # Determine ID
            if entity_type == "module":
                eid = entity.module_Id
                id_field = "module_Id"
            elif entity_type == "data_set":
                eid = entity.data_Set_Id
                id_field = "data_Set_Id"
            elif entity_type == "step":
                eid = entity.step_Id
                id_field = "step_Id"
            elif entity_type == "assertion":
                eid = entity.assertion_Id
                id_field = "assertion_Id"
            elif entity_type == "scenario":
                eid = entity.scenario_Id
                id_field = "scenario_Id"
            elif entity_type == "test_result":
                eid = entity.result_Id
                id_field = "result_Id"
            elif entity_type == "env_config":
                eid = entity.config_Id
                id_field = "config_Id"
            else:
                eid = 0
                id_field = "id"

            if eid == 0:
                eid = self._next_id(entity_type)
                setattr(entity, id_field, eid)

            data_json = entity.to_json() if hasattr(entity, 'to_json') else json.dumps(entity.to_dict())

            # Check if exists
            c = self._conn.execute(f"SELECT id FROM {table} WHERE id = ?", (eid,))
            exists = c.fetchone()

            if exists:
                self._conn.execute(f"UPDATE {table} SET data = ? WHERE id = ?", (data_json, eid))
            else:
                self._conn.execute(f"INSERT INTO {table} (id, data) VALUES (?, ?)", (eid, data_json))
            self._conn.commit()
            return eid

    def load(self, entity_type: str, entity_id: int):
        """Load an entity by ID."""
        with self._lock:
            table = self._get_table(entity_type)
            c = self._conn.execute(f"SELECT data FROM {table} WHERE id = ?", (entity_id,))
            row = c.fetchone()
            if row is None:
                return None

            data = json.loads(row[0])

            if entity_type == "module":
                return Module.from_json(data)
            elif entity_type == "data_set":
                return DataSet.from_json(data)
            elif entity_type == "step":
                return Step.from_json(data)
            elif entity_type == "assertion":
                return Assertion.from_json(data)
            elif entity_type == "scenario":
                return Scenario.from_json(data)
            elif entity_type == "test_result":
                return TestResult.from_json(data)
            elif entity_type == "env_config":
                return EnvironmentConfig.from_json(data)
            return None

    def load_all(self, entity_type: str) -> list:
        """Load all entities of a type."""
        with self._lock:
            table = self._get_table(entity_type)
            c = self._conn.execute(f"SELECT data FROM {table} ORDER BY id")
            results = []
            for row in c.fetchall():
                data = json.loads(row[0])
                if entity_type == "module":
                    results.append(Module.from_json(data))
                elif entity_type == "data_set":
                    results.append(DataSet.from_json(data))
                elif entity_type == "step":
                    results.append(Step.from_json(data))
                elif entity_type == "assertion":
                    results.append(Assertion.from_json(data))
                elif entity_type == "scenario":
                    results.append(Scenario.from_json(data))
                elif entity_type == "test_result":
                    results.append(TestResult.from_json(data))
                elif entity_type == "env_config":
                    results.append(EnvironmentConfig.from_json(data))
            return results

    def delete(self, entity_type: str, entity_id: int) -> dict:
        """Delete an entity with dependency checking."""
        with self._lock:
            table = self._get_table(entity_type)

            # Check dependencies
            dependents = []
            if entity_type == "step":
                for s in self.load_all("scenario"):
                    if entity_id in (s.step_Ids or []):
                        dependents.append(f"Scenario [{s.scenario_Id}] {s.scenario_Name}")
                for st in self.load_all("step"):
                    if entity_id in (st.assertion_Ids or []):
                        dependents.append(f"Step [{st.step_Id}] {st.step_Name}")
            elif entity_type == "assertion":
                for s in self.load_all("scenario"):
                    if entity_id in (s.assertion_Ids or []):
                        dependents.append(f"Scenario [{s.scenario_Id}] {s.scenario_Name}")
                for st in self.load_all("step"):
                    if entity_id in (st.assertion_Ids or []):
                        dependents.append(f"Step [{st.step_Id}] {st.step_Name}")
            elif entity_type == "scenario":
                for s in self.load_all("scenario"):
                    if entity_id in (s.nested_Scenario_Ids or []):
                        dependents.append(f"Scenario [{s.scenario_Id}] {s.scenario_Name}")
                # Check pre/post conditions
                for s in self.load_all("scenario"):
                    if getattr(s, 'pre_On_True_Scenario_Id', 0) == entity_id or \
                       getattr(s, 'pre_On_False_Scenario_Id', 0) == entity_id or \
                       getattr(s, 'post_On_True_Scenario_Id', 0) == entity_id or \
                       getattr(s, 'post_On_False_Scenario_Id', 0) == entity_id:
                        dependents.append(f"Scenario [{s.scenario_Id}] {s.scenario_Name} (as branch)")
            elif entity_type == "data_set":
                for s in self.load_all("scenario"):
                    if s.data_Set_Id == entity_id:
                        dependents.append(f"Scenario [{s.scenario_Id}] {s.scenario_Name}")
            elif entity_type == "module":
                for entity_type_check in ["step", "assertion", "scenario", "data_set"]:
                    for e in self.load_all(entity_type_check):
                        if entity_id in (e.module_Ids or []):
                            dependents.append(f"{entity_type_check.capitalize()} [{getattr(e, id_field, 0)}] {getattr(e, 'step_Name', getattr(e, 'assertion_Name', getattr(e, 'scenario_Name', '')))}")

            if dependents:
                return {"deleted": False, "blocked": True, "dependents": dependents}

            self._conn.execute(f"DELETE FROM {table} WHERE id = ?", (entity_id,))
            self._conn.commit()
            return {"deleted": True}

    def get_By_Module(self, entity_type: str, module_id: int) -> list:
        """Get all entities of a type that have the given module."""
        with self._lock:
            all_entities = self.load_all(entity_type)
            return [e for e in all_entities if module_id in (e.module_Ids or [])]

    # ── Convenience methods ───────────────────────────────────

    # Modules
    def save_module(self, m: Module) -> int: return self.save(m, "module")
    def load_module(self, mid: int) -> Module | None: return self.load("module", mid)
    def list_modules(self) -> list: return self.load_all("module")
    def delete_module(self, mid: int) -> dict: return self.delete("module", mid)

    # Data Sets
    def save_data_set(self, ds: DataSet) -> int: return self.save(ds, "data_set")
    def load_data_set(self, dsid: int) -> DataSet | None: return self.load("data_set", dsid)
    def list_data_sets(self) -> list: return self.load_all("data_set")
    def delete_data_set(self, dsid: int) -> dict: return self.delete("data_set", dsid)

    # Steps
    def save_step(self, s: Step) -> int: return self.save(s, "step")
    def load_step(self, sid: int) -> Step | None: return self.load("step", sid)
    def list_steps(self) -> list: return self.load_all("step")
    def delete_step(self, sid: int) -> dict: return self.delete("step", sid)

    # Assertions
    def save_assertion(self, a: Assertion) -> int: return self.save(a, "assertion")
    def load_assertion(self, aid: int) -> Assertion | None: return self.load("assertion", aid)
    def list_assertions(self) -> list: return self.load_all("assertion")
    def delete_assertion(self, aid: int) -> dict: return self.delete("assertion", aid)

    # Scenarios
    def save_scenario(self, s: Scenario) -> int: return self.save(s, "scenario")
    def load_scenario(self, sid: int) -> Scenario | None: return self.load("scenario", sid)
    def list_scenarios(self) -> list: return self.load_all("scenario")
    def delete_scenario(self, sid: int) -> dict: return self.delete("scenario", sid)

    # Test Results
    def save_result(self, r: TestResult) -> int: return self.save(r, "test_result")
    def load_result(self, rid: int) -> TestResult | None: return self.load("test_result", rid)
    def list_results(self) -> list: return self.load_all("test_result")
    def delete_result(self, rid: int) -> dict: return self.delete("test_result", rid)

    # Environment Config
    def save_config(self, cfg: EnvironmentConfig) -> int:
        cfg.config_Id = cfg.config_Id or self._next_id("env_config")
        return self.save(cfg, "env_config")
    def load_config(self) -> EnvironmentConfig | None:
        configs = self.load_all("env_config")
        return configs[0] if configs else None
    def load_config_by_id(self, cid: int) -> EnvironmentConfig | None: return self.load("env_config", cid)
    def list_configs(self) -> list: return self.load_all("env_config")
    def delete_config(self, cid: int) -> dict: return self.delete("env_config", cid)

    def close(self):
        self._conn.close()

