"""
Data models for ERP Test Automation Framework v7.
Login fields removed — login is regular steps with {{global.var}}.
Includes: Module, DataSet, Step, Assertion, AssertionResult, TestResult, Scenario.
Scenario has branch flag, pre/post conditions, step conditions.
"""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from enum import Enum
from datetime import datetime
import json
import re

_VAR_PATTERN = re.compile(r'\{\{(global\.\w+|\w+)\}\}')
_GLOBAL_PATTERN = re.compile(r'\{\{global\.(\w+)\}\}')


class ActionType(Enum):
    CLICK = "click"
    DOUBLE_CLICK = "double_click"
    TYPE = "type"
    SELECT = "select"
    HOVER = "hover"
    WAIT = "wait"
    NAVIGATE = "navigate"
    SCROLL = "scroll"
    SCREENSHOT = "screenshot"
    PRESS_KEY = "press_key"
    CHECK = "check"
    UNCHECK = "uncheck"
    COMBOBOX_SELECT = "combobox_select"

    @classmethod
    def labels(cls):
        return {
            cls.CLICK: "Click", cls.DOUBLE_CLICK: "Double Click",
            cls.TYPE: "Type Text", cls.SELECT: "Select Option",
            cls.HOVER: "Hover", cls.WAIT: "Wait",
            cls.NAVIGATE: "Navigate to URL", cls.SCROLL: "Scroll",
            cls.SCREENSHOT: "Screenshot", cls.PRESS_KEY: "Press Key",
            cls.CHECK: "Check Checkbox", cls.UNCHECK: "Uncheck Checkbox",
            cls.COMBOBOX_SELECT: "Combobox Select",
        }

    @classmethod
    def from_value_safe(cls, v):
        try:
            return cls(v)
        except ValueError:
            aliases = {
                "type_text": cls.TYPE, "doubleclick": cls.DOUBLE_CLICK,
                "keypress": cls.PRESS_KEY, "combobox": cls.COMBOBOX_SELECT,
            }
            return aliases.get(str(v).lower(), cls.CLICK)


class AssertionType(Enum):
    FIELD_VALUE = "field_value"
    DIALOG_MESSAGE = "dialog_message"
    ELEMENT_VISIBLE = "element_visible"
    ELEMENT_NOT_VISIBLE = "element_not_visible"
    BUTTON_ENABLED = "button_enabled"
    BUTTON_DISABLED = "button_disabled"
    ERROR_MESSAGE = "error_message"
    TEXT_CONTAINS = "text_contains"
    ATTRIBUTE_VALUE = "attribute_value"
    URL_CONTAINS = "url_contains"
    TITLE_EQUALS = "title_equals"
    ELEMENT_COUNT = "element_count"
    RESPONSE_STATUS = "response_status"
    NETWORK_ERROR = "network_error"

    @classmethod
    def labels(cls):
        return {
            cls.FIELD_VALUE: "Field Value", cls.DIALOG_MESSAGE: "Dialog Message",
            cls.ELEMENT_VISIBLE: "Element Visible", cls.ELEMENT_NOT_VISIBLE: "Element Not Visible",
            cls.BUTTON_ENABLED: "Button Enabled", cls.BUTTON_DISABLED: "Button Disabled",
            cls.ERROR_MESSAGE: "Error Message", cls.TEXT_CONTAINS: "Text Contains",
            cls.ATTRIBUTE_VALUE: "Attribute Value", cls.URL_CONTAINS: "URL Contains",
            cls.TITLE_EQUALS: "Title Equals", cls.ELEMENT_COUNT: "Element Count",
            cls.RESPONSE_STATUS: "Response Status", cls.NETWORK_ERROR: "Network Error",
        }

    @classmethod
    def from_value_safe(cls, v):
        try:
            return cls(v)
        except ValueError:
            return cls.ELEMENT_VISIBLE


class ComparisonOperator(Enum):
    EQUALS = "equals"
    CONTAINS = "contains"
    NOT_EQUALS = "not_equals"
    GREATER_THAN = "greater_than"
    LESS_THAN = "less_than"
    MATCHES_REGEX = "matches_regex"

    @classmethod
    def labels(cls):
        return {
            cls.EQUALS: "Equals", cls.CONTAINS: "Contains",
            cls.NOT_EQUALS: "Not Equals", cls.GREATER_THAN: "Greater Than",
            cls.LESS_THAN: "Less Than", cls.MATCHES_REGEX: "Matches Regex",
        }

    @classmethod
    def from_value_safe(cls, v):
        try:
            return cls(v)
        except ValueError:
            return cls.EQUALS


