"""
Step recorder using Playwright codegen + AST parser.
FIXED: _extract_action returns _ActionResult objects (not dicts) so .action_Type.value works.
FIXED: AST parsing handles all locator chains (get_by_role, get_by_label, etc.)
"""
from __future__ import annotations
import ast, subprocess, sys, tempfile, os, re
from datetime import datetime
from collections import namedtuple
from Models import Step, ActionType

_ActionResult = namedtuple('_ActionResult', ['action_Type', 'target_Selector', 'input_Value', 'target_Description'])


class StepRecorder:
    """Records steps using Playwright codegen and converts them to Step objects."""

    def start_recording(self, url: str, browser: str = "chromium") -> list:
        bt = str(browser)
        if "firefox" in bt.lower():
            flag = ["--browser", "firefox"]
        elif "webkit" in bt.lower() or "safari" in bt.lower():
            flag = ["--browser", "webkit"]
        elif "edge" in bt.lower():
            flag = ["--browser", "chromium", "--channel", "msedge"]
        else:
            flag = []

        fd, temp_path = tempfile.mkstemp(suffix=".py")
        os.close(fd)

        cmd = [sys.executable, "-m", "playwright", "codegen",
               "--target", "python", "--output", temp_path] + flag + [url]
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

    def _extract_action(self, call) -> _ActionResult | None:
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

    def _map_page_action(self, call, method) -> _ActionResult | None:
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
        return _ActionResult(action_Type=action_type, target_Selector=sel,
                             input_Value=input_val, target_Description=sel)

    def _extract_locator_action(self, call) -> _ActionResult | None:
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

        return _ActionResult(action_Type=action_type, target_Selector=selector,
                             input_Value=input_val, target_Description=desc)

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
        steps = []
        order = 0

        patterns = [
            (r'page\.goto\("([^"]*)"\)', ActionType.NAVIGATE, "goto"),
            (r'page\.get_by_label\("([^"]*)"\)\.click\(\)', ActionType.CLICK, "click label"),
            (r'page\.get_by_label\("([^"]*)"\)\.fill\("([^"]*)"\)', ActionType.TYPE, "fill label"),
            (r'page\.get_by_label\("([^"]*)"\)\.press\("([^"]*)"\)', ActionType.PRESS_KEY, "press label"),
            (r'page\.get_by_text\("([^"]*)"\)\.click\(\)', ActionType.CLICK, "click text"),
            (r'page\.get_by_text\("([^"]*)"\)\.fill\("([^"]*)"\)', ActionType.TYPE, "fill text"),
            (r'page\.get_by_placeholder\("([^"]*)"\)\.click\(\)', ActionType.CLICK, "click placeholder"),
            (r'page\.get_by_placeholder\("([^"]*)"\)\.fill\("([^"]*)"\)', ActionType.TYPE, "fill placeholder"),
            (r'page\.get_by_role\("([^"]*)", name="([^"]*)"\)\.click\(\)', ActionType.CLICK, "click role"),
            (r'page\.get_by_role\("([^"]*)", name="([^"]*)"\)\.fill\("([^"]*)"\)', ActionType.TYPE, "fill role"),
            (r'page\.get_by_role\("([^"]*)", name="([^"]*)"\)\.press\("([^"]*)"\)', ActionType.PRESS_KEY, "press role"),
            (r'page\.get_by_test_id\("([^"]*)"\)\.click\(\)', ActionType.CLICK, "click test-id"),
            (r'page\.get_by_test_id\("([^"]*)"\)\.fill\("([^"]*)"\)', ActionType.TYPE, "fill test-id"),
            (r'page\.get_by_alt_text\("([^"]*)"\)\.click\(\)', ActionType.CLICK, "click alt"),
            (r'page\.get_by_title\("([^"]*)"\)\.click\(\)', ActionType.CLICK, "click title"),
            (r'page\.locator\("([^"]*)"\)\.click\(\)', ActionType.CLICK, "click locator"),
            (r'page\.locator\("([^"]*)"\)\.fill\("([^"]*)"\)', ActionType.TYPE, "fill locator"),
            (r'page\.locator\("([^"]*)"\)\.press\("([^"]*)"\)', ActionType.PRESS_KEY, "press locator"),
            (r'page\.locator\("([^"]*)"\)\.dblclick\(\)', ActionType.DOUBLE_CLICK, "dblclick locator"),
            (r'page\.locator\("([^"]*)"\)\.select_option\("([^"]*)"\)', ActionType.SELECT, "select locator"),
            (r'page\.locator\("([^"]*)"\)\.hover\(\)', ActionType.HOVER, "hover locator"),
            (r'page\.locator\("([^"]*)"\)\.check\(\)', ActionType.CHECK, "check locator"),
            (r'page\.locator\("([^"]*)"\)\.uncheck\(\)', ActionType.UNCHECK, "uncheck locator"),
            (r'page\.wait_for_selector\("([^"]*)"\)', ActionType.WAIT, "wait_for_selector"),
            (r'page\.screenshot\(path="([^"]*)"\)', ActionType.SCREENSHOT, "screenshot"),
        ]

        for line in code_text.splitlines():
            for pattern, at, desc in patterns:
                m = re.search(pattern, line)
                if m:
                    order += 1
                    groups = m.groups()
                    sel = groups[0] if groups else ""
                    inp = groups[1] if len(groups) > 1 else ""

                    if "get_by_label" in pattern:
                        sel = f"label={sel}"
                    elif "get_by_text" in pattern:
                        sel = f"text={sel}"
                    elif "get_by_placeholder" in pattern:
                        sel = f"placeholder={sel}"
                    elif "get_by_role" in pattern:
                        role = groups[0]
                        name = groups[1] if len(groups) > 1 else ""
                        inp = groups[2] if len(groups) > 2 else inp
                        sel = f"role={role} name={name}" if name else f"role={role}"
                    elif "get_by_test_id" in pattern:
                        sel = f"test-id={sel}"
                    elif "get_by_alt_text" in pattern:
                        sel = f"alt={sel}"
                    elif "get_by_title" in pattern:
                        sel = f"title={sel}"

                    steps.append(Step(
                        step_Name=f"Step {order}: {at.value} {sel[:50]}",
                        action_Type=at,
                        target_Selector=sel,
                        input_Value=inp,
                        target_Description=sel,
                        step_Order=order,
                        timestamp=datetime.now().isoformat()))
                    break

        return steps

