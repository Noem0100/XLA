"""Kiểm thử lọc gam màu qua hue tuần hoàn và bảo toàn ảnh RGBA đầu vào."""
import numpy as np
import pytest

from app.core.filters import channel_view, color_range


@pytest.mark.parametrize('channel', [0, 1, 2])
def test_channel_view_preserves_component_not_only_hue(channel):
    """Màu hỗn hợp vẫn hiện cường độ kênh, hai kênh còn lại bằng 0."""
    image = np.array([[[210, 90, 65, 255], [170, 70, 50, 128],
                       [240, 190, 165, 0], [127, 127, 127, 255]]], dtype=np.uint8)
    original = image.copy()
    expected = np.zeros_like(image)
    expected[..., channel] = image[..., channel]
    expected[..., 3] = image[..., 3]
    result = channel_view(image, channel)
    np.testing.assert_array_equal(result, expected)
    np.testing.assert_array_equal(image, original)
    assert not np.shares_memory(result, image)


def test_channel_view_brightness_uses_histogram_weights():
    """Chỉ chế độ độ sáng tạo ảnh xám; RGB giữ nguyên alpha."""
    image = np.array([[[255, 0, 0, 3], [0, 255, 0, 128], [0, 0, 255, 255]]], dtype=np.uint8)
    np.testing.assert_array_equal(channel_view(image, 3),
                                  [[[54, 54, 54, 3], [182, 182, 182, 128], [18, 18, 18, 255]]])


@pytest.mark.parametrize('channel', [-1, 4, None, 'red', 1.5])
def test_invalid_view_channel_raises(channel):
    with pytest.raises(ValueError):
        channel_view(np.full((1, 1, 4), 255, dtype=np.uint8), channel)


@pytest.mark.parametrize('channel', [0, 1, 2])
def test_only_chosen_primary_keeps_its_color(channel):
    """Gam chính được giữ nguyên, hai gam khác thành xám có độ sáng biết trước."""
    image = np.array([[[255, 0, 0, 255], [0, 255, 0, 128], [0, 0, 255, 0]]], dtype=np.uint8)
    original = image.copy()
    expected = np.array([[[54, 54, 54, 255], [182, 182, 182, 128], [18, 18, 18, 0]]], dtype=np.uint8)
    expected[0, channel] = image[0, channel]
    result = color_range(image, channel)
    np.testing.assert_array_equal(result, expected)
    np.testing.assert_array_equal(image, original)
    assert result.dtype == np.uint8 and result.shape == image.shape
    assert not np.shares_memory(result, image)


def test_red_range_wraps_across_hue_zero():
    """Hai màu đỏ ở hai phía 0/360 độ vẫn có sắc đỏ rõ, xanh bị chuyển xám."""
    image = np.array([[[255, 8, 0, 255], [255, 0, 8, 255], [0, 255, 0, 255]]], dtype=np.uint8)
    result = color_range(image, 0)
    assert np.all(result[0, :2, 0] >= 250)
    assert np.all(result[0, :2, 1:3] <= 10)
    np.testing.assert_array_equal(result[0, 2], [182, 182, 182, 255])


@pytest.mark.parametrize('channel', [0, 1, 2, 3])
def test_neutral_levels_and_alpha_remain_unchanged(channel):
    """Ảnh xám và các giá trị alpha không đổi khi bật bất kỳ gam màu nào."""
    image = np.array([[[0, 0, 0, 0], [27, 27, 27, 1], [128, 128, 128, 127],
                       [255, 255, 255, 255]]], dtype=np.uint8)
    np.testing.assert_array_equal(color_range(image, channel), image)


def test_brightness_produces_expected_gray_levels():
    """Kênh độ sáng dùng trọng số Y' thống nhất với histogram và giữ alpha."""
    image = np.array([[[255, 0, 0, 3], [0, 255, 0, 128], [0, 0, 255, 255],
                       [255, 255, 255, 0]]], dtype=np.uint8)
    result = color_range(image, 3)
    expected = np.array([[[54, 54, 54, 3], [182, 182, 182, 128], [18, 18, 18, 255],
                          [255, 255, 255, 0]]], dtype=np.uint8)
    np.testing.assert_array_equal(result, expected)


def test_neighboring_hues_fade_gradually_to_gray():
    """Sắc cam trong gam đỏ được pha mềm, sắc vàng ở biên thành xám."""
    image = np.array([[[255, 0, 0, 255], [255, 128, 0, 255], [255, 255, 0, 255]]], dtype=np.uint8)
    result = color_range(image, 0)
    spread = np.ptp(result[0, :, :3].astype(int), axis=1)
    assert spread[0] == 255 and 0 < spread[1] < 255 and spread[2] == 0


@pytest.mark.parametrize('channel', [-1, 4, None, 'red', 1.5])
def test_invalid_color_channel_raises(channel):
    """Kênh không hợp lệ báo lỗi thay vì chọn nhầm gam màu."""
    with pytest.raises(ValueError):
        color_range(np.full((1, 1, 4), 255, dtype=np.uint8), channel)
