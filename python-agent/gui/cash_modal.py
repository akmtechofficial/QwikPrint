from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame, QGraphicsDropShadowEffect
)
from PyQt6.QtCore import Qt, QPropertyAnimation, QEasingCurve, QUrl
from PyQt6.QtGui import QColor, QFont, QDesktopServices
from audio_service import audio_service
from api_client import api_client
import webbrowser

class CashApprovalDialog(QDialog):
    def __init__(self, job: dict, parent=None):
        super().__init__(parent)
        self.job = job
        self.job_id = job.get("jobId", "UNKNOWN")

        self.setWindowTitle("PrintSoft - Cash Payment Approval Required")
        self.setFixedWidth(540)
        self.setWindowFlags(
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Window |
            Qt.WindowType.WindowCloseButtonHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)

        self.setStyleSheet("""
            QDialog {
                background-color: #0f172a;
                color: #ffffff;
                border-radius: 12px;
            }
            QLabel {
                color: #ffffff;
                background: transparent;
                font-family: 'Segoe UI', sans-serif;
            }
            QFrame#header_frame {
                background: #1e293b;
                border-radius: 10px;
                border: 1px solid #334155;
                padding: 4px;
            }
            QFrame#details_frame {
                background: #1e293b;
                border-radius: 10px;
                border: 1px solid #334155;
            }
            QPushButton#reject_btn {
                background-color: #ef4444;
                color: white;
                font-size: 14px;
                font-weight: bold;
                border: none;
                border-radius: 8px;
                padding: 14px 20px;
            }
            QPushButton#reject_btn:hover {
                background-color: #dc2626;
            }
            QPushButton#approve_btn {
                background-color: #22c55e;
                color: white;
                font-size: 14px;
                font-weight: bold;
                border: none;
                border-radius: 8px;
                padding: 14px 20px;
            }
            QPushButton#approve_btn:hover {
                background-color: #16a34a;
            }
            QPushButton#view_btn {
                background-color: #6366f1;
                color: white;
                font-size: 11px;
                font-weight: bold;
                border: none;
                border-radius: 5px;
                padding: 5px 12px;
            }
            QPushButton#view_btn:hover {
                background-color: #4f46e5;
            }
        """)

        self.init_ui()
        try:
            audio_service.play_cash_chime()
        except Exception:
            pass

    def init_ui(self):
        file_name = self.job.get("file", {}).get("originalName", "Document.pdf")
        copies = self.job.get("printOptions", {}).get("copies", 1)
        pages = self.job.get("file", {}).get("pageCount", 1)
        amount = self.job.get("pricing", {}).get("totalCost", 0)
        color_mode = self.job.get("printOptions", {}).get("colorMode", "bw")
        page_range = self.job.get("printOptions", {}).get("pageRange", "A4")
        paper_size = page_range.split(" / ")[0] if " / " in page_range else "A4"
        color_str = "Black & White" if color_mode == "bw" else "Color"
        short_job_id = self.job_id[-10:] if len(self.job_id) > 10 else self.job_id

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(10)

        # ---- HEADER BANNER ----
        header_frame = QFrame()
        header_frame.setObjectName("header_frame")
        header_frame.setFixedHeight(52)
        h_lay = QHBoxLayout(header_frame)
        h_lay.setContentsMargins(14, 8, 14, 8)

        dot = QLabel("●")
        dot.setStyleSheet("color: #f59e0b; font-size: 16px; font-weight: bold;")

        title = QLabel("  NEW CASH PRINT JOB — APPROVAL REQUIRED")
        title.setStyleSheet("color: #f59e0b; font-size: 13px; font-weight: bold; letter-spacing: 1px;")

        h_lay.addWidget(dot)
        h_lay.addWidget(title)
        h_lay.addStretch()
        main_layout.addWidget(header_frame)

        # ---- DETAILS CARD ----
        details_frame = QFrame()
        details_frame.setObjectName("details_frame")
        d_lay = QVBoxLayout(details_frame)
        d_lay.setContentsMargins(16, 14, 16, 14)
        d_lay.setSpacing(10)

        def make_row(label: str, value: str, value_bold=True, value_color="#ffffff", show_view_btn=False):
            row = QHBoxLayout()
            lbl = QLabel(label)
            lbl.setStyleSheet("color: #94a3b8; font-size: 12px;")
            lbl.setFixedWidth(110)

            val = QLabel(value)
            val.setStyleSheet(f"color: {value_color}; font-size: 12px; font-weight: {'bold' if value_bold else 'normal'};")
            val.setWordWrap(True)

            row.addWidget(lbl)
            row.addWidget(val, 1)

            if show_view_btn:
                view_btn = QPushButton("👁 Download & View")
                view_btn.setObjectName("view_btn")
                view_btn.setFixedHeight(26)
                view_btn.setCursor(Qt.CursorShape.PointingHandCursor)
                view_btn.clicked.connect(self.open_download_view)
                row.addWidget(view_btn)

            return row

        d_lay.addLayout(make_row("Job Ticket ID", short_job_id, value_color="#f8fafc"))
        d_lay.addLayout(make_row(
            "Document Name",
            (file_name[:28] + "...") if len(file_name) > 31 else file_name,
            show_view_btn=True
        ))
        d_lay.addLayout(make_row("Pages & Copies", f"{pages} Page(s) × {copies} Copy(ies)"))
        d_lay.addLayout(make_row("Print Specs", f"{paper_size} • {color_str}"))

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("background: #334155; margin: 4px 0;")
        sep.setFixedHeight(1)
        d_lay.addWidget(sep)

        # Cash to collect row
        cash_row = QHBoxLayout()
        cash_lbl = QLabel("CASH TO COLLECT")
        cash_lbl.setStyleSheet("color: #ffffff; font-size: 13px; font-weight: bold;")
        amount_lbl = QLabel(f"₹{int(amount) if amount == int(amount) else f'{amount:.2f}'}")
        amount_lbl.setStyleSheet("color: #22c55e; font-size: 22px; font-weight: bold;")
        cash_row.addWidget(cash_lbl)
        cash_row.addStretch()
        cash_row.addWidget(amount_lbl)
        d_lay.addLayout(cash_row)

        main_layout.addWidget(details_frame)

        # ---- ACTION BUTTONS ----
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)

        reject_btn = QPushButton("✕  REJECT")
        reject_btn.setObjectName("reject_btn")
        reject_btn.setMinimumHeight(46)
        reject_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        reject_btn.clicked.connect(self.reject_cash)

        approve_btn = QPushButton(f"✔  APPROVE CASH")
        approve_btn.setObjectName("approve_btn")
        approve_btn.setMinimumHeight(46)
        approve_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        approve_btn.clicked.connect(self.approve_cash)

        btn_layout.addWidget(reject_btn)
        btn_layout.addWidget(approve_btn)
        main_layout.addLayout(btn_layout)

    def open_download_view(self):
        from config_manager import config_mgr
        server_url = config_mgr.get("server_url", "http://localhost:8000")
        url = f"{server_url}/api/agent/download-file/{self.job_id}"
        QDesktopServices.openUrl(QUrl(url))

    def reject_cash(self):
        sender = self.sender()
        if sender and isinstance(sender, QPushButton):
            sender.setEnabled(False)
            sender.setText("⏳ Rejecting...")
            from PyQt6.QtWidgets import QApplication
            QApplication.processEvents()

        try:
            api_client.reject_cash_payment(self.job_id)
            self.reject()
        finally:
            if sender and isinstance(sender, QPushButton):
                sender.setEnabled(True)
                sender.setText("✕  REJECT")

    def approve_cash(self):
        sender = self.sender()
        if sender and isinstance(sender, QPushButton):
            sender.setEnabled(False)
            sender.setText("⏳ Approving...")
            from PyQt6.QtWidgets import QApplication
            QApplication.processEvents()

        try:
            success, msg = api_client.confirm_cash_payment(self.job_id)
            if success:
                self.accept()
            else:
                print(f"[Cash Approval Error] {msg}")
                self.accept()
        finally:
            if sender and isinstance(sender, QPushButton):
                sender.setEnabled(True)
                sender.setText("✔  APPROVE CASH")
