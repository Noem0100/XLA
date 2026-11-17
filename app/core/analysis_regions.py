"""Phân đoạn dựa trên vùng, Chương 3 trang 23–37.

Mọi hàm giữ alpha và mảng đầu vào; pixel alpha=0 không tham gia thống kê,
liên thông hoặc khởi tạo cụm. K-means học trên tối đa 32768 mẫu xác định,
rồi gán lại tất cả pixel nhìn thấy theo từng khối để giới hạn bộ nhớ.
"""
import cv2
import numpy as np

from .enhancement_point import _finite, _image, _integer, gray_plane


def _boolean(value, name):
    if not isinstance(value, (bool, np.bool_)):
        raise ValueError(f'{name} phải là giá trị bật/tắt.')
    return bool(value)


def _connectivity(value):
    value = _integer(value, 'Liên thông', 4, 8)
    if value not in (4, 8):
        raise ValueError('Liên thông phải là 4 hoặc 8.')
    return value


def _render(image, pixels):
    """Đóng gói xám/RGB, xóa RGB ẩn để chúng không trở thành vùng kết quả."""
    result = image.copy()
    result[..., :3] = pixels[..., None] if pixels.ndim == 2 else pixels
    result[image[..., 3] == 0, :3] = 0
    return result


def _binary(image, threshold, invert):
    threshold = _finite(threshold, 'Ngưỡng T', 0, 255)
    invert = _boolean(invert, 'Đảo nền/vật thể')
    foreground = gray_plane(image) >= threshold
    if invert:
        foreground = ~foreground
    return (foreground & (image[..., 3] > 0)).astype(np.uint8)


def _colors(labels):
    """Màu nhãn ổn định, nền đen; không sử dụng bộ sinh số ngẫu nhiên toàn cục."""
    hashed = labels.astype(np.uint32) * np.uint32(2654435761)
    result = np.empty((*labels.shape, 3), np.uint8)
    for channel, shift in enumerate((0, 8, 16)):
        result[..., channel] = 48 + ((hashed >> shift) & 255) % 208
    result[labels <= 0] = 0
    return result


def adaptive_threshold(image, method='mean', size=15, offset=5., invert=False):
    """Trang 23–24: g=255 khi f>m_cục_bộ−C; mean hoặc trọng số Gaussian.

    Trung bình chuẩn hóa theo số/trọng số pixel có alpha>0 trong cửa sổ.
    Biên ảnh được lặp lại. Không làm tròn m trước phép so sánh.
    """
    _image(image)
    if method not in ('mean', 'gaussian'):
        raise ValueError('Phương pháp ngưỡng phải là mean hoặc gaussian.')
    size = _integer(size, 'Cửa sổ', 3, 255)
    if size % 2 == 0:
        raise ValueError('Cửa sổ phân ngưỡng phải là số lẻ.')
    offset = _finite(offset, 'Hằng số C', -255, 255)
    invert = _boolean(invert, 'Đảo nền/vật thể')
    visible = image[..., 3] > 0
    if not visible.any():
        return image.copy()
    weights = visible.astype(np.float32)
    source = gray_plane(image).astype(np.float32)
    if method == 'mean':
        smooth = lambda plane: cv2.blur(plane, (size, size), borderType=cv2.BORDER_REPLICATE)
    else:
        smooth = lambda plane: cv2.GaussianBlur(plane, (size, size), 0, borderType=cv2.BORDER_REPLICATE)
    total = smooth(weights)
    local = smooth(source * weights) / np.maximum(total, np.finfo(np.float32).tiny)
    # A tiny numerical tolerance avoids false positives on constant neighborhoods.
    mask = source > local - offset + 1e-5
    if invert:
        mask = ~mask
    return _render(image, (mask & visible).astype(np.uint8) * 255)


