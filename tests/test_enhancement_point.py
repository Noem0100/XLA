"""Đối chiếu biến đổi điểm/histogram với ví dụ tính tay trong Chương 2."""
import numpy as np
import pytest

from app.core import enhancement_point as point


def rgba_levels(levels, alpha=255):
    """Dựng ảnh xám RGBA nhỏ từ dãy mức để kiểm tra kết quả tính tay."""
    values = np.asarray(levels, dtype=np.uint8).reshape(1, -1)
    return np.dstack((values, values, values, np.full_like(values, alpha)))


def test_chapter_log_gamma_and_negative_examples():
    """Ví dụ 2.4: r=50 lần lượt ra 205,181,113 qua âm bản/log/gamma0.5."""
    image = rgba_levels([50])
    assert point.negative(image)[0, 0, 0] == 205
    assert point.logarithm(image)[0, 0, 0] == 181
    assert point.gamma(image, .5)[0, 0, 0] == 113


def test_linear_clips_signed_values_without_absolute_value():
    """Bài giảng yêu cầu cộng b rồi clip; số âm không bị convertScaleAbs đảo dấu."""
    image = rgba_levels([20, 30, 210, 240])
    np.testing.assert_array_equal(point.linear(image, gain=1.5, pivot=128)[0, :, 0], [0, 0, 251, 255])
    np.testing.assert_array_equal(point.linear(image, bias=-40)[0, :, 0], [0, 0, 170, 200])
    np.testing.assert_array_equal(point.linear(image, bias=40)[0, :, 0], [60, 70, 250, 255])


def test_piecewise_and_bunching_examples():
    """Giãn [80,170] cho125→128; bó B64 cho30,90,150,210→0,64,128,192."""
    image = rgba_levels([0, 80, 125, 170, 255])
    np.testing.assert_array_equal(point.piecewise(image)[0, :, 0], [0, 0, 128, 255, 255])
    np.testing.assert_array_equal(point.quantize(rgba_levels([30, 90, 150, 210]))[0, :, 0], [0, 64, 128, 192])
    np.testing.assert_array_equal(point.piecewise(image, 0, 0, 255, 255), image)


def test_threshold_boundary_and_bit_planes():
    """Ngưỡng tay gồm dấu bằng; LSB/MSB đúng các bit của mã xám."""
    image = rgba_levels([0, 1, 127, 128, 129, 255])
    np.testing.assert_array_equal(point.threshold(image, 128)[0, :, 0], [0, 0, 0, 255, 255, 255])
    np.testing.assert_array_equal(point.bit_plane(image, 0)[0, :, 0], [0, 255, 255, 0, 255, 255])
    np.testing.assert_array_equal(point.bit_plane(image, 7)[0, :, 0], [0, 0, 0, 255, 255, 255])


def test_equalization_uses_chapter_cdf_and_ignores_hidden_pixels():
    """CDF trực tiếp khác cdf-min OpenCV; pixel giấu không được tính vào phân bố."""
    image = rgba_levels([0, 0, 128, 255, 15])
    image[0, -1, 3] = 0
    result = point.equalize(image)
    np.testing.assert_array_equal(result[0, :4, 0], [128, 128, 191, 255])
    np.testing.assert_array_equal(point.equalize(rgba_levels([75, 75]))[0, :, 0], [255, 255])


def test_histogram_matching_discrete_inverse_cdf():
    """Đối sánh dùng ngưỡng CDF đích đầu tiên đạt CDF nguồn, giữ alpha nguồn."""
    source = rgba_levels([0, 255], alpha=128)
    reference = rgba_levels([50, 100, 150, 200, 0])
    reference[0, -1, 3] = 0
    result = point.match_histogram(source, reference)
    np.testing.assert_array_equal(result[0, :, 0], [100, 200])
    np.testing.assert_array_equal(result[..., 3], source[..., 3])
    np.testing.assert_array_equal(point.match_histogram(source, rgba_levels([123]))[0, :, 0], [123, 123])
    with pytest.raises(ValueError):
        point.match_histogram(source, rgba_levels([0], alpha=0))


def test_otsu_hand_computed_six_level_histogram():
    """Bảng2.2 có n=[15,5,4,3,2,1], ngưỡng cực đại là t=1 và nền≤1."""
    levels = np.repeat(np.arange(6), [15, 5, 4, 3, 2, 1])
    image = rgba_levels(np.append(levels, 255))
    image[0, -1, 3] = 0
    result, threshold = point.otsu(image)
    assert threshold == 1
    np.testing.assert_array_equal(result[0, :30, 0], np.where(levels > 1, 255, 0))


@pytest.mark.parametrize('function', [point.linear, point.negative, point.logarithm,
    point.gamma, point.piecewise, point.threshold, point.bit_plane, point.quantize,
    point.equalize, point.clahe, lambda image: point.match_histogram(image, rgba_levels([20, 200]))])
def test_point_operations_preserve_source_and_alpha(function, rgba):
    """Mỗi phép trả RGBA mới, giữ alpha kể cả bán trong suốt và không sửa nguồn."""
    before = rgba.copy()
    result = function(rgba)
    np.testing.assert_array_equal(rgba, before)
    np.testing.assert_array_equal(result[..., 3], rgba[..., 3])
    assert result.shape == rgba.shape and result.dtype == np.uint8
    assert not np.shares_memory(result, rgba)


def test_transparent_statistics_and_clahe_ignore_hidden_rgb():
    """Ảnh hoàn toàn trong suốt an toàn; RGB giấu không gây thay đổi CLAHE thấy được."""
    transparent = rgba_levels([20, 100, 200], alpha=0)
    for function in (point.equalize, point.clahe):
        np.testing.assert_array_equal(function(transparent), transparent)
    np.testing.assert_array_equal(point.otsu(transparent)[0], transparent)
    first = np.tile(rgba_levels([25, 75, 125, 175]), (4, 1, 1))
    first[:, 3, 3] = 0
    second = first.copy()
    second[:, 3, :3] = [255, 0, 255]
    np.testing.assert_array_equal(point.clahe(first, tiles=2)[..., :3], point.clahe(second, tiles=2)[..., :3])


@pytest.mark.parametrize('function', [
    lambda image: point.linear(image, gain=np.nan),
    lambda image: point.logarithm(image, gain=-1),
    lambda image: point.gamma(image, gamma=0),
    lambda image: point.gamma(image, gamma=np.inf),
    lambda image: point.piecewise(image, 80, 0, 80, 255),
    lambda image: point.piecewise(image, 0, 5, 200, 255),
    lambda image: point.threshold(image, 256),
    lambda image: point.bit_plane(image, 8),
    lambda image: point.bit_plane(image, 1.5),
    lambda image: point.quantize(image, 0),
    lambda image: point.clahe(image, tiles=0),
    lambda image: point.clahe(image, clip_limit=np.nan),
])
def test_invalid_point_parameters_raise(function):
    """Tham số sai bị chặn trước khi NumPy/OpenCV trả kết quả khó đoán."""
    with pytest.raises(ValueError):
        function(rgba_levels([50]))
