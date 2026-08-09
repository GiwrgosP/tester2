"""
Step executor, assertion evaluator, and variable substitutor v7.
FIXED: Navigate uses pre-substituted URL directly.
FIXED: Unsubstituted variables fail with clear error.
FIXED: Type action uses press_sequentially() for ExtJS compatibility.
NEW: Combobox Select action — click → type → wait → Enter in one step.
NEW: Response Status assertion — checks HTTP response status codes.
NEW: Network Error assertion — checks if network requests failed.
_get_locator() converts label=, text=, role=, placeholder=, test-id= to Playwright locators.
"""
from __future__ import annotations
import re
from Models import Step, ActionType, Assertion, AssertionResult, ComparisonOperator, ResultStatus

_VAR_PATTERN = re.compile(r'\{\{(global\.\w+|\w+)\}\}')


class VariableSubstitutor:
    """Replaces {{global.x}} and {{local_x}} placeholders with values."""
    pattern = _VAR_PATTERN

    @staticmethod
    def substitute(value: str, data_row: dict | None = None, global_vars: dict | None = None) -> str:
        if not value:
            return value

        def replacer(m):
            var_name = m.group(1)
            if var_name.startswith("global."):
                gv_name = var_name[7:]
                if global_vars and gv_name in global_vars:
                    return str(global_vars[gv_name])
                return m.group(0)
            else:
                if data_row and var_name in data_row:
                    return str(data_row[var_name])
                return m.group(0)

        return _VAR_PATTERN.sub(replacer, value)

    @staticmethod
    def substitute_Global(value: str, global_vars: dict | None) -> str:
        if not value or not global_vars:
            return value

        def replacer(m):
            gv_name = m.group(1)
            if gv_name in global_vars:
                return str(global_vars[gv_name])
            return m.group(0)

        return re.sub(r'\{\{global\.(\w+)\}\}', replacer, value)

    @staticmethod
    def substitute_Local(value: str, data_row: dict | None) -> str:
        if not value or not data_row:
            return value

        def replacer(m):
            var_name = m.group(1)
            if var_name in data_row:
                return str(data_row[var_name])
            return m.group(0)

        return re.sub(r'\{\{(\w+)\}\}', replacer, value)

    @staticmethod
    def extract_Variables(value: str) -> list:
        return _VAR_PATTERN.findall(value or "")

    @staticmethod
    def extract_Global_Variables(value: str) -> list:
        return re.findall(r'\{\{global\.(\w+)\}\}', value or "")

    @staticmethod
    def extract_Local_Variables(value: str) -> list:
        all_vars = _VAR_PATTERN.findall(value or "")
        return [v for v in all_vars if not v.startswith("global.")]

    @staticmethod
    def has_unsubstituted(value: str) -> bool:
        return bool(_VAR_PATTERN.search(value or ""))

    @staticmethod
    def get_unsubstituted_names(value: str) -> list:
        return _VAR_PATTERN.findall(value or "")

    @staticmethod
    def validate_Variables(step_or_assertion, data_set=None, global_vars=None) -> list:
        missing = []
        if hasattr(step_or_assertion, 'get_Global_Variables'):
            for gv in step_or_assertion.get_Global_Variables():
                if not global_vars or gv not in global_vars:
                    missing.append(f"global.{gv}")
        if hasattr(step_or_assertion, 'get_Variables'):
            all_vars = step_or_assertion.get_Variables()
            local_vars = [v for v in all_vars if not v.startswith("global.")]
            if data_set and hasattr(data_set, 'columns'):
                for lv in local_vars:
                    if lv not in data_set.columns:
                        missing.append(lv)
            elif local_vars:
                missing.extend(local_vars)
        return missing


def _get_locator(page, selector: str):
    """Convert a selector string to a Playwright locator."""
    selector = selector.strip()

    if selector.startswith("label="):
        return page.get_by_label(selector[6:])
    if selector.startswith("text="):
        return page.get_by_text(selector[5:])
    if selector.startswith("placeholder="):
        return page.get_by_placeholder(selector[12:])
    if selector.startswith("test-id="):
        return page.get_by_test_id(selector[8:])
    if selector.startswith("alt="):
        return page.get_by_alt_text(selector[4:])
    if selector.startswith("title="):
        return page.get_by_title(selector[6:])
    if selector.startswith("role="):
        rest = selector[5:]
        if " name=" in rest:
            role_part, name_part = rest.split(" name=", 1)
            return page.get_by_role(role_part.strip(), name=name_part.strip())
        return page.get_by_role(rest.strip())

    return page.locator(selector)


