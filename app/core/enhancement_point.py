"""Biến đổi mức xám và histogram theo các mục 2.2–2.3 của Chương 2."""
import cv2
import numpy as np

from .adjustments import pack


def _image(image):
    """Kiểm tra hợp đồng RGBA 8 bit, không nhận ảnh rỗng hoặc kiểu ngầm định."""
    if (not isinstance(image, np.ndarray) or image.dtype != np.uint8
            or image.ndim != 3 or image.shape[2] != 4
            or image.shape[0] == 0 or image.shape[1] == 0):
        raise ValueError('Ảnh phải là mảng RGBA uint8 không rỗng.')
    return image


def _finite(value, name, minimum=None, maximum=None):
    """Đọc một tham số hữu hạn và kiểm tra giới hạn có ý nghĩa của thuật toán."""
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f'{name} phải là số hữu hạn.') from exc
    if not np.isfinite(number):
        raise ValueError(f'{name} phải là số hữu hạn.')
    if minimum is not None and number < minimum:
        raise ValueError(f'{name} phải lớn hơn hoặc bằng {minimum}.')
    if maximum is not None and number > maximum:
        raise ValueError(f'{name} phải nhỏ hơn hoặc bằng {maximum}.')
    return number


def _integer(value, name, minimum, maximum):
    """Chỉ nhận số nguyên trong miền quy định, tránh cắt mất phần thập phân."""
    number = _finite(value, name, minimum, maximum)
    if not number.is_integer() or isinstance(value, (bool, np.bool_)):
        raise ValueError(f'{name} phải là số nguyên.')
    return int(number)


def _lut_image(image, lut):
    """Ánh xạ ba kênh RGB bằng LUT và giữ nguyên alpha cùng mảng nguồn."""
    result = image.copy()
    result[..., :3] = lut[image[..., :3]]
    return result


def gray_plane(image):
    """Tính Y' gần đúng trên mã sRGB 8 bit, cùng trọng số với histogram của app."""
    _image(image)
    gray = image[..., 0].astype(np.float64)
    gray *= .2126
    gray += image[..., 1] * .7152
    gray += image[..., 2] * .0722
    return np.rint(gray).astype(np.uint8)


def linear(image, gain=1., bias=0., pivot=0.):
    """Áp dụng g=a(r-m)+m+b rồi bão hòa; giá trị âm không bị lấy trị tuyệt đối."""
    _image(image)
    gain = _finite(gain, 'Hệ số a', -1e6, 1e6)
    bias = _finite(bias, 'Độ sáng b', -1e6, 1e6)
    pivot = _finite(pivot, 'Tâm co giãn m', 0, 255)
    return pack(gain * (image[..., :3].astype(np.float64) - pivot) + pivot + bias, image)


def negative(image):
    """Đảo mức xám theo s=255-r cho từng kênh RGB."""
    _image(image)
    result = image.copy()
    result[..., :3] = 255 - image[..., :3]
    return result


def logarithm(image, gain=1.):
    """Nén dải động bằng gain·255·ln(1+r)/ln(256), tương ứng ví dụ r=50 → 181."""
    _image(image)
    gain = _finite(gain, 'Hệ số log', 0, 1e6)
    lut = np.clip(np.rint(gain * 255 * np.log1p(np.arange(256)) / np.log(256)), 0, 255).astype(np.uint8)
    return _lut_image(image, lut)


def gamma(image, gamma=.45):
    """Hiệu chỉnh theo số mũ trực tiếp γ: γ<1 làm sáng, γ>1 làm tối."""
    _image(image)
    gamma = _finite(gamma, 'Gamma', .001, 1000)
    lut = np.rint(255 * (np.arange(256) / 255) ** gamma).astype(np.uint8)
    return _lut_image(image, lut)


def piecewise(image, r1=80, s1=0, r2=170, s2=255):
    """Giãn tương phản theo các nút (0,0),(r1,s1),(r2,s2),(255,255)."""
    _image(image)
    r1 = _finite(r1, 'r₁', 0, 255)
    s1 = _finite(s1, 's₁', 0, 255)
    r2 = _finite(r2, 'r₂', 0, 255)
    s2 = _finite(s2, 's₂', 0, 255)
    if r1 >= r2:
        raise ValueError('Cần r₁ < r₂; dùng công cụ Phân ngưỡng khi hai ngưỡng trùng nhau.')
    if (r1 == 0 and s1 != 0) or (r2 == 255 and s2 != 255):
        raise ValueError('Nút ở đầu miền phải khớp (0,0) hoặc (255,255).')
    points = [(0., 0.), (r1, s1), (r2, s2), (255., 255.)]
    unique = dict(points)
    x = np.array(sorted(unique))
    y = np.array([unique[value] for value in x])
    lut = np.rint(np.interp(np.arange(256), x, y)).astype(np.uint8)
    return _lut_image(image, lut)