def multi_otsu(image):
    """Trang 23: tìm hai ngưỡng cực đại phương sai giữa ba lớp không rỗng.

    Quy ước lớp: f≤T1 → 0, T1<f≤T2 → 128, f>T2 → 255.
    Ảnh chỉ có một/hai mức được giữ xám/phân thành hai lớp tương ứng.
    """
    gray = gray_plane(image)
    visible = image[..., 3] > 0
    if not visible.any():
        return image.copy(), 'Không có pixel nhìn thấy để tìm ngưỡng.'
    histogram = np.bincount(gray[visible], minlength=256).astype(np.float64)
    levels = np.flatnonzero(histogram)
    if len(levels) < 3:
        output = gray if len(levels) == 1 else (gray > levels[0]).astype(np.uint8) * 255
        return _render(image, output), f'Ảnh chỉ có {len(levels)} mức xám; không đủ ba lớp không rỗng.'
    weight = np.cumsum(histogram)
    moment = np.cumsum(histogram * np.arange(256))
    best_score, best_pair = -np.inf, None
    for first in range(int(levels[0]), int(levels[-2])):
        second = np.arange(first + 1, 255)
        w0, w1, w2 = weight[first], weight[second] - weight[first], weight[-1] - weight[second]
        valid = (w1 > 0) & (w2 > 0)
        if not valid.any():
            continue
        second, w1, w2 = second[valid], w1[valid], w2[valid]
        m0, m1, m2 = moment[first], moment[second] - moment[first], moment[-1] - moment[second]
        scores = m0 * m0 / w0 + m1 * m1 / w1 + m2 * m2 / w2
        index = int(np.argmax(scores))
        if scores[index] > best_score:
            best_score, best_pair = float(scores[index]), (first, int(second[index]))
    first, second = best_pair
    output = np.where(gray <= first, 0, np.where(gray <= second, 128, 255)).astype(np.uint8)
    return _render(image, output), f'Otsu ba lớp: T₁ = {first}, T₂ = {second}; mức đầu ra 0, 128, 255.'


def region_grow(image, seed_x=0, seed_y=0, tolerance=15., connectivity=4):
    """Trang 25–27: vùng liên thông của |f(x,y)−f(seed)|≤T, mầm cố định.

    Tọa độ mầm dùng (x,y), gốc ở góc trái trên, đơn vị pixel ảnh gốc.
    Flood fill trên mặt nạ đủ điều kiện tránh phép tăng trưởng theo hàng xóm
    khiến mức xám trôi dần, khác tiêu chí cố định của Ví dụ 3.5.
    """
    _image(image)
    seed_x = _integer(seed_x, 'Tọa độ x của mầm', 0, image.shape[1] - 1)
    seed_y = _integer(seed_y, 'Tọa độ y của mầm', 0, image.shape[0] - 1)
    tolerance = _finite(tolerance, 'Ngưỡng đồng nhất T', 0, 255)
    connectivity = _connectivity(connectivity)
    visible = image[..., 3] > 0
    if not visible.any():
        return image.copy(), 'Không có pixel nhìn thấy để tăng trưởng vùng.'
    if not visible[seed_y, seed_x]:
        raise ValueError('Điểm mầm nằm trong vùng trong suốt; hãy chọn một pixel nhìn thấy.')
    gray = gray_plane(image).astype(np.int16)
    eligible = ((np.abs(gray - gray[seed_y, seed_x]) <= tolerance) & visible).astype(np.uint8)
    count, _, _, _ = cv2.floodFill(eligible, None, (seed_x, seed_y), 2, flags=connectivity)
    output = (eligible == 2).astype(np.uint8) * 255
    return _render(image, output), f'Mầm ({seed_x}, {seed_y}), mức {gray[seed_y, seed_x]}: {count} pixel, liên thông {connectivity}.'


def _nearest(samples, centers):
    """Gán từng mẫu cho tâm gần nhất mà không tạo mảng N×K×3."""
    best = np.full(len(samples), np.inf, np.float32)
    labels = np.zeros(len(samples), np.int32)
    for index, center in enumerate(centers):
        distance = np.sum((samples - center) ** 2, axis=1)
        nearer = distance < best
        best[nearer], labels[nearer] = distance[nearer], index
    return labels, best


