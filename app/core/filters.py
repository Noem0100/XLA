"""Lọc không gian, hiệu ứng và công cụ minh họa môn xử lý ảnh."""
import cv2
import numpy as np
from .adjustments import pack, adjust

PRESETS = ['Nguyên bản', 'Chân dung', 'Phong cảnh', 'Điện ảnh', 'Vintage', 'Đen trắng', 'Sepia']


def channel_view(image, channel):
    """Tách R/G/B theo đúng cường độ kênh; kênh 3 hiển thị độ sáng Y'."""
    if not isinstance(channel, (int, np.integer)) or not 0 <= channel <= 3:
        raise ValueError('Kênh lọc phải là đỏ (0), xanh lá (1), xanh dương (2) hoặc độ sáng (3).')
    if channel == 3:
        rgb = image[..., :3].astype(np.float32)
        gray = rgb @ np.array([.2126, .7152, .0722], dtype=np.float32)
        return pack(np.repeat(gray[..., None], 3, axis=2), image)
    result = np.zeros_like(image)
    result[..., channel] = image[..., channel]
    result[..., 3] = image[..., 3]
    return result


def color_range(image, channel):
    """Giữ gam đỏ/xanh lá/xanh dương, chuyển gam khác sang xám; kênh 3 là Y'."""
    if not isinstance(channel, (int, np.integer)) or not 0 <= channel <= 3:
        raise ValueError('Kênh lọc phải là đỏ (0), xanh lá (1), xanh dương (2) hoặc độ sáng (3).')
    rgb = np.ascontiguousarray(image[..., :3])
    gray = (rgb[..., 0] * np.float32(.2126) + rgb[..., 1] * np.float32(.7152)
            + rgb[..., 2] * np.float32(.0722))
    if channel == 3:
        return pack(np.repeat(gray[..., None], 3, axis=2), image)
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    # Hue OpenCV có chu kỳ 180; khoảng cách tròn giữ cả hai phía của gam đỏ.
    distance = np.abs(hsv[..., 0].astype(np.float32) - channel * 60)
    distance = np.minimum(distance, 180 - distance)
    weight = np.clip(1 - distance / 30, 0, 1)
    # Smoothstep làm mềm ranh giới gam màu, tránh vùng chọn bị cắt đột ngột.
    weight = weight * weight * (3 - 2 * weight)
    effect = gray[..., None] + weight[..., None] * (rgb.astype(np.float32) - gray[..., None])
    return pack(effect, image)


def preset(image, name, strength=100):
    """Tạo preset rồi trộn tuyến tính với ảnh đầu vào theo cường độ."""
    recipes = {'Chân dung': dict(exposure=15, shadows=22, temperature=12, saturation=-8),
               'Phong cảnh': dict(contrast=20, saturation=28, vibrance=20),
               'Điện ảnh': dict(contrast=22, temperature=-20, fade=15, saturation=-18),
               'Vintage': dict(temperature=28, fade=35, saturation=-25)}
    if name == 'Nguyên bản':
        return image.copy()
    if name == 'Đen trắng':
        gray = cv2.cvtColor(image[..., :3], cv2.COLOR_RGB2GRAY)
        effect = pack(np.repeat(gray[..., None], 3, axis=2), image)
    elif name == 'Sepia':
        matrix = np.array([[.393, .769, .189], [.349, .686, .168], [.272, .534, .131]])
        effect = pack(image[..., :3] @ matrix.T, image)
    elif name in recipes:
        effect = adjust(image, recipes[name])
    else:
        raise ValueError('Preset không tồn tại.')
    a = np.clip(strength / 100, 0, 1)
    return pack(image[..., :3] * (1 - a) + effect[..., :3] * a, image)


def spatial(image, kind, amount=10):
    """Dispatcher Gaussian, median, bilateral, NLM, unsharp, CLAHE, Canny, Otsu."""
    rgb = np.ascontiguousarray(image[..., :3])
    amount = max(1, int(amount))
    if kind == 'Gaussian':
        result = cv2.GaussianBlur(rgb, (0, 0), max(.1, amount / 3))
    elif kind == 'Median':
        result = cv2.medianBlur(rgb, min(31, 2 * (amount // 4) + 3))
    elif kind == 'Bilateral':
        result = cv2.bilateralFilter(rgb, 9, amount * 4, amount * 4)
    elif kind == 'Khử nhiễu NLM':
        bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
        result = cv2.cvtColor(cv2.fastNlMeansDenoisingColored(bgr, None, amount, amount, 7, 21), cv2.COLOR_BGR2RGB)
    elif kind == 'Làm nét':
        blur = cv2.GaussianBlur(rgb, (0, 0), 1.5)
        result = rgb.astype(np.float32) + amount / 10 * (rgb.astype(np.float32) - blur)
    elif kind == 'CLAHE':
        lab = cv2.cvtColor(rgb, cv2.COLOR_RGB2LAB)
        lab[..., 0] = cv2.createCLAHE(clipLimit=max(1., amount / 5), tileGridSize=(8, 8)).apply(lab[..., 0])
        result = cv2.cvtColor(lab, cv2.COLOR_LAB2RGB)
    elif kind in ('Canny', 'Otsu'):
        gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
        if kind == 'Canny':
            result = cv2.Canny(gray, amount * 3, amount * 6)
        else:
            _, result = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        result = np.repeat(result[..., None], 3, axis=2)
    elif kind == 'Âm bản':
        result = 255 - rgb
    elif kind == 'Cartoon':
        smooth = cv2.bilateralFilter(rgb, 9, 90, 90)
        gray = cv2.medianBlur(cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY), 5)
        edges = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY, 9, 5)
        result = cv2.bitwise_and(smooth, smooth, mask=edges)
    elif kind == 'Phác thảo':
        gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY).astype(np.float32)
        blur = cv2.GaussianBlur(255 - gray, (0, 0), max(1, amount / 3))
        result = np.repeat(np.clip(gray * 255 / np.maximum(255 - blur, 1), 0, 255)[..., None], 3, axis=2)
    else:
        raise ValueError('Bộ lọc không tồn tại.')
    return pack(result, image)


def vignette(image, amount=40):
    """Giảm sáng theo bình phương khoảng cách chuẩn hóa tới tâm."""
    h, w = image.shape[:2]
    yy, xx = np.mgrid[-1:1:complex(h), -1:1:complex(w)]
    weight = np.clip(1 - amount / 100 * (xx * xx + yy * yy) / 2, 0, 1)
    return pack(image[..., :3] * weight[..., None], image)
