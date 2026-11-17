"""Biến đổi hình học trên cả bốn kênh RGBA."""
import numpy as np
from PIL import Image, ImageOps

MAX_PIXELS = 20_000_000


def check_size(width, height):
    """Chặn kích thước không hợp lệ hoặc vượt giới hạn bộ nhớ ứng dụng."""
    if width < 1 or height < 1 or width * height > MAX_PIXELS:
        raise ValueError('Kích thước phải dương và không vượt 20 triệu pixel.')


def crop(image, box):
    """Cắt vùng (trái, trên, phải, dưới), chặn biên và từ chối vùng rỗng."""
    h, w = image.shape[:2]
    x1, y1, x2, y2 = [int(v) for v in box]
    x1, x2 = sorted((max(0, min(w, x1)), max(0, min(w, x2))))
    y1, y2 = sorted((max(0, min(h, y1)), max(0, min(h, y2))))
    if x2 <= x1 or y2 <= y1:
        raise ValueError('Hãy kéo chọn một vùng ảnh trước khi cắt.')
    return image[y1:y2, x1:x2].copy()


def resize(image, width, height):
    """Nội suy Lanczos, xử lý alpha bằng cơ chế RGBA của Pillow."""
    check_size(width, height)
    return np.array(Image.fromarray(image).resize((width, height), Image.Resampling.LANCZOS))


def rotate(image, degrees):
    """Xoay ngược chiều kim đồng hồ, mở rộng canvas và nền trong suốt."""
    import math
    h, w = image.shape[:2]
    angle = math.radians(degrees)
    check_size(max(1, int(abs(w * math.cos(angle)) + abs(h * math.sin(angle))) + 2),
               max(1, int(abs(h * math.cos(angle)) + abs(w * math.sin(angle))) + 2))
    return np.array(Image.fromarray(image).rotate(degrees, Image.Resampling.BICUBIC, expand=True))


def flip(image, horizontal=True):
    """Đảo thứ tự cột hoặc hàng, trả bản sao liên tục."""
    return np.flip(image, axis=1 if horizontal else 0).copy()


def border(image, size, color):
    """Thêm khung đặc bên ngoài, giữ nguyên các pixel ảnh bên trong."""
    h, w = image.shape[:2]
    check_size(w + 2 * size, h + 2 * size)
    return np.array(ImageOps.expand(Image.fromarray(image), border=size, fill=color))