def kmeans(image, clusters=4, iterations=30):
    """Trang 32–35: K-means RGB, khởi tạo K-means++ bằng RNG riêng có seed 0.

    Tối đa 32768 pixel nhìn thấy được lấy mẫu không hoàn lại với seed 0.
    Học tâm trên mẫu, sau đó gán toàn ảnh theo khối 65536 pixel. OpenCV chỉ
    chạy một lần với nhãn khởi tạo tường minh, không đổi RNG toàn cục.
    """
    _image(image)
    clusters = _integer(clusters, 'Số cụm K', 2, 16)
    iterations = _integer(iterations, 'Số vòng lặp', 1, 100)
    indices = np.flatnonzero(image[..., 3].reshape(-1) > 0)
    if not len(indices):
        return image.copy(), 'Không có pixel nhìn thấy để phân cụm.'
    rng = np.random.default_rng(0)
    sample_indices = indices if len(indices) <= 32768 else rng.choice(indices, 32768, replace=False)
    flat_rgb = image.reshape(-1, 4)[:, :3]
    samples = np.ascontiguousarray(flat_rgb[sample_indices], dtype=np.float32)
    clusters = min(clusters, len(np.unique(samples, axis=0)))
    centers = [samples[int(rng.integers(len(samples)))]]
    nearest = np.sum((samples - centers[0]) ** 2, axis=1)
    for _ in range(1, clusters):
        probabilities = nearest.astype(np.float64)
        probabilities /= probabilities.sum()
        center = samples[int(rng.choice(len(samples), p=probabilities))]
        centers.append(center)
        nearest = np.minimum(nearest, np.sum((samples - center) ** 2, axis=1))
    initial, _ = _nearest(samples, np.asarray(centers))
    if clusters > 1:
        _, _, centers = cv2.kmeans(samples, clusters, initial.reshape(-1, 1),
                                  (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_MAX_ITER, iterations, .1),
                                  1, cv2.KMEANS_USE_INITIAL_LABELS)
    else:
        centers = np.asarray(centers, np.float32)
    palette = np.clip(np.rint(centers), 0, 255).astype(np.uint8)
    result = image.copy()
    result_rgb = result.reshape(-1, 4)[:, :3]
    result_rgb[:] = 0
    for start in range(0, len(indices), 65536):
        block = indices[start:start + 65536]
        labels, _ = _nearest(flat_rgb[block].astype(np.float32), centers)
        result_rgb[block] = palette[labels]
    return result, f'K-means RGB: {clusters} cụm; học trên {len(samples):,}/{len(indices):,} pixel (mẫu cố định), gán toàn ảnh.'


def _component_labels(binary, connectivity, min_size):
    count, labels, stats, _ = cv2.connectedComponentsWithStats(binary, connectivity=connectivity)
    keep = stats[:, cv2.CC_STAT_AREA] >= min_size
    keep[0] = False
    mapping = np.zeros(count, np.int32)
    mapping[keep] = np.arange(1, int(keep.sum()) + 1)
    return mapping[labels], int(keep.sum()), count - 1


def components(image, threshold=128, connectivity=8, min_size=1, output='labels', invert=False):
    """Trang 36–37: gán nhãn N4/N8 và bỏ các vùng có diện tích <min_size.

    Vật thể mặc định là mức xám ≥T. output='labels' tô màu từng đối tượng,
    output='binary' trả mặt nạ trắng/đen sau khi loại vùng nhỏ.
    """
    _image(image)
    connectivity = _connectivity(connectivity)
    min_size = _integer(min_size, 'Diện tích tối thiểu', 1, 1_000_000_000)
    if output not in ('labels', 'binary'):
        raise ValueError('Kết quả thành phần phải là labels hoặc binary.')
    binary = _binary(image, threshold, invert)
    if not np.any(image[..., 3]):
        return image.copy(), 'Không có pixel nhìn thấy để gán nhãn.'
    labels, count, total = _component_labels(binary, connectivity, min_size)
    pixels = _colors(labels) if output == 'labels' else (labels > 0).astype(np.uint8) * 255
    return _render(image, pixels), f'{count} vùng liên thông {connectivity}; đã loại {total - count} vùng nhỏ hơn {min_size} pixel.'