class StepExecutor:
    """Executes steps on a Playwright page. Registry pattern.
    Navigate steps use the pre-substituted URL directly (no locator).
    Type action uses press_sequentially() for ExtJS compatibility.
    Combobox Select does click → type → wait → Enter in one step.
    Checks for unsubstituted variables before acting."""
    _executors = {}

    @classmethod
    def register(cls, action_type: str):
        def decorator(func):
            cls._executors[action_type] = func
            return func
        return decorator

    @classmethod
    def execute(cls, page, step: Step, data_row=None, global_vars=None) -> bool:
        sel = VariableSubstitutor.substitute(step.target_Selector, data_row, global_vars)
        val = VariableSubstitutor.substitute(step.input_Value, data_row, global_vars)
        timeout = step.selector_Timeout_Ms or 30000

        # Navigate: use URL directly, not a locator
        if step.action_Type.value == "navigate":
            if VariableSubstitutor.has_unsubstituted(sel):
                missing = VariableSubstitutor.get_unsubstituted_names(sel)
                raise ValueError(f"Unsubstituted variable(s) in URL: {missing}.")
            page.goto(sel)
            return True

        # Check for unsubstituted variables
        if VariableSubstitutor.has_unsubstituted(sel):
            missing = VariableSubstitutor.get_unsubstituted_names(sel)
            raise ValueError(f"Unsubstituted variable(s) in selector: {missing}.")
        if VariableSubstitutor.has_unsubstituted(val):
            missing = VariableSubstitutor.get_unsubstituted_names(val)
            raise ValueError(f"Unsubstituted variable(s) in input value: {missing}.")

        # Non-element actions
        if step.action_Type.value == "wait":
            page.wait_for_timeout(step.wait_Time_Ms or 1000)
            return True
        if step.action_Type.value == "screenshot":
            page.screenshot(path=val or f"scr_{step.step_Id}.png")
            return True
        if step.action_Type.value == "scroll":
            page.mouse.wheel(0, 300)
            return True

        # Element-based actions: try primary + fallbacks
        selectors = [sel] + [
            VariableSubstitutor.substitute(s, data_row, global_vars)
            for s in (step.fallback_Selectors or [])
        ]
        last_error = None
        for s in selectors:
            try:
                locator = _get_locator(page, s)
                executor = cls._executors.get(step.action_Type.value)
                if not executor:
                    raise ValueError(f"Unknown action: {step.action_Type.value}")
                return executor(page, step, locator, val, timeout)
            except Exception as e:
                last_error = e
                if s == selectors[-1]:
                    raise
                continue
        if last_error:
            raise last_error
        return False


# ── Step executors ─────────────────────────────────────────────

@StepExecutor.register("click")
def _exec_click(page, step, locator, val, timeout):
    locator.click(timeout=timeout); return True

@StepExecutor.register("double_click")
def _exec_dblclick(page, step, locator, val, timeout):
    locator.dblclick(timeout=timeout); return True

@StepExecutor.register("type")
def _exec_type(page, step, locator, val, timeout):
    if hasattr(locator, 'press_sequentially'):
        try:
            locator.press_sequentially(val, timeout=timeout)
        except Exception:
            if hasattr(locator, 'type'):
                locator.type(val, timeout=timeout)
            else:
                locator.fill(val, timeout=timeout)
    elif hasattr(locator, 'type'):
        locator.type(val, timeout=timeout)
    else:
        locator.fill(val, timeout=timeout)
    return True

@StepExecutor.register("select")
def _exec_select(page, step, locator, val, timeout):
    locator.select_option(val); return True

