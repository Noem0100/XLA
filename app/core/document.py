"""Trạng thái ảnh độc lập Qt; undo/redo có giới hạn bộ nhớ."""
from .io import png_bytes, from_png


class Document:
    """Giữ ảnh gốc bất biến, ảnh hiện tại và các snapshot nén PNG."""
    def __init__(self, image, original=None):
        """Tạo trạng thái đầu tiên và đánh dấu chưa có thay đổi."""
        self.original = (image if original is None else original).copy()
        self.current = image.copy()
        self.entries = [(0, 'Mở ảnh', png_bytes(image))]
        self.index = 0
        self.serial = 0
        self.saved_id = 0
        self.max_bytes = 256 * 1024 * 1024
        self.max_steps = 20

    @property
    def dirty(self):
        """So sánh mã trạng thái hiện tại với mã đã lưu dự án gần nhất."""
        return self.entries[self.index][0] != self.saved_id

    def mark_saved(self):
        """Đánh dấu snapshot hiện tại đã được lưu dạng dự án."""
        self.saved_id = self.entries[self.index][0]

    def commit(self, image, label):
        """Bỏ nhánh redo, thêm snapshot mới, giới hạn 20 bước hoặc 256 MiB."""
        encoded = png_bytes(image)
        self.serial += 1
        self.entries = self.entries[:self.index + 1]
        self.entries.append((self.serial, label, encoded))
        while len(self.entries) > 1 and (len(self.entries) > self.max_steps or
                                        sum(len(e[2]) for e in self.entries) > self.max_bytes):
            self.entries.pop(0)
        self.index = len(self.entries) - 1
        self.current = image.copy()

    def undo(self):
        """Lùi một snapshot nếu có; trả False tại giới hạn lịch sử."""
        if self.index == 0:
            return False
        self.index -= 1
        self.current = from_png(self.entries[self.index][2])
        return True

    def redo(self):
        """Đi tới snapshot kế tiếp nếu chưa tạo nhánh chỉnh sửa khác."""
        if self.index + 1 >= len(self.entries):
            return False
        self.index += 1
        self.current = from_png(self.entries[self.index][2])
        return True

    def labels(self):
        """Danh sách nhãn theo nhánh hiện tại, dùng ở UI và manifest."""
        return [entry[1] for entry in self.entries[:self.index + 1]]
