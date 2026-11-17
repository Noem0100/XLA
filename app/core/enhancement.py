"""Danh mục và bộ điều phối thuật toán nâng cao chất lượng theo Chương 2."""
from dataclasses import dataclass
import cv2
import numpy as np
from . import enhancement_point as point
from . import enhancement_spatial as spatial
from . import enhancement_frequency as frequency
from .adjustments import pack


@dataclass(frozen=True)
class Algorithm:
    """Mô tả thuật toán, tham số và trang tham chiếu trong bài giảng."""
    title: str
    group: str
    pages: str
    description: str
    fields: tuple = ()
    gray_only: bool = False
    reference: bool = False
    frames: bool = False
    diagnostic: bool = False


SIZE = ('size', 'Cửa sổ lẻ (pixel)', 3, 1, 31)
SIGMA = ('sigma', 'Sigma Gaussian', 1.0, .1, 20.)
AMOUNT = ('amount', 'Hệ số tăng nét k', .5, 0., 5.)
CLIP = ('clip_limit', 'Giới hạn CLAHE', 2.0, .1, 20.)
TILES = ('tiles', 'Số ô mỗi chiều', 8, 2, 32)
FAMILY = ('family', 'Hàm truyền', ['gaussian', 'butterworth', 'ideal'], 0, 0)
CUTOFF = ('cutoff', 'D₀ / cạnh ngắn ảnh đệm', .08, .001, .5)
ORDER = ('order', 'Bậc Butterworth n', 2, 1, 10)
PSF = ('psf', 'Mô hình mờ PSF', ['gaussian', 'motion'], 0, 0)
PSF_SIZE = ('size', 'Kích thước PSF lẻ', 7, 1, 31)

