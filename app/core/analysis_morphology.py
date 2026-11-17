"""Hình thái học nhị phân và ảnh xám theo mục 3.4, Chương 3."""
import cv2
import numpy as np

from .adjustments import pack
from .enhancement_point import _finite, _image, _integer, gray_plane


def _boolean(value, name):
    """Không âm thầm hiểu chuỗi hoặc một số bất kỳ thành giá trị đúng/sai."""
    if not isinstance(value, (bool, np.bool_)):
        raise ValueError(f'{name} phải là giá trị đúng hoặc sai.')
    return bool(value)


def _kernel(size, shape):
    """Phần tử cấu trúc lẻ, có gốc ở tâm: vuông, chữ thập hoặc elip."""
    size = _integer(size, 'Kích thước phần tử cấu trúc', 1, 99)
    if size % 2 == 0:
        raise ValueError('Kích thước phần tử cấu trúc phải là số lẻ.')
    shapes = {'rect': cv2.MORPH_RECT, 'cross': cv2.MORPH_CROSS, 'ellipse': cv2.MORPH_ELLIPSE}
    if shape not in shapes:
        raise ValueError('Hình phần tử cấu trúc phải là rect, cross hoặc ellipse.')
    return cv2.getStructuringElement(shapes[shape], (size, size))


def _binary(image, threshold, invert):
    """Đối tượng trắng g>T, hoặc g≤T nếu đảo; pixel alpha=0 luôn thuộc nền."""
    threshold = _finite(threshold, 'Ngưỡng nhị phân', 0, 255)
    invert = _boolean(invert, 'Đảo đối tượng')
    gray = gray_plane(image)
    foreground = gray <= threshold if invert else gray > threshold
    return foreground & (image[..., 3] > 0)


def _result(plane, image):
    """Xuất ảnh xám RGBA và giữ alpha gốc, không sửa mảng đầu vào."""
    plane = np.where(image[..., 3] > 0, plane, 0).astype(np.uint8)
    return pack(np.repeat(plane[..., None], 3, axis=2), image)