def watershed(image, threshold=128, foreground_ratio=.55, min_size=9, invert=False):
    """Trang 30–31: watershed có mầm tại cực đại biến đổi khoảng cách.

    Lọc vùng nhỏ, tìm cực đại khoảng cách trong cửa sổ 3×3, giữ các cực đại
    cao ít nhất foreground_ratio×đỉnh của từng thành phần liên thông.
    Nền được đánh dấu riêng; đường phân thủy trong vật thể có màu đỏ.
    """
    _image(image)
    foreground_ratio = _finite(foreground_ratio, 'Tỉ lệ độ cao mầm', .05, .95)
    min_size = _integer(min_size, 'Diện tích tối thiểu', 1, 1_000_000_000)
    binary = _binary(image, threshold, invert)
    if not np.any(image[..., 3]):
        return image.copy(), 'Không có pixel nhìn thấy để phân thủy.'
    regions, count, _ = _component_labels(binary, 8, min_size)
    foreground = regions > 0
    if not count:
        return _render(image, np.zeros_like(binary)), 'Không có vật thể vượt ngưỡng và diện tích tối thiểu.'
    # Đệm nền xử lý cả vật thể chạm mép và ảnh hoàn toàn trắng.
    padded = np.pad(foreground.astype(np.uint8), 1)
    distance = cv2.distanceTransform(padded, cv2.DIST_L2, 5)[1:-1, 1:-1]
    peaks = np.zeros(count + 1, np.float32)
    np.maximum.at(peaks, regions, distance)
    local_max = cv2.dilate(distance, np.ones((3, 3), np.uint8))
    seeds = foreground & (distance >= local_max - 1e-5) & (distance >= foreground_ratio * peaks[regions])
    seed_count, seed_labels = cv2.connectedComponents(seeds.astype(np.uint8), connectivity=8)
    markers = np.ones(padded.shape, np.int32)
    inner = markers[1:-1, 1:-1]
    inner[foreground] = 0
    inner[seeds] = seed_labels[seeds] + 1
    rgb = image[..., :3].copy()
    rgb[~foreground] = 0
    surface = cv2.copyMakeBorder(cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR), 1, 1, 1, 1, cv2.BORDER_CONSTANT)
    cv2.watershed(surface, markers)
    result_labels = markers[1:-1, 1:-1]
    objects = np.where(foreground & (result_labels > 1), result_labels - 1, 0)
    colors = _colors(objects)
    boundary = foreground & (result_labels == -1)
    colors[boundary] = (255, 0, 0)
    return _render(image, colors), f'Watershed: {seed_count - 1} mầm, biên phân thủy màu đỏ; nền đen.'


