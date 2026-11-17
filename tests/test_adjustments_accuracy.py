"""Known color examples catch differences between HSL, HSV and gamma conventions."""
import numpy as np
import pytest

from app.core import adjustments, enhancement_point


@pytest.mark.parametrize('saturation,lightness,expected', [
    (0, 25, [255, 128, 128]),
    (0, 50, [255, 255, 255]),
    (0, -50, [0, 0, 0]),
    (-100, 0, [128, 128, 128]),
])
def test_hsl_red_uses_lightness_and_hsl_saturation(saturation, lightness, expected):
    """Red has HSL L=0.5; lightening must work even when HSV V is already 1."""
    source = np.array([[[255, 0, 0, 157]]], dtype=np.uint8)
    before = source.copy()
    result = adjustments.hsl(source, 0, 0, saturation, lightness)
    np.testing.assert_allclose(result[0, 0, :3], expected, atol=1)
    assert result[0, 0, 3] == 157
    np.testing.assert_array_equal(source, before)


def test_hsl_edits_only_selected_hue_and_keeps_gray_neutral():
    """A red selection lightens red; green, blue and uncolored pixels stay unchanged."""
    source = np.array([[[255, 0, 0, 255], [0, 255, 0, 255],
                        [0, 0, 255, 255], [80, 80, 80, 255]]], dtype=np.uint8)
    result = adjustments.hsl(source, 0, 0, 0, 25)
    np.testing.assert_allclose(result[0, 0, :3], [255, 128, 128], atol=1)
    np.testing.assert_array_equal(result[0, 1:], source[0, 1:])


@pytest.mark.parametrize('gamma', [.1, .5, 1., 2., 3.])
def test_main_gamma_matches_direct_power_transform(gamma):
    """Both gamma controls must use s=255(r/255)^gamma, with 100 meaning gamma=1."""
    values = np.arange(256, dtype=np.uint8).reshape(16, 16)
    source = np.dstack((values, values, values, 255 - values))
    result = adjustments.adjust(source, {'gamma': gamma * 100})
    expected = enhancement_point.gamma(source, gamma)
    np.testing.assert_allclose(result, expected, atol=1)
    np.testing.assert_array_equal(result[..., 3], source[..., 3])
