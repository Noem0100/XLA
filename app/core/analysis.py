"""Danh mục và điều phối phát hiện biên, phân vùng và hình thái học."""
from . import analysis_edges as edges
from . import analysis_regions as regions
from . import analysis_morphology as morphology
from .enhancement import Algorithm
from .enhancement_point import _image
from .geometry import MAX_PIXELS


DIRECTION = ('direction', 'Hướng đạo hàm', ['magnitude', 'x', 'y'], 0, 0)
INVERT = ('invert', 'Đảo nền và vật thể', [False, True], 0, 0)
CONNECTIVITY = ('connectivity', 'Liên thông', [4, 8], 0, 0)
THRESHOLD = ('threshold', 'Ngưỡng nhị phân T', 127, 0, 255)
SHAPE = ('shape', 'Phần tử cấu trúc', ['cross', 'rect', 'ellipse'], 0, 0)
MORPH_FIELDS = (
    ('size', 'Kích thước phần tử lẻ (pixel)', 3, 1, 99), SHAPE,
    ('iterations', 'Số lần co / giãn mỗi bước', 1, 1, 20),
    ('grayscale', 'Xử lý trực tiếp ảnh xám', [False, True], 0, 0), THRESHOLD, INVERT,
)

ALGORITHMS = {
    'roberts': Algorithm('Phát hiện biên Roberts', 'Phát hiện biên', '9',
        'Gradient hai đường chéo bằng mặt nạ 2×2. Hiển thị độ lớn hoặc trị tuyệt đối từng đạo hàm.',
        (DIRECTION,), gray_only=True),
    'prewitt': Algorithm('Phát hiện biên Prewitt', 'Phát hiện biên', '10',
        'Gradient bằng mặt nạ 3×3 trọng số đều. Giá trị đạo hàm được tính có dấu trước khi lấy độ lớn.',
        (DIRECTION,), gray_only=True),
    'log_zero_crossing': Algorithm('Phát hiện biên LoG', 'Phát hiện biên', '12–13',
        'Làm trơn Gaussian, tính Laplacian rồi tìm điểm đổi dấu. Ngưỡng lớn loại các biên yếu.',
        (('sigma', 'Sigma Gaussian', 1.2, .1, 50.),
         ('threshold', 'Chênh lệch tối thiểu khi đổi dấu', 5., 0., 2040.)), gray_only=True),
    'hough_lines': Algorithm('Phát hiện đường thẳng Hough', 'Phát hiện biên', '18–21',
        'Tìm biên Canny rồi dò đường thẳng, vẽ kết quả màu đỏ lên ảnh. Độ dài và khoảng đứt chỉ dùng cho Hough xác suất.',
        (('mode', 'Phương pháp Hough', ['probabilistic', 'standard'], 0, 0),
         ('threshold', 'Số phiếu tối thiểu', 50, 1, 1_000_000),
         ('min_length', 'Độ dài đường tối thiểu (pixel)', 40., 0., 1_000_000.),
         ('max_gap', 'Khoảng đứt tối đa (pixel)', 10., 0., 1_000_000.),
         ('canny_low', 'Ngưỡng Canny thấp', 60., 0., 2040.),
         ('canny_high', 'Ngưỡng Canny cao', 150., 0., 2040.),
         ('line_width', 'Độ dày nét vẽ (pixel)', 2, 1, 20),
         ('max_lines', 'Số đường tối đa', 100, 1, 1000))),
    'adaptive_threshold': Algorithm('Phân ngưỡng thích nghi', 'Phân vùng ảnh', '23–24',
        'So sánh mức xám với trung bình cục bộ trừ C. Chọn trung bình đều hoặc Gaussian; kết quả là mặt nạ nhị phân.',
        (('method', 'Trung bình cục bộ', ['mean', 'gaussian'], 0, 0),
         ('size', 'Cửa sổ lẻ (pixel)', 15, 3, 255),
         ('offset', 'Hằng số C', 5., -255., 255.), INVERT), gray_only=True),
    'multi_otsu': Algorithm('Phân ngưỡng Otsu ba lớp', 'Phân vùng ảnh', '23',
        'Tìm hai ngưỡng tối đa hóa phương sai giữa ba lớp. Kết quả có ba mức 0, 128, 255; thông báo cả hai ngưỡng.',
        gray_only=True),
    'region_grow': Algorithm('Tăng trưởng vùng từ điểm mầm', 'Phân vùng ảnh', '25–27',
        'Chọn vùng liên thông có mức xám lệch không quá T so với mầm cố định. Tọa độ (x,y) tính trên ảnh gốc, gốc ở góc trái trên.',
        (('seed_x', 'Tọa độ mầm x (pixel ảnh gốc)', 0, 0, MAX_PIXELS - 1),
         ('seed_y', 'Tọa độ mầm y (pixel ảnh gốc)', 0, 0, MAX_PIXELS - 1),
         ('tolerance', 'Sai khác mức xám tối đa T', 15., 0., 255.), CONNECTIVITY), gray_only=True),
    'split_merge': Algorithm('Tách và hợp vùng', 'Phân vùng ảnh', '28–29',
        'Tách tứ phân rồi hợp các vùng kề nhau khi max−min ≤ T. Kết quả là mức xám trung bình từng vùng; tối đa 1.048.576 pixel.',
        (('tolerance', 'Sai khác mức xám tối đa T', 20., 0., 255.),
         ('min_size', 'Cạnh dừng tách (pixel)', 4, 1, 256)), gray_only=True),
    'watershed': Algorithm('Tách vật thể bằng Watershed', 'Phân vùng ảnh', '30–31',
        'Tạo mầm từ cực đại khoảng cách trong vật thể rồi phân thủy. Mỗi vùng có một màu, biên phân chia màu đỏ và nền đen.',
        (('threshold', 'Ngưỡng chọn vật thể (mức ≥ T)', 128, 0, 255),
         ('foreground_ratio', 'Tỉ lệ độ cao mầm', .55, .05, .95),
         ('min_size', 'Diện tích vật thể tối thiểu (pixel)', 9, 1, 1_000_000_000), INVERT)),
    'kmeans': Algorithm('Phân cụm màu K-means', 'Phân vùng ảnh', '32–35',
        'Gom các pixel RGB thành K nhóm màu. Học trên tối đa 32.768 mẫu cố định rồi gán màu tâm cụm cho toàn ảnh.',
        (('clusters', 'Số cụm màu K', 4, 2, 16),
         ('iterations', 'Số vòng lặp tối đa', 30, 1, 100))),
    'components': Algorithm('Gán nhãn vùng liên thông', 'Phân vùng ảnh', '36–37',
        'Chọn vật thể có mức xám ≥ T, gán nhãn theo liên thông 4 hoặc 8 và loại vùng nhỏ. Có thể xuất màu nhãn hoặc mặt nạ.',
        (('threshold', 'Ngưỡng chọn vật thể (mức ≥ T)', 128, 0, 255),
         ('connectivity', 'Liên thông', [8, 4], 0, 0),
         ('min_size', 'Diện tích tối thiểu (pixel)', 1, 1, 1_000_000_000),
         ('output', 'Kết quả', ['labels', 'binary'], 0, 0), INVERT)),
}

