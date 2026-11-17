"""Điểm khởi động desktop, chạy: python main.py."""
import sys
from PySide6.QtWidgets import QApplication
from app.ui.window import MainWindow
from app.ui.theme import STYLE


def main():
    """Khởi tạo Qt, stylesheet và vòng lặp sự kiện."""
    application = QApplication(sys.argv)
    application.setApplicationName("Minh Đăng Photo")
    application.setStyle("Fusion")
    application.setStyleSheet(STYLE)
    window = MainWindow()
    window.show()
    sys.exit(application.exec())


if __name__ == "__main__":
    main()
