import os
import json
import winreg
import sys

CONFIG_DIR = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "PrintSoft")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")

DEFAULT_CONFIG = {
    "server_url": "http://localhost:8000",
    "api_key": "",
    "shop_id": "",
    "shop_name": "",
    "device_id": "",
    "device_token": "",
    "device_name": "Windows Desktop Agent",
    "selected_printer": "",
    "bw_rate": 2.0,
    "color_rate": 10.0,
    "duplex_discount": 0.5,
    "auto_print": True,
    "sound_enabled": True,
    "auto_start": True
}

class ConfigManager:
    def __init__(self):
        os.makedirs(CONFIG_DIR, exist_ok=True)
        self.config = {}
        self.config = self.load_config()

    def load_config(self) -> dict:
        if not os.path.exists(CONFIG_FILE):
            self.save_config(DEFAULT_CONFIG)
            return DEFAULT_CONFIG.copy()
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                merged = DEFAULT_CONFIG.copy()
                merged.update(data)
                return merged
        except Exception as e:
            print(f"[Config Error] Failed to read config: {e}")
            return DEFAULT_CONFIG.copy()

    def save_config(self, data: dict = None) -> bool:
        if not hasattr(self, 'config') or self.config is None:
            self.config = {}
        if data is not None:
            self.config.update(data)
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=4)
            return True
        except Exception as e:
            print(f"[Config Error] Failed to save config: {e}")
            return False

    def get(self, key: str, default=None):
        return self.config.get(key, default)

    def set(self, key: str, value):
        self.config[key] = value
        self.save_config()

    def is_configured(self) -> bool:
        return bool(self.get("api_key") and self.get("shop_id") and self.get("device_id") and self.get("device_token"))

    def set_auto_start(self, enable: bool):
        """Sets Windows registry key for launch on startup."""
        app_name = "PrintSoftAgent"
        exe_path = sys.executable if getattr(sys, 'frozen', False) else f'"{sys.executable}" "{os.path.abspath(sys.argv[0])}"'
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_ALL_ACCESS)
            if enable:
                winreg.SetValueEx(key, app_name, 0, winreg.REG_SZ, exe_path)
            else:
                try:
                    winreg.DeleteValue(key, app_name)
                except FileNotFoundError:
                    pass
            winreg.CloseKey(key)
            self.set("auto_start", enable)
        except Exception as e:
            print(f"[AutoStart Error] {e}")

config_mgr = ConfigManager()
