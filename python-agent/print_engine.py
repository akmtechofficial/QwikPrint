import os
import tempfile
import requests
import subprocess
import time
from config_manager import config_mgr
from printer_service import HAS_WIN32, printer_service

if HAS_WIN32:
    import win32api

# Paper size in points (1 inch = 72 pt)
PAPER_SIZES_PT = {
    "A4":     (595, 842),
    "A3":     (842, 1191),
    "LETTER": (612, 792),
    "LEGAL":  (612, 1008),
}


class PrintEngine:
    def __init__(self):
        self.temp_dir = os.path.join(tempfile.gettempdir(), "PrintSoftAgent")
        os.makedirs(self.temp_dir, exist_ok=True)
        self.sumatra_path = self._find_sumatra()

    # ──────────────────────────────────────────────────────────
    #  Internal Helpers
    # ──────────────────────────────────────────────────────────

    def _find_sumatra(self) -> str:
        """Finds SumatraPDF executable if available."""
        local_bin = os.path.join(os.path.dirname(__file__), "bin", "SumatraPDF.exe")
        if os.path.exists(local_bin):
            return local_bin
        system_paths = [
            r"C:\Program Files\SumatraPDF\SumatraPDF.exe",
            r"C:\Program Files (x86)\SumatraPDF\SumatraPDF.exe",
        ]
        for path in system_paths:
            if os.path.exists(path):
                return path
        return ""

    def cleanup(self, *paths):
        """Removes one or more local temp files silently on successful print."""
        for p in paths:
            try:
                if p and os.path.exists(p):
                    os.remove(p)
            except Exception:
                pass

    # ──────────────────────────────────────────────────────────
    #  File Download
    # ──────────────────────────────────────────────────────────

    def download_file(self, download_url: str, job_id: str, original_filename: str) -> str:
        """Downloads a document file to a local temp path and returns the path."""
        ext = os.path.splitext(original_filename)[1] or ".pdf"
        local_filename = f"job_{job_id[-8:]}_{int(time.time())}{ext}"
        local_path = os.path.join(self.temp_dir, local_filename)

        if not download_url.startswith("http"):
            # If the download_url IS a local filesystem path, copy it instead
            if os.path.exists(download_url):
                import shutil
                shutil.copy2(download_url, local_path)
                return local_path
            raise RuntimeError(f"Invalid download URL or file path: {download_url}")

        res = requests.get(download_url, timeout=30, stream=True)
        if res.status_code == 200:
            with open(local_path, "wb") as f:
                for chunk in res.iter_content(chunk_size=8192):
                    f.write(chunk)
            return local_path
        else:
            raise RuntimeError(f"File download failed with HTTP status {res.status_code}")

    # ──────────────────────────────────────────────────────────
    #  Image → PDF Conversion  (for rendered canvas PNG files)
    # ──────────────────────────────────────────────────────────

    def image_to_pdf(self, image_path: str, paper_size_key: str = "A4",
                     orientation: str = "portrait") -> str:
        """
        Converts a PNG/JPG image to a properly sized single-page PDF
        at 150 DPI so SumatraPDF can silently print it.
        """
        try:
            from PIL import Image

            img = Image.open(image_path).convert("RGB")
            pw, ph = PAPER_SIZES_PT.get(paper_size_key.upper(), PAPER_SIZES_PT["A4"])

            img_w, img_h = img.size
            # Auto-detect landscape from image ratio or explicit orientation
            if orientation == "landscape" or (img_w > img_h and pw < ph):
                pw, ph = ph, pw  # swap to landscape

            dpi = 150
            page_w_px = int(pw / 72 * dpi)
            page_h_px = int(ph / 72 * dpi)

            # Leave a small margin (0.15 inch)
            margin = int(dpi * 0.15)
            avail_w = page_w_px - 2 * margin
            avail_h = page_h_px - 2 * margin

            scale = min(avail_w / img_w, avail_h / img_h)
            new_w = max(1, int(img_w * scale))
            new_h = max(1, int(img_h * scale))
            img = img.resize((new_w, new_h), Image.LANCZOS)

            page = Image.new("RGB", (page_w_px, page_h_px), "white")
            x_off = (page_w_px - new_w) // 2
            y_off = (page_h_px - new_h) // 2
            page.paste(img, (x_off, y_off))

            pdf_path = image_path.rsplit(".", 1)[0] + "_print.pdf"
            page.save(pdf_path, "PDF", resolution=dpi)
            print(f"[PrintEngine] Image→PDF: {pdf_path}")
            return pdf_path

        except ImportError:
            raise RuntimeError(
                "Pillow not installed. Please run: pip install Pillow"
            )
        except Exception as e:
            raise RuntimeError(f"Image→PDF conversion failed: {e}")

    # ──────────────────────────────────────────────────────────
    #  Main Print Entry Point
    # ──────────────────────────────────────────────────────────

    def print_file(self, file_path: str, printer_name: str, options: dict) -> bool:
        """
        Spools a file (PDF or image) to the target printer.
        Images are auto-converted to PDF via Pillow before printing.
        """
        if not printer_name:
            raise RuntimeError("No usable printer detected. Please configure a valid printer.")

        allow_virtual = config_mgr.get("allow_virtual_printers", True)
        if printer_service.is_virtual_printer(printer_name) and not allow_virtual:
            raise RuntimeError(f"Cannot print to virtual printer '{printer_name}'. Please connect a physical hardware printer or enable Virtual Printers in settings.")

        if not printer_service.validate_printer_exists(printer_name):
            raise RuntimeError(f"Target printer '{printer_name}' is not installed or available on this system.")

        copies     = int(options.get("copies", 1))
        color_mode = options.get("colorMode", "bw")   # "color" | "bw"
        duplex     = options.get("duplex", "single")   # "single" | "double_long" | "double_short"
        page_range = options.get("pageRange", "")      # "A4 / 4in1" style or numeric range

        print(
            f"[PrintEngine] '{os.path.basename(file_path)}' → '{printer_name}' "
            f"| copies={copies} mode={color_mode} duplex={duplex}"
        )

        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Local print file not found: {file_path}")

        # Parse paper size and orientation from page_range metadata
        paper_size_key = "A4"
        orientation = "portrait"
        if page_range and "/" in page_range:
            parts = [p.strip() for p in page_range.split("/")]
            paper_size_key = parts[0].upper() if parts[0] else "A4"
        if "landscape" in page_range.lower():
            orientation = "landscape"

        # Auto-convert image files → PDF before printing
        original_image_path = None
        img_exts = (".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp", ".tiff")
        if file_path.lower().endswith(img_exts):
            print("[PrintEngine] Image file detected — converting to PDF…")
            original_image_path = file_path
            try:
                file_path = self.image_to_pdf(file_path, paper_size_key, orientation)
            except Exception as conv_err:
                raise RuntimeError(f"Cannot print image: {conv_err}")

        try:
            # ── Method 1: SumatraPDF (silent, best quality) ──
            if self.sumatra_path and file_path.lower().endswith(".pdf"):
                settings_parts = [f"{copies}x"]

                if color_mode == "bw":
                    settings_parts.append("monochrome")
                else:
                    settings_parts.append("color")

                if duplex in ("double_long", "duplex", "double"):
                    settings_parts.append("duplexlong")
                elif duplex == "double_short":
                    settings_parts.append("duplexshort")
                else:
                    settings_parts.append("simplex")

                settings_str = ",".join(settings_parts)
                cmd = [
                    self.sumatra_path,
                    "-print-to", printer_name,
                    "-print-settings", settings_str,
                    "-silent",
                    file_path,
                ]
                print(f"[PrintEngine] SumatraPDF command: {' '.join(cmd)}")
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=90)

                if result.returncode == 0:
                    print(f"[PrintEngine Success] SumatraPDF printed '{os.path.basename(file_path)}' to '{printer_name}'")
                    self.cleanup(file_path, original_image_path)
                    return True
                else:
                    print(
                        f"[PrintEngine Warning] SumatraPDF exit={result.returncode}: {result.stderr.strip()}"
                    )
                    # Fall through to Win32 ShellExecute / win32print

            # ── Method 2: Win32 printing path with verification ──
            if HAS_WIN32:
                import win32api
                import win32print

                # Verify printer is accessible
                try:
                    h_printer = win32print.OpenPrinter(printer_name)
                    win32print.ClosePrinter(h_printer)
                except Exception as open_err:
                    raise RuntimeError(f"Cannot open printer '{printer_name}': {open_err}")

                try:
                    for _ in range(copies):
                        res_code = win32api.ShellExecute(0, "printto", file_path, f'"{printer_name}"', ".", 0)
                        if isinstance(res_code, int) and res_code <= 32:
                            raise RuntimeError(f"ShellExecute failed with OS error code {res_code}")
                        time.sleep(1.5)

                    print(f"[PrintEngine Success] Document spooled to '{printer_name}' via Windows Shell")
                    self.cleanup(file_path, original_image_path)
                    return True
                except Exception as e:
                    raise RuntimeError(f"Windows print spooling failed for '{printer_name}': {e}")

            # ── No method available ──
            raise RuntimeError("No valid print method available. Install SumatraPDF or pywin32.")

        except Exception as err:
            # Preserve local file on failure for diagnostics/retry
            print(f"[PrintEngine Diagnostic] Print failed for file '{file_path}': {err}")
            print(f"[PrintEngine Diagnostic] Preserved local file for diagnostics: {file_path}")
            raise


print_engine = PrintEngine()