@StepExecutor.register("combobox_select")
def _exec_combobox(page, step, locator, val, timeout):
    locator.click(timeout=timeout)
    try:
        locator.fill("", timeout=timeout)
    except Exception:
        pass
    if hasattr(locator, 'press_sequentially'):
        try:
            locator.press_sequentially(val, timeout=timeout, delay=50)
        except Exception:
            if hasattr(locator, 'type'):
                locator.type(val, timeout=timeout, delay=50)
            else:
                locator.fill(val, timeout=timeout)
    elif hasattr(locator, 'type'):
        locator.type(val, timeout=timeout, delay=50)
    else:
        locator.fill(val, timeout=timeout)
    page.wait_for_timeout(300)
    locator.press("Enter", timeout=timeout)
    page.wait_for_timeout(200)
    return True

@StepExecutor.register("hover")
def _exec_hover(page, step, locator, val, timeout):
    locator.hover(timeout=timeout); return True

@StepExecutor.register("press_key")
def _exec_press_key(page, step, locator, val, timeout):
    locator.press(val, timeout=timeout); return True

@StepExecutor.register("check")
def _exec_check(page, step, locator, val, timeout):
    locator.check(timeout=timeout); return True

@StepExecutor.register("uncheck")
def _exec_uncheck(page, step, locator, val, timeout):
    locator.uncheck(timeout=timeout); return True


class AssertionEvaluator:
    """Evaluates assertions. Registry pattern.
    Network-based assertions use _responses and _failed_requests set by Runner."""
    _evaluators = {}
    _responses: list = []
    _failed_requests: list = []

    @classmethod
    def register(cls, assertion_type: str):
        def decorator(func):
            cls._evaluators[assertion_type] = func
            return func
        return decorator

    @classmethod
    def evaluate(cls, page, assertion: Assertion, data_row=None, global_vars=None) -> AssertionResult:
        sel = VariableSubstitutor.substitute(assertion.target_Selector, data_row, global_vars)
        expected = VariableSubstitutor.substitute(assertion.expected_Value, data_row, global_vars)

        if VariableSubstitutor.has_unsubstituted(sel):
            missing = VariableSubstitutor.get_unsubstituted_names(sel)
            return AssertionResult(assertion_Id=assertion.assertion_Id, assertion_Name=assertion.assertion_Name,
                                   status=ResultStatus.ERROR, error_Message=f"Unsubstituted variable(s) in selector: {missing}")
        if VariableSubstitutor.has_unsubstituted(expected):
            missing = VariableSubstitutor.get_unsubstituted_names(expected)
            return AssertionResult(assertion_Id=assertion.assertion_Id, assertion_Name=assertion.assertion_Name,
                                   status=ResultStatus.ERROR, error_Message=f"Unsubstituted variable(s) in expected value: {missing}")

        evaluator = cls._evaluators.get(assertion.assertion_Type.value)
        if not evaluator:
            return AssertionResult(assertion_Id=assertion.assertion_Id, assertion_Name=assertion.assertion_Name,
                                   status=ResultStatus.ERROR, error_Message=f"Unknown assertion type: {assertion.assertion_Type.value}")
        try:
            if assertion.assertion_Type.value in ("response_status", "network_error"):
                return evaluator(page, assertion, sel, expected)
            locator = _get_locator(page, sel)
            return evaluator(page, assertion, locator, expected)
        except Exception as e:
            return AssertionResult(assertion_Id=assertion.assertion_Id, assertion_Name=assertion.assertion_Name,
                                   status=ResultStatus.ERROR, error_Message=str(e))

    @staticmethod
    def _cmp(actual: str, expected: str, operator: ComparisonOperator) -> bool:
        if operator == ComparisonOperator.EQUALS: return actual == expected
        if operator == ComparisonOperator.CONTAINS: return expected in actual
        if operator == ComparisonOperator.NOT_EQUALS: return actual != expected
        if operator == ComparisonOperator.GREATER_THAN:
            try: return float(actual) > float(expected)
            except: return False
        if operator == ComparisonOperator.LESS_THAN:
            try: return float(actual) < float(expected)
            except: return False
        if operator == ComparisonOperator.MATCHES_REGEX: return re.search(expected, actual) is not None
        return False


# ── Assertion evaluators ───────────────────────────────────────

