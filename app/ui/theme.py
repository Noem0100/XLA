"""Thiết kế giao diện tập trung trong một stylesheet."""
STYLE = '''
QMainWindow, QDialog { background: #f3f6fa; color: #233044; }
QWidget { background-color: #f3f6fa; color: #233044; font-family: 'Segoe UI', 'DejaVu Sans'; font-size: 12px; }
QLabel { background: transparent; }
QFrame#panel { background: #ffffff; border: 1px solid #d7e0ea; border-radius: 12px; }
QLabel#brand { color: #172b43; font-size: 23px; font-weight: 700; }
QLabel#section { color: #52647a; font-size: 11px; font-weight: 700; }
QPushButton { background: #eef3f8; border: 1px solid #c5d1df; border-radius: 7px; padding: 8px 12px; text-align: left; }
QPushButton:hover { background: #e0edf7; border-color: #3685c3; }
QPushButton:pressed, QPushButton:checked { background: #cceee6; border-color: #16856f; }
QPushButton:disabled { color: #7c8999; background: #edf1f5; }
QPushButton#primary { background: #147d68; color: #ffffff; font-weight: 700; border: none; }
QPushButton#primary:hover { background: #106653; }
QPushButton#primary:disabled { background: #e2e8ef; color: #7c8999; }
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QPlainTextEdit { background: #ffffff; border: 1px solid #c5d1df; border-radius: 5px; padding: 6px; selection-background-color: #147d68; selection-color: #ffffff; }
QComboBox QAbstractItemView { background: #ffffff; selection-background-color: #dcefe9; selection-color: #145c4c; }
QScrollArea { border: none; background: transparent; }
QScrollArea > QWidget > QWidget { background: #ffffff; }
QTabWidget::pane { border: none; }
QTabBar::tab { background: #e8eef5; padding: 9px 12px; margin-right: 3px; border-radius: 5px; }
QTabBar::tab:selected { background: #d4eee6; color: #145c4c; }
QSlider::groove:horizontal { height: 4px; background: #c5d1df; border-radius: 2px; }
QSlider::sub-page:horizontal { background: #147d68; border-radius: 2px; }
QSlider::handle:horizontal { background: #147d68; width: 12px; margin: -4px 0; border-radius: 6px; }
QListWidget { background: #ffffff; border: 1px solid #d7e0ea; border-radius: 6px; padding: 5px; }
QListWidget::item { padding: 5px; }
QListWidget::item:selected { background: #d4eee6; color: #145c4c; }
QStatusBar { background: #ffffff; color: #52647a; }
QToolTip { background: #ffffff; color: #233044; border: 1px solid #b6c5d5; padding: 6px; }
QScrollBar:vertical { background: #edf2f7; width: 9px; }
QScrollBar::handle:vertical { background: #a6b6c8; min-height: 30px; border-radius: 4px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
QScrollBar:horizontal { background: #edf2f7; height: 9px; }
QScrollBar::handle:horizontal { background: #a6b6c8; min-width: 30px; border-radius: 4px; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0px; }
QScrollBar::add-page, QScrollBar::sub-page { background: none; }
QMenuBar, QMenu { background: #ffffff; color: #233044; }
QMenuBar::item:selected, QMenu::item:selected { background: #d4eee6; color: #145c4c; }
QMessageBox { background: #ffffff; }
'''
