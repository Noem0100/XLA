"""Lọc không gian và đánh giá ảnh theo Chương 2, đầu vào RGBA 8 bit."""
import cv2
import numpy as np

from .adjustments import pack


def _image(image):
    """Kiểm tra hợp đồng RGBA uint8 và kích thước ảnh khác rỗng."""
    if (not isinstance(image, np.ndarray) or image.dtype != np.uint8
            or image.ndim != 3 or image.shape[2] != 4 or min(image.shape[:2]) < 1):
        raise ValueError('Ảnh phải là mảng RGBA uint8 với chiều rộng, chiều cao lớn hơn 0.')
    return image


def _number(value, name, minimum=0., maximum=None, strict=False):
    """Đọc tham số hữu hạn trong khoảng để tránh chia cho 0 và tràn số."""
    if isinstance(value, (bool, np.bool_)):
        raise ValueError(f'{name} phải là một số hữu hạn.')
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f'{name} phải là một số hữu hạn.') from exc
    if (not np.isfinite(result) or result < minimum or (strict and result == minimum)
            or (maximum is not None and result > maximum)):
        raise ValueError(f'{name} nằm ngoài khoảng cho phép.')
    return result


def _integer(value, name, minimum, maximum):
    """Chỉ nhận số nguyên thật trong khoảng giới hạn bộ nhớ và kích thước mặt nạ."""
    if (isinstance(value, (bool, np.bool_)) or not isinstance(value, (int, np.integer))
            or not minimum <= value <= maximum):
        raise ValueError(f'{name} phải là số nguyên từ {minimum} đến {maximum}.')
    return int(value)


def _size(value, name='Cỡ cửa sổ', maximum=31):
    """Chọn cửa sổ lẻ từ 3 để mọi bộ lọc có cùng quy ước tâm."""
    result = _integer(value, name, 3, maximum)
    if result % 2 == 0:
        raise ValueError(f'{name} phải là số lẻ.')
    return result


def _median_reflect(rgb, size):
    """Đệm REFLECT_101 trước khi gọi medianBlur vốn mặc định dùng REPLICATE."""
    radius = size // 2
    padded = cv2.copyMakeBorder(rgb, radius, radius, radius, radius, cv2.BORDER_REFLECT_101)
    return cv2.medianBlur(padded, size)[radius:radius + rgb.shape[0], radius:radius + rgb.shape[1]]


def smooth(image, kind='mean', size=3, sigma=1.):
    """Làm trơn RGB với biên REFLECT_101; sigma=0 dùng mặt nạ Gauss tự động OpenCV."""
    _image(image)
    size = _size(size)
    sigma = _number(sigma, 'Sigma', maximum=100.)
    rgb = np.ascontiguousarray(image[..., :3])
    if kind == 'mean':
        result = cv2.blur(rgb, (size, size), borderType=cv2.BORDER_REFLECT_101)
    elif kind == 'gaussian':
        result = cv2.GaussianBlur(rgb, (size, size), sigma, borderType=cv2.BORDER_REFLECT_101)
    elif kind == 'median':
        result = _median_reflect(rgb, size)
    else:
        raise ValueError('Kiểu làm trơn phải là mean, gaussian hoặc median.')
    return pack(result, image)