for _key, _title, _description in (
    ('dilate', 'Giãn ảnh', 'Mở rộng vật thể nhị phân hoặc lấy cực đại mức xám trong phần tử cấu trúc.'),
    ('erode', 'Co ảnh', 'Thu nhỏ vật thể nhị phân hoặc lấy cực tiểu mức xám trong phần tử cấu trúc.'),
    ('open', 'Mở hình thái học', 'Co rồi giãn để loại các chi tiết sáng nhỏ.'),
    ('close', 'Đóng hình thái học', 'Giãn rồi co để nối khe hẹp và lấp khoảng tối nhỏ.'),
    ('boundary', 'Trích biên hình thái học', 'Lấy ảnh trừ ảnh co để giữ biên phía trong của vật thể.'),
    ('top_hat', 'Trích chi tiết sáng Top-hat', 'Lấy ảnh trừ ảnh mở để tách các chi tiết sáng nhỏ hơn phần tử cấu trúc.'),
):
    ALGORITHMS[_key] = Algorithm(_title, 'Hình thái học', '39–46',
        _description + ' Chế độ nhị phân dùng vật thể mức xám > T; chế độ ảnh xám không phân ngưỡng.',
        MORPH_FIELDS, gray_only=True)

ALGORITHMS.update({
    'fill_holes': Algorithm('Lấp lỗ kín trong vật thể', 'Hình thái học', '47',
        'Lấp các miền nền kín bên trong vật thể, giữ nền thông ra biên ảnh. Liên thông ở đây áp dụng cho nền.',
        (THRESHOLD, INVERT, CONNECTIVITY), gray_only=True),
    'hit_or_miss': Algorithm('Dò mẫu hình thái học Hit-or-miss', 'Hình thái học', '45',
        'Dò góc trên trái của vật thể bằng mẫu tiền cảnh và hậu cảnh; có thể quay mẫu từng góc 90°.',
        (THRESHOLD, INVERT, ('rotation', 'Góc quay mẫu ngược chiều kim đồng hồ', [0, 90, 180, 270], 0, 0)),
        gray_only=True),
    'skeleton': Algorithm('Trích khung xương hình thái học', 'Hình thái học', '48',
        'Giữ tâm các phần tử cấu trúc lớn nhất nằm trong vật thể. Khung có thể rộng hai pixel khi vật thể có bề rộng chẵn.',
        (THRESHOLD, INVERT, SHAPE), gray_only=True),
})


