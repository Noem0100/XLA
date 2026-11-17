"""Kiểm thử đáp ứng tần số, khử vân tuần hoàn và mô hình khôi phục ảnh."""
import cv2
import numpy as np
import pytest

from app.core import enhancement_frequency as frequency


def rgba_gray(gray):
    """Ghép ảnh mức xám thành RGBA đục để kiểm tra các đáp ứng số."""
    gray = np.asarray(gray, dtype=np.uint8)
    return np.dstack((gray, gray, gray, np.full(gray.shape, 255, dtype=np.uint8)))


@pytest.mark.parametrize('family', ['gaussian', 'butterworth', 'ideal'])
def test_low_pass_rejects_fine_sinusoid(family):
    """Thông thấp làm giảm dao động tần số cao trong vùng xa biên đệm."""
    x = np.arange(128)
    image = rgba_gray(np.tile(np.rint(128 + 40 * np.sin(2 * np.pi * x / 4)), (128, 1)))
    result = frequency.frequency_filter(image, family=family, cutoff=.025)
    original = image[32:-32, 32:-32, 0].astype(float)
    filtered = result[32:-32, 32:-32, 0].astype(float)
    # Lọc lý tưởng vẫn có gợn chậm do biên đệm; đo riêng sóng cần loại bỏ.
    amplitude = 2 * abs((filtered * np.sin(2 * np.pi * np.arange(32, 96) / 4)).mean())
    assert amplitude < 1
    assert filtered.std() < original.std() / 3
    assert abs(filtered.mean() - 128) < 5


def test_high_pass_retains_signed_response_and_boost_identity():
    """Ảnh thông cao có cả hai phía mức 128, boost hệ số 0 giữ nguyên ảnh."""
    gray = np.full((64, 64), 80, dtype=np.uint8)
    gray[:, 32:] = 180
    image = rgba_gray(gray)
    response = frequency.frequency_filter(image, pass_type='high', cutoff=.08)
    assert response[32, 31, 0] < 128 < response[32, 32, 0]
    assert abs(int(response[32, 10, 0]) - 128) <= 1
    np.testing.assert_array_equal(frequency.frequency_filter(image, pass_type='boost', amount=0), image)


def test_notch_removes_selected_periodic_stripes():
    """Cặp chắn tại ±16 chu kỳ/128 pixel loại phần lớn nhiễu vân dọc."""
    x = np.arange(128)
    image = rgba_gray(np.tile(np.rint(128 + 40 * np.cos(2 * np.pi * 16 * x / 128)), (128, 1)))
    result = frequency.notch_filter(image, offset_x=.125, offset_y=0, radius=.02)
    original = image[32:-32, 32:-32, 0].astype(float)
    filtered = result[32:-32, 32:-32, 0].astype(float)
    assert filtered.std() < original.std() / 4
    assert abs(filtered.mean() - 128) < 2


def test_notch_is_symmetric_for_opposite_offsets():
    """Đổi dấu tọa độ chỉ hoán đổi hai đỉnh chắn, không đổi kết quả thực."""
    image = rgba_gray(np.arange(256, dtype=np.uint8).reshape(16, 16))
    a = frequency.notch_filter(image, .18, -.14, .02)
    b = frequency.notch_filter(image, -.18, .14, .02)
    np.testing.assert_array_equal(a, b)


@pytest.mark.parametrize('method', ['inverse', 'wiener'])
@pytest.mark.parametrize('psf', ['gaussian', 'motion'])
def test_delta_psf_restoration_has_no_shift_or_sign_error(method, psf):
    """PSF xung đơn vị và K=0 khôi phục đúng vị trí, không đảo hay dịch ảnh."""
    image = rgba_gray(np.arange(256, dtype=np.uint8).reshape(16, 16))
    result = frequency.restore(image, method=method, psf=psf, size=1, noise=0)
    np.testing.assert_array_equal(result, image)


def test_wiener_delta_psf_matches_known_gain():
    """Với H=1 và K=1, công thức Wiener cho đúng một nửa mức xám."""
    image = rgba_gray(np.full((8, 8), 120, dtype=np.uint8))
    result = frequency.restore(image, size=1, noise=1)
    np.testing.assert_array_equal(result[..., :3], 60)