def split_merge(image, tolerance=20., min_size=4):
    """Trang 28–29: tách tứ phân rồi hợp lá kề N4 có max−min≤T.

    Dừng tách khi cạnh dài nhất ≤min_size hoặc vùng đồng nhất. Vì vậy lá
    cuối ở kích thước tối thiểu có thể chưa đồng nhất. Các cặp lá được xét
    theo chênh lệch trung bình tăng dần; chỉ hợp nếu toàn vùng sau hợp vẫn
    thỏa max−min≤T. Pixel trong suốt không nối hai vùng rời nhau.

    Giới hạn 1,048,576 pixel và 65,536 lá tránh cây tứ phân quá lớn trên ảnh
    nhiều nhiễu. Kết quả hiển thị mức xám trung bình từng vùng cuối cùng.
    """
    _image(image)
    tolerance = _finite(tolerance, 'Ngưỡng đồng nhất T', 0, 255)
    min_size = _integer(min_size, 'Cạnh nhỏ nhất', 1, 256)
    height, width = image.shape[:2]
    if height * width > 1_048_576:
        raise ValueError('Tách–hợp hỗ trợ tối đa 1.048.576 pixel; hãy giảm kích thước ảnh trước.')
    gray = gray_plane(image)
    visible = image[..., 3] > 0
    if not visible.any():
        return image.copy(), 'Không có pixel nhìn thấy để tách–hợp vùng.'
    labels = np.zeros((height, width), np.int32)
    minima, maxima, totals, counts = [0.], [0.], [0.], [0]
    stack = [(0, height, 0, width)]
    while stack:
        y0, y1, x0, x1 = stack.pop()
        block_visible = visible[y0:y1, x0:x1]
        if not block_visible.any():
            continue
        block = gray[y0:y1, x0:x1]
        values = block[block_visible]
        low, high = int(values.min()), int(values.max())
        homogeneous = high - low <= tolerance and block_visible.all()
        if homogeneous or max(y1 - y0, x1 - x0) <= min_size:
            if block_visible.all():
                parts, part_count = np.ones(block.shape, np.int32), 2
            else:
                part_count, parts = cv2.connectedComponents(block_visible.astype(np.uint8), connectivity=4)
            for part in range(1, part_count):
                if len(counts) > 65_536:
                    raise ValueError('Tách–hợp vượt 65.536 lá; hãy tăng cạnh nhỏ nhất hoặc ngưỡng đồng nhất.')
                mask = parts == part
                part_values = block[mask]
                labels[y0:y1, x0:x1][mask] = len(counts)
                minima.append(float(part_values.min()))
                maxima.append(float(part_values.max()))
                totals.append(float(part_values.sum(dtype=np.float64)))
                counts.append(len(part_values))
            continue
        ys = (y0, (y0 + y1) // 2, y1) if y1 - y0 > 1 else (y0, y1)
        xs = (x0, (x0 + x1) // 2, x1) if x1 - x0 > 1 else (x0, x1)
        for top, bottom in zip(ys[:-1], ys[1:]):
            for left, right in zip(xs[:-1], xs[1:]):
                stack.append((top, bottom, left, right))
    size = len(counts)
    minima, maxima = np.asarray(minima), np.asarray(maxima)
    totals, counts = np.asarray(totals), np.asarray(counts)
    parent = np.arange(size)

    def representative(label):
        while parent[label] != label:
            parent[label] = parent[parent[label]]
            label = parent[label]
        return int(label)

    edges = []
    for first, second in ((labels[:, :-1], labels[:, 1:]), (labels[:-1, :], labels[1:, :])):
        boundary = (first != second) & (first > 0) & (second > 0)
        lo = np.minimum(first[boundary], second[boundary]).astype(np.int64)
        hi = np.maximum(first[boundary], second[boundary])
        edges.append(lo * size + hi)
    encoded = np.unique(np.concatenate(edges))
    first, second = encoded // size, encoded % size
    means = totals / np.maximum(counts, 1)
    order = np.argsort(np.abs(means[first] - means[second]), kind='stable')
    for index in order:
        left, right = representative(int(first[index])), representative(int(second[index]))
        if left == right:
            continue
        low, high = min(minima[left], minima[right]), max(maxima[left], maxima[right])
        if high - low <= tolerance:
            parent[right] = left
            minima[left], maxima[left] = low, high
            totals[left] += totals[right]
            counts[left] += counts[right]
    mapping = np.asarray([representative(label) for label in range(size)])
    means = np.clip(np.rint(totals / np.maximum(counts, 1)), 0, 255).astype(np.uint8)
    output = means[mapping[labels]]
    final_count = len(np.unique(mapping[1:]))
    return _render(image, output), f'Tách–hợp: {size - 1} lá → {final_count} vùng; N4, max−min ≤ {tolerance:g}, cạnh dừng {min_size}.'
