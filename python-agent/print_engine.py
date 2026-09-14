import os
import sys
import tempfile
import requests
import subprocess
import time
from config_manager import config_mgr
from printer_service import HAS_WIN32

if HAS_WIN32:
    import win32api

class PrintEngine:
    def __init__(self):
        self.temp_dir = os.path.join(tempfile.gettempdir(), "PrintSoftAgent")
        os.makedirs(self.temp_dir, exist_ok=True)
        self.sumatra_path = self._find_sumatra()

    def _find_sumatra(self) -> str:
        """Finds SumatraPDF executable if available."""
        local_bin = os.path.join(os.path.dirname(__file__), "bin", "SumatraPDF.exe")
        if os.path.exists(local_bin):
            return local_bin
        
        system_paths = [
            r"C:\Program Files\SumatraPDF\SumatraPDF.exe",
            r"C:\Program Files (x86)\SumatraPDF\SumatraPDF.exe"
        ]
        for path in system_paths:
            if os.path.exists(path):
                return path
        return ""

    def download_file(self, download_url: str, job_id: str, original_filename: str) -> str:
        """Downloads document file to local temp path."""
        ext = os.path.splitext(original_filename)[1] or ".pdf"
        local_filename = f"job_{job_id[-8:]}_{int(time.time())}{ext}"
        local_path = os.path.join(self.temp_dir, local_filename)

        if download_url.startswith("mock-r2.storage") or not download_url.startswith("http"):
            # Mock placeholder file for testing
            with open(local_path, "wb") as f:
                f.write(b"%PDF-1.4 Mock PDF Content for Print Soft Agent Test")
            return local_path

        res = requests.get(download_url, timeout=30, stream=True)
        if res.status_code == 200:
            with open(local_path, "wb") as f:
                for chunk in res.iter_content(chunk_size=8192):
                    f.write(chunk)
            return local_path
        else:
            raise Exception(f"File download failed with status code {res.status_code}")

    def print_file(self, file_path: str, printer_name: str, options: dict) -> bool:
        """Spools file to target printer with options (copies, color, duplex, pages)."""
        copies = int(options.get("copies", 1))
        color_mode = options.get("colorMode", "bw") # "color" or "bw"
        duplex = options.get("duplex", "single") # "single", "double_long", "double_short"
        page_range = options.get("pageRange", "") # "1-5,7"

        print(f"[PrintEngine] Printing '{file_path}' on '{printer_name}' | Copies: {copies} | Mode: {color_mode} | Duplex: {duplex}")

        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Local print file not found: {file_path}")

        # 1. SumatraPDF Printing (Best for Windows PDF Silent Printing)
        if self.sumatra_path and file_path.lower().endswith(".pdf"):
            settings = [f"{copies}x"]
            if color_mode == "bw":
                settings.append("monochrome")
            elif color_mode == "color":
                settings.append("color")
                
            if duplex in ["double_long", "duplex", "double"]:
                settings.append("duplexlong")
            elif duplex == "double_short":
                settings.append("duplexshort")
            else:
                settings.append("simplex")

            if page_range and page_range.lower() != "all":
                settings.append(page_range)

            settings_str = ",".join(settings)
            cmd = [
                self.sumatra_path,
                "-print-to", printer_name,
                "-print-settings", settings_str,
                "-silent",
                file_path
            ]
            print(f"[PrintEngine] Executing SumatraPDF: {' '.join(cmd)}")
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                self.cleanup(file_path)
                return True
            else:
                print(f"[PrintEngine Error] SumatraPDF exit code {result.returncode}: {result.stderr}")

        # 2. Win32 API Fallback (ShellExecute printto)
        if HAS_WIN32:
            try:
                for i in range(copies):
                    win32api.ShellExecute(0, "printto", file_path, f'"{printer_name}"', ".", 0)
                    time.sleep(1)
                self.cleanup(file_path)
                return True
            except Exception as e:
                print(f"[PrintEngine Error] ShellExecute printto failed: {e}")
                self.cleanup(file_path)
                raise RuntimeError(f"Windows printer spooler error: {e}")

        # Real Hardware Printing Required - No Simulation
        self.cleanup(file_path)
        raise RuntimeError(f"Real Windows printing failed. Target printer '{printer_name}' is offline or win32 print API is unavailable.")

    def cleanup(self, file_path: str):
        """Removes local temp file."""
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
        except Exception:
            pass

print_engine = PrintEngine()
