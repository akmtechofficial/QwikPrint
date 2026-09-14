from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame
)
from PyQt6.QtCore import Qt
from audio_service import audio_service
from api_client import api_client

class CashApprovalDialog(QDialog):
    def __init__(self, job: dict, parent=None):
        super().__init__(parent)
        self.job = job
        self.job_id = job.get("jobId", "UNKNOWN")
        self.setWindowTitle("💵 Cash Payment Request - PrintSoft")
        self.setFixedSize(450, 360)
        self.setWindowFlags(
            Qt.WindowType.WindowStaysOnTopHint | 
            Qt.WindowType.CustomizeWindowHint | 
            Qt.WindowType.WindowTitleHint
        )
        self.init_ui()
        # Play audio chime
        audio_service.play_cash_chime()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)

        # Header Frame
        header = QFrame()
        header.setProperty("class", "card")
        h_layout = QVBoxLayout(header)

        title = QLabel("💰 CASH PAYMENT CONFIRMATION")
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #f59e0b;")
        
        sub = QLabel(f"Customer is at your counter requesting to pay cash.")
        sub.setProperty("class", "subtitle")

        h_layout.addWidget(title)
        h_layout.addWidget(sub)
        layout.addWidget(header)

        # Details Card
        details = QFrame()
        details.setProperty("class", "card")
        d_layout = QVBoxLayout(details)
        d_layout.setSpacing(8)

        file_name = self.job.get("file", {}).get("originalName", "Document.pdf")
        copies = self.job.get("printOptions", {}).get("copies", 1)
        pages = self.job.get("file", {}).get("pageCount", 1)
        amount = self.job.get("pricing", {}).get("totalCost", 0)

        d_layout.addWidget(QLabel(f"📄 <b>File:</b> {file_name}"))
        d_layout.addWidget(QLabel(f"🖨️ <b>Print Specs:</b> {copies} copy/copies | {pages} page(s)"))
        
        amount_lbl = QLabel(f"💵 Collect Cash: ₹{amount:.2f}")
        amount_lbl.setStyleSheet("font-size: 18px; font-weight: bold; color: #10b981; padding: 4px 0;")
        d_layout.addWidget(amount_lbl)

        layout.addWidget(details)
        layout.addStretch()

        # Action Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)

        decline_btn = QPushButton("Decline")
        decline_btn.setProperty("class", "danger")
        decline_btn.clicked.connect(self.reject)

        approve_btn = QPushButton(f"Approve & Print (Collect ₹{amount:.2f})")
        approve_btn.setProperty("class", "success")
        approve_btn.setMinimumHeight(44)
        approve_btn.clicked.connect(self.approve_cash)

        btn_layout.addWidget(decline_btn)
        btn_layout.addWidget(approve_btn)
        layout.addLayout(btn_layout)

    def approve_cash(self):
        success, msg = api_client.confirm_cash_payment(self.job_id)
        if success:
            self.accept()
        else:
            print(f"[Cash Approval Error] {msg}")
            self.accept()