def nearest_mean(image, size=3, neighbors=3, threshold=2.):
    """Trung bình K mức gần tâm trên từng kênh; chỉ thay nếu sai khác lớn hơn ngưỡng."""
    _image(image)
    size = _size(size)
    neighbors = _integer(neighbors, 'Số láng giềng K', 1, size * size)
    threshold = _number(threshold, 'Ngưỡng thay thế', maximum=255.)
    rgb = np.ascontiguousarray(image[..., :3])
    radius = size // 2
    padded = cv2.copyMakeBorder(rgb, radius, radius, radius, radius, cv2.BORDER_REFLECT_101)
    windows = np.lib.stride_tricks.sliding_window_view(padded, (size, size), axis=(0, 1))
    result = rgb.copy()
    height, width = rgb.shape[:2]
    # Tối đa khoảng một triệu phần tử cửa sổ mỗi khối, kể cả ảnh rất rộng.
    budget = 1_000_000
    columns = min(width, max(1, budget // (3 * size * size)))
    rows = max(1, budget // (columns * 3 * size * size))
    for top in range(0, height, rows):
        bottom = min(height, top + rows)
        for left in range(0, width, columns):
            right = min(width, left + columns)
            values = windows[top:bottom, left:right].reshape(bottom - top, right - left, 3, size * size)
            center = rgb[top:bottom, left:right].astype(np.int16)
            distances = np.abs(values.astype(np.int16) - center[..., None])
            closest = np.argpartition(distances, neighbors - 1, axis=-1)[..., :neighbors]
            average = np.take_along_axis(values, closest, axis=-1).mean(axis=-1)
            result[top:bottom, left:right] = np.where(
                np.abs(average - center) > threshold, np.rint(average), center).astype(np.uint8)
    return pack(result, image)


def sobel(image, direction='magnitude'):
    """Hiển thị |Gx|, |Gy| hoặc sqrt(Gx²+Gy²) trên ảnh xám, clip 0–255, không chuẩn hóa."""
    _image(image)
    if direction not in ('magnitude', 'x', 'y'):
        raise ValueError('Hướng Sobel phải là magnitude, x hoặc y.')
    gray = cv2.cvtColor(np.ascontiguousarray(image[..., :3]), cv2.COLOR_RGB2GRAY).astype(np.float64)
    gx = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3, borderType=cv2.BORDER_REFLECT_101)
    gy = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3, borderType=cv2.BORDER_REFLECT_101)
    values = np.hypot(gx, gy) if direction == 'magnitude' else np.abs(gx if direction == 'x' else gy)
    return pack(np.repeat(values[..., None], 3, axis=2), image)


def laplacian(image, amount=1., edges_only=False):
    """Mặt nạ Laplace 4 lân cận tâm âm; làm nét f−k∇²f hoặc xem |∇²f| có clip."""
    _image(image)
    amount = _number(amount, 'Hệ số Laplacian', maximum=20.)
    if not isinstance(edges_only, (bool, np.bool_)):
        raise ValueError('Chế độ xem biên phải là giá trị đúng/sai.')
    rgb = image[..., :3].astype(np.float64)
    lap = cv2.Laplacian(rgb, cv2.CV_64F, ksize=1, borderType=cv2.BORDER_REFLECT_101)
    return pack(np.abs(lap) if edges_only else rgb - amount * lap, image)


def unsharp(image, sigma=1., amount=1., size=0):
    """Unsharp/high-boost: f+k(f−Gauss(f)); size=0 suy cỡ từ sigma, clip kết quả 8 bit."""
    _image(image)
    sigma = _number(sigma, 'Sigma', maximum=100.)
    amount = _number(amount, 'Hệ số high-boost', maximum=20.)
    if size != 0 or isinstance(size, (bool, np.bool_)):
        size = _size(size)
    elif not isinstance(size, (int, np.integer)):
        raise ValueError('Cỡ cửa sổ phải là số nguyên 0 hoặc số lẻ từ 3 đến 31.')
    if size == 0 and sigma == 0:
        raise ValueError('Sigma phải lớn hơn 0 khi cỡ cửa sổ bằng 0.')
    rgb = image[..., :3].astype(np.float64)
    blurred = cv2.GaussianBlur(rgb, (size, size), sigma, borderType=cv2.BORDER_REFLECT_101)
    return pack(rgb + amount * (rgb - blurred), image)


def adaptive_median(image, max_size=7):
    """Trung vị thích nghi hai bước A/B theo từng kênh, tăng cửa sổ 3..max_size."""
    _image(image)
    max_size = _size(max_size, 'Cỡ cửa sổ tối đa')
    rgb = np.ascontiguousarray(image[..., :3])
    result = rgb.copy()
    unresolved = np.ones(rgb.shape, dtype=bool)
    median = rgb
    for size in range(3, max_size + 1, 2):
        kernel = np.ones((size, size), dtype=np.uint8)
        minimum = cv2.erode(rgb, kernel, borderType=cv2.BORDER_REFLECT_101)
        maximum = cv2.dilate(rgb, kernel, borderType=cv2.BORDER_REFLECT_101)
        median = _median_reflect(rgb, size)
        stage_a = (median > minimum) & (median < maximum)
        stage_b = (rgb > minimum) & (rgb < maximum)
        resolved = unresolved & stage_a
        result[resolved] = np.where(stage_b, rgb, median)[resolved]
        unresolved &= ~stage_a
        if not np.any(unresolved):
            break
    result[unresolved] = median[unresolved]
    return pack(result, image)


def average_images(images):
    """Cộng dồn RGB theo trọng số alpha của ít nhất hai ảnh cùng cỡ; giữ alpha ảnh đầu."""
    iterator = iter(images)
    try:
        first = _image(next(iterator))
    except StopIteration as exc:
        raise ValueError('Cần ít nhất hai ảnh để tính trung bình.') from exc
    alpha = first[..., 3].astype(np.float64)
    total = first[..., :3].astype(np.float64) * alpha[..., None]
    weight = alpha.copy()
    count = 1
    for image in iterator:
        _image(image)
        if image.shape != first.shape:
            raise ValueError('Các ảnh lấy trung bình phải có cùng kích thước RGBA.')
        alpha = image[..., 3].astype(np.float64)
        total += image[..., :3].astype(np.float64) * alpha[..., None]
        weight += alpha
        count += 1
    if count < 2:
        raise ValueError('Cần ít nhất hai ảnh để tính trung bình.')
    average = np.divide(total, weight[..., None], out=np.zeros_like(total), where=weight[..., None] > 0)
    return pack(average, first)


def quality_metrics(image, reference):
    """MSE/PSNR và SSIM Gaussian 11×11 σ=1.5; chỉ xét giao pixel có alpha>0."""
    _image(image)
    _image(reference)
    if image.shape != reference.shape:
        raise ValueError('Ảnh đánh giá và ảnh tham chiếu phải có cùng kích thước RGBA.')
    visible = (image[..., 3] > 0) & (reference[..., 3] > 0)
    if not np.any(visible):
        raise ValueError('Hai ảnh không có pixel nhìn thấy chung để đánh giá.')
    difference = image[..., :3][visible].astype(np.float64) - reference[..., :3][visible]
    mse = float(np.mean(difference ** 2))
    psnr = float('inf') if mse == 0 else float(10 * np.log10(255. ** 2 / mse))
    mask = visible.astype(np.float64)

    def local_mean(values):
        """Chuẩn hóa cửa sổ Gaussian theo pixel hợp lệ, không đưa RGB ẩn vào thống kê."""
        return cv2.GaussianBlur(values * mask, (11, 11), 1.5,
                                borderType=cv2.BORDER_REFLECT_101) / normalizer

    normalizer = cv2.GaussianBlur(mask, (11, 11), 1.5, borderType=cv2.BORDER_REFLECT_101)
    normalizer = np.maximum(normalizer, np.finfo(np.float64).eps)
    c1, c2 = (.01 * 255) ** 2, (.03 * 255) ** 2
    similarities = []
    for channel in range(3):
        x = image[..., channel].astype(np.float64)
        y = reference[..., channel].astype(np.float64)
        mean_x, mean_y = local_mean(x), local_mean(y)
        variance_x = np.maximum(0, local_mean(x * x) - mean_x * mean_x)
        variance_y = np.maximum(0, local_mean(y * y) - mean_y * mean_y)
        covariance = local_mean(x * y) - mean_x * mean_y
        numerator = (2 * mean_x * mean_y + c1) * (2 * covariance + c2)
        denominator = (mean_x ** 2 + mean_y ** 2 + c1) * (variance_x + variance_y + c2)
        similarities.append(float(np.mean(np.clip(numerator[visible] / denominator[visible], -1, 1))))
    return {'mse': mse, 'psnr': psnr, 'ssim': float(np.mean(similarities))}


def pipeline(image, median_size=3, clip_limit=2., tiles=8, sigma=1., amount=.5):
    """Khử muối tiêu bằng trung vị → CLAHE trên độ sáng LAB → unsharp nhẹ."""
    _image(image)
    median_size = _size(median_size)
    clip_limit = _number(clip_limit, 'Ngưỡng CLAHE', maximum=100., strict=True)
    tiles = _integer(tiles, 'Số ô CLAHE', 1, 64)
    sigma = _number(sigma, 'Sigma', maximum=100., strict=True)
    amount = _number(amount, 'Hệ số high-boost', maximum=20.)
    cleaned = smooth(image, 'median', median_size)
    lab = cv2.cvtColor(cleaned[..., :3], cv2.COLOR_RGB2LAB)
    lab[..., 0] = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=(tiles, tiles)).apply(lab[..., 0])
    enhanced = pack(cv2.cvtColor(lab, cv2.COLOR_LAB2RGB), image)
    return unsharp(enhanced, sigma=sigma, amount=amount)
