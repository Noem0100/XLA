"""Phát hiện biên và liên kết đường thẳng theo mục 3.2 của Chương 3."""
import cv2
import numpy as np

from .adjustments import pack
from .enhancement_point import _finite, _image, _integer, gray_plane


def _visible_gray(image):
    """Lấp RGB ẩn bằng trung vị nhìn thấy để màu ẩn không tạo biên giả."""
    gray = gray_plane(image)
    visible = image[..., 3] > 0
    gray[~visible] = round(float(np.median(gray[visible]))) if np.any(visible) else 0
    return gray, visible


def _gray_result(plane, image, visible):
    """Ghép mặt phẳng xám vào RGBA, giữ alpha và đặt nền trong suốt về 0."""
    plane = np.where(visible, plane, 0)
    return pack(np.repeat(plane[..., None], 3, axis=2), image)


def gradient(image, kind='roberts', direction='magnitude'):
    """Roberts 2×2 hoặc Prewitt 3×3; |Gx|, |Gy| hay hypot, bão hòa 255.

    Mặt nạ đúng trang 9–10; Roberts đặt gốc ở ô trên trái. Đệm phản xạ
    REFLECT_101 và tính dấu bằng số thực trước khi lấy độ lớn.
    """
    _image(image)
    if kind not in ('roberts', 'prewitt'):
        raise ValueError('Toán tử biên phải là Roberts hoặc Prewitt.')
    if direction not in ('x', 'y', 'magnitude'):
        raise ValueError('Hướng gradient phải là x, y hoặc magnitude.')
    gray, visible = _visible_gray(image)
    if not np.any(visible):
        return image.copy()
    if kind == 'roberts':
        kernel_x = np.array([[1, 0], [0, -1]], dtype=np.float64)
        kernel_y = np.array([[0, 1], [-1, 0]], dtype=np.float64)
        anchor = (0, 0)
    else:
        kernel_x = np.array([[-1, 0, 1]] * 3, dtype=np.float64)
        kernel_y = kernel_x.T.copy()
        anchor = (-1, -1)
    gx = cv2.filter2D(gray, cv2.CV_64F, kernel_x, anchor=anchor, borderType=cv2.BORDER_REFLECT_101)
    gy = cv2.filter2D(gray, cv2.CV_64F, kernel_y, anchor=anchor, borderType=cv2.BORDER_REFLECT_101)
    value = np.hypot(gx, gy) if direction == 'magnitude' else np.abs(gx if direction == 'x' else gy)
    return _gray_result(value, image, visible)


def _zero_crossings(response, threshold):
    """Đổi dấu trên 8 lân cận; chọn phía gần 0 để giữ biên mảnh, không cuộn biên."""
    response = response.copy()
    response[np.abs(response) < 1e-9] = 0
    height, width = response.shape
    edges = np.zeros(response.shape, dtype=bool)
    for dy, dx in ((0, 1), (1, 0), (1, 1), (1, -1)):
        ay = slice(0, height - dy)
        by = slice(dy, height)
        ax = slice(max(0, -dx), min(width, width - dx))
        bx = slice(max(0, dx), min(width, width + dx))
        a, b = response[ay, ax], response[by, bx]
        changes = (a * b < 0) & (np.abs(a - b) >= threshold)
        # Khi hai phía bằng độ lớn, giữ phía đầu tiên để không nhân đôi biên.
        nearer_a = np.abs(a) <= np.abs(b)
        edges[ay, ax] |= changes & nearer_a
        edges[by, bx] |= changes & ~nearer_a
        if height <= 2 * dy or width <= 2 * abs(dx):
            continue
        cy = slice(dy, height - dy) if dy else slice(0, height)
        cx = slice(abs(dx), width - abs(dx)) if dx else slice(0, width)
        first_y = slice(0, height - 2 * dy)
        last_y = slice(2 * dy, height)
        if dx >= 0:
            first_x, last_x = slice(0, width - 2 * dx), slice(2 * dx, width)
        else:
            first_x, last_x = slice(-2 * dx, width), slice(0, width + 2 * dx)
        first, last = response[first_y, first_x], response[last_y, last_x]
        edges[cy, cx] |= ((response[cy, cx] == 0) & (first * last < 0)
                          & (np.abs(first - last) >= threshold))
    return edges