class ResultStatus(Enum):
    PASSED = "passed"
    FAILED = "failed"
    ERROR = "error"
    PARTIAL = "partial"

    @classmethod
    def from_value_safe(cls, v):
        try:
            return cls(v)
        except ValueError:
            return cls.PASSED


def _to_dict(obj):
    d = asdict(obj)
    for k, v in list(d.items()):
        if isinstance(v, Enum):
            d[k] = v.value
    return d


def _extract_all_vars(text: str) -> list:
    return _VAR_PATTERN.findall(text or "")


def _extract_global_vars(text: str) -> list:
    return _GLOBAL_PATTERN.findall(text or "")


def _extract_local_vars(text: str) -> list:
    all_vars = _extract_all_vars(text)
    globals_set = set(_extract_global_vars(text))
    return [v for v in all_vars if v not in globals_set]


@dataclass
class Module:
    module_Id: int = 0
    module_Name: str = ""
    module_Description: str = ""
    module_Color: str = "#3B82F6"
    parent_Module_Id: int = 0
    created_At: str = ""

    def __post_init__(self):
        if not self.created_At:
            self.created_At = datetime.now().isoformat()

    def to_json(self):
        return json.dumps(_to_dict(self), indent=2)

    @classmethod
    def from_json(cls, data):
        if isinstance(data, str):
            data = json.loads(data)
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class DataSet:
    data_Set_Id: int = 0
    data_Set_Name: str = ""
    data_Set_Description: str = ""
    columns: list = field(default_factory=list)
    rows: list = field(default_factory=list)
    module_Ids: list = field(default_factory=list)
    created_At: str = ""

    def __post_init__(self):
        if not self.created_At:
            self.created_At = datetime.now().isoformat()

    def get_Variables(self) -> list:
        return list(self.columns)

    def to_json(self):
        return json.dumps(_to_dict(self), indent=2)

    @classmethod
    def from_json(cls, data):
        if isinstance(data, str):
            data = json.loads(data)
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class Step:
    step_Id: int = 0
    step_Name: str = ""
    action_Type: ActionType = ActionType.CLICK
    target_Selector: str = ""
    fallback_Selectors: list = field(default_factory=list)
    target_Description: str = ""
    input_Value: str = ""
    wait_Time_Ms: int = 0
    selector_Timeout_Ms: int = 30000
    step_Order: int = 0
    timestamp: str = ""
    screenshot_Path: str = ""
    assertion_Ids: list = field(default_factory=list)
    module_Ids: list = field(default_factory=list)

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()

    def get_Variables(self) -> list:
        vars_set = set()
        for text in [self.input_Value, self.target_Selector]:
            vars_set.update(_extract_all_vars(text))
        return sorted(vars_set)

    def get_Global_Variables(self) -> list:
        vars_set = set()
        for text in [self.input_Value, self.target_Selector]:
            vars_set.update(_extract_global_vars(text))
        return sorted(vars_set)

    def to_json(self):
        d = _to_dict(self)
        d["action_Type"] = self.action_Type.value
        return json.dumps(d, indent=2)

    @classmethod
    def from_json(cls, data):
        if isinstance(data, str):
            data = json.loads(data)
        data["action_Type"] = ActionType.from_value_safe(data.get("action_Type", "click"))
        data = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
        return cls(**data)


