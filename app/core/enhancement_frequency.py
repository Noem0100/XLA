"""Miền tần số Chương 2: Fourier, thông thấp/cao, chắn và khôi phục ảnh.

Tần số nhập theo phần của cạnh ngắn sau đệm nên có thể dùng cùng tham số
cho bản xem trước và ảnh đầy đủ. Mọi phép xử lý giữ alpha và không sửa ảnh
đầu vào. Giới hạn kích thước FFT để tránh cấp phát nhiều GB ngoài ý muốn.
"""
import cv2
import numpy as np


MAX_FFT_PIXELS = 32_000_000


def _image(image):
    """Kiểm tra hợp đồng ảnh RGBA 8 bit có kích thước khác không."""
    if not isinstance(image, np.ndarray) or image.dtype != np.uint8 or image.ndim != 3 or image.shape[2] != 4 or min(image.shape[:2]) < 1:
        raise ValueError('Cần ảnh RGBA 8 bit không rỗng.')
    return image.shape[:2]


def _number(value, name, minimum=None, maximum=None, strict=False):
    """Đổi tham số thành số thực hữu hạn và kiểm tra khoảng cho phép."""
    try:
        value = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f'{name} phải là số hữu hạn.') from exc
    if not np.isfinite(value) or (minimum is not None and (value <= minimum if strict else value < minimum)) or (maximum is not None and value > maximum):
        raise ValueError(f'{name} nằm ngoài khoảng cho phép.')
    return value


def _shape(image, minimum=0):
    """Đệm ít nhất gấp đôi mỗi chiều và chặn khối FFT quá lớn."""
    h, w = _image(image)
    shape = max(2 * h, minimum), max(2 * w, minimum)
    if shape[0] * shape[1] > MAX_FFT_PIXELS:
        raise ValueError('Ảnh quá lớn cho FFT (tối đa 32 triệu điểm sau đệm). Hãy thu nhỏ ảnh trước khi lọc miền tần số.')
    return shape


def _distance_squared(shape):
    """Khoảng cách tới DC ở thứ tự DFT gốc, tương đương dịch tâm phổ."""
    y = (np.fft.fftfreq(shape[0]) * shape[0]).astype(np.float32)
    x = (np.fft.fftfreq(shape[1]) * shape[1]).astype(np.float32)
    return y[:, None] ** 2 + x[None, :] ** 2


def _low_transfer(shape, family, cutoff, order):
    """Tạo H thông thấp lý tưởng, Butterworth hoặc Gauss theo Chương 2."""
    if family not in ('ideal', 'butterworth', 'gaussian'):
        raise ValueError('Họ bộ lọc phải là ideal, butterworth hoặc gaussian.')
    cutoff = _number(cutoff, 'Tần số cắt', 0, .5, strict=True)
    if not isinstance(order, (int, np.integer)) or not 1 <= order <= 20:
        raise ValueError('Bậc Butterworth phải là số nguyên từ 1 đến 20.')
    distance = _distance_squared(shape)
    scale = (cutoff * min(shape)) ** 2
    if family == 'ideal':
        return (distance <= scale).astype(np.float32)
    distance /= scale
    if family == 'gaussian':
        distance *= -.5
        np.exp(distance, out=distance)
    else:
        # Tính trong log để bậc lớn không tràn số khi D0 rất nhỏ.
        with np.errstate(divide='ignore'):
            np.log(distance, out=distance)
        distance *= order
        np.clip(distance, -80, 80, out=distance)
        np.exp(distance, out=distance)
        distance += 1
        np.reciprocal(distance, out=distance)
        distance[0, 0] = 1
    return distance


