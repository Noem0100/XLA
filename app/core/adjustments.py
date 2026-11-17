"""Biến đổi điểm ảnh; đầu vào/đầu ra RGBA uint8, không sửa mảng gốc."""
import cv2
import numpy as np

DEFAULTS = dict(exposure=0, brightness=0, contrast=0, highlights=0, shadows=0,
                saturation=0, vibrance=0, temperature=0, tint=0, gamma=100,
                black=0, white=255, fade=0)


def pack(rgb, source):
    """Clip RGB về 8 bit rồi ghép alpha ban đầu; trả mảng liên tục."""
    return np.dstack((np.clip(np.rint(rgb), 0, 255).astype(np.uint8), source[..., 3]))


def adjust(image, values):
    """Pipeline exposure → tone → white balance → gamma → HSV → fade."""
    p = {**DEFAULTS, **values}
    x = image[..., :3].astype(np.float32) / 255
    x *= 2 ** (p['exposure'] / 100)
    x += p['brightness'] / 200
    x = (x - .5) * (1 + p['contrast'] / 100) + .5
    luminance = np.clip(x @ np.array([.2126, .7152, .0722], np.float32), 0, 1)
    x += (p['shadows'] / 200 * (1 - luminance) ** 2
          + p['highlights'] / 200 * luminance ** 2)[..., None]
    x[..., 0] += p['temperature'] / 400
    x[..., 2] -= p['temperature'] / 400
    x[..., 1] += p['tint'] / 400
    black, white = p['black'] / 255, p['white'] / 255
    if white <= black:
        raise ValueError('Điểm trắng phải lớn hơn điểm đen.')
    x = np.clip((x - black) / (white - black), 0, 1)
    x = x ** (100 / max(10, p['gamma']))
    hsv = cv2.cvtColor(x.astype(np.float32), cv2.COLOR_RGB2HSV)
    hsv[..., 1] = np.clip(hsv[..., 1] * (1 + p['saturation'] / 100)
                         + p['vibrance'] / 100 * hsv[..., 1] * (1 - hsv[..., 1]), 0, 1)
    x = cv2.cvtColor(hsv, cv2.COLOR_HSV2RGB)
    x = x * (1 - p['fade'] / 200) + p['fade'] / 400
    return pack(x * 255, image)


def curve(image, points, channel='RGB'):
    """LUT 256 phần tử từ các nút đường cong nội suy tuyến tính."""
    points = sorted(points)
    if len(points) < 2 or len({p[0] for p in points}) != len(points):
        raise ValueError('Cần ít nhất hai nút có tọa độ X khác nhau.')
    if any(not 0 <= v <= 255 for pair in points for v in pair):
        raise ValueError('Tọa độ đường cong phải nằm trong 0–255.')
    lut = np.interp(np.arange(256), *np.array(points).T).astype(np.uint8)
    out = image.copy()
    channels = range(3) if channel == 'RGB' else (['R', 'G', 'B'].index(channel),)
    for c in channels:
        out[..., c] = lut[image[..., c]]
    return out


def hsl(image, center, hue, saturation, lightness, width=35):
    """Chỉnh dải màu chọn bằng trọng số khoảng cách vòng tròn hue."""
    hsv = cv2.cvtColor(image[..., :3].astype(np.float32) / 255, cv2.COLOR_RGB2HSV)
    delta = np.abs(hsv[..., 0] - center)
    delta = np.minimum(delta, 360 - delta)
    weight = np.clip(1 - delta / width, 0, 1) * np.clip(hsv[..., 1] * 5, 0, 1)
    hsv[..., 0] = (hsv[..., 0] + hue * weight) % 360
    hsv[..., 1] = np.clip(hsv[..., 1] * (1 + saturation / 100 * weight), 0, 1)
    hsv[..., 2] = np.clip(hsv[..., 2] + lightness / 100 * weight, 0, 1)
    return pack(cv2.cvtColor(hsv, cv2.COLOR_HSV2RGB) * 255, image)


def auto_tone(image):
    """Kéo giãn phân vị 1–99% trên RGB chung, bỏ pixel trong suốt."""
    rgb = image[..., :3]
    visible = rgb[image[..., 3] > 0]
    if visible.size == 0:
        return image.copy()
    low, high = np.percentile(visible, (1, 99))
    if high - low < 1:
        return image.copy()
    return pack((rgb.astype(np.float32) - low) * 255 / (high - low), image)


def white_balance(image):
    """Gray world: cân trung bình ba kênh trên vùng có alpha > 0."""
    rgb = image[..., :3].astype(np.float32)
    visible = rgb[image[..., 3] > 0]
    if visible.size == 0:
        return image.copy()
    means = np.maximum(visible.mean(axis=0), 1)
    return pack(rgb * (means.mean() / means), image)
