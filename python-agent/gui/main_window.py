import os
import time
import io
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QTableWidget, QTableWidgetItem, QHeaderView, 
    QFrame, QComboBox, QCheckBox, QMessageBox, QTabWidget, 
    QTextEdit, QSplitter, QDoubleSpinBox, QScrollArea
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPixmap, QImage
from config_manager import config_mgr
from api_client import api_client
from printer_service import printer_service
from print_engine import print_engine
from gui.setup_dialog import SetupDialog
from gui.styles import LIGHT_THEME_QSS, DARK_THEME_QSS

class MainWindow(QMainWindow):
    agent_toggle_requested = pyqtSignal(bool)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("QwikPrint Agent - XeroBot Edition v4.0.5")
        self.resize(1100, 720)
        
        self.is_dark_theme = False
        self.agent_running = True
        self.processed_count = 0
        self.total_revenue = 0.0

        self.setStyleSheet(LIGHT_THEME_QSS)
        self.init_ui()
        self.generate_qr_code()

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(10)

        # -------------------------------------------------------------
        # 1. TOP HEADER (Active Shop Name & Controls)
        # -------------------------------------------------------------
        header_frame = QFrame()
        header_frame.setProperty("class", "card")
        h_layout = QHBoxLayout(header_frame)
        h_layout.setContentsMargins(10, 6, 10, 6)

        # Shop Name Display (User rule: Active Shop Name in header)
        shop_id = config_mgr.get('shop_id', 'AKM Tech Zone')
        title_box = QVBoxLayout()
        self.shop_title = QLabel(f"🖨️ {shop_id}")
        self.shop_title.setProperty("class", "title")
        sub_title = QLabel("Powered by QwikPrint Agent v4.0.5")
        sub_title.setProperty("class", "subtitle")
        title_box.addWidget(self.shop_title)
        title_box.addWidget(sub_title)
        h_layout.addLayout(title_box)

        h_layout.addStretch()

        # Right status & Theme controls
        self.status_badge = QLabel("🟢 Running")
        self.status_badge.setStyleSheet("color: #16a34a; font-weight: bold; font-size: 13px; margin-right: 10px;")
        h_layout.addWidget(self.status_badge)

        self.light_btn = QPushButton("Light")
        self.light_btn.setProperty("class", "theme-btn")
        self.light_btn.setStyleSheet("background: #dc2626; color: white;")
        self.light_btn.clicked.connect(self.set_light_theme)
        h_layout.addWidget(self.light_btn)

        self.dark_btn = QPushButton("Dark")
        self.dark_btn.clicked.connect(self.set_dark_theme)
        h_layout.addWidget(self.dark_btn)

        lang_combo = QComboBox()
        lang_combo.addItems(["English", "Hindi"])
        h_layout.addWidget(lang_combo)

        setup_btn = QPushButton("⚙️ Settings")
        setup_btn.clicked.connect(self.open_setup)
        h_layout.addWidget(setup_btn)

        main_layout.addWidget(header_frame)

        # -------------------------------------------------------------
        # 2. MAIN TAB WIDGET
        # -------------------------------------------------------------
        self.tabs = QTabWidget()
        
        # Tab 1: Print Queue
        queue_tab = QWidget()
        self.init_queue_tab(queue_tab)
        self.tabs.addTab(queue_tab, "🖨️ Print Queue")

        # Other Tabs (Placeholders matching screenshot)
        self.tabs.addTab(QWidget(), "🏢 Offices")
        self.tabs.addTab(QWidget(), "🪪 Passport Photo")
        self.tabs.addTab(QWidget(), "💳 Aadhaar / PAN")
        self.tabs.addTab(QWidget(), "🏪 Shop")
        
        # Pricing & Rates Tab
        pricing_tab = QWidget()
        self.init_pricing_tab(pricing_tab)
        pricing_scroll = QScrollArea()
        pricing_scroll.setWidgetResizable(True)
        pricing_scroll.setWidget(pricing_tab)
        self.tabs.addTab(pricing_scroll, "💰 Pricing & Rates")
        
        # Printers Tab
        printers_tab = QWidget()
        self.init_printers_tab(printers_tab)
        printers_scroll = QScrollArea()
        printers_scroll.setWidgetResizable(True)
        printers_scroll.setWidget(printers_tab)
        self.tabs.addTab(printers_scroll, "🖨️ Printers")
        
        self.tabs.addTab(QWidget(), "💬 WhatsApp")
        
        main_layout.addWidget(self.tabs)

    def init_queue_tab(self, tab: QWidget):
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # Action Bar
        action_frame = QFrame()
        action_frame.setProperty("class", "card")
        a_layout = QHBoxLayout(action_frame)
        a_layout.setContentsMargins(8, 6, 8, 6)

        self.agent_stop_btn = QPushButton("⏹️ Stop Agent")
        self.agent_stop_btn.setProperty("class", "danger")
        self.agent_stop_btn.clicked.connect(self.toggle_agent_state)
        a_layout.addWidget(self.agent_stop_btn)

        fetch_btn = QPushButton("🔄 Fetch Jobs")
        fetch_btn.clicked.connect(lambda: self.log_message("Manual fetch jobs requested..."))
        a_layout.addWidget(fetch_btn)

        bg_btn = QPushButton("⬇️ Run in Background")
        bg_btn.clicked.connect(self.hide)
        a_layout.addWidget(bg_btn)

        update_btn = QPushButton("⬆️ Update")
        a_layout.addWidget(update_btn)

        a_layout.addSpacing(16)
        self.status_msg_lbl = QLabel("<b>Current job:</b> <span style='color: #16a34a;'>Ready — waiting for jobs</span>")
        a_layout.addWidget(self.status_msg_lbl)

        a_layout.addStretch()
        self.sync_lbl = QLabel("Synced 00:04:58 | ☑️ Queue empty")
        self.sync_lbl.setStyleSheet("color: #64748b; font-size: 12px;")
        a_layout.addWidget(self.sync_lbl)

        layout.addWidget(action_frame)

        # Splitter: Left (Tables & Log) | Right (QR Panel)
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # --- LEFT PANEL ---
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(8)

        # Table 1: Active Print Queue Table
        self.queue_table = QTableWidget(0, 11)
        self.queue_table.setHorizontalHeaderLabels([
            "Token", "Customer", "Files", "Pages", "₹ Price", 
            "Mode", "Orient", "Sides", "Paper", "Pay", "Status"
        ])
        self.queue_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        left_layout.addWidget(self.queue_table, 2)

        # Divider & Today's Summary Row
        summary_frame = QFrame()
        s_layout = QHBoxLayout(summary_frame)
        s_layout.setContentsMargins(4, 2, 4, 2)
        
        today_date = time.strftime("%Y-%m-%d")
        self.today_summary_lbl = QLabel(f"<b>Today {today_date} — <span style='color: #c2410c;'>0 prints • ₹0.00</span></b>")
        s_layout.addWidget(self.today_summary_lbl)
        s_layout.addStretch()
        refresh_history_btn = QPushButton("Refresh")
        refresh_history_btn.setFixedHeight(26)
        s_layout.addWidget(refresh_history_btn)
        left_layout.addWidget(summary_frame)

        # Table 2: Today's Finished Prints History Table
        self.history_table = QTableWidget(0, 9)
        self.history_table.setHorizontalHeaderLabels([
            "Time", "Type", "Client", "Office", "Files", "Pages", "₹ Price", "Mode", "Pay"
        ])
        self.history_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        left_layout.addWidget(self.history_table, 2)

        # Log Console Box
        self.log_console = QTextEdit()
        self.log_console.setProperty("class", "log-console")
        self.log_console.setReadOnly(True)
        self.log_console.setMaximumHeight(100)
        left_layout.addWidget(self.log_console, 1)

        splitter.addWidget(left_widget)

        # --- RIGHT PANEL (QR Code Box - Clean without Access Code) ---
        right_widget = QFrame()
        right_widget.setProperty("class", "card")
        right_widget.setFixedWidth(260)
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(12, 16, 12, 16)
        right_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)

        qr_title = QLabel("📱 <b>Scan to Upload</b>")
        qr_title.setStyleSheet("font-size: 16px; color: #c2410c;")
        right_layout.addWidget(qr_title)

        self.qr_label = QLabel()
        self.qr_label.setFixedSize(210, 210)
        self.qr_label.setStyleSheet("border: 2px solid #cbd5e1; border-radius: 8px; background: white;")
        self.qr_label.setScaledContents(True)
        right_layout.addWidget(self.qr_label)

        qr_desc = QLabel("Share with customers to upload files directly from mobile.")
        qr_desc.setWordWrap(True)
        qr_desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        qr_desc.setStyleSheet("color: #64748b; font-size: 12px; margin-top: 10px;")
        right_layout.addWidget(qr_desc)

        splitter.addWidget(right_widget)
        layout.addWidget(splitter)

    def init_pricing_tab(self, tab: QWidget):
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(16, 16, 16, 16)

        p_card = QFrame()
        p_card.setProperty("class", "card")
        p_layout = QVBoxLayout(p_card)
        p_layout.setSpacing(14)

        title = QLabel("💰 Manage Shop Print Rates & Pricing")
        title.setProperty("class", "title")
        p_layout.addWidget(title)

        subtitle = QLabel("Update Black & White rate, Color rate, and Duplex discount. Rates sync directly with Web Portal.")
        subtitle.setProperty("class", "subtitle")
        p_layout.addWidget(subtitle)

        # B&W Rate
        p_layout.addWidget(QLabel("Black & White Rate per Page (₹):"))
        self.bw_spin = QDoubleSpinBox()
        self.bw_spin.setRange(0.1, 500.0)
        self.bw_spin.setSingleStep(0.5)
        self.bw_spin.setValue(float(config_mgr.get("bw_rate", 2.0)))
        p_layout.addWidget(self.bw_spin)

        # Color Rate
        p_layout.addWidget(QLabel("Color Rate per Page (₹):"))
        self.color_spin = QDoubleSpinBox()
        self.color_spin.setRange(0.1, 1000.0)
        self.color_spin.setSingleStep(0.5)
        self.color_spin.setValue(float(config_mgr.get("color_rate", 10.0)))
        p_layout.addWidget(self.color_spin)

        # Duplex Discount
        p_layout.addWidget(QLabel("Duplex (Both Sides) Discount per Sheet (₹):"))
        self.duplex_spin = QDoubleSpinBox()
        self.duplex_spin.setRange(0.0, 100.0)
        self.duplex_spin.setSingleStep(0.25)
        self.duplex_spin.setValue(float(config_mgr.get("duplex_discount", 0.5)))
        p_layout.addWidget(self.duplex_spin)

        # Save Button
        save_rates_btn = QPushButton("💾 Save & Sync Print Rates")
        save_rates_btn.setProperty("class", "success")
        save_rates_btn.clicked.connect(self.save_pricing_rates)
        p_layout.addWidget(save_rates_btn)

        layout.addWidget(p_card)
        layout.addStretch()

    def save_pricing_rates(self):
        bw = self.bw_spin.value()
        color = self.color_spin.value()
        duplex = self.duplex_spin.value()

        success, msg = api_client.update_pricing(bw, color, duplex)
        if success:
            self.log_message(f"Pricing updated: B&W ₹{bw}/pg, Color ₹{color}/pg, Duplex -₹{duplex}")
            QMessageBox.information(self, "Pricing Updated 🎉", f"{msg}\n\n• B&W Rate: ₹{bw:.2f}/page\n• Color Rate: ₹{color:.2f}/page\n• Duplex Discount: ₹{duplex:.2f}")
        else:
            QMessageBox.warning(self, "Update Failed ❌", f"Could not sync pricing: {msg}")
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(16, 16, 16, 16)
        
        p_card = QFrame()
        p_card.setProperty("class", "card")
        p_layout = QVBoxLayout(p_card)

        p_layout.addWidget(QLabel("<b>Target Windows Hardware Printer:</b>"))
        self.printer_combo = QComboBox()
        self.reload_printers()
        self.printer_combo.currentTextChanged.connect(self.on_printer_changed)
        p_layout.addWidget(self.printer_combo)

        test_btn = QPushButton("📄 Send Test Print Page")
        test_btn.clicked.connect(self.send_test_print)
        p_layout.addWidget(test_btn)

        layout.addWidget(p_card)
        layout.addStretch()

    def reload_printers(self):
        self.printer_combo.blockSignals(True)
        self.printer_combo.clear()
        printers = printer_service.get_installed_printers()
        self.printer_combo.addItems(printers)
        selected = config_mgr.get("selected_printer") or printer_service.get_default_printer()
        if selected in printers:
            self.printer_combo.setCurrentText(selected)
        self.printer_combo.blockSignals(False)

    def on_printer_changed(self, text):
        if text:
            config_mgr.set("selected_printer", text)

    def generate_qr_code(self):
        """Generates QR Code Image for Customer Upload URL."""
        try:
            import qrcode
            shop_id = config_mgr.get("shop_id", "SHOP_AKM_001")
            url = f"{config_mgr.get('server_url', 'http://localhost:8000')}/s/{shop_id}"
            
            qr = qrcode.QRCode(version=1, box_size=6, border=2)
            qr.add_data(url)
            qr.make(fit=True)
            img = qr.make_image(fill_color="#0f172a", back_color="#ffffff")
            
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            qimg = QImage.fromData(buf.getvalue())
            pixmap = QPixmap.fromImage(qimg)
            self.qr_label.setPixmap(pixmap)
        except Exception as e:
            self.log_message(f"QR Generator Error: {e}")

    def log_message(self, text: str):
        timestamp = time.strftime("[%H:%M:%S]")
        self.log_console.append(f"{timestamp} {text}")

    def toggle_agent_state(self):
        self.agent_running = not self.agent_running
        if self.agent_running:
            self.agent_stop_btn.setText("⏹️ Stop Agent")
            self.agent_stop_btn.setProperty("class", "danger")
            self.status_badge.setText("🟢 Running")
            self.log_message("Print Agent RESUMED.")
        else:
            self.agent_stop_btn.setText("▶️ Start Agent")
            self.agent_stop_btn.setProperty("class", "success")
            self.status_badge.setText("🔴 Stopped")
            self.log_message("Print Agent STOPPED by user.")
        
        self.agent_stop_btn.style().unpolish(self.agent_stop_btn)
        self.agent_stop_btn.style().polish(self.agent_stop_btn)
        self.agent_toggle_requested.emit(self.agent_running)

    def set_light_theme(self):
        self.is_dark_theme = False
        self.setStyleSheet(LIGHT_THEME_QSS)
        self.log_message("Theme switched to light mode.")

    def set_dark_theme(self):
        self.is_dark_theme = True
        self.setStyleSheet(DARK_THEME_QSS)
        self.log_message("Theme switched to dark mode.")

    def open_setup(self):
        dlg = SetupDialog(self)
        if dlg.exec():
            shop_id = config_mgr.get("shop_id", "SHOP_AKM_001")
            self.shop_title.setText(f"🖨️ {shop_id}")
            self.generate_qr_code()
            self.reload_printers()

    def update_connection_status(self, is_online: bool):
        if is_online:
            self.status_badge.setText("🟢 Running")
            self.sync_lbl.setText(f"Synced {time.strftime('%H:%M:%S')} | ☑️ Queue connected")
        else:
            self.status_badge.setText("🔴 Disconnected")

    def update_queue_table(self, jobs: list):
        self.queue_table.setRowCount(0)
        for job in jobs:
            row = self.queue_table.rowCount()
            self.queue_table.insertRow(row)

            job_id = job.get("jobId", "")[-6:]
            file_name = job.get("file", {}).get("originalName", "Document.pdf")
            copies = str(job.get("printOptions", {}).get("copies", 1))
            pages = str(job.get("file", {}).get("pageCount", 1))
            status = job.get("status", "QUEUED")
            price = f"₹{job.get('pricing', {}).get('totalCost', 0):.2f}"

            self.queue_table.setItem(row, 0, QTableWidgetItem(f"#{job_id}"))
            self.queue_table.setItem(row, 1, QTableWidgetItem("Customer"))
            self.queue_table.setItem(row, 2, QTableWidgetItem(file_name))
            self.queue_table.setItem(row, 3, QTableWidgetItem(pages))
            self.queue_table.setItem(row, 4, QTableWidgetItem(price))
            self.queue_table.setItem(row, 5, QTableWidgetItem(job.get("printOptions", {}).get("colorMode", "bw")))
            self.queue_table.setItem(row, 6, QTableWidgetItem("Portrait"))
            self.queue_table.setItem(row, 7, QTableWidgetItem(job.get("printOptions", {}).get("duplex", "single")))
            self.queue_table.setItem(row, 8, QTableWidgetItem("A4"))
            self.queue_table.setItem(row, 9, QTableWidgetItem("Cash" if "PENDING" in status else "Paid"))
            self.queue_table.setItem(row, 10, QTableWidgetItem(status))

    def send_test_print(self):
        printer = self.printer_combo.currentText()
        if not printer:
            QMessageBox.warning(self, "No Printer", "Please select a target printer first.")
            return

        try:
            import tempfile
            test_path = os.path.join(tempfile.gettempdir(), "test_printsoft.txt")
            with open(test_path, "w") as f:
                f.write(f"=== QwikPrint Agent Test Page ===\nTime: {time.ctime()}\nPrinter: {printer}\n")
            success = print_engine.print_file(test_path, printer, {"copies": 1})
            if success:
                self.log_message(f"Test print page spooled to '{printer}'.")
                QMessageBox.information(self, "Test Print Sent", f"Test print page spooled to '{printer}'.")
        except Exception as e:
            self.log_message(f"Test print error: {e}")
