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
    """Environment configuration for a test run."""
    config_Id: int = 0
    config_Name: str = ""
    device_type: DeviceType = DeviceType.DESKTOP
    browser_type: BrowserType = BrowserType.CHROME
    web_app_url: str = ""
    headless: bool = False
    timeout_sec: int = 30
    global_Variables: list = field(default_factory=list)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["device_type"] = self.device_type.value
        d["browser_type"] = self.browser_type.value
        d["global_Variables"] = [gv.to_dict() if isinstance(gv, GlobalVariable) else gv for gv in self.global_Variables]
        return d

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)

    @classmethod
    def from_dict(cls, data: dict) -> "EnvironmentConfig":
        d = dict(data)
        d["device_type"] = DeviceType(d.get("device_type", "desktop"))
        d["browser_type"] = BrowserType(d.get("browser_type", "chrome"))
        gv_list = d.get("global_Variables", [])
        d["global_Variables"] = [
            GlobalVariable.from_dict(gv) if isinstance(gv, dict) else gv
            for gv in gv_list
        ]
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})

    @classmethod
    def from_json(cls, json_str) -> "EnvironmentConfig":
        data = json.loads(json_str) if isinstance(json_str, str) else json_str
        return cls.from_dict(data)

    def get_playwright_browser_name(self) -> str:
        if self.browser_type == BrowserType.FIREFOX:
            return "firefox"
        if self.browser_type == BrowserType.SAFARI:
            return "webkit"
        return "chromium"

    def get_playwright_launch_channel(self) -> str | None:
        return self.browser_type.get_playwright_channel()

    def get_device_descriptor(self) -> dict:
        """Return Playwright device descriptor dict for browser context.
        For mobile/tablet, includes user_agent so the server responds as mobile."""
        presets = DeviceType.get_presets()
        preset = presets.get(self.device_type, {})

        if self.device_type == DeviceType.MOBILE:
            return {
                "viewport": preset.get("viewport", {"width": 390, "height": 844}),
                "is_mobile": True,
                "has_touch": True,
                "user_agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
            }
        elif self.device_type == DeviceType.TABLET:
            return {
                "viewport": preset.get("viewport", {"width": 768, "height": 1024}),
                "is_mobile": True,
                "has_touch": True,
                "user_agent": "Mozilla/5.0 (iPad; CPU OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
            }
        else:
            # Desktop — no user_agent override
            return {
                "viewport": preset.get("viewport", {"width": 1920, "height": 1080}),
            }

