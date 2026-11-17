"""Một trang ảnh giữ tài liệu, vùng chọn và trạng thái giao diện riêng."""
from app.core import adjustments
from app.core.document import Document
from .canvas import Canvas


class ImagePage(Canvas):
    """Canvas độc lập cho mỗi ảnh, không dùng chung lịch sử hay mask."""

    def __init__(self, image, name, original=None, created=False):
        """Tạo tài liệu mới cùng các giá trị điều khiển mặc định."""
        super().__init__()
        self.document = Document(image, original)
        if created:
            self.document.saved_id = -1
        self.source_name = name
        self.adjustment_values = adjustments.DEFAULTS.copy()
        self.filter_channel = None
        self.filter_mode = 'channel'
        self.history_row = 0
        self.property_tab = 0
        self.preset_index = 0
        self.preset_strength = 100
        self.brush_index = 0
        self.brush_amount = 25
        self.feather = 5
        self.hint = 'Kéo để di chuyển ảnh. Cuộn chuột để zoom.'

    @property
    def unsaved(self):
        """Tính cả điều chỉnh đang xem trước khi đóng một tab không hoạt động."""
        return (self.document.dirty or self.adjustment_values != adjustments.DEFAULTS
                or self.filter_channel is not None)
