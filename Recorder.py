"""
Step recorder using Playwright codegen + AST parser.
Records user interactions and converts them to Step objects.
FIXED: AST parsing of locator chains (get_by_role, get_by_label, etc.)
"""
from __future__ import annotations
import ast, subprocess, sys, tempfile, os
from datetime import datetime
from Models import Step, ActionType


class StepRecorder:
    """Records steps via Playwright codegen subprocess + AST parser."""

    _BROWSER_MAP = {
        "chrome": [], "chromium": [], "default": [],
        "firefox": ["--browser", "firefox"],
        "webkit": ["--browser", "webkit"], "safari": ["--browser", "webkit"],
        "edge": ["--browser", "chromium", "--channel", "msedge"],
    }

    def start_recording(self, url: str, browser: str = "chromium") -> list:
        bt = str(browser).lower()
        browser_flag = []
        for key, flag in self._BROWSER_MAP.items():
            if key in bt:
                browser_flag = flag
                break

        fd, temp_path = tempfile.mkstemp(suffix=".py")
        os.close(fd)

        cmd = [sys.executable, "-m", "playwright", "codegen",
               "--target", "python", "--output", temp_path]
        cmd += browser_flag
        cmd.append(url)

        print(f"[Recorder] Running: {' '.join(cmd)}")
        try:
            subprocess.run(cmd, timeout=300)
        except subprocess.TimeoutExpired:
            print("[Recorder] Timed out")

        if not os.path.exists(temp_path):
            print("[Recorder] No output file — no steps recorded")
            return []

        with open(temp_path, "r", encoding="utf-8") as f:
            code_text = f.read()

        steps = self._parse(code_text)
        os.remove(temp_path)
        print(f"[Recorder] Parsed {len(steps)} steps")
        return steps

    def convert_To_Variables(self, steps: list) -> list:
        """Replace input values with {{variable}} placeholders."""
        for step in steps:
            if step.input_Value:
                var_name = step.input_Value.strip().lower()
                var_name = var_name.replace(" ", "_").replace("-", "_")
                if var_name:
                    step.input_Value = f"{{{{{var_name}}}}}"
        return steps

    # ── AST Parser ────────────────────────────────────────────

    def _parse(self, code_text: str) -> list:
        try:
            tree = ast.parse(code_text)
        except SyntaxError:
            return self._parse_regex_fallback(code_text)

        steps = []
        order = 0
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Expr) and isinstance(node.value, ast.Call)):
                continue
            call = node.value
            action = self._extract_action(call)
            if action:
                order += 1
                steps.append(Step(
                    step_Name=f"Step {order}: {action.action_Type.value} {action.target_Selector[:50]}",
                    action_Type=action.action_Type,
                    target_Selector=action.target_Selector,
                    input_Value=action.input_Value,
                    target_Description=action.target_Description,
                    step_Order=order,
                    timestamp=datetime.now().isoformat()))
        return steps

    def _extract_action(self, call):
        """Extract action from an AST Call node."""
        if isinstance(call.func, ast.Attribute):
            # Direct call: page.goto(), page.click(), page.fill()
            if isinstance(call.func.value, ast.Name) and call.func.value.id == "page":
                method = call.func.attr
                return self._map_page_action(call, method)
            # Locator chain: page.get_by_role("button", name="Save").click()
            if isinstance(call.func.value, ast.Call):
                return self._extract_locator_action(call)
        return None

    def _map_page_action(self, call, method):
        """Map direct page.* calls."""
        sel = self._ast_value(call.args[0]) if call.args else ""
        at_map = {
            "goto": ActionType.NAVIGATE, "click": ActionType.CLICK,
            "dblclick": ActionType.DOUBLE_CLICK, "fill": ActionType.TYPE,
            "press": ActionType.PRESS_KEY, "select_option": ActionType.SELECT,
            "hover": ActionType.HOVER, "screenshot": ActionType.SCREENSHOT,
            "wait_for_selector": ActionType.WAIT,
        }
        action_type = at_map.get(method)
        if not action_type:
            return None
        input_val = self._ast_value(call.args[1]) if len(call.args) > 1 else ""
        return {"action_Type": action_type, "target_Selector": sel,
                "input_Value": input_val, "target_Description": sel}

    def _extract_locator_action(self, call):
        """Extract action from locator chain: page.get_by_role(...).click()."""
        chain = []
        current = call
        while isinstance(current, ast.Call) and isinstance(current.func, ast.Attribute):
            chain.append((current.func.attr, current))
            current = current.func.value
        if isinstance(current, ast.Name) and current.id == "page":
            chain.append(("page", current))

        method = chain[0][0]
        at_map = {
            "click": ActionType.CLICK, "dblclick": ActionType.DOUBLE_CLICK,
            "fill": ActionType.TYPE, "press": ActionType.PRESS_KEY,
            "select_option": ActionType.SELECT, "hover": ActionType.HOVER,
            "check": ActionType.CHECK, "uncheck": ActionType.UNCHECK,
            "wait_for": ActionType.WAIT,
        }
        action_type = at_map.get(method)
        if not action_type:
            return None

        input_val = self._ast_value(chain[0][1].args[0]) if chain[0][1].args else ""

        # Build selector from the locator chain
        selector = ""
        desc = ""
        for name, node in reversed(chain[1:]):
            if name == "page":
                continue
            if isinstance(node, ast.Call) and node.args:
                if name == "get_by_role":
                    role = self._ast_value(node.args[0])
                    if len(node.args) > 1 and isinstance(node.args[1], ast.keyword):
                        name_val = self._ast_value(node.args[1].value)
                        selector = f"role={role} name={name_val}"
                    else:
                        selector = f"role={role}"
                    desc = selector
                elif name == "get_by_label":
                    val = self._ast_value(node.args[0])
                    selector = f"label={val}"
                    desc = val
                elif name == "get_by_text":
                    val = self._ast_value(node.args[0])
                    selector = f"text={val}"
                    desc = val
                elif name == "get_by_placeholder":
                    val = self._ast_value(node.args[0])
                    selector = f"placeholder={val}"
                    desc = val
                elif name == "get_by_test_id":
                    val = self._ast_value(node.args[0])
                    selector = f"test-id={val}"
                    desc = val
                elif name == "get_by_alt_text":
                    val = self._ast_value(node.args[0])
                    selector = f"alt={val}"
                    desc = val
                elif name == "get_by_title":
                    val = self._ast_value(node.args[0])
                    selector = f"title={val}"
                    desc = val
                elif name == "locator":
                    val = self._ast_value(node.args[0])
                    selector = val
                    desc = val
                elif name == "frame_locator":
                    pass
                elif name == "first":
                    pass
                elif name == "last":
                    pass
                elif name == "nth":
                    pass
                else:
                    pass

        return {"action_Type": action_type, "target_Selector": selector,
                "input_Value": input_val, "target_Description": desc}

    def _ast_value(self, node) -> str:
        """Safely extract a value from an AST node."""
        if node is None:
            return ""
        if isinstance(node, ast.Constant):
            return str(node.value)
        try:
            return str(ast.literal_eval(node))
        except Exception:
            return ""

    def _parse_regex_fallback(self, code_text: str) -> list:
        """Fallback regex parser for non-AST-parseable output."""
        import re
        steps = []
        order = 0

        # page.goto("url")
        for m in re.finditer(r'page\.goto\("([^"]+)"\)', code_text):
            order += 1
            steps.append(Step(
                step_Name=f"Step {order}: navigate {m.group(1)[:50]}",
                action_Type=ActionType.NAVIGATE,
                target_Selector=m.group(1),
                step_Order=order,
                timestamp=datetime.now().isoformat()))

        # page.get_by_role("button", name="Save").click()
        for m in re.finditer(
                r'page\.get_by_role\("([^"]+)",\s*name="([^"]+)"\)\.(\w+)\(\)', code_text):
            order += 1
            at_map = {"click": ActionType.CLICK, "fill": ActionType.TYPE,
                      "press": ActionType.PRESS_KEY, "hover": ActionType.HOVER}
            steps.append(Step(
                step_Name=f"Step {order}: {m.group(3)} {m.group(2)}",
                action_Type=at_map.get(m.group(3), ActionType.CLICK),
                target_Selector=f"role={m.group(1)} name={m.group(2)}",
                step_Order=order,
                timestamp=datetime.now().isoformat()))

        # page.get_by_label("text").click() or .fill("value")
        for m in re.finditer(
                r'page\.get_by_label\("([^"]+)"\)\.(\w+)\((?:"([^"]*)")?\)', code_text):
            order += 1
            at_map = {"click": ActionType.CLICK, "fill": ActionType.TYPE,
                      "press": ActionType.PRESS_KEY, "hover": ActionType.HOVER}
            steps.append(Step(
                step_Name=f"Step {order}: {m.group(2)} {m.group(1)}",
                action_Type=at_map.get(m.group(2), ActionType.CLICK),
                target_Selector=f"label={m.group(1)}",
                input_Value=m.group(3) or "",
                step_Order=order,
                timestamp=datetime.now().isoformat()))

        # page.get_by_text("text").click()
        for m in re.finditer(
                r'page\.get_by_text\("([^"]+)"\)\.(\w+)\(\)', code_text):
            order += 1
            at_map = {"click": ActionType.CLICK, "fill": ActionType.TYPE,
                      "press": ActionType.PRESS_KEY, "hover": ActionType.HOVER}
            steps.append(Step(
                step_Name=f"Step {order}: {m.group(2)} {m.group(1)}",
                action_Type=at_map.get(m.group(2), ActionType.CLICK),
                target_Selector=f"text={m.group(1)}",
                step_Order=order,
                timestamp=datetime.now().isoformat()))

        # page.get_by_placeholder("text").click() or .fill()
        for m in re.finditer(
                r'page\.get_by_placeholder\("([^"]+)"\)\.(\w+)\((?:"([^"]*)")?\)', code_text):
            order += 1
            at_map = {"click": ActionType.CLICK, "fill": ActionType.TYPE,
                      "press": ActionType.PRESS_KEY, "hover": ActionType.HOVER}
            steps.append(Step(
                step_Name=f"Step {order}: {m.group(2)} {m.group(1)}",
                action_Type=at_map.get(m.group(2), ActionType.CLICK),
                target_Selector=f"placeholder={m.group(1)}",
                input_Value=m.group(3) or "",
                step_Order=order,
                timestamp=datetime.now().isoformat()))

        # page.get_by_test_id("id").click()
        for m in re.finditer(
                r'page\.get_by_test_id\("([^"]+)"\)\.(\w+)\(\)', code_text):
            order += 1
            at_map = {"click": ActionType.CLICK, "fill": ActionType.TYPE,
                      "press": ActionType.PRESS_KEY, "hover": ActionType.HOVER}
            steps.append(Step(
                step_Name=f"Step {order}: {m.group(2)} {m.group(1)}",
                action_Type=at_map.get(m.group(2), ActionType.CLICK),
                target_Selector=f"test-id={m.group(1)}",
                step_Order=order,
                timestamp=datetime.now().isoformat()))

        # page.click("selector"), page.fill("selector", "value")
        for m in re.finditer(
                r'page\.(\w+)\("([^"]+)"(?:,\s*"([^"]*)")?\)', code_text):
            method = m.group(1)
            if method in ("goto", "get_by_role", "get_by_label", "get_by_text",
                          "get_by_placeholder", "get_by_test_id"):
                continue
            at_map = {"click": ActionType.CLICK, "dblclick": ActionType.DOUBLE_CLICK,
                      "fill": ActionType.TYPE, "press": ActionType.PRESS_KEY,
                      "hover": ActionType.HOVER, "select_option": ActionType.SELECT,
                      "check": ActionType.CHECK, "uncheck": ActionType.UNCHECK,
                      "screenshot": ActionType.SCREENSHOT}
            if method in at_map:
                order += 1
                steps.append(Step(
                    step_Name=f"Step {order}: {method} {m.group(2)[:50]}",
                    action_Type=at_map[method],
                    target_Selector=m.group(2),
                    input_Value=m.group(3) or "",
                    step_Order=order,
                    timestamp=datetime.now().isoformat()))

        return steps

