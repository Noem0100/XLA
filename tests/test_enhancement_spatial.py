"""Ví dụ số Chương 2 và các trường hợp biên của lọc không gian, chỉ số chất lượng."""
import numpy as np
import pytest

from app.core import enhancement_spatial as spatial


def rgba_gray(values):
    """Tạo RGBA từ ma trận xám, giữ nguyên giá trị để tính tay bộ lọc."""
    gray = np.asarray(values, dtype=np.uint8)
    return np.dstack((np.repeat(gray[..., None], 3, axis=2), np.full(gray.shape, 255, dtype=np.uint8)))


@pytest.fixture
def chapter_matrix():
    """Ma trận 5×5 trang 33: điểm nhiễu 50 ở biên nền 10/100."""
    image = rgba_gray([[10, 10, 10, 100, 100]] * 5)
    image[2, 2, :3] = 50
    return image


@pytest.mark.parametrize('kind,expected', [('mean', 44), ('gaussian', 43), ('median', 10)])
def test_textbook_smoothing_center(chapter_matrix, kind, expected):
    """Tổng 400/9, Gauss nhị thức 680/16 và trung vị 10 khớp ví dụ 2.8–2.10."""
    result = spatial.smooth(chapter_matrix, kind, size=3, sigma=0)
    np.testing.assert_array_equal(result[2, 2, :3], [expected] * 3)


@pytest.mark.parametrize('kind', ['mean', 'gaussian', 'median'])
def test_smoothing_uses_reflected_border(kind):
    """Góc ảnh dùng REFLECT_101, khác quy ước lặp pixel biên mặc định của median."""
    image = rgba_gray([[1, 2, 100], [3, 4, 100], [100, 100, 100]])
    result = spatial.smooth(image, kind, size=3, sigma=0)
    np.testing.assert_array_equal(result[0, 0, :3], [3] * 3)


def test_k_nearest_center_and_strict_threshold():
    """K=3 lấy 16,4,4 thành 8; ngưỡng bằng sai khác không thay pixel."""
    image = rgba_gray([[1, 2, 3], [2, 16, 4], [2, 1, 4]])
    assert spatial.nearest_mean(image)[1, 1, 0] == 8
    assert spatial.nearest_mean(image, threshold=8)[1, 1, 0] == 16
    np.testing.assert_array_equal(spatial.nearest_mean(image, neighbors=1), image)


def test_k_nearest_tiling_matches_whole_window_result():
    """Ảnh rộng vượt giới hạn khối vẫn được lọc liên tục tại đường nối hai khối."""
    row = np.arange(256, dtype=np.uint8)
    values = np.tile(row, 9)[None, :]
    image = rgba_gray(np.repeat(values, 3, axis=0))
    # Cửa sổ 31 với K=1 luôn là mức của chính tâm, kể cả hai phía ranh giới khối.
    np.testing.assert_array_equal(spatial.nearest_mean(image, size=31, neighbors=1), image)


def test_laplacian_four_neighbors_and_sobel_clip(chapter_matrix):
    """Laplace=-70 nên f−Laplace=120; Sobel Gx=360 clip255 và Gy=0."""
    assert spatial.laplacian(chapter_matrix)[2, 2, 0] == 120
    assert spatial.laplacian(chapter_matrix, edges_only=True)[2, 2, 0] == 70
    assert spatial.sobel(chapter_matrix, 'x')[2, 2, 0] == 255
    assert spatial.sobel(chapter_matrix, 'y')[2, 2, 0] == 0
    assert spatial.sobel(chapter_matrix, 'magnitude')[2, 2, 0] == 255


def test_unsharp_uses_float_mask_and_zero_amount_identity(chapter_matrix):
    """High-boost tính từ Gauss chính xác 42.5 trước khi clip, không tràn uint8."""
    result = spatial.unsharp(chapter_matrix, sigma=0, size=3, amount=2)
    assert result[2, 2, 0] == 65
    np.testing.assert_array_equal(spatial.unsharp(chapter_matrix, amount=0), chapter_matrix)
    np.testing.assert_array_equal(spatial.laplacian(chapter_matrix, amount=0), chapter_matrix)


def test_adaptive_median_grows_window_and_keeps_valid_center():
    """Bước A mở cửa sổ 3 lên 5; bước B giữ điểm hợp lệ dù khác trung vị."""
    image = rgba_gray(np.full((5, 5), 100, dtype=np.uint8))
    image[1:4, 1:4, :3] = 255
    image[2, 2, :3] = 0
    assert spatial.adaptive_median(image, max_size=3)[2, 2, 0] == 255
    assert spatial.adaptive_median(image, max_size=5)[2, 2, 0] == 100
    valid = rgba_gray([[0, 30, 30], [30, 20, 30], [30, 30, 255]])
    assert spatial.adaptive_median(valid, max_size=3)[1, 1, 0] == 20


@pytest.mark.parametrize('shape', [(1, 1), (1, 4), (4, 1), (4, 5)])
def test_filters_handle_tiny_constant_images(shape):
    """Ảnh hằng và một hàng/cột không sinh NaN hoặc lỗi đệm biên."""
    image = rgba_gray(np.full(shape, 80, dtype=np.uint8))
    for result in [spatial.smooth(image), spatial.smooth(image, 'median', 7),
                   spatial.nearest_mean(image, size=5), spatial.adaptive_median(image),
                   spatial.unsharp(image), spatial.laplacian(image)]:
        np.testing.assert_array_equal(result, image)
    assert not np.any(spatial.sobel(image)[..., :3])