def log_zero_crossing(image, sigma=1.2, threshold=5.):
    """Làm trơn Gauss → Laplace 4 hướng → đổi dấu; ngưỡng là chênh lệch đáp ứng.

    Đây là biên nhị phân LoG ở trang 12–13, không phải trị tuyệt đối Laplace.
    Sigma tăng sẽ loại bớt chi tiết; ngưỡng tăng loại các đổi dấu yếu do nhiễu.
    """
    _image(image)
    sigma = _finite(sigma, 'Sigma Gauss', .1, 50.)
    threshold = _finite(threshold, 'Ngưỡng đổi dấu', 0., 2040.)
    gray, visible = _visible_gray(image)
    if not np.any(visible):
        return image.copy()
    blurred = cv2.GaussianBlur(gray.astype(np.float64), (0, 0), sigma,
                               borderType=cv2.BORDER_REFLECT_101)
    response = cv2.Laplacian(blurred, cv2.CV_64F, ksize=1, borderType=cv2.BORDER_REFLECT_101)
    edges = _zero_crossings(response, threshold)
    return _gray_result(edges.astype(np.uint8) * 255, image, visible)


def hough_lines(image, mode='probabilistic', threshold=50, min_length=40,
                max_gap=10, canny_low=60, canny_high=150, line_width=2, max_lines=100):
    """Canny rồi Hough chuẩn/xác suất; vẽ tối đa max_lines đường đỏ lên ảnh gốc.

    Bỏ phiếu với bước rho=1 pixel, theta=1 độ (trang 18–21, 51). Chỉ Hough
    xác suất dùng độ dài tối thiểu và khoảng đứt đoạn tối đa. Màu vẽ là RGB.
    """
    _image(image)
    if mode not in ('standard', 'probabilistic'):
        raise ValueError('Hough phải là standard (chuẩn) hoặc probabilistic (xác suất).')
    threshold = _integer(threshold, 'Số phiếu Hough', 1, 1000000)
    min_length = _finite(min_length, 'Độ dài tối thiểu', 0, 1000000)
    max_gap = _finite(max_gap, 'Khoảng đứt tối đa', 0, 1000000)
    canny_low = _finite(canny_low, 'Ngưỡng Canny thấp', 0, 2040)
    canny_high = _finite(canny_high, 'Ngưỡng Canny cao', 0, 2040)
    if canny_low >= canny_high:
        raise ValueError('Ngưỡng Canny thấp phải nhỏ hơn ngưỡng cao.')
    line_width = _integer(line_width, 'Độ dày nét', 1, 20)
    max_lines = _integer(max_lines, 'Số đường tối đa', 1, 1000)
    gray, visible = _visible_gray(image)
    if not np.any(visible) or min(gray.shape) < 2:
        return image.copy()
    edges = cv2.Canny(gray, canny_low, canny_high)
    edges[~visible] = 0
    rgb = np.ascontiguousarray(image[..., :3]).copy()
    if mode == 'probabilistic':
        lines = cv2.HoughLinesP(edges, 1, np.pi / 180, threshold,
                                minLineLength=min_length, maxLineGap=max_gap)
        if lines is not None:
            for x1, y1, x2, y2 in lines.reshape(-1, 4)[:max_lines]:
                cv2.line(rgb, (int(x1), int(y1)), (int(x2), int(y2)),
                         (255, 64, 64), line_width, cv2.LINE_8)
    else:
        lines = cv2.HoughLines(edges, 1, np.pi / 180, threshold)
        extent = int(np.ceil(np.hypot(*gray.shape))) + 1
        if lines is not None:
            for rho, theta in lines.reshape(-1, 2)[:max_lines]:
                cosine, sine = float(np.cos(theta)), float(np.sin(theta))
                x, y = float(rho) * cosine, float(rho) * sine
                p1 = (round(x - extent * sine), round(y + extent * cosine))
                p2 = (round(x + extent * sine), round(y - extent * cosine))
                cv2.line(rgb, p1, p2, (255, 64, 64), line_width, cv2.LINE_8)
    rgb[~visible] = image[..., :3][~visible]
    return pack(rgb, image)