def _apply_transfer(image, transfer, *, border='zero', pass_type='low', amount=1., logarithmic=False):
    """Lọc từng kênh bằng DFT float32, xử lý có dấu rồi mới bão hòa 8 bit."""
    h, w = _image(image)
    shape = transfer.shape[:2]
    result = image.copy()
    visible = image[..., 3] > 0
    for channel in range(3):
        source = np.where(visible, image[..., channel], 0).astype(np.float32)
        working = np.log1p(source) if logarithmic else source
        if border == 'reflect':
            padded = cv2.copyMakeBorder(working, 0, shape[0] - h, 0, shape[1] - w, cv2.BORDER_REFLECT_101)
        else:
            padded = np.zeros(shape, dtype=np.float32)
            padded[:h, :w] = working
        transformed = cv2.dft(padded, flags=cv2.DFT_COMPLEX_OUTPUT)
        del padded, working
        if transfer.ndim == 2:
            transformed *= transfer[..., None]
        else:
            transformed = cv2.mulSpectrums(transformed, transfer, 0)
        restored = cv2.idft(transformed, flags=cv2.DFT_SCALE | cv2.DFT_REAL_OUTPUT)[:h, :w]
        del transformed
        if logarithmic:
            # expm1 vượt ln(256) cũng sẽ bị clip 255, tránh overflow không cần thiết.
            restored = np.expm1(np.clip(restored, -80, np.log(256.)))
        elif pass_type == 'high':
            restored = 128 + restored
        elif pass_type == 'boost':
            restored = source + amount * restored
        result[..., channel] = np.clip(np.rint(restored), 0, 255).astype(np.uint8)
    return result


def spectrum(image):
    """Phổ biên độ log1p dịch tâm của Y', chuẩn hóa về ảnh xám 8 bit."""
    h, w = _image(image)
    if h * w > MAX_FFT_PIXELS:
        raise ValueError('Ảnh quá lớn để xem phổ Fourier; hãy thu nhỏ ảnh trước.')
    rgb = image[..., :3]
    gray = (rgb[..., 0] * np.float32(.2126) + rgb[..., 1] * np.float32(.7152) + rgb[..., 2] * np.float32(.0722))
    gray[image[..., 3] == 0] = 0
    transformed = cv2.dft(gray, flags=cv2.DFT_COMPLEX_OUTPUT)
    magnitude = np.log1p(cv2.magnitude(transformed[..., 0], transformed[..., 1]))
    magnitude = np.fft.fftshift(magnitude)
    minimum, maximum = float(magnitude.min()), float(magnitude.max())
    values = np.zeros((h, w), dtype=np.uint8) if maximum - minimum < 1e-8 else np.clip(np.rint((magnitude - minimum) * 255 / (maximum - minimum)), 0, 255).astype(np.uint8)
    result = image.copy()
    result[..., :3] = values[..., None]
    return result


def frequency_filter(image, family='gaussian', pass_type='low', cutoff=.08, order=2, amount=1.):
    """Thông thấp, cao hoặc tăng nét; D0 = cutoff × cạnh ngắn sau đệm 2M×2N.

    Thông cao là ảnh phân tích có mức 128 ở đáp ứng bằng 0 để giữ cả dấu âm.
    Chế độ boost dùng f + amount × HP(f), còn low trả đáp ứng thông thấp.
    """
    if pass_type not in ('low', 'high', 'boost'):
        raise ValueError('Chế độ lọc phải là low, high hoặc boost.')
    amount = _number(amount, 'Cường độ tăng nét', 0, 10)
    shape = _shape(image)
    transfer = _low_transfer(shape, family, cutoff, order)
    if pass_type != 'low':
        transfer = 1 - transfer
    return _apply_transfer(image, transfer, pass_type=pass_type, amount=amount)


def notch_filter(image, offset_x=.15, offset_y=0., radius=.025):
    """Lọc chắn Gauss tại cặp đỉnh đối xứng; tọa độ/radius theo cạnh ngắn đệm.

    Điểm ở DC được giữ nguyên. Không cho chọn cặp đỉnh quá gần gốc vì khi đó
    không phân biệt được nhiễu tuần hoàn với độ sáng nền của ảnh.
    """
    shape = _shape(image)
    offset_x = _number(offset_x, 'Vị trí ngang', -.5, .5)
    offset_y = _number(offset_y, 'Vị trí dọc', -.5, .5)
    radius = _number(radius, 'Bán kính chắn', 0, .25, strict=True)
    if np.hypot(offset_x, offset_y) <= 2 * radius:
        raise ValueError('Chọn đỉnh nhiễu cách DC hơn hai lần bán kính chắn.')
    extent = min(shape)
    x = (np.fft.fftfreq(shape[1]) * shape[1]).astype(np.float32)
    y = (np.fft.fftfreq(shape[0]) * shape[0]).astype(np.float32)
    transfer = np.ones(shape, dtype=np.float32)
    for sign in (-1, 1):
        dx = np.abs(x - sign * offset_x * extent)
        dy = np.abs(y - sign * offset_y * extent)
        dx = np.minimum(dx, shape[1] - dx)
        dy = np.minimum(dy, shape[0] - dy)
        distance = dy[:, None] ** 2 + dx[None, :] ** 2
        distance *= -1 / (2 * (radius * extent) ** 2)
        np.exp(distance, out=distance)
        transfer *= 1 - distance
    transfer[0, 0] = 1
    return _apply_transfer(image, transfer)


