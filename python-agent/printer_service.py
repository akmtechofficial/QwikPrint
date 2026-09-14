import sys
from config_manager import config_mgr

HAS_WIN32 = False
if sys.platform == "win32":
    try:
        import win32print
        import win32api
        HAS_WIN32 = True
    except ImportError:
        HAS_WIN32 = False

# Known virtual / software printer keywords
VIRTUAL_PRINTER_KEYWORDS = [
    "fax",
    "pdf",
    "xps",
    "onenote",
    "virtual",
    "writer",
    "document writer",
    "root print queue",
    "send to",
    "cutepdf",
    "bullzip",
    "pdf24",
    "dopdf",
    "primopdf",
    "microsoft print to pdf",
    "microsoft xps document writer",
]

class PrinterService:
    def __init__(self):
        pass

    def is_virtual_printer(self, printer_name: str) -> bool:
        """Returns True if the printer is a virtual/software printer."""
        if not printer_name:
            return True
        p_lower = printer_name.lower().strip()
        return any(kw in p_lower for kw in VIRTUAL_PRINTER_KEYWORDS)

    def get_installed_printers(self) -> list[str]:
        """Lists all installed Windows printers."""
        if not HAS_WIN32:
            return []
        try:
            flags = win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS
            printers = win32print.EnumPrinters(flags)
            return [p[2] for p in printers if p and len(p) >= 3 and p[2]]
        except Exception as e:
            print(f"[PrinterService Error] EnumPrinters failed: {e}")
            return []

    def get_default_printer(self) -> str:
        """Gets system default printer name."""
        if not HAS_WIN32:
            return ""
        try:
            def_p = win32print.GetDefaultPrinter()
            return def_p if def_p else ""
        except Exception as e:
            print(f"[PrinterService Error] GetDefaultPrinter failed: {e}")
            return ""

    def get_printer_status(self, printer_name: str) -> str:
        """Checks printer status: ready, offline, paper_jam, paper_out, error, busy, or not_found."""
        if not HAS_WIN32 or not printer_name:
            return "ready" if not HAS_WIN32 else "not_found"
        
        installed = self.get_installed_printers()
        if printer_name not in installed:
            return "not_found"

        try:
            handle = win32print.OpenPrinter(printer_name)
            try:
                info = win32print.GetPrinter(handle, 2)
                status = info.get("Status", 0)
                if status == 0:
                    return "ready"
                elif status & win32print.PRINTER_STATUS_PAPER_JAM:
                    return "paper_jam"
                elif status & win32print.PRINTER_STATUS_PAPER_OUT:
                    return "paper_out"
                elif status & win32print.PRINTER_STATUS_ERROR:
                    return "error"
                elif status & win32print.PRINTER_STATUS_OFFLINE:
                    return "offline"
                return "busy"
            finally:
                win32print.ClosePrinter(handle)
        except Exception as e:
            print(f"[PrinterService Debug] Could not open printer '{printer_name}': {e}")
            return "offline"

    def get_printer_capabilities(self, printer_name: str) -> dict:
        """Detects color and duplex capabilities dynamically using win32print API."""
        caps = {"color": False, "duplex": False}
        if not HAS_WIN32 or not printer_name or self.is_virtual_printer(printer_name):
            return caps
        
        try:
            # DC_COLORDEVICE = 32
            color_res = win32print.DeviceCapabilities(printer_name, "", 32, None)
            caps["color"] = bool(color_res > 0)
        except Exception:
            caps["color"] = False

        try:
            # DC_DUPLEX = 7
            duplex_res = win32print.DeviceCapabilities(printer_name, "", 7, None)
            caps["duplex"] = bool(duplex_res > 0)
        except Exception:
            caps["duplex"] = False

        return caps

    def get_physical_printers(self) -> list[str]:
        """Returns list of installed non-virtual physical printers."""
        installed = self.get_installed_printers()
        return [p for p in installed if not self.is_virtual_printer(p)]

    def validate_printer_exists(self, printer_name: str) -> bool:
        """Validates if the given printer exists in installed printers."""
        if not printer_name:
            return False
        return printer_name in self.get_installed_printers()

    def select_best_printer(self, color_mode: str = "bw", paper_size: str = "A4", override_printer: str = "") -> str:
        """
        Robust printer discovery & selection logic.
        Diagnostic logging prints all printers, status, and usability.
        """
        installed = self.get_installed_printers()
        print(f"\n[PrinterService Diagnostics] Scanning installed printers ({len(installed)} total)...")
        
        printer_diagnostics = []
        physical_printers = []
        
        for p in installed:
            is_virt = self.is_virtual_printer(p)
            status = self.get_printer_status(p)
            caps = self.get_printer_capabilities(p) if not is_virt else {"color": False, "duplex": False}
            usable = (not is_virt) and (status in ["ready", "busy"])
            
            diag_entry = {
                "name": p,
                "virtual": is_virt,
                "status": status,
                "usable": usable,
                "color_support": caps["color"],
                "duplex_support": caps["duplex"]
            }
            printer_diagnostics.append(diag_entry)
            print(f"  • Printer: '{p}' | Virtual: {is_virt} | Status: {status} | Usable: {usable} | Caps: {caps}")

            if usable:
                physical_printers.append(diag_entry)

        # Requirement 3: User explicit selection override
        allow_virtual = config_mgr.get("allow_virtual_printers", True)
        if override_printer:
            if self.validate_printer_exists(override_printer):
                is_virt = self.is_virtual_printer(override_printer)
                st = self.get_printer_status(override_printer)
                if is_virt and not allow_virtual:
                    print(f"[PrinterService Warning] Selected override printer '{override_printer}' is a virtual printer but allow_virtual_printers is disabled!")
                else:
                    print(f"[PrinterService] Using explicit user override printer: '{override_printer}' (Virtual={is_virt}, Status={st})")
                    return override_printer
            else:
                print(f"[PrinterService Warning] Selected override printer '{override_printer}' is not installed!")

        # Requirement 1 & 2: Prefer actual installed physical printer online/ready
        default_p = self.get_default_printer()
        if default_p and not self.is_virtual_printer(default_p) and self.get_printer_status(default_p) in ["ready", "busy"]:
            if color_mode.lower() == "color":
                for entry in physical_printers:
                    if entry["color_support"]:
                        print(f"[PrinterService] Selected physical color printer: '{entry['name']}'")
                        return entry["name"]
            print(f"[PrinterService] Selected ready physical default printer: '{default_p}'")
            return default_p

        # Search physical printers
        if physical_printers:
            if color_mode.lower() == "color":
                for entry in physical_printers:
                    if entry["color_support"]:
                        print(f"[PrinterService] Selected physical color printer: '{entry['name']}'")
                        return entry["name"]
            
            best_physical = physical_printers[0]["name"]
            print(f"[PrinterService] Selected physical printer: '{best_physical}'")
            return best_physical

        # Fallback for virtual printer testing/demo mode
        if allow_virtual and installed:
            non_fax = [p for p in installed if "fax" not in p.lower()]
            selected_virt = non_fax[0] if non_fax else installed[0]
            print(f"[PrinterService Testing Mode] Virtual printers enabled — selected '{selected_virt}'")
            return selected_virt

        # Requirement 4: No physical/usable printer exists
        print("[PrinterService Error] No usable physical printer detected!")
        return ""

printer_service = PrinterService()