@AssertionEvaluator.register("field_value")
def _eval_field_value(page, a, locator, expected):
    actual = locator.input_value()
    passed = AssertionEvaluator._cmp(actual, expected, a.comparison_Operator)
    return AssertionResult(assertion_Id=a.assertion_Id, assertion_Name=a.assertion_Name,
                           expected_Value=expected, actual_Value=actual,
                           status=ResultStatus.PASSED if passed else ResultStatus.FAILED)

@AssertionEvaluator.register("dialog_message")
def _eval_dialog_message(page, a, locator, expected):
    dialog_text = []
    page.on("dialog", lambda d: dialog_text.append(d.message))
    page.wait_for_timeout(a.timeout_Ms)
    actual = dialog_text[0] if dialog_text else ""
    passed = AssertionEvaluator._cmp(actual, expected, a.comparison_Operator)
    return AssertionResult(assertion_Id=a.assertion_Id, assertion_Name=a.assertion_Name,
                           expected_Value=expected, actual_Value=actual,
                           status=ResultStatus.PASSED if passed else ResultStatus.FAILED)

@AssertionEvaluator.register("element_visible")
def _eval_visible(page, a, locator, expected):
    is_vis = locator.is_visible()
    return AssertionResult(assertion_Id=a.assertion_Id, assertion_Name=a.assertion_Name,
                           actual_Value=str(is_vis),
                           status=ResultStatus.PASSED if is_vis else ResultStatus.FAILED)

@AssertionEvaluator.register("element_not_visible")
def _eval_not_visible(page, a, locator, expected):
    is_vis = locator.is_visible()
    return AssertionResult(assertion_Id=a.assertion_Id, assertion_Name=a.assertion_Name,
                           actual_Value=str(not is_vis),
                           status=ResultStatus.PASSED if not is_vis else ResultStatus.FAILED)

@AssertionEvaluator.register("button_enabled")
def _eval_enabled(page, a, locator, expected):
    is_en = locator.is_enabled()
    return AssertionResult(assertion_Id=a.assertion_Id, assertion_Name=a.assertion_Name,
                           actual_Value=str(is_en),
                           status=ResultStatus.PASSED if is_en else ResultStatus.FAILED)

@AssertionEvaluator.register("button_disabled")
def _eval_disabled(page, a, locator, expected):
    is_en = locator.is_enabled()
    return AssertionResult(assertion_Id=a.assertion_Id, assertion_Name=a.assertion_Name,
                           actual_Value=str(not is_en),
                           status=ResultStatus.PASSED if not is_en else ResultStatus.FAILED)

@AssertionEvaluator.register("error_message")
def _eval_error(page, a, locator, expected):
    locators_to_try = [locator]
    for css in [".error", ".alert-danger", "[role='alert']", ".validation-error", ".error-message"]:
        locators_to_try.append(page.locator(css))
    actual = ""
    for loc in locators_to_try:
        try:
            if loc.is_visible():
                actual = loc.text_content() or ""
                break
        except Exception:
            continue
    passed = AssertionEvaluator._cmp(actual, expected, a.comparison_Operator)
    return AssertionResult(assertion_Id=a.assertion_Id, assertion_Name=a.assertion_Name,
                           expected_Value=expected, actual_Value=actual,
                           status=ResultStatus.PASSED if passed else ResultStatus.FAILED)

@AssertionEvaluator.register("text_contains")
def _eval_text_contains(page, a, locator, expected):
    actual = locator.text_content() or ""
    passed = expected in actual
    return AssertionResult(assertion_Id=a.assertion_Id, assertion_Name=a.assertion_Name,
                           expected_Value=expected, actual_Value=actual,
                           status=ResultStatus.PASSED if passed else ResultStatus.FAILED)

@AssertionEvaluator.register("attribute_value")
def _eval_attribute(page, a, locator, expected):
    parts = expected.split("=", 1)
    attr_name = parts[0]
    exp_val = parts[1] if len(parts) > 1 else ""
    actual = locator.get_attribute(attr_name) or ""
    passed = AssertionEvaluator._cmp(actual, exp_val, a.comparison_Operator)
    return AssertionResult(assertion_Id=a.assertion_Id, assertion_Name=a.assertion_Name,
                           expected_Value=exp_val, actual_Value=actual,
                           status=ResultStatus.PASSED if passed else ResultStatus.FAILED)