def threshold(image, threshold=128):
    """Phân ngưỡng chọn tay trên Y': r<T ra 0, r≥T ra 255."""
    value = _finite(threshold, 'Ngưỡng T', 0, 255)
    gray = gray_plane(image)
    result = np.where(gray >= value, 255, 0).astype(np.uint8)
    return pack(np.repeat(result[..., None], 3, axis=2), image)


def bit_plane(image, bit=7):
    """Tách một trong tám mặt phẳng bit Y', bit 0 là LSB và bit 7 là MSB."""
    bit = _integer(bit, 'Mặt phẳng bit', 0, 7)
    plane = ((gray_plane(image) >> bit) & 1) * 255
    return pack(np.repeat(plane[..., None], 3, axis=2), image)


def quantize(image, step=64):
    """Bó cụm theo g=floor(r/B)·B; B=64 cho các mức 0,64,128,192."""
    _image(image)
    step = _integer(step, 'Kích thước bó B', 1, 256)
    result = image.copy()
    rgb = image[..., :3].astype(np.uint16)
    result[..., :3] = ((rgb // step) * step).astype(np.uint8)
    return result


def equalize(image):
    """Cân bằng đúng CDF trong bài giảng: s=round(255·CDF), không trừ CDF_min."""
    _image(image)
    visible = image[..., 3] > 0
    if not np.any(visible):
        return image.copy()
    result = image.copy()
    for channel in range(3):
        counts = np.bincount(image[..., channel][visible], minlength=256)
        cdf = counts.cumsum(dtype=np.float64) / counts.sum()
        lut = np.rint(255 * cdf).astype(np.uint8)
        result[..., channel] = lut[image[..., channel]]
    return result


def match_histogram(image, reference):
    """Đối sánh từng kênh bằng G⁻¹(T(r)); chỉ dùng pixel có alpha>0 để tính CDF."""
    _image(image)
    _image(reference)
    visible = image[..., 3] > 0
    if not np.any(visible):
        return image.copy()
    target_visible = reference[..., 3] > 0
    if not np.any(target_visible):
        raise ValueError('Ảnh tham chiếu không có pixel nhìn thấy để đối sánh histogram.')
    result = image.copy()
    for channel in range(3):
        source_counts = np.bincount(image[..., channel][visible], minlength=256)
        target_counts = np.bincount(reference[..., channel][target_visible], minlength=256)
        source_cdf = source_counts.cumsum(dtype=np.float64) / source_counts.sum()
        target_cdf = target_counts.cumsum(dtype=np.float64) / target_counts.sum()
        lut = np.minimum(255, np.searchsorted(target_cdf, source_cdf, side='left')).astype(np.uint8)
        result[..., channel] = lut[image[..., channel]]
    return result


def clahe(image, clip_limit=2., tiles=8):
    """Cân bằng cục bộ có giới hạn; alpha=0 được lấp bằng trung vị nhìn thấy."""
    _image(image)
    clip_limit = _finite(clip_limit, 'Clip limit', .001, 1000)
    if isinstance(tiles, (tuple, list)):
        if len(tiles) != 2:
            raise ValueError('Lưới CLAHE cần đúng hai kích thước.')
        grid = tuple(_integer(value, 'Số ô CLAHE', 1, 64) for value in tiles)
    else:
        size = _integer(tiles, 'Số ô CLAHE', 1, 64)
        grid = (size, size)
    visible = image[..., 3] > 0
    if not np.any(visible):
        return image.copy()
    result = image.copy()
    engine = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=grid)
    for channel in range(3):
        plane = image[..., channel].copy()
        plane[~visible] = round(float(np.median(plane[visible])))
        result[..., channel] = engine.apply(plane)
    return result


def otsu(image):
    """Chọn ngưỡng cực đại phương sai giữa lớp; nền ≤t, đối tượng >t."""
    gray = gray_plane(image)
    visible = image[..., 3] > 0
    if not np.any(visible):
        return image.copy(), 0
    counts = np.bincount(gray[visible], minlength=256)
    probabilities = counts / counts.sum()
    weight = probabilities.cumsum()
    mean = (probabilities * np.arange(256)).cumsum()
    denominator = weight * (1 - weight)
    score = np.zeros(256, dtype=np.float64)
    valid = denominator > 1e-15
    score[valid] = (mean[-1] * weight[valid] - mean[valid]) ** 2 / denominator[valid]
    value = int(np.argmax(score))
    result = np.where(gray > value, 255, 0).astype(np.uint8)
    return pack(np.repeat(result[..., None], 3, axis=2), image), value
