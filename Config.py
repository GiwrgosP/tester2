"""
Configuration classes for ERP Test Automation Framework v7.
EnvironmentConfig includes global variables.
No login credentials class — login data lives on Step via {{global.var}}.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict, field
from enum import Enum
import json


class DeviceType(Enum):
    MOBILE = "mobile"
    DESKTOP = "desktop"
    TABLET = "tablet"

    @classmethod
    def get_presets(cls) -> dict:
        return {
            cls.MOBILE: {"viewport": {"width": 390, "height": 844}, "is_mobile": True, "has_touch": True},
            cls.TABLET: {"viewport": {"width": 768, "height": 1024}, "is_mobile": True, "has_touch": True},
            cls.DESKTOP: {"viewport": {"width": 1920, "height": 1080}},
        }


class BrowserType(Enum):
    CHROME = "chrome"
    FIREFOX = "firefox"
    SAFARI = "safari"
    EDGE = "edge"

    def get_playwright_channel(self) -> str | None:
        if self == BrowserType.EDGE:
            return "msedge"
        return None


class AuthType(Enum):
    BASIC = "basic"
    FORM = "form"
    OAUTH = "oauth"


@dataclass
class GlobalVariable:
    var_Id: int = 0
    var_Name: str = ""
    var_Value: str = ""
    var_Description: str = ""
    is_Sensitive: bool = False

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)

    @classmethod
    def from_dict(cls, data: dict) -> "GlobalVariable":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

    @classmethod
    def from_json(cls, json_str) -> "GlobalVariable":
        data = json.loads(json_str) if isinstance(json_str, str) else json_str
        return cls.from_dict(data)


@dataclass
class EnvironmentConfig:
    config_Id: int = 0
    config_Name: str = ""
    device_type: DeviceType = DeviceType.DESKTOP
    browser_type: BrowserType = BrowserType.CHROME
    web_app_url: str = ""
    headless: bool = False
    timeout_sec: int = 30
    config_Type: str = "dev"
    global_Variables: list = field(default_factory=list)

    def __post_init__(self):
        if self.global_Variables is None:
            self.global_Variables = []

    def get_Global_Variables_Dict(self) -> dict:
        result = {}
        for gv in self.global_Variables:
            if isinstance(gv, GlobalVariable):
                result[gv.var_Name] = gv.var_Value
            elif isinstance(gv, dict):
                result[gv.get("var_Name", "")] = gv.get("var_Value", "")
        return result

    def to_json(self) -> str:
        d = asdict(self)
        d["device_type"] = self.device_type.value
        d["browser_type"] = self.browser_type.value
        return json.dumps(d, indent=2)

    @classmethod
    def from_json(cls, json_str) -> "EnvironmentConfig":
        d = json.loads(json_str) if isinstance(json_str, str) else json_str
        d["device_type"] = DeviceType(d.get("device_type", "desktop"))
        d["browser_type"] = BrowserType(d.get("browser_type", "chrome"))
        d["global_Variables"] = [GlobalVariable.from_dict(gv) if isinstance(gv, dict) else gv
                                  for gv in d.get("global_Variables", [])]
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})

    def get_playwright_browser_name(self) -> str:
        if self.browser_type == BrowserType.FIREFOX:
            return "firefox"
        if self.browser_type == BrowserType.SAFARI:
            return "webkit"
        return "chromium"

    def get_playwright_launch_channel(self) -> str | None:
        return self.browser_type.get_playwright_channel()

    def get_device_descriptor(self) -> dict:
        return DeviceType.get_presets().get(self.device_type, {})

