"""Công cụ Chương 1 còn thiếu: kênh màu, mặt nạ HSV, số học và tịnh tiến."""
import cv2
import numpy as np
from .adjustments import pack
from .enhancement import Algorithm
from .enhancement_point import _image, _finite, _integer


ALGORITHMS = {
    'channel': Algorithm('Tách kênh trong không gian màu', 'Không gian màu', '35–41, 52',
        'Hiển thị một kênh thành ảnh xám. HSV: H được giãn 0–179 thành 0–255; Lab dùng mã 8 bit OpenCV (a/b trung tính = 128).',
        (('space', 'Không gian màu', ['RGB', 'CMY', 'HSV', 'YCbCr', 'Lab'], 0, 0),
         ('channel', 'Kênh số 0 / 1 / 2', 0, 0, 2))),
    'hsv_mask': Algorithm('Tách vùng theo khoảng màu HSV', 'Không gian màu', '37–38, 54–55',
        'H: 0–179, S/V: 0–255 theo OpenCV. Nếu H thấp > H cao, chọn khoảng qua màu đỏ ở H=0. Xuất mặt nạ hoặc giữ màu trên nền đen; giữ alpha nguồn.',
        (('hue_low', 'H thấp', 0, 0, 179), ('hue_high', 'H cao', 25, 0, 179),
         ('saturation_low', 'S thấp', 100, 0, 255), ('saturation_high', 'S cao', 255, 0, 255),
         ('value_low', 'V thấp', 100, 0, 255), ('value_high', 'V cao', 255, 0, 255),
         ('output', 'Kết quả', ['color', 'mask'], 0, 0))),
    'arithmetic': Algorithm('Phép toán giữa hai ảnh', 'Số học và logic', '47',
        'Hai ảnh phải cùng kích thước. Cộng/trừ bão hòa 0–255; nhân A×B/255; chia 255×A/B (B=0 cho 0); AND/OR trên mask xám ≥128. RGB ẩn được xem là 0; giữ alpha ảnh nguồn.',
        (('operation', 'Phép toán', ['add', 'subtract', 'difference', 'multiply', 'divide', 'and', 'or'], 0, 0),),
        reference=True),
    'translate': Algorithm('Tịnh tiến ảnh', 'Biến đổi hình học', '29',
        'Dịch theo ma trận affine: x sang phải, y xuống dưới. Giữ kích thước khung; phần ra ngoài bị cắt, phần trống trong suốt. Nội suy láng giềng gần nhất.',
        (('dx', 'Dịch ngang x (pixel)', 30, -20000, 20000),
         ('dy', 'Dịch dọc y (pixel)', 30, -20000, 20000))),
}


def channel(image, space='RGB', channel=0):
    """Tách đúng thứ tự kênh RGB/CMY/HSV/YCbCr/Lab, đưa về ảnh xám RGBA."""
    _image(image)
    channel = _integer(channel, 'Kênh màu', 0, 2)
    rgb = np.ascontiguousarray(image[..., :3])
    if space == 'RGB':
        planes = rgb
    elif space == 'CMY':
        planes = 255 - rgb
    elif space == 'HSV':
        planes = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
        if channel == 0:
            return pack(np.repeat((planes[..., 0].astype(np.float32) * 255 / 179)[..., None], 3, axis=2), image)
    elif space == 'YCbCr':
        planes = cv2.cvtColor(rgb, cv2.COLOR_RGB2YCrCb)[..., [0, 2, 1]]
    elif space == 'Lab':
        planes = cv2.cvtColor(rgb, cv2.COLOR_RGB2LAB)
    else:
        raise ValueError('Không gian màu phải là RGB, CMY, HSV, YCbCr hoặc Lab.')
    return pack(np.repeat(planes[..., channel, None], 3, axis=2), image)