def test_average_streaming_weights_alpha_and_preserves_first_alpha():
    """Giá trị RGB ẩn không pha vào ảnh; alpha bán trong suốt có trọng số đúng."""
    first = np.array([[[0, 20, 40, 255], [250, 250, 250, 0], [20, 40, 60, 128]]], dtype=np.uint8)
    second = np.array([[[100, 120, 140, 255], [10, 20, 30, 255], [80, 100, 120, 128]]], dtype=np.uint8)
    result = spatial.average_images(image for image in [first, second])
    expected = np.array([[[50, 70, 90, 255], [10, 20, 30, 0], [50, 70, 90, 128]]], dtype=np.uint8)
    np.testing.assert_array_equal(result, expected)
    np.testing.assert_array_equal(first[0, 0], [0, 20, 40, 255])
    opaque = np.array([[[0, 0, 0, 255]]], dtype=np.uint8)
    partial = np.array([[[255, 255, 255, 85]]], dtype=np.uint8)
    assert spatial.average_images([opaque, partial])[0, 0, 0] == 64


@pytest.mark.parametrize('images', [[], [rgba_gray([[10]])], [rgba_gray([[10]]), rgba_gray([[10, 20]])]])
def test_average_rejects_missing_or_mismatched_frames(images):
    """Cần ít nhất hai khung cùng kích thước để cộng dồn cảnh tĩnh."""
    with pytest.raises(ValueError):
        spatial.average_images(iter(images))


def test_quality_metrics_identity_and_known_error():
    """Sai khác hằng 10 cho MSE100 và PSNR28.1308; ảnh trùng có SSIM1."""
    image = rgba_gray(np.full((12, 13), 80, dtype=np.uint8))
    identity = spatial.quality_metrics(image, image.copy())
    assert identity['mse'] == 0 and np.isinf(identity['psnr'])
    assert identity['ssim'] == pytest.approx(1)
    reference = rgba_gray(np.full((12, 13), 90, dtype=np.uint8))
    metrics = spatial.quality_metrics(image, reference)
    assert metrics['mse'] == 100
    assert metrics['psnr'] == pytest.approx(28.1308036087)
    c1 = (.01 * 255) ** 2
    assert metrics['ssim'] == pytest.approx((2 * 80 * 90 + c1) / (80 ** 2 + 90 ** 2 + c1))


def test_quality_ignores_hidden_rgb_even_in_local_ssim_windows():
    """Thay RGB phía alpha=0 không ảnh hưởng MSE và cả cửa sổ Gaussian SSIM."""
    reference = rgba_gray(np.arange(25, dtype=np.uint8).reshape(5, 5) * 8)
    image = reference.copy()
    image[0, 0, :3] += 10
    image[1:3, 1:3, 3] = 0
    metrics = spatial.quality_metrics(image, reference)
    image[1:3, 1:3, :3] = 255
    assert spatial.quality_metrics(image, reference) == pytest.approx(metrics)
    reference[4, 4, 3] = 0
    image[4, 4, :3] = 255
    metrics = spatial.quality_metrics(image, reference)
    image[4, 4, :3] = 0
    assert spatial.quality_metrics(image, reference) == pytest.approx(metrics)


def test_quality_tiny_image_and_no_visible_intersection():
    """SSIM trên một pixel hữu hạn; hai ảnh không giao alpha nhìn thấy bị từ chối."""
    metrics = spatial.quality_metrics(rgba_gray([[0]]), rgba_gray([[255]]))
    assert metrics['mse'] == 65025 and metrics['psnr'] == 0
    assert np.isfinite(metrics['ssim'])
    hidden = rgba_gray([[40]])
    hidden[..., 3] = 0
    with pytest.raises(ValueError, match='nhìn thấy'):
        spatial.quality_metrics(hidden, rgba_gray([[40]]))
    with pytest.raises(ValueError, match='kích thước'):
        spatial.quality_metrics(rgba_gray([[40]]), rgba_gray([[40, 40]]))


@pytest.mark.parametrize('function,kwargs', [
    (spatial.smooth, {'kind': 'unknown'}), (spatial.smooth, {'size': 4}),
    (spatial.smooth, {'sigma': np.nan}), (spatial.nearest_mean, {'neighbors': 0}),
    (spatial.nearest_mean, {'neighbors': 10}), (spatial.nearest_mean, {'threshold': -1}),
    (spatial.sobel, {'direction': 'z'}), (spatial.laplacian, {'amount': np.inf}),
    (spatial.unsharp, {'sigma': 0, 'size': 0}), (spatial.unsharp, {'size': 4}),
    (spatial.adaptive_median, {'max_size': 33}), (spatial.pipeline, {'clip_limit': 0}),
    (spatial.pipeline, {'tiles': 0}), (spatial.pipeline, {'sigma': np.nan})])
def test_invalid_spatial_parameters_report_value_error(chapter_matrix, function, kwargs):
    """Tham số sai được chặn rõ ràng trước khi gọi OpenCV."""
    with pytest.raises(ValueError):
        function(chapter_matrix, **kwargs)


@pytest.mark.parametrize('function', [spatial.smooth, spatial.nearest_mean, spatial.sobel,
                                     spatial.laplacian, spatial.unsharp, spatial.adaptive_median,
                                     spatial.pipeline])
def test_rgba_contract_and_input_immutability(rgba, function):
    """Mọi bộ lọc giữ đúng dtype/kích thước/alpha và không sửa mảng nguồn."""
    original = rgba.copy()
    result = function(rgba)
    assert result.dtype == np.uint8 and result.shape == rgba.shape
    assert np.isfinite(result).all()
    np.testing.assert_array_equal(result[..., 3], original[..., 3])
    np.testing.assert_array_equal(rgba, original)
    with pytest.raises(ValueError):
        function(rgba[..., :3])
