"""Chạy tác vụ nặng ngoài GUI; truyền kết quả qua signal Qt."""
from PySide6.QtCore import QThread, Signal


class Worker(QThread):
    """Một tác vụ tại một thời điểm; cửa sổ giữ tham chiếu đến khi finished."""
    result = Signal(object)
    error = Signal(str)

    def __init__(self, function, parent=None):
        """Lưu callable không chạm widget trong luồng nền."""
        super().__init__(parent)
        self.function = function

    def run(self):
        """Thực thi callable; lỗi được gửi lên giao diện thay vì làm app thoát."""
        try:
            self.result.emit(self.function())
        except Exception as exc:
            self.error.emit(f'{type(exc).__name__}: {exc}')
