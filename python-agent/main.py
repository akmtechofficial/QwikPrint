import sys
import os
import time
from PyQt6.QtWidgets import QApplication, QSystemTrayIcon, QMenu, QMessageBox
from PyQt6.QtGui import QIcon, QAction, QPixmap, QPainter, QColor
from PyQt6.QtCore import QThread, pyqtSignal, QObject, Qt
from PyQt6.QtNetwork import QLocalServer, QLocalSocket

from config_manager import config_mgr
from api_client import api_client
from printer_service import printer_service
from print_engine import print_engine
from gui.main_window import MainWindow
from gui.setup_dialog import SetupDialog
from gui.cash_modal import CashApprovalDialog

# -------------------------------------------------------------
# Background Polling Worker Thread
# -------------------------------------------------------------
class AgentWorker(QObject):
    connection_changed = pyqtSignal(bool)
    queue_updated = pyqtSignal(list)
    cash_approval_requested = pyqtSignal(dict)
    job_processed = pyqtSignal(dict, bool, str)

    def __init__(self):
        super().__init__()
        self._running = True
        self.is_active = True
        self.last_heartbeat = 0
        self.active_cash_jobs = set()

    def set_active(self, state: bool):
        self.is_active = state

    def stop(self):
        self._running = False

    def run(self):
        print("[AgentWorker] Background polling daemon started.")
        while self._running:
            try:
                if not self.is_active:
                    time.sleep(1)
                    continue

                now = time.time()
                # 1. Send Heartbeat every 20s
                if now - self.last_heartbeat > 20:
                    printer_name = config_mgr.get("selected_printer") or printer_service.get_default_printer()
                    p_status = printer_service.get_printer_status(printer_name)
                    is_online = api_client.send_heartbeat(p_status)
                    self.connection_changed.emit(is_online)
                    self.last_heartbeat = now

                # 2. Fetch Queue & Cash Pending Jobs
                if config_mgr.is_configured():
                    queued_jobs, cash_pending_jobs = api_client.fetch_queue()
                    self.queue_updated.emit(queued_jobs + cash_pending_jobs)

                    # Trigger Cash Approval Popup for new cash pending jobs
                    for cash_job in cash_pending_jobs:
                        job_id = cash_job.get("jobId")
                        if job_id and job_id not in self.active_cash_jobs:
                            self.active_cash_jobs.add(job_id)
                            self.cash_approval_requested.emit(cash_job)

                    # Auto-Print Queued Jobs if enabled
                    if config_mgr.get("auto_print", True):
                        for job in queued_jobs:
                            self.process_job(job)

            except Exception as e:
                print(f"[AgentWorker Error] {e}")
                self.connection_changed.emit(False)

            time.sleep(3)

    def process_job(self, job: dict):
        job_id = job.get("jobId")
        file_meta = job.get("file", {})
        filename = file_meta.get("originalName", "document.pdf")
        options = job.get("printOptions", {})
        printer_name = config_mgr.get("selected_printer") or printer_service.get_default_printer()

        print(f"[AgentWorker] Processing job #{job_id[-6:]} ({filename})...")

        # Step A: Claim Job
        claimed, claimed_job = api_client.claim_job(job_id)
        if not claimed:
            print(f"[AgentWorker] Job {job_id} could not be claimed.")
            return

        # Step B: Mark DOWNLOADING
        api_client.update_status(job_id, "DOWNLOADING")

        # Step C: Get Presigned Download URL
        download_url = api_client.get_download_url(job_id)
        if not download_url:
            api_client.update_status(job_id, "DOWNLOAD_FAILED", "Could not get download URL")
            self.job_processed.emit(job, False, "Failed to get download URL")
            return

        # Step D: Download File
        try:
            local_path = print_engine.download_file(download_url, job_id, filename)
        except Exception as dl_err:
            api_client.update_status(job_id, "DOWNLOAD_FAILED", str(dl_err))
            self.job_processed.emit(job, False, f"Download failed: {dl_err}")
            return

        # Step E: Mark PRINTING
        api_client.update_status(job_id, "PRINTING")

        # Step F: Print File
        try:
            success = print_engine.print_file(local_path, printer_name, options)
            if success:
                api_client.update_status(job_id, "PRINTED")
                self.job_processed.emit(job, True, "Successfully printed!")
            else:
                api_client.update_status(job_id, "PRINT_FAILED", "Print spooler failed")
                self.job_processed.emit(job, False, "Print spooler failed")
        except Exception as p_err:
            api_client.update_status(job_id, "PRINT_FAILED", str(p_err))
            self.job_processed.emit(job, False, str(p_err))