ALGORITHMS = {
    'pipeline': Algorithm('Khử nhiễu → CLAHE → tăng nét', 'Quy trình tổng hợp', '55',
        'Trung vị khử nhiễu trước, CLAHE tăng tương phản cục bộ, unsharp làm nét sau cùng.',
        (('median_size', 'Cửa sổ trung vị lẻ', 3, 1, 31), CLIP, TILES, SIGMA, AMOUNT)),
    'linear': Algorithm('Độ sáng và tương phản tuyến tính', 'Biến đổi mức xám', '9–12',
        'g = a(f − m) + m + b. Giá trị âm được chặn về 0; giá trị lớn hơn 255 bị bão hòa.',
        (('gain', 'Hệ số tương phản a', 1.2, -3., 5.), ('bias', 'Độ sáng b (mức)', 0., -255., 255.),
         ('pivot', 'Tâm co giãn m', 128., 0., 255.))),
    'negative': Algorithm('Âm bản', 'Biến đổi mức xám', '13–16', 's = 255 − r.'),
    'log': Algorithm('Biến đổi logarit', 'Biến đổi mức xám', '13–16',
        's = c ln(1 + r), c = 255 / ln(256). Nén dải động và làm nổi vùng tối.',
        (('gain', 'Hệ số nhân c chuẩn hóa', 1., .1, 3.),)),
    'gamma': Algorithm('Gamma theo công thức bài giảng', 'Biến đổi mức xám', '13–16, 57',
        's = 255(r/255)^γ. γ < 1 làm sáng, γ > 1 làm tối; dùng số mũ trực tiếp.',
        (('gamma', 'Số mũ γ', .45, .05, 5.),)),
    'piecewise': Algorithm('Giãn tương phản từng đoạn', 'Biến đổi mức xám', '17',
        'Hàm gấp khúc qua (0,0), (r₁,s₁), (r₂,s₂), (255,255). Cần r₁ < r₂.',
        tuple((key, label, value, 0, 255) for key, label, value in
              [('r1', 'r₁ đầu vào', 80), ('s1', 's₁ đầu ra', 0), ('r2', 'r₂ đầu vào', 170), ('s2', 's₂ đầu ra', 255)])),
    'threshold': Algorithm('Phân ngưỡng chọn tay', 'Biến đổi mức xám', '18',
        'Mức xám r ≥ T thành trắng; r < T thành đen.', (('threshold', 'Ngưỡng T', 128, 0, 255),), gray_only=True),
    'bit_plane': Algorithm('Cắt mặt phẳng bit', 'Biến đổi mức xám', '18–19',
        'Tách một trong tám bit của ảnh xám; bit 7 là MSB, bit 0 là LSB.',
        (('bit', 'Mặt phẳng bit (0–7)', 7, 0, 7),), gray_only=True),
    'quantize': Algorithm('Bó cụm / lượng tử hóa mức xám', 'Biến đổi mức xám', '20',
        'g = floor(f / B) × B. B = 64 cho bốn mức 0, 64, 128, 192.', (('step', 'Độ rộng cụm B', 64, 1, 256),)),
    'equalize': Algorithm('Cân bằng histogram toàn cục', 'Xử lý histogram', '23–26',
        'LUT = round(255 × CDF), đúng thuật toán bốn bước trang 24; không trừ CDF nhỏ nhất như OpenCV. Ảnh một mức sẽ thành trắng.'),
    'match': Algorithm('Đối sánh histogram ảnh tham chiếu', 'Xử lý histogram', '27',
        'Ánh xạ CDF ảnh nguồn sang CDF ảnh tham chiếu để chuẩn hóa đặc trưng sáng.', reference=True),
    'clahe': Algorithm('CLAHE có chỉnh tham số', 'Xử lý histogram', '27, 57',
        'Cân bằng histogram theo ô, giới hạn khuếch đại nhiễu; điều chỉnh clip limit và số ô.', (CLIP, TILES)),
    'otsu': Algorithm('Otsu và ngưỡng tự động', 'Xử lý histogram', '28–30, 57',
        'Tối đa phương sai giữa hai lớp. Mức ≤ t là nền, mức > t là đối tượng; hiển thị ngưỡng tìm được.', gray_only=True),
    'mean': Algorithm('Lọc trung bình', 'Lọc không gian', '34, 37–38',
        'Trung bình mọi điểm trong cửa sổ. Khử nhiễu nhưng có thể làm nhòe biên.', (SIZE,)),
    'gaussian': Algorithm('Lọc Gaussian', 'Lọc không gian', '35, 37–38',
        'Trọng số dồn về tâm; chọn sigma = 0 để OpenCV xác định từ kích thước cửa sổ.',
        (SIZE, ('sigma', 'Sigma (0: tự động)', 1., 0., 20.))),
    'median': Algorithm('Lọc trung vị', 'Lọc không gian', '36–38',
        'Lấy giá trị ở giữa khi sắp xếp cửa sổ, phù hợp nhiễu muối tiêu.', (SIZE,)),
    'nearest': Algorithm('Trung bình K giá trị gần nhất', 'Lọc không gian', '39',
        'Chọn K mức gần mức ở tâm nhất (gồm tâm). Chỉ thay khi chênh lệch trung bình vượt τ.',
        (SIZE, ('neighbors', 'Số giá trị K', 3, 1, 961), ('threshold', 'Ngưỡng thay τ', 2., 0., 255.))),
    'sobel': Algorithm('Gradient Sobel', 'Lọc không gian', '40',
        'Hiển thị trị tuyệt đối Gx, Gy hoặc độ lớn gradient; các giá trị vượt 255 bị chặn.',
        (('direction', 'Hướng đạo hàm', ['magnitude', 'x', 'y'], 0, 0),), gray_only=True),
    'laplacian': Algorithm('Làm nét Laplacian', 'Lọc không gian', '41, 43, 58',
        'g = f − k∇²f, mặt nạ bốn lân cận tâm âm. Đạo hàm được tính có dấu trước khi chặn.',
        (('amount', 'Hệ số Laplacian k', 1., 0., 5.),)),
    'lap_edges': Algorithm('Hiển thị biên Laplacian', 'Lọc không gian', '41, 43',
        'Hiển thị |∇²f| của mặt nạ bốn lân cận.', gray_only=True),
    'unsharp': Algorithm('Unsharp / high-boost', 'Lọc không gian', '42–44, 58',
        'g = f + k(f − f_mờ). k = 1 là unsharp; k > 1 là high-boost.', (SIGMA, AMOUNT)),
    'frequency_low': Algorithm('Fourier: lọc thông thấp', 'Miền tần số', '45–49, 59',
        'Đệm 0 lên gấp đôi, DFT → nhân H → IDFT và cắt ảnh. D₀ nhỏ làm trơn mạnh; lọc lý tưởng có thể gây ringing.', (FAMILY, CUTOFF, ORDER)),
    'frequency_high': Algorithm('Fourier: lọc thông cao', 'Miền tần số', '49–50',
        'H_HP = 1 − H_LP. Hiển thị đáp ứng có dấu quanh mức 128, giữ cả biên dương và âm.',
        (FAMILY, CUTOFF, ORDER), gray_only=True),
    'frequency_boost': Algorithm('Fourier: tăng nét thông cao', 'Miền tần số', '49–50',
        'Cộng k lần thành phần thông cao vào ảnh đầu vào để tăng chi tiết.', (FAMILY, CUTOFF, ORDER, AMOUNT)),
    'notch': Algorithm('Fourier: lọc chắn nhiễu tuần hoàn', 'Miền tần số', '50–51',
        'Chặn cặp đỉnh đối xứng ±(u,v) bằng notch Gaussian. Tọa độ tính từ tâm phổ, theo cạnh ngắn ảnh đệm.',
        (('offset_x', 'Tần số ngang / cạnh đệm', .15, -.49, .49),
         ('offset_y', 'Tần số dọc / cạnh đệm', 0., -.49, .49), ('radius', 'Bán kính / cạnh đệm', .025, .001, .2))),
    'spectrum': Algorithm('Xem phổ biên độ Fourier', 'Miền tần số', '46, 60',
        'Hiển thị log(1 + |F|), dịch tần số thấp về tâm. Phổ là ảnh phân tích; không áp dụng thay ảnh đang chỉnh.',
        gray_only=True, diagnostic=True),
    'adaptive_median': Algorithm('Trung vị thích nghi', 'Khử nhiễu và khôi phục', '54 (mở rộng)',
        'Tăng cửa sổ dần để loại xung nhiễu muối tiêu, giữ các tâm chưa bị nhiễu.',
        (('max_size', 'Cửa sổ lớn nhất lẻ', 7, 3, 31),)),
    'homomorphic': Algorithm('Lọc đồng hình', 'Khử nhiễu và khôi phục', '54 (mở rộng)',
        'Logarit → lọc tần số → mũ ngược, giảm chiếu sáng biến thiên chậm và tăng chi tiết.',
        (CUTOFF, ('low_gain', 'Gain vùng tần số thấp', .5, .05, 2.),
         ('high_gain', 'Gain vùng tần số cao', 1.5, .1, 4.), ('sharpness', 'Độ dốc chuyển tiếp', 1., .1, 5.))),
    'inverse': Algorithm('Khôi phục bằng lọc ngược', 'Khử nhiễu và khôi phục', '54',
        'Ước lượng ảnh trước mờ từ PSF giả định. Giới hạn mẫu số ε để giảm khuếch đại tại tần số H gần 0.',
        (PSF, PSF_SIZE, SIGMA, ('epsilon', 'Ngưỡng mẫu số ε', .01, .0001, 1.))),
    'wiener': Algorithm('Khôi phục bằng Wiener', 'Khử nhiễu và khôi phục', '54',
        'conj(H) / (|H|² + K). PSF và tỉ số nhiễu/tín hiệu K là giả định cần chỉnh theo ảnh.',
        (PSF, PSF_SIZE, SIGMA, ('noise', 'Tỉ số nhiễu/tín hiệu K', .01, .0001, 1.))),
    'average': Algorithm('Trung bình nhiều ảnh cùng cảnh', 'Khử nhiễu và khôi phục', '53',
        'Ảnh đang mở và các ảnh thêm phải cùng kích thước, đã căn chỉnh cùng cảnh tĩnh. Không tự căn chỉnh.', frames=True),
}