def hsv_mask(image, hue_low=0, hue_high=25, saturation_low=100,
             saturation_high=255, value_low=100, value_high=255, output='color'):
    """Tách màu bằng khoảng HSV; hỗ trợ khoảng Hue băng qua điểm 0 của vòng màu."""
    _image(image)
    hue_low = _integer(hue_low, 'H thấp', 0, 179)
    hue_high = _integer(hue_high, 'H cao', 0, 179)
    saturation_low = _integer(saturation_low, 'S thấp', 0, 255)
    saturation_high = _integer(saturation_high, 'S cao', 0, 255)
    value_low = _integer(value_low, 'V thấp', 0, 255)
    value_high = _integer(value_high, 'V cao', 0, 255)
    if saturation_low > saturation_high or value_low > value_high:
        raise ValueError('S/V thấp phải nhỏ hơn hoặc bằng S/V cao.')
    if output not in ('color', 'mask'):
        raise ValueError('Chọn kết quả color hoặc mask.')
    hsv = cv2.cvtColor(np.ascontiguousarray(image[..., :3]), cv2.COLOR_RGB2HSV)
    h, s, v = (hsv[..., index] for index in range(3))
    selected_hue = (h >= hue_low) & (h <= hue_high) if hue_low <= hue_high else (h >= hue_low) | (h <= hue_high)
    selected = (selected_hue & (s >= saturation_low) & (s <= saturation_high)
                & (v >= value_low) & (v <= value_high) & (image[..., 3] > 0))
    values = np.repeat((selected.astype(np.uint8) * 255)[..., None], 3, axis=2) if output == 'mask' else np.where(selected[..., None], image[..., :3], 0)
    return pack(values, image)


def arithmetic(image, reference, operation='add'):
    """Tính số thực trước bão hòa, không tràn uint8; AND/OR dùng mask nhị phân."""
    _image(image)
    if reference is None:
        raise ValueError('Hãy chọn ảnh thứ hai cho phép toán.')
    _image(reference)
    if reference.shape != image.shape:
        raise ValueError('Hai ảnh phải có cùng kích thước; hãy đổi kích thước trước.')
    a = np.where(image[..., 3, None] > 0, image[..., :3], 0).astype(np.float32)
    b = np.where(reference[..., 3, None] > 0, reference[..., :3], 0).astype(np.float32)
    if operation == 'add':
        result = a + b
    elif operation == 'subtract':
        result = a - b
    elif operation == 'difference':
        result = np.abs(a - b)
    elif operation == 'multiply':
        result = a * b / 255
    elif operation == 'divide':
        result = np.divide(255 * a, b, out=np.zeros_like(a), where=b != 0)
    elif operation in ('and', 'or'):
        mask_a = cv2.cvtColor(a, cv2.COLOR_RGB2GRAY) >= 128
        mask_b = cv2.cvtColor(b, cv2.COLOR_RGB2GRAY) >= 128
        selected = mask_a & mask_b if operation == 'and' else mask_a | mask_b
        result = np.repeat((selected.astype(np.uint8) * 255)[..., None], 3, axis=2)
    else:
        raise ValueError('Phép toán hai ảnh không hợp lệ.')
    return pack(result, image)


def translate(image, dx=30, dy=30):
    """Tịnh tiến số nguyên trên khung cố định và điền phần mới bằng RGBA=(0,0,0,0)."""
    _image(image)
    dx = _integer(dx, 'Dịch ngang', -20000, 20000)
    dy = _integer(dy, 'Dịch dọc', -20000, 20000)
    height, width = image.shape[:2]
    matrix = np.array([[1, 0, dx], [0, 1, dy]], dtype=np.float32)
    return cv2.warpAffine(image, matrix, (width, height), flags=cv2.INTER_NEAREST,
                          borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0))


def process(image, algorithm, params=None, reference=None):
    """Điều phối các phép Chương 1 cùng hợp đồng (ảnh, mô tả) của công cụ bài học."""
    _image(image)
    params = dict(params or {})
    functions = {'channel': channel, 'hsv_mask': hsv_mask, 'translate': translate}
    if algorithm == 'arithmetic':
        result = arithmetic(image, reference, **params)
    elif algorithm in functions:
        result = functions[algorithm](image, **params)
    else:
        raise ValueError('Thuật toán Chương 1 không tồn tại.')
    return result, ''