@AssertionEvaluator.register("url_contains")
def _eval_url(page, a, locator, expected):
    actual = page.url
    passed = expected in actual
    return AssertionResult(assertion_Id=a.assertion_Id, assertion_Name=a.assertion_Name,
                           expected_Value=expected, actual_Value=actual,
                           status=ResultStatus.PASSED if passed else ResultStatus.FAILED)

@AssertionEvaluator.register("title_equals")
def _eval_title(page, a, locator, expected):
    actual = page.title()
    passed = AssertionEvaluator._cmp(actual, expected, a.comparison_Operator)
    return AssertionResult(assertion_Id=a.assertion_Id, assertion_Name=a.assertion_Name,
                           expected_Value=expected, actual_Value=actual,
                           status=ResultStatus.PASSED if passed else ResultStatus.FAILED)

@AssertionEvaluator.register("element_count")
def _eval_count(page, a, locator, expected):
    actual = str(locator.count())
    passed = AssertionEvaluator._cmp(actual, expected, a.comparison_Operator)
    return AssertionResult(assertion_Id=a.assertion_Id, assertion_Name=a.assertion_Name,
                           expected_Value=expected, actual_Value=actual,
                           status=ResultStatus.PASSED if passed else ResultStatus.FAILED)

@AssertionEvaluator.register("response_status")
def _eval_response_status(page, a, selector, expected):
    import fnmatch
    url_pattern = selector.strip() if selector else ""
    expected_status = expected.strip()

    matching = []
    for resp in AssertionEvaluator._responses:
        if not url_pattern:
            if resp["url"] == page.url or resp["url"].rstrip("/") == page.url.rstrip("/"):
                matching.append(resp)
        else:
            if fnmatch.fnmatch(resp["url"], url_pattern):
                matching.append(resp)

    if not matching:
        return AssertionResult(
            assertion_Id=a.assertion_Id, assertion_Name=a.assertion_Name,
            expected_Value=expected_status, actual_Value="(no matching response found)",
            status=ResultStatus.FAILED,
            error_Message=f"No HTTP response found matching '{url_pattern or page.url}'")

    last = matching[-1]
    actual_status = str(last["status"])
    passed = AssertionEvaluator._cmp(actual_status, expected_status, a.comparison_Operator)
    return AssertionResult(
        assertion_Id=a.assertion_Id, assertion_Name=a.assertion_Name,
        expected_Value=expected_status, actual_Value=f"{actual_status} ({last['url'][:80]})",
        status=ResultStatus.PASSED if passed else ResultStatus.FAILED)

@AssertionEvaluator.register("network_error")
def _eval_network_error(page, a, selector, expected):
    import fnmatch
    url_pattern = selector.strip() if selector else "*"
    expected_result = (expected or "no_errors").strip().lower()

    errors_found = []
    for req in AssertionEvaluator._failed_requests:
        if fnmatch.fnmatch(req["url"], url_pattern):
            errors_found.append(f"FAILED: {req['url'][:80]} ({req.get('error', 'unknown')})")
    for resp in AssertionEvaluator._responses:
        if resp["status"] >= 400 and fnmatch.fnmatch(resp["url"], url_pattern):
            errors_found.append(f"HTTP {resp['status']}: {resp['url'][:80]}")

    if expected_result == "has_errors":
        passed = len(errors_found) > 0
        return AssertionResult(
            assertion_Id=a.assertion_Id, assertion_Name=a.assertion_Name,
            expected_Value="has_errors", actual_Value=f"{len(errors_found)} error(s) found",
            status=ResultStatus.PASSED if passed else ResultStatus.FAILED,
            error_Message="" if passed else "Expected errors but none found")
    else:
        passed = len(errors_found) == 0
        error_detail = "; ".join(errors_found[:5]) if errors_found else "no errors"
        return AssertionResult(
            assertion_Id=a.assertion_Id, assertion_Name=a.assertion_Name,
            expected_Value="no_errors", actual_Value=f"{len(errors_found)} error(s)",
            status=ResultStatus.PASSED if passed else ResultStatus.FAILED,
            error_Message=error_detail if errors_found else "")