def _gray_image(image):
    """Đổi ảnh RGBA sang ba kênh Y giống nhau, giữ alpha để tính thống kê."""
    gray = cv2.cvtColor(image[..., :3], cv2.COLOR_RGB2GRAY)
    return np.dstack((gray, gray, gray, image[..., 3]))


def process(image, algorithm, params=None, mode='luminance', reference=None, frames=None):
    """Điều phối một phép xử lý; trả ảnh RGBA và thông số bổ sung để hiển thị."""
    if algorithm not in ALGORITHMS:
        raise ValueError('Thuật toán không tồn tại.')
    if mode not in ('luminance', 'rgb', 'grayscale'):
        raise ValueError('Chế độ xử lý màu không hợp lệ.')
    spec = ALGORITHMS[algorithm]
    params = dict(params or {})
    gray = spec.gray_only or mode != 'rgb'
    source = _gray_image(image) if gray else image
    target = _gray_image(reference) if gray and reference is not None else reference
    info = ''
    if algorithm in ('linear', 'negative', 'log', 'gamma', 'piecewise', 'threshold', 'bit_plane', 'quantize', 'equalize', 'clahe'):
        function = getattr(point, 'logarithm' if algorithm == 'log' else algorithm)
        result = function(source, **params)
    elif algorithm == 'match':
        if reference is None:
            raise ValueError('Hãy chọn ảnh tham chiếu để đối sánh histogram.')
        result = point.match_histogram(source, target)
    elif algorithm == 'otsu':
        result, threshold = point.otsu(source)
        info = f'Ngưỡng Otsu t* = {threshold} · nền ≤ t*, đối tượng > t*'
    elif algorithm in ('mean', 'gaussian', 'median'):
        result = spatial.smooth(source, kind=algorithm, **params)
    elif algorithm == 'nearest':
        result = spatial.nearest_mean(source, **params)
    elif algorithm == 'lap_edges':
        result = spatial.laplacian(source, edges_only=True)
    elif algorithm in ('sobel', 'laplacian', 'unsharp', 'adaptive_median', 'pipeline'):
        result = getattr(spatial, algorithm)(source, **params)
    elif algorithm.startswith('frequency_'):
        result = frequency.frequency_filter(source, pass_type=algorithm.split('_')[1], **params)
    elif algorithm == 'notch':
        result = frequency.notch_filter(source, **params)
    elif algorithm == 'spectrum':
        result = frequency.spectrum(source)
    elif algorithm == 'homomorphic':
        result = frequency.homomorphic(source, **params)
    elif algorithm in ('inverse', 'wiener'):
        result = frequency.restore(source, method=algorithm, **params)
    elif algorithm == 'average':
        def sources():
            """Chuyển chế độ từng khung để cộng dồn mà không giữ toàn bộ ảnh."""
            yield source
            for frame in (() if frames is None else frames):
                yield _gray_image(frame) if gray else frame
        result = spatial.average_images(sources())
    if mode == 'luminance' and not spec.gray_only:
        delta = result[..., :1].astype(np.float32) - source[..., :1].astype(np.float32)
        result = pack(image[..., :3].astype(np.float32) + delta, image)
    return result, info
