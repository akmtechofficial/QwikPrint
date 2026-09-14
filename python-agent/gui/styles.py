LIGHT_THEME_QSS = """
QMainWindow, QDialog {
    background-color: #faf8f5;
    color: #1e293b;
    font-family: 'Segoe UI', system-ui, sans-serif;
}

QWidget {
    color: #1e293b;
}

QFrame.card {
    background-color: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    padding: 10px;
}

QFrame.card:hover {
    border-color: #cbd5e1;
}

QLabel {
    font-size: 13px;
    color: #1e293b;
}

QLabel.title {
    font-size: 20px;
    font-weight: bold;
    color: #c2410c;
}

QLabel.subtitle {
    font-size: 12px;
    color: #64748b;
}

/* Tab Widget */
QTabWidget::pane {
    border: 1px solid #cbd5e1;
    background: #ffffff;
    border-radius: 4px;
}

QTabBar::tab {
    background: #f1f5f9;
    color: #475569;
    padding: 8px 16px;
    font-weight: 600;
    border: 1px solid #cbd5e1;
    border-bottom: none;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
    margin-right: 2px;
}

QTabBar::tab:hover {
    background: #e2e8f0;
    color: #1e293b;
}

QTabBar::tab:selected {
    background: #ffffff;
    color: #c2410c;
    border-bottom: 2px solid #c2410c;
}

/* Buttons */
QPushButton {
    background-color: #ffffff;
    color: #334155;
    border: 1px solid #cbd5e1;
    border-radius: 6px;
    padding: 8px 16px;
    font-weight: 600;
    font-size: 13px;
}

QPushButton:hover {
    background-color: #f1f5f9;
    border-color: #6366f1;
    color: #4f46e5;
}

QPushButton:pressed {
    background-color: #e2e8f0;
    border-color: #4338ca;
}

QPushButton:disabled {
    background-color: #f1f5f9;
    color: #94a3b8;
    border-color: #e2e8f0;
}

QPushButton.danger {
    background-color: #dc2626;
    color: #ffffff;
    border: 1px solid #b91c1c;
}

QPushButton.danger:hover {
    background-color: #b91c1c;
    border-color: #991b1b;
}

QPushButton.danger:pressed {
    background-color: #991b1b;
}

QPushButton.success {
    background-color: #16a34a;
    color: #ffffff;
    border: 1px solid #15803d;
}

QPushButton.success:hover {
    background-color: #15803d;
    border-color: #166534;
}

QPushButton.success:pressed {
    background-color: #166534;
}

QPushButton.theme-btn {
    background-color: #ef4444;
    color: #ffffff;
    border: none;
    font-weight: bold;
}

QPushButton.theme-btn:hover {
    background-color: #dc2626;
}

/* Inputs & Combos */
QLineEdit, QComboBox, QDoubleSpinBox {
    background-color: #ffffff;
    border: 1px solid #cbd5e1;
    border-radius: 6px;
    padding: 6px 10px;
    color: #1e293b;
}

QLineEdit:hover, QComboBox:hover, QDoubleSpinBox:hover {
    border-color: #94a3b8;
}

QLineEdit:focus, QComboBox:focus, QDoubleSpinBox:focus {
    border-color: #6366f1;
}

/* Table View */
QTableWidget {
    background-color: #ffffff;
    border: 1px solid #cbd5e1;
    gridline-color: #e2e8f0;
    color: #1e293b;
    font-size: 12px;
}

QHeaderView::section {
    background-color: #f8fafc;
    color: #475569;
    padding: 6px;
    font-weight: bold;
    border: 1px solid #cbd5e1;
}

QTextEdit.log-console {
    background-color: #faf8f5;
    border: 1px solid #cbd5e1;
    color: #64748b;
    font-family: 'Consolas', 'Courier New', monospace;
    font-size: 11px;
}
"""

DARK_THEME_QSS = """
QMainWindow, QDialog {
    background-color: #0f172a;
    color: #f8fafc;
    font-family: 'Segoe UI', system-ui, sans-serif;
}

QWidget {
    color: #f8fafc;
}

QFrame.card {
    background-color: #1e293b;
    border: 1px solid #334155;
    border-radius: 8px;
    padding: 10px;
}

QFrame.card:hover {
    border-color: #475569;
}

QLabel {
    font-size: 13px;
    color: #f8fafc;
}

QLabel.title {
    font-size: 20px;
    font-weight: bold;
    color: #f97316;
}

QLabel.subtitle {
    font-size: 12px;
    color: #94a3b8;
}

/* Tab Widget */
QTabWidget::pane {
    border: 1px solid #334155;
    background: #1e293b;
    border-radius: 4px;
}

QTabBar::tab {
    background: #0f172a;
    color: #94a3b8;
    padding: 8px 16px;
    font-weight: 600;
    border: 1px solid #334155;
    border-bottom: none;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
    margin-right: 2px;
}

QTabBar::tab:hover {
    background: #1e293b;
    color: #f8fafc;
}

QTabBar::tab:selected {
    background: #1e293b;
    color: #f97316;
    border-bottom: 2px solid #f97316;
}

/* Buttons */
QPushButton {
    background-color: #334155;
    color: #f8fafc;
    border: 1px solid #475569;
    border-radius: 6px;
    padding: 8px 16px;
    font-weight: 600;
    font-size: 13px;
}

QPushButton:hover {
    background-color: #475569;
    border-color: #818cf8;
    color: #ffffff;
}

QPushButton:pressed {
    background-color: #1e293b;
    border-color: #6366f1;
}

QPushButton:disabled {
    background-color: #1e293b;
    color: #64748b;
    border-color: #334155;
}

QPushButton.danger {
    background-color: #ef4444;
    color: #ffffff;
    border: 1px solid #dc2626;
}

QPushButton.danger:hover {
    background-color: #dc2626;
}

QPushButton.danger:pressed {
    background-color: #b91c1c;
}

QPushButton.success {
    background-color: #10b981;
    color: #ffffff;
    border: 1px solid #059669;
}

QPushButton.success:hover {
    background-color: #059669;
}

QPushButton.success:pressed {
    background-color: #047857;
}

QPushButton.theme-btn {
    background-color: #ef4444;
    color: #ffffff;
    border: none;
    font-weight: bold;
}

/* Inputs & Combos */
QLineEdit, QComboBox, QDoubleSpinBox {
    background-color: #0f172a;
    border: 1px solid #334155;
    border-radius: 6px;
    padding: 6px 10px;
    color: #f8fafc;
}

QLineEdit:hover, QComboBox:hover, QDoubleSpinBox:hover {
    border-color: #475569;
}

QLineEdit:focus, QComboBox:focus, QDoubleSpinBox:focus {
    border-color: #818cf8;
}

/* Table View */
QTableWidget {
    background-color: #1e293b;
    border: 1px solid #334155;
    gridline-color: #334155;
    color: #f8fafc;
    font-size: 12px;
}

QHeaderView::section {
    background-color: #0f172a;
    color: #94a3b8;
    padding: 6px;
    font-weight: bold;
    border: 1px solid #334155;
}

QTextEdit.log-console {
    background-color: #0f172a;
    border: 1px solid #334155;
    color: #94a3b8;
    font-family: 'Consolas', 'Courier New', monospace;
    font-size: 11px;
}
"""