def fields_for_image(algorithm, image_shape):
    """Điều chỉnh miền tọa độ mầm theo ảnh hiện hành mà không đổi registry chung."""
    if algorithm not in ALGORITHMS:
        raise ValueError('Chức năng phân tích ảnh không tồn tại.')
    fields = ALGORITHMS[algorithm].fields
    if algorithm != 'region_grow':
        return fields
    height, width = image_shape[:2]
    if height < 1 or width < 1:
        raise ValueError('Ảnh cần có chiều rộng và chiều cao lớn hơn 0.')
    dimensions = {'seed_x': width, 'seed_y': height}
    return tuple((key, title, dimensions[key] // 2, 0, dimensions[key] - 1)
                 if key in dimensions else (key, title, value, minimum, maximum)
                 for key, title, value, minimum, maximum in fields)


def process(image, algorithm, params=None):
    """Trả (ảnh RGBA, thông tin kết quả), dùng trực tiếp các thuật toán đã kiểm thử."""
    _image(image)
    if algorithm not in ALGORITHMS:
        raise ValueError('Chức năng phân tích ảnh không tồn tại.')
    params = dict(params or {})
    allowed = {field[0] for field in ALGORITHMS[algorithm].fields}
    if params.keys() - allowed:
        raise ValueError('Tham số không hợp lệ: ' + ', '.join(sorted(params.keys() - allowed)))
    if algorithm in ('roberts', 'prewitt'):
        return edges.gradient(image, kind=algorithm, **params), ''
    if algorithm in ('log_zero_crossing', 'hough_lines'):
        return getattr(edges, algorithm)(image, **params), ''
    if algorithm in ('dilate', 'erode', 'open', 'close', 'boundary', 'top_hat'):
        return morphology.morphology(image, operation=algorithm, **params), ''
    if algorithm in ('fill_holes', 'hit_or_miss', 'skeleton'):
        return getattr(morphology, algorithm)(image, **params), ''
    if algorithm == 'adaptive_threshold':
        return regions.adaptive_threshold(image, **params), ''
    return getattr(regions, algorithm)(image, **params)