def morphology(image, operation='dilate', size=3, shape='cross', iterations=1,
               threshold=127, invert=False, grayscale=False):
    """Giãn, co, mở, đóng, trích biên hoặc top-hat trên ảnh nhị phân/ảnh xám.

    Nhị phân dùng nền 0 ngoài ảnh; đệm đủ rộng cho phép đóng không cắt vật
    thể sát mép. Ảnh xám dùng max/min trên các điểm nhìn thấy, ngoài ảnh và
    pixel ẩn không tham gia cực trị. Top-hat = ảnh − mở, biên = ảnh − co.
    Iterations là số lần co/giãn ở mỗi bước, không phải lặp cả mở/đóng.
    """
    _image(image)
    if operation not in ('dilate', 'erode', 'open', 'close', 'boundary', 'top_hat'):
        raise ValueError('Phép hình thái học không hợp lệ.')
    kernel = _kernel(size, shape)
    iterations = _integer(iterations, 'Số lần co/giãn', 1, 20)
    grayscale = _boolean(grayscale, 'Chế độ ảnh xám')
    foreground = _binary(image, threshold, invert)
    visible = image[..., 3] > 0
    if not np.any(visible):
        return image.copy()
    if grayscale:
        source = gray_plane(image)

        def dilate(plane):
            result = plane.copy()
            for _ in range(iterations):
                result[~visible] = 0
                result = cv2.dilate(result, kernel, borderType=cv2.BORDER_CONSTANT, borderValue=0)
            return result

        def erode(plane):
            result = plane.copy()
            for _ in range(iterations):
                result[~visible] = 255
                result = cv2.erode(result, kernel, borderType=cv2.BORDER_CONSTANT, borderValue=255)
            return result
    else:
        radius = (kernel.shape[0] // 2) * iterations
        source = np.pad(foreground.astype(np.uint8) * 255, radius, constant_values=0)

        def dilate(plane):
            return cv2.dilate(plane, kernel, iterations=iterations,
                              borderType=cv2.BORDER_CONSTANT, borderValue=0)

        def erode(plane):
            return cv2.erode(plane, kernel, iterations=iterations,
                             borderType=cv2.BORDER_CONSTANT, borderValue=0)

    if operation == 'dilate':
        result = dilate(source)
    elif operation == 'erode':
        result = erode(source)
    elif operation == 'open':
        result = dilate(erode(source))
    elif operation == 'close':
        result = erode(dilate(source))
    elif operation == 'boundary':
        result = cv2.subtract(source, erode(source))
    else:
        result = cv2.subtract(source, dilate(erode(source)))
    if not grayscale:
        result = result[radius:radius + image.shape[0], radius:radius + image.shape[1]]
    return _result(result, image)


def fill_holes(image, threshold=127, invert=False, connectivity=4):
    """Lấp mọi miền nền kín; nền chạm mép hoặc vùng trong suốt luôn được giữ.

    Tương đương tái tạo nền từ mầm biên bằng giãn có ràng buộc (trang 47),
    dùng nhãn liên thông để tránh hàng nghìn vòng lặp trên ảnh lớn.
    Connectivity quy định liên thông của nền cần lấp, không phải vật thể.
    """
    _image(image)
    connectivity = _integer(connectivity, 'Liên thông nền', 4, 8)
    if connectivity not in (4, 8):
        raise ValueError('Liên thông nền chỉ nhận 4 hoặc 8.')
    foreground = _binary(image, threshold, invert)
    visible = image[..., 3] > 0
    if not np.any(visible):
        return image.copy()
    count, labels = cv2.connectedComponents((~foreground).astype(np.uint8), connectivity=connectivity)
    exterior = np.zeros(count, dtype=bool)
    exterior[labels[0, :]] = True
    exterior[labels[-1, :]] = True
    exterior[labels[:, 0]] = True
    exterior[labels[:, -1]] = True
    exterior[labels[~visible]] = True
    # Nhãn 0 là tiền cảnh sẵn có, không phải một thành phần của nền.
    holes = (labels > 0) & ~exterior[labels]
    result = (foreground | holes) & visible
    return _result(result.astype(np.uint8) * 255, image)


def hit_or_miss(image, threshold=127, invert=False, rotation=0):
    """Dò góc trên trái theo ví dụ trang 45, có thể quay mẫu ngược chiều kim đồng hồ.

    B₁ gồm tâm, phải, dưới; B₂ gồm trên, trái; các ô chéo không bị ràng buộc.
    Phép trúng trật = co(A,B₁) giao co(phần bù A,B₂). Ngoài ảnh là nền.
    """
    _image(image)
    rotation = _integer(rotation, 'Góc quay mẫu', 0, 270)
    if rotation not in (0, 90, 180, 270):
        raise ValueError('Góc quay mẫu chỉ nhận 0, 90, 180 hoặc 270 độ.')
    foreground = _binary(image, threshold, invert)
    if not np.any(image[..., 3] > 0):
        return image.copy()
    pattern = np.rot90(np.array([[0, -1, 0], [-1, 1, 1], [0, 1, 0]], dtype=np.int8), rotation // 90)
    hit_kernel = (pattern == 1).astype(np.uint8)
    miss_kernel = (pattern == -1).astype(np.uint8)
    hit = cv2.erode(foreground.astype(np.uint8), hit_kernel,
                    borderType=cv2.BORDER_CONSTANT, borderValue=0)
    miss = cv2.erode((~foreground).astype(np.uint8), miss_kernel,
                     borderType=cv2.BORDER_CONSTANT, borderValue=1)
    return _result((hit & miss) * 255, image)


def skeleton(image, threshold=127, invert=False, shape='cross'):
    """Khung xương hình thái học S=∪k[(A⊖kB) − mở(A⊖kB,B)], trang 48.

    Với B=3×3, các lớp co tương ứng khoảng cách L1 (chữ thập/elip) hoặc
    Chebyshev (vuông). Hợp trên bằng các cực đại không nghiêm ngặt của
    khoảng cách trong B, tránh lặp co hàng nghìn lần trên ảnh lớn.
    Khung có thể rộng hai pixel khi đối tượng có bề rộng chẵn.
    """
    _image(image)
    kernel = _kernel(3, shape)
    foreground = _binary(image, threshold, invert)
    if not np.any(image[..., 3] > 0):
        return image.copy()
    padded = np.pad(foreground.astype(np.uint8), 1, constant_values=0)
    metric = cv2.DIST_C if shape == 'rect' else cv2.DIST_L1
    distance = cv2.distanceTransform(padded, metric, 3)[1:-1, 1:-1]
    neighborhood = cv2.dilate(distance, kernel, borderType=cv2.BORDER_CONSTANT, borderValue=0)
    centers = foreground & (distance >= neighborhood)
    return _result(centers.astype(np.uint8) * 255, image)
