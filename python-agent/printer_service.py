import sys

HAS_WIN32 = False
if sys.platform == "win32":
    try:
        import win32print
        import win32api
        HAS_WIN32 = True
    except ImportError:
        HAS_WIN32 = False

class PrinterService:
    def __init__(self):
        pass

    def get_installed_printers(self) -> list[str]:
        """Lists all installed Windows printers."""
        if not HAS_WIN32:
            return ["Virtual PDF Printer (Simulated)"]
        try:
            flags = win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS
            printers = win32print.EnumPrinters(flags)
            return [p[2] for p in printers]
        except Exception as e:
            print(f"[PrinterService Error] EnumPrinters failed: {e}")
            return ["Default Printer"]

    def get_default_printer(self) -> str:
        """Gets system default printer."""
        if not HAS_WIN32:
            return "Virtual PDF Printer (Simulated)"
        try:
            return win32print.GetDefaultPrinter()
        except Exception as e:
            print(f"[PrinterService Error] GetDefaultPrinter failed: {e}")
            printers = self.get_installed_printers()
            return printers[0] if printers else ""

    def get_printer_status(self, printer_name: str) -> str:
        """Checks printer status."""
        if not HAS_WIN32 or not printer_name:
            return "ready"
        try:
            handle = win32print.OpenPrinter(printer_name)
            info = win32print.GetPrinter(handle, 2)
            win32print.ClosePrinter(handle)
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
        except Exception:
            return "ready"

printer_service = PrinterService()
