"""
Test execution engine v7. Loads global variables from config, passes to executors.
Enhanced page-load waiting. Conditional branching (pre/post conditions).
Network response tracking for assertions.
"""
from __future__ import annotations
import time, os
from datetime import datetime
from PyQt5.QtCore import QObject, pyqtSignal
from Config import EnvironmentConfig
from Models import Scenario, TestResult, AssertionResult, ResultStatus
from Storage import DataBase
from Evaluator import StepExecutor, AssertionEvaluator, VariableSubstitutor, _get_locator


class TestRunner(QObject):
    log_message = pyqtSignal(str)
    progress = pyqtSignal(int)
    step_completed = pyqtSignal(str, bool)
    assertion_evaluated = pyqtSignal(str, str)
    scenario_completed = pyqtSignal(str, bool)
    finished = pyqtSignal(object)

    def __init__(self, env_config: EnvironmentConfig, db: DataBase):
        super().__init__()
        self.env = env_config
        self.db = db
        self._ar = []
        self._sp = 0
        self._sf = 0
        self._spass = 0
        self._sfail = 0
        self._global_vars = {}
        self._responses = []
        self._failed_requests = []

    def run_scenarios(self, scenario_ids: list) -> TestResult:
        t0 = time.time()
        self.log_message.emit("Starting test execution...")
        self._ar = []
        self._sp = 0
        self._sf = 0
        self._spass = 0
        self._sfail = 0

        self._global_vars = self.env.get_Global_Variables_Dict()
        if self._global_vars:
            self.log_message.emit(f"Loaded {len(self._global_vars)} global variables: {', '.join(self._global_vars.keys())}")

        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            bn = self.env.get_playwright_browser_name()
            ch = self.env.get_playwright_launch_channel()
            kw = {"headless": self.env.headless}
            if ch:
                kw["channel"] = ch
            if bn == "firefox":
                br = p.firefox.launch(**kw)
            elif bn == "webkit":
                br = p.webkit.launch(**kw)
            else:
                br = p.chromium.launch(**kw)

            # Build context with device descriptor
            device_descriptor = self.env.get_device_descriptor()
            ctx = br.new_context(**device_descriptor)
            page = ctx.new_page()
            page.set_default_timeout(self.env.timeout_sec * 1000)

            # Set up network response tracking for assertions
            page.on("response", lambda r: self._responses.append({"url": r.url, "status": r.status}))
            page.on("requestfailed", lambda req: self._failed_requests.append({"url": req.url, "error": str(req.failure)}))
            AssertionEvaluator._responses = self._responses
            AssertionEvaluator._failed_requests = self._failed_requests

            device_name = str(self.env.device_type.value)
            self.log_message.emit(f"Browser: {bn} | Device: {device_name} | Headless: {self.env.headless}")
            self.log_message.emit(f"Context viewport: {device_descriptor.get('viewport', 'default')}")

            if self.env.web_app_url:
                page.goto(self.env.web_app_url)
                self._wait_for_page_load(page)

            total = len(scenario_ids)
            for i, sid in enumerate(scenario_ids):
                sc = self.db.load_scenario(sid)
                if sc is None:
                    continue
                self.log_message.emit(f"\n--- Running: {sc.scenario_Name} ---")

                # Data-driven
                data_rows = [None]
                if sc.data_Set_Id and sc.data_Set_Id > 0:
                    ds = self.db.load_data_set(sc.data_Set_Id)
                    if ds and ds.rows:
                        data_rows = ds.rows
                        self.log_message.emit(f"  Data set: {ds.data_Set_Name} ({len(ds.rows)} rows)")

                for row_idx, row in enumerate(data_rows):
                    if row is not None:
                        self.log_message.emit(f"  >> Row {row_idx+1}/{len(data_rows)}: {row}")
                    ap, results = self._exec_sc(page, sc, row, row_idx)
                    self._ar.extend(results)
                    if ap:
                        self._spass += 1
                    else:
                        self._sfail += 1
                    self.scenario_completed.emit(sc.scenario_Name, ap)

                self.progress.emit(int((i + 1) / total * 100))

            br.close()

        dur = time.time() - t0
        ta = len(self._ar)
        pa = sum(1 for r in self._ar if r.is_passed())
        result = TestResult(
            test_Name=f"Test Run {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            total_Scenarios=total, passed_Scenarios=self._spass, failed_Scenarios=self._sfail,
            total_Steps=self._sp + self._sf, passed_Steps=self._sp, failed_Steps=self._sf,
            total_Assertions=ta, passed_Assertions=pa, failed_Assertions=ta - pa,
            execution_Duration_Sec=round(dur, 2), assertion_Results=self._ar)
        result.calculate_status()
        result.result_Id = self.db.save_result(result)

        self.log_message.emit(f"\n=== Complete: {result.status.value.upper()} ===")
        self.log_message.emit(f"Scenarios: {result.passed_Scenarios}/{result.total_Scenarios} | "
                              f"Steps: {result.passed_Steps}/{result.total_Steps} | "
                              f"Assertions: {result.passed_Assertions}/{result.total_Assertions}")
        self.finished.emit(result)
        return result

    def _wait_for_page_load(self, page):
        try:
            page.wait_for_load_state("load", timeout=15000)
        except Exception:
            pass
        try:
            page.wait_for_load_state("networkidle", timeout=10000)
        except Exception:
            pass
        try:
            page.wait_for_load_state("domcontentloaded", timeout=10000)
        except Exception:
            pass
        page.wait_for_timeout(500)

    def _wait_for_selector(self, page, selector: str, timeout: int = 10000):
        if not selector:
            return
        if selector.startswith("http://") or selector.startswith("https://"):
            return
        try:
            locator = _get_locator(page, selector)
            locator.wait_for(state="visible", timeout=timeout)
        except Exception:
            pass

    def _execute_step_with_condition(self, page, step, data_row, gv, step_idx, step_conditions):
        """Execute a step, checking for a per-step condition first."""
        condition = step_conditions.get(str(step_idx)) or step_conditions.get(step_idx)
        if condition:
            assertion_id = condition.get("assertion_Id", 0)
            run_if = condition.get("run_If", "always")

            if assertion_id and assertion_id > 0 and run_if != "always":
                assertion = self.db.load_assertion(assertion_id)
                if assertion:
                    result = AssertionEvaluator.evaluate(page, assertion, data_row, gv)
                    should_run = (result.is_passed() and run_if == "passed") or \
                                 (not result.is_passed() and run_if == "failed")
                    self.log_message.emit(
                        f"    [condition] {assertion.assertion_Name}: {result.status.value} "
                        f"→ {'running' if should_run else 'skipped'}")
                    if not should_run:
                        self.log_message.emit(f"    Skipped (condition not met): {step.step_Name}")
                        return True

        self.log_message.emit(f"  Step: {step.step_Name} ({step.action_Type.value})")
        try:
            StepExecutor.execute(page, step, data_row, gv)
            self._sp += 1
            self.step_completed.emit(step.step_Name, True)
            return True
        except Exception as e:
            self._sf += 1
            self.step_completed.emit(step.step_Name, False)
            self.log_message.emit(f"    FAILED: {e}")
            try:
                os.makedirs("saved_data/screenshots", exist_ok=True)
                page.screenshot(path=f"saved_data/screenshots/step_{step.step_Id}_fail.png")
            except Exception:
                pass
            return False

    def _evaluate_assertions_for_step(self, page, step, data_row, gv, row_idx):
        results = []
        for aid in step.assertion_Ids:
            a = self.db.load_assertion(aid)
            if a is None:
                continue
            r = AssertionEvaluator.evaluate(page, a, data_row, gv)
            r.scope = "step"
            r.step_Name = step.step_Name
            r.data_Row_Index = row_idx
            if not r.is_passed():
                try:
                    os.makedirs("saved_data/screenshots", exist_ok=True)
                    r.screenshot_Path = f"saved_data/screenshots/sa_{a.assertion_Id}_fail.png"
                    page.screenshot(path=r.screenshot_Path)
                except Exception:
                    pass
            results.append(r)
            self.assertion_evaluated.emit(a.assertion_Name, r.status.value)
            self.log_message.emit(f"    [step] {a.assertion_Name}: {r.status.value}")
        return results

    def _evaluate_assertions_for_scenario(self, page, sc, data_row, gv, row_idx):
        results = []
        for aid in sc.assertion_Ids:
            a = self.db.load_assertion(aid)
            if a is None:
                continue
            r = AssertionEvaluator.evaluate(page, a, data_row, gv)
            r.scope = "scenario"
            r.step_Name = ""
            r.data_Row_Index = row_idx
            if not r.is_passed():
                try:
                    os.makedirs("saved_data/screenshots", exist_ok=True)
                    r.screenshot_Path = f"saved_data/screenshots/ca_{a.assertion_Id}_fail.png"
                    page.screenshot(path=r.screenshot_Path)
                except Exception:
                    pass
            results.append(r)
            self.assertion_evaluated.emit(a.assertion_Name, r.status.value)
            self.log_message.emit(f"  [scenario] {a.assertion_Name}: {r.status.value}")
        return results

    def _exec_sc(self, page, sc, data_row, row_idx, depth=0, visited=None):
        """Execute a scenario with pre/post conditional branching."""
        if visited is None:
            visited = set()

        if sc.scenario_Id in visited:
            self.log_message.emit(f"  [WARNING] Circular reference: {sc.scenario_Name} — skipping")
            return True, []
        visited.add(sc.scenario_Id)

        all_r = []
        ap = True
        gv = self._global_vars
        indent = "  " * (depth + 1)
        step_conditions = getattr(sc, 'step_Conditions', {}) or {}

        # ══════════════════════════════════════════════════════
        # 1. PRE-CONDITION — evaluate before any steps
        # ══════════════════════════════════════════════════════
        pre_assertion_id = getattr(sc, 'pre_Condition_Assertion_Id', 0) or 0
        pre_on_true = getattr(sc, 'pre_On_True_Scenario_Id', 0) or 0
        pre_on_false = getattr(sc, 'pre_On_False_Scenario_Id', 0) or 0
        pre_stop_true = getattr(sc, 'pre_Stop_If_True', False)
        pre_stop_false = getattr(sc, 'pre_Stop_If_False', False)

        if pre_assertion_id > 0:
            assertion = self.db.load_assertion(pre_assertion_id)
            if assertion:
                self.log_message.emit(f"{indent}PRE-CONDITION: {assertion.assertion_Name}")
                result = AssertionEvaluator.evaluate(page, assertion, data_row, gv)
                result.scope = "scenario"
                result.step_Name = f"pre-condition of {sc.scenario_Name}"
                result.data_Row_Index = row_idx
                all_r.append(result)
                self.assertion_evaluated.emit(assertion.assertion_Name, result.status.value)
                self.log_message.emit(f"{indent}  → {result.status.value}")

                if result.is_passed():
                    if pre_on_true > 0:
                        branch_sc = self.db.load_scenario(pre_on_true)
                        if branch_sc:
                            self.log_message.emit(f"{indent}  → Running branch: {branch_sc.scenario_Name}")
                            bp, br = self._exec_sc(page, branch_sc, data_row, row_idx, depth + 1, visited)
                            all_r.extend(br)
                            if not bp:
                                ap = False
                    if pre_stop_true:
                        self.log_message.emit(f"{indent}  → Stopping main scenario (pre-condition passed + stop flag)")
                        return ap, all_r
                else:
                    if pre_on_false > 0:
                        branch_sc = self.db.load_scenario(pre_on_false)
                        if branch_sc:
                            self.log_message.emit(f"{indent}  → Running branch: {branch_sc.scenario_Name}")
                            bp, br = self._exec_sc(page, branch_sc, data_row, row_idx, depth + 1, visited)
                            all_r.extend(br)
                            if not bp:
                                ap = False
                    if pre_stop_false:
                        self.log_message.emit(f"{indent}  → Stopping main scenario (pre-condition failed + stop flag)")
                        return ap, all_r

        # ══════════════════════════════════════════════════════
        # 2. MAIN STEPS — execute in order with per-step conditions
        # ══════════════════════════════════════════════════════
        for idx, sid in enumerate(sc.step_Ids):
            step = self.db.load_step(sid)
            if step is None:
                self.log_message.emit(f"{indent}Step {sid} not found, skipping.")
                continue

            self._wait_for_page_load(page)

            sel = VariableSubstitutor.substitute(step.target_Selector, data_row, gv)
            non_element_actions = ["navigate", "wait", "screenshot", "scroll"]
            if step.action_Type.value not in non_element_actions:
                self._wait_for_selector(page, sel, timeout=step.selector_Timeout_Ms or 10000)

            step_passed = self._execute_step_with_condition(
                page, step, data_row, gv, idx, step_conditions)

            if not step_passed:
                ap = False

            step_results = self._evaluate_assertions_for_step(page, step, data_row, gv, row_idx)
            all_r.extend(step_results)
            if any(not r.is_passed() for r in step_results):
                ap = False

        # ══════════════════════════════════════════════════════
        # 3. NESTED SCENARIOS — recursive
        # ══════════════════════════════════════════════════════
        for nid in sc.nested_Scenario_Ids:
            ns = self.db.load_scenario(nid)
            if ns and nid != sc.scenario_Id:
                self.log_message.emit(f"{indent}>> Nested: {ns.scenario_Name}")
                np, nr = self._exec_sc(page, ns, data_row, row_idx, depth + 1, visited)
                all_r.extend(nr)
                if not np:
                    ap = False

        # ══════════════════════════════════════════════════════
        # 4. SCENARIO-LEVEL ASSERTIONS — after all steps
        # ══════════════════════════════════════════════════════
        sc_results = self._evaluate_assertions_for_scenario(page, sc, data_row, gv, row_idx)
        all_r.extend(sc_results)
        if any(not r.is_passed() for r in sc_results):
            ap = False

        # ══════════════════════════════════════════════════════
        # 5. POST-CONDITION — evaluate after all steps
        # ══════════════════════════════════════════════════════
        post_assertion_id = getattr(sc, 'post_Condition_Assertion_Id', 0) or 0
        post_on_true = getattr(sc, 'post_On_True_Scenario_Id', 0) or 0
        post_on_false = getattr(sc, 'post_On_False_Scenario_Id', 0) or 0

        if post_assertion_id > 0:
            assertion = self.db.load_assertion(post_assertion_id)
            if assertion:
                self.log_message.emit(f"{indent}POST-CONDITION: {assertion.assertion_Name}")
                result = AssertionEvaluator.evaluate(page, assertion, data_row, gv)
                result.scope = "scenario"
                result.step_Name = f"post-condition of {sc.scenario_Name}"
                result.data_Row_Index = row_idx
                all_r.append(result)
                self.assertion_evaluated.emit(assertion.assertion_Name, result.status.value)
                self.log_message.emit(f"{indent}  → {result.status.value}")

                if result.is_passed():
                    if post_on_true > 0:
                        branch_sc = self.db.load_scenario(post_on_true)
                        if branch_sc:
                            self.log_message.emit(f"{indent}  → Running branch: {branch_sc.scenario_Name}")
                            bp, br = self._exec_sc(page, branch_sc, data_row, row_idx, depth + 1, visited)
                            all_r.extend(br)
                            if not bp:
                                ap = False
                else:
                    if post_on_false > 0:
                        branch_sc = self.db.load_scenario(post_on_false)
                        if branch_sc:
                            self.log_message.emit(f"{indent}  → Running branch: {branch_sc.scenario_Name}")
                            bp, br = self._exec_sc(page, branch_sc, data_row, row_idx, depth + 1, visited)
                            all_r.extend(br)
                            if not bp:
                                ap = False

        return ap, all_r