# -------------------------------------------------------------
# System Tray Icon Generator
# -------------------------------------------------------------
def create_tray_icon() -> QIcon:
    """Generates a sleek 32x32 QIcon dynamically."""
    pixmap = QPixmap(32, 32)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setBrush(QColor("#3b82f6"))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawRoundedRect(2, 2, 28, 28, 6, 6)
    painter.setBrush(QColor("#ffffff"))
    painter.drawRect(8, 8, 16, 12)
    painter.drawRect(6, 20, 20, 6)
    painter.end()
    return QIcon(pixmap)

# -------------------------------------------------------------
# Main Application Launcher
# -------------------------------------------------------------
def main():
    app = QApplication(sys.argv)
    app.setApplicationName("PrintSoftAgent")
    app.setQuitOnLastWindowClosed(False)

    # Single Instance Lock
    server_name = "PrintSoftAgentSingleInstanceLock"
    socket = QLocalSocket()
    socket.connectToServer(server_name)
    if socket.waitForConnected(500):
        QMessageBox.information(None, "Already Running", "PrintSoft Agent is already running in your System Tray.")
        sys.exit(0)

    server = QLocalServer()
    server.listen(server_name)

    # Main Window
    main_window = MainWindow()

    # Mandatory Setup Check on First Launch
    while not config_mgr.is_configured():
        setup_dlg = SetupDialog()
        res = setup_dlg.exec()
        if not res or not config_mgr.is_configured():
            msg_box = QMessageBox.warning(
                None,
                "API Key Required",
                "QwikPrint Software requires a valid API Key from your Web Dashboard to pair and run.\n\nWould you like to enter your API Key now?",
                QMessageBox.StandardButton.Retry | QMessageBox.StandardButton.Close
            )
            if msg_box == QMessageBox.StandardButton.Close:
                sys.exit(0)

    main_window.show()

    # Background Worker Thread
    worker_thread = QThread()
    worker = AgentWorker()
    worker.moveToThread(worker_thread)

    worker_thread.started.connect(worker.run)
    worker.connection_changed.connect(main_window.update_connection_status)
    worker.queue_updated.connect(main_window.update_queue_table)
    main_window.agent_toggle_requested.connect(worker.set_active)

    def handle_cash_approval(cash_job):
        dlg = CashApprovalDialog(cash_job, main_window)
        dlg.exec()

    def handle_job_processed(job, success, msg):
        pages = job.get("file", {}).get("pageCount", 1) * job.get("printOptions", {}).get("copies", 1)
        if success:
            main_window.update_stats(1, pages)
            tray.showMessage("Job Printed ✅", f"Successfully printed '{job.get('file', {}).get('originalName')}'", QSystemTrayIcon.MessageIcon.Information, 3000)
        else:
            tray.showMessage("Print Failed ❌", f"Error: {msg}", QSystemTrayIcon.MessageIcon.Warning, 4000)

    worker.cash_approval_requested.connect(handle_cash_approval)
    worker.job_processed.connect(handle_job_processed)

    worker_thread.start()

    # System Tray
    tray = QSystemTrayIcon(create_tray_icon(), app)
    tray.setToolTip("PrintSoft Windows Agent - Active")

    menu = QMenu()
    open_action = QAction("Open Dashboard", app)
    open_action.triggered.connect(lambda: (main_window.show(), main_window.activateWindow()))
    menu.addAction(open_action)

    setup_action = QAction("Setup / Pair Device", app)
    setup_action.triggered.connect(main_window.open_setup)
    menu.addAction(setup_action)

    menu.addSeparator()

    quit_action = QAction("Exit PrintSoft Agent", app)
    def on_quit():
        worker.stop()
        worker_thread.quit()
        worker_thread.wait()
        app.quit()
    quit_action.triggered.connect(on_quit)
    menu.addAction(quit_action)

    tray.setContextMenu(menu)
    tray.show()

    sys.exit(app.exec())

if __name__ == "__main__":
    main()
