from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
    QPushButton, QMessageBox, QFrame, QComboBox
)
from PyQt6.QtCore import Qt
from config_manager import config_mgr
from api_client import api_client
from printer_service import printer_service

class SetupDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("QwikPrint Agent - 1-Click API Key Pairing")
        self.setFixedSize(520, 480)
        self.setModal(True)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)

        # Header Frame
        header_frame = QFrame()
        header_frame.setProperty("class", "card")
        h_layout = QVBoxLayout(header_frame)
        
        title_lbl = QLabel("🔑 Pair Desktop Software via API Key")
        title_lbl.setProperty("class", "title")
        subtitle_lbl = QLabel("Copy the Secret API Key from your Web Dashboard and paste it below.")
        subtitle_lbl.setProperty("class", "subtitle")
        subtitle_lbl.setWordWrap(True)

        h_layout.addWidget(title_lbl)
        h_layout.addWidget(subtitle_lbl)
        layout.addWidget(header_frame)

        # Form Fields
        form_frame = QFrame()
        form_frame.setProperty("class", "card")
        f_layout = QVBoxLayout(form_frame)
        f_layout.setSpacing(14)

        # Server URL
        f_layout.addWidget(QLabel("Server Endpoint URL:"))
        self.url_input = QLineEdit(config_mgr.get("server_url", "http://localhost:8000"))
        f_layout.addWidget(self.url_input)

        # 1-Click Secret API Key (Pasted from Dashboard)
        f_layout.addWidget(QLabel("Secret API Key (From Web Dashboard):"))
        self.api_key_input = QLineEdit(config_mgr.get("api_key", ""))
        self.api_key_input.setPlaceholderText("Paste your Secret API Key here")
        f_layout.addWidget(self.api_key_input)

        # Target Printer Select
        f_layout.addWidget(QLabel("Target Windows Hardware Printer:"))
        self.printer_combo = QComboBox()
        printers = printer_service.get_installed_printers()
        self.printer_combo.addItems(printers)
        default_p = config_mgr.get("selected_printer") or printer_service.get_default_printer()
        if default_p in printers:
            self.printer_combo.setCurrentText(default_p)
        f_layout.addWidget(self.printer_combo)

        layout.addWidget(form_frame)
        layout.addStretch()

        # Action Buttons
        btn_layout = QHBoxLayout()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)

        save_btn = QPushButton("🔗 Connect & Pair Software")
        save_btn.setProperty("class", "success")
        save_btn.clicked.connect(self.save_and_pair)

        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(save_btn)
        layout.addLayout(btn_layout)

    def save_and_pair(self):
        server_url = self.url_input.text().strip()
        api_key = self.api_key_input.text().strip()
        selected_printer = self.printer_combo.currentText()

        if not server_url or not api_key:
            QMessageBox.warning(self, "Missing API Key", "Please paste your Secret API Key from your Web Dashboard.")
            return

        # Call verify_api_key endpoint
        success, msg, data = api_client.verify_api_key(server_url, api_key)
        
        if success:
            config_mgr.save_config({
                "server_url": server_url,
                "api_key": api_key,
                "shop_id": data.get("shopId"),
                "shop_name": data.get("shopName"),
                "device_id": data.get("deviceId"),
                "device_token": data.get("deviceToken"),
                "bw_rate": data.get("bwRate", 2.0),
                "color_rate": data.get("colorRate", 10.0),
                "duplex_discount": data.get("duplexDiscount", 0.5),
                "device_name": "Windows Desktop PC",
                "selected_printer": selected_printer
            })

            QMessageBox.information(self, "Paired Successfully 🎉", 
                                    f"{msg}\n\n"
                                    f"Store: {data.get('shopName')}\n"
                                    f"Shop ID: {data.get('shopId')}\n"
                                    f"Selected Printer: {selected_printer}\n"
                                    f"License: 1 API Key = 1 PC Bound")
            self.accept()
        else:
            QMessageBox.critical(self, "Pairing Error ❌", f"{msg}\n\nPlease verify your API Key in your Web Dashboard.")
