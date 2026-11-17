"""Mask cục bộ, inpaint, chữ, overlay và collage; không phụ thuộc Qt."""
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageOps
from .adjustments import adjust
from .filters import spatial
from .geometry import check_size


def local_edit(image, mask, mode, amount=25, feather=5):
    """Trộn hiệu ứng qua mask mềm hoặc inpaint Telea vùng mask > 0."""
    if mask.shape != image.shape[:2] or not np.any(mask):
        raise ValueError('Hãy tô vùng cần chỉnh bằng cọ trước.')
    if mode == 'Xóa chi tiết Telea':
        result = image.copy()
        result[..., :3] = cv2.inpaint(np.ascontiguousarray(image[..., :3]), mask, 3, cv2.INPAINT_TELEA)
        return result
    if mode == 'Làm sáng vùng':
        effect = adjust(image, dict(exposure=amount))
    elif mode == 'Làm tối vùng':
        effect = adjust(image, dict(exposure=-amount))
    elif mode == 'Làm mịn vùng':
        effect = spatial(image, 'Bilateral', amount)
    elif mode == 'Làm mờ vùng':
        effect = spatial(image, 'Gaussian', amount)
    elif mode == 'Xóa nền bằng cọ':
        effect = image.copy()
        effect[..., 3] = 0
    else:
        raise ValueError('Chế độ cọ không tồn tại.')
    weight = mask.astype(np.float32) / 255
    if feather > 0:
        weight = cv2.GaussianBlur(weight, (0, 0), feather)
    return np.clip(np.rint(image * (1 - weight[..., None]) + effect * weight[..., None]), 0, 255).astype(np.uint8)


def text_layer(image, text, x, y, size, color, font_path):
    """Raster chữ Unicode lên lớp RGBA rồi alpha composite với ảnh."""
    if not text.strip():
        raise ValueError('Nội dung chữ không được trống.')
    if not font_path:
        raise ValueError('Chọn file font TTF/OTF để hiển thị tiếng Việt đúng.')
    font = ImageFont.truetype(font_path, size)
    layer = Image.new('RGBA', (image.shape[1], image.shape[0]))
    ImageDraw.Draw(layer).multiline_text((x, y), text, font=font, fill=color, stroke_width=0)
    return np.array(Image.alpha_composite(Image.fromarray(image), layer))


def overlay(image, sticker, x, y, width, opacity=100):
    """Co overlay theo tỉ lệ và ghép alpha, cho phép đặt lệch một phần ảnh."""
    height = max(1, round(sticker.shape[0] * width / sticker.shape[1]))
    check_size(width, height)
    layer = Image.fromarray(sticker).resize((width, height), Image.Resampling.LANCZOS)
    alpha = np.array(layer.getchannel('A')).astype(np.float32) * np.clip(opacity / 100, 0, 1)
    layer.putalpha(Image.fromarray(alpha.astype(np.uint8)))
    result = Image.fromarray(image).copy()
    result.alpha_composite(layer, (x, y))
    return np.array(result)


def collage(images, columns=2, cell=600, gap=16):
    """Ghép lưới, fit tâm mỗi ảnh vào ô vuông bằng Lanczos."""
    if not images:
        raise ValueError('Cần ít nhất một ảnh.')
    rows = (len(images) + columns - 1) // columns
    size = (columns * cell + (columns + 1) * gap, rows * cell + (rows + 1) * gap)
    check_size(*size)
    canvas = Image.new('RGBA', size, '#f3f0eb')
    for i, image in enumerate(images):
        tile = ImageOps.fit(Image.fromarray(image), (cell, cell), Image.Resampling.LANCZOS)
        canvas.alpha_composite(tile, (gap + (i % columns) * (cell + gap), gap + (i // columns) * (cell + gap)))
    return np.array(canvas)