def restore(image, method='wiener', psf='gaussian', size=7, sigma=1.5, noise=.01, epsilon=.01):
    """Lọc ngược/Wiener với PSF giả định Gauss hoặc chuyển động ngang.

    Đệm phản chiếu ít nhất gấp đôi để giảm đường viền; PSF được đưa tâm về
    gốc trước DFT. Lọc ngược bỏ các tần số |H| < epsilon. Wiener dùng
    conj(H)/(|H|² + noise), noise là xấp xỉ tỉ số nhiễu/tín hiệu K.
    Hiệu quả phụ thuộc mức khớp giữa PSF giả định và hiện tượng mờ thật.
    """
    if method not in ('wiener', 'inverse') or psf not in ('gaussian', 'motion'):
        raise ValueError('Chọn wiener/inverse và PSF gaussian/motion.')
    if not isinstance(size, (int, np.integer)) or size < 1 or size > 63 or size % 2 != 1:
        raise ValueError('Kích thước PSF phải lẻ, từ 1 đến 63.')
    sigma = _number(sigma, 'Sigma PSF', 0, 20, strict=True)
    noise = _number(noise, 'Tỉ số nhiễu K', 0, 10)
    epsilon = _number(epsilon, 'Ngưỡng ổn định', 0, 1, strict=True)
    shape = _shape(image, minimum=size + 1)
    if psf == 'gaussian':
        vector = cv2.getGaussianKernel(size, sigma, cv2.CV_32F)
        kernel = vector @ vector.T
    else:
        kernel = np.zeros((size, size), dtype=np.float32)
        kernel[size // 2] = 1 / size
    plane = np.zeros(shape, dtype=np.float32)
    plane[:size, :size] = kernel
    plane = np.roll(plane, (-(size // 2), -(size // 2)), axis=(0, 1))
    transfer = cv2.dft(plane, flags=cv2.DFT_COMPLEX_OUTPUT)
    del plane
    power = transfer[..., 0] ** 2 + transfer[..., 1] ** 2
    if method == 'wiener':
        denominator = np.maximum(power + noise, np.finfo(np.float32).eps)
        transfer[..., 0] /= denominator
        transfer[..., 1] /= -denominator
    else:
        valid = power >= epsilon ** 2
        denominator = np.maximum(power, epsilon ** 2)
        transfer[..., 0] = np.where(valid, transfer[..., 0] / denominator, 0)
        transfer[..., 1] = np.where(valid, -transfer[..., 1] / denominator, 0)
    return _apply_transfer(image, transfer, border='reflect')


def homomorphic(image, cutoff=.08, low_gain=.5, high_gain=1.5, sharpness=1.):
    """Lọc đồng hình log1p → H → expm1 để giảm chiếu sáng chậm, tăng chi tiết."""
    shape = _shape(image)
    cutoff = _number(cutoff, 'Tần số cắt', 0, .5, strict=True)
    low_gain = _number(low_gain, 'Hệ số tần thấp', 0, 2)
    high_gain = _number(high_gain, 'Hệ số tần cao', low_gain, 5)
    sharpness = _number(sharpness, 'Độ dốc', 0, 20, strict=True)
    transfer = _distance_squared(shape)
    transfer *= -sharpness / (cutoff * min(shape)) ** 2
    np.exp(transfer, out=transfer)
    transfer = low_gain + (high_gain - low_gain) * (1 - transfer)
    return _apply_transfer(image, transfer, logarithmic=True)