def test_wiener_reduces_error_when_gaussian_psf_matches():
    """Khôi phục làm giảm MSE khi mô hình PSF trùng phép mờ trên ảnh tổng hợp."""
    original = np.full((64, 64), 70, dtype=np.uint8)
    original[20:44, 20:44] = 180
    original[28:36, 28:36] = 110
    blurred = cv2.GaussianBlur(original, (5, 5), 1., borderType=cv2.BORDER_REFLECT_101)
    result = frequency.restore(rgba_gray(blurred), size=5, sigma=1., noise=.0001)[..., 0]
    before = np.mean((blurred.astype(float) - original) ** 2)
    after = np.mean((result.astype(float) - original) ** 2)
    assert after < before / 4


def test_spectrum_black_and_dc_peak():
    """Ảnh đen có phổ đen hữu hạn, ảnh hằng có đỉnh DC đúng tâm."""
    black = rgba_gray(np.zeros((16, 20), dtype=np.uint8))
    assert not np.any(frequency.spectrum(black)[..., :3])
    constant = rgba_gray(np.full((16, 20), 50, dtype=np.uint8))
    result = frequency.spectrum(constant)
    assert result[8, 10, 0] == 255
    assert np.count_nonzero(result[..., 0]) == 1


@pytest.mark.parametrize('algorithm,params', [
    (frequency.spectrum, {}),
    (frequency.frequency_filter, {}),
    (frequency.frequency_filter, {'pass_type': 'high'}),
    (frequency.notch_filter, {}),
    (frequency.restore, {}),
    (frequency.homomorphic, {}),
])
def test_alpha_source_and_constant_or_transparent_are_safe(algorithm, params):
    """Mọi bộ lọc giữ alpha, dữ liệu nguồn và trả ảnh 8 bit hữu hạn."""
    image = np.full((13, 15, 4), 80, dtype=np.uint8)
    image[..., 3] = np.arange(15, dtype=np.uint8) * 17
    original = image.copy()
    result = algorithm(image, **params)
    assert result.shape == image.shape and result.dtype == np.uint8
    np.testing.assert_array_equal(result[..., 3], image[..., 3])
    np.testing.assert_array_equal(image, original)
    image[..., 3] = 0
    assert algorithm(image, **params).dtype == np.uint8


def test_homomorphic_unit_transfer_is_identity():
    """Hai hệ số bằng 1 tạo H=1, log và exp ngược nhau trong sai số 8 bit."""
    image = rgba_gray(np.arange(256, dtype=np.uint8).reshape(16, 16))
    np.testing.assert_array_equal(frequency.homomorphic(image, low_gain=1, high_gain=1), image)


@pytest.mark.parametrize('function,params', [
    (frequency.frequency_filter, {'cutoff': 0}),
    (frequency.frequency_filter, {'cutoff': float('nan')}),
    (frequency.frequency_filter, {'family': 'unknown'}),
    (frequency.frequency_filter, {'order': 0}),
    (frequency.frequency_filter, {'pass_type': 'unknown'}),
    (frequency.notch_filter, {'offset_x': 0, 'offset_y': 0}),
    (frequency.notch_filter, {'radius': -1}),
    (frequency.restore, {'size': 2}),
    (frequency.restore, {'noise': -1}),
    (frequency.restore, {'epsilon': 0}),
    (frequency.restore, {'sigma': float('inf')}),
    (frequency.homomorphic, {'low_gain': 2, 'high_gain': 1}),
])
def test_invalid_parameters_raise(function, params):
    """Tham số không hợp lệ được báo rõ trước khi biến đổi Fourier."""
    image = rgba_gray(np.full((8, 8), 80, dtype=np.uint8))
    with pytest.raises(ValueError):
        function(image, **params)


def test_fft_memory_budget_is_checked_before_allocation(monkeypatch):
    """Chặn khối FFT quá lớn trước cấp phát bộ nhớ của phép biến đổi."""
    monkeypatch.setattr(frequency, 'MAX_FFT_PIXELS', 100)
    with pytest.raises(ValueError, match='FFT'):
        frequency.frequency_filter(rgba_gray(np.zeros((10, 10), dtype=np.uint8)))