@dataclass
class Assertion:
    assertion_Id: int = 0
    assertion_Name: str = ""
    assertion_Type: AssertionType = AssertionType.ELEMENT_VISIBLE
    target_Selector: str = ""
    expected_Value: str = ""
    comparison_Operator: ComparisonOperator = ComparisonOperator.EQUALS
    attribute_Name: str = ""
    timeout_Ms: int = 5000
    module_Ids: list = field(default_factory=list)

    def get_Variables(self) -> list:
        vars_set = set()
        vars_set.update(_extract_all_vars(self.expected_Value))
        vars_set.update(_extract_all_vars(self.target_Selector))
        return sorted(vars_set)

    def get_Global_Variables(self) -> list:
        vars_set = set()
        vars_set.update(_extract_global_vars(self.expected_Value))
        vars_set.update(_extract_global_vars(self.target_Selector))
        return sorted(vars_set)

    def to_json(self):
        d = _to_dict(self)
        d["assertion_Type"] = self.assertion_Type.value
        d["comparison_Operator"] = self.comparison_Operator.value
        return json.dumps(d, indent=2)

    @classmethod
    def from_json(cls, data):
        if isinstance(data, str):
            data = json.loads(data)
        data["assertion_Type"] = AssertionType.from_value_safe(data.get("assertion_Type", "element_visible"))
        data["comparison_Operator"] = ComparisonOperator.from_value_safe(data.get("comparison_Operator", "equals"))
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class AssertionResult:
    result_Id: int = 0
    assertion_Id: int = 0
    assertion_Name: str = ""
    expected_Value: str = ""
    actual_Value: str = ""
    status: ResultStatus = ResultStatus.PASSED
    error_Message: str = ""
    screenshot_Path: str = ""
    timestamp: str = ""
    scope: str = "step"
    step_Name: str = ""
    data_Row_Index: int = -1

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()

    def is_passed(self):
        return self.status == ResultStatus.PASSED

    def to_json(self):
        d = _to_dict(self)
        d["status"] = self.status.value
        return json.dumps(d, indent=2)

    @classmethod
    def from_json(cls, data):
        if isinstance(data, str):
            data = json.loads(data)
        data["status"] = ResultStatus.from_value_safe(data.get("status", "passed"))
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class TestResult:
    result_Id: int = 0
    test_Name: str = ""
    total_Scenarios: int = 0
    passed_Scenarios: int = 0
    failed_Scenarios: int = 0
    total_Steps: int = 0
    passed_Steps: int = 0
    failed_Steps: int = 0
    total_Assertions: int = 0
    passed_Assertions: int = 0
    failed_Assertions: int = 0
    execution_Duration_Sec: float = 0.0
    execution_Timestamp: str = ""
    assertion_Results: list = field(default_factory=list)
    status: ResultStatus = ResultStatus.PASSED
    scenario_Results: list = field(default_factory=list)
    data_Row_Index: int = -1

    def __post_init__(self):
        if not self.execution_Timestamp:
            self.execution_Timestamp = datetime.now().isoformat()

    def calculate_status(self):
        if self.failed_Assertions == 0 and self.failed_Steps == 0 and self.failed_Scenarios == 0:
            self.status = ResultStatus.PASSED
        elif self.passed_Assertions == 0 and self.passed_Steps == 0:
            self.status = ResultStatus.FAILED
        else:
            self.status = ResultStatus.PARTIAL

    def to_json(self):
        d = _to_dict(self)
        d["status"] = self.status.value
        d["assertion_Results"] = [
            ar if isinstance(ar, dict) else json.loads(ar.to_json())
            for ar in self.assertion_Results
        ]
        return json.dumps(d, indent=2)

    @classmethod
    def from_json(cls, data):
        if isinstance(data, str):
            data = json.loads(data)
        data["status"] = ResultStatus.from_value_safe(data.get("status", "passed"))
        ar = data.get("assertion_Results", [])
        data["assertion_Results"] = [
            AssertionResult.from_json(r) if isinstance(r, dict)
            else AssertionResult.from_json(json.loads(r))
            for r in ar
        ]
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class Scenario:
    scenario_Id: int = 0
    scenario_Name: str = ""
    scenario_Description: str = ""
    step_Ids: list = field(default_factory=list)
    nested_Scenario_Ids: list = field(default_factory=list)
    assertion_Ids: list = field(default_factory=list)
    execution_Order: int = 0
    module_Ids: list = field(default_factory=list)
    data_Set_Id: int = 0

    # Branch scenarios are helpers — hidden from the Runner tab
    is_Branch_Scenario: bool = False

    # Pre-condition — evaluated BEFORE any steps
    pre_Condition_Assertion_Id: int = 0
    pre_On_True_Scenario_Id: int = 0
    pre_On_False_Scenario_Id: int = 0
    pre_On_True_Step_Ids: list = field(default_factory=list)
    pre_On_False_Step_Ids: list = field(default_factory=list)
    pre_Stop_If_True: bool = False
    pre_Stop_If_False: bool = False

    # Post-condition — evaluated AFTER all steps complete
    post_Condition_Assertion_Id: int = 0
    post_On_True_Scenario_Id: int = 0
    post_On_False_Scenario_Id: int = 0
    post_On_True_Step_Ids: list = field(default_factory=list)
    post_On_False_Step_Ids: list = field(default_factory=list)

    # Step conditions — {step_index_str: {"assertion_Id": int, "run_If": str}}
    step_Conditions: dict = field(default_factory=dict)

    def get_Variables(self) -> list:
        vars_set = set()
        for sid in self.step_Ids:
            vars_set.update(_extract_all_vars(str(sid)))
        return sorted(vars_set)

    def to_json(self):
        return json.dumps(_to_dict(self), indent=2)

    @classmethod
    def from_json(cls, data):
        if isinstance(data, str):
            data = json.loads(data)
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

