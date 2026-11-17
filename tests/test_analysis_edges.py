"""Mặt nạ Chương 3, đổi dấu LoG và đường thẳng tổng hợp để kiểm thử Hough."""
import numpy as np
import pytest

from app.core import analysis_edges as edges


def rgba_gray(values):
    gray = np.asarray(values, dtype=np.uint8)
    return np.dstack((gray, gray, gray, np.full(gray.shape, 255, dtype=np.uint8)))


def test_roberts_textbook_diagonal_masks_and_magnitude():
    """Biên 20|200 ở trang 10 có Gx=-180, Gy=180, độ lớn 254.56."""
    image = rgba_gray([[20, 20, 200, 200]] * 4)
    assert edges.gradient(image, 'roberts', 'x')[1, 1, 0] == 180
    assert edges.gradient(image, 'roberts', 'y')[1, 1, 0] == 180
    assert edges.gradient(image, 'roberts')[1, 1, 0] == 255
    assert edges.gradient(image, 'roberts')[1, 0, 0] == 0


def test_prewitt_equal_weights_and_signed_response_before_absolute():
    """Ba hàng cùng trọng số: biên 70|20 có Gx=-150, Gy=0."""
    image = rgba_gray([[70, 70, 20, 20, 20]] * 5)
    assert edges.gradient(image, 'prewitt', 'x')[2, 1, 0] == 150
    assert edges.gradient(image, 'prewitt', 'y')[2, 1, 0] == 0
    assert edges.gradient(image, 'prewitt')[2, 1, 0] == 150


def test_zero_crossing_selects_single_nearest_endpoint_and_exact_zero():
    response = np.array([[5., 3., -1., -5., -5.]])
    np.testing.assert_array_equal(edges._zero_crossings(response, 2), [[False, False, True, False, False]])
    np.testing.assert_array_equal(edges._zero_crossings(response, 5), np.zeros((1, 5), dtype=bool))
    np.testing.assert_array_equal(edges._zero_crossings(np.array([[2., 0., -2.]]), 1), [[False, True, False]])
    assert not edges._zero_crossings(np.array([[0., 0., 2., 2.]]), 0).any()


def test_log_step_edges_are_thin_and_constant_region_has_no_edges():
    image = rgba_gray(np.pad(np.full((16, 16), 255, dtype=np.uint8), ((0, 0), (16, 0))))
    result = edges.log_zero_crossing(image, sigma=1, threshold=5)
    columns = np.where(np.any(result[..., 0] > 0, axis=0))[0]
    assert len(columns) == 1
    assert columns[0] in (15, 16)
    assert not edges.log_zero_crossing(image, threshold=2040)[..., :3].any()


@pytest.mark.parametrize('mode', ['standard', 'probabilistic'])
def test_hough_marks_known_vertical_line_and_keeps_other_colors(mode):
    gray = np.zeros((96, 96), dtype=np.uint8)
    gray[8:88, 45] = 255
    image = rgba_gray(gray)
    result = edges.hough_lines(image, mode=mode, threshold=35, min_length=50, max_gap=2, line_width=1)
    red = np.all(result[..., :3] == (255, 64, 64), axis=2)
    assert red[:, 43:48].sum() >= 50
    assert not red[:, :20].any()
    if mode == 'probabilistic':
        np.testing.assert_array_equal(edges.hough_lines(image, threshold=35, min_length=200), image)


@pytest.mark.parametrize('shape', [(1, 1), (1, 7), (7, 1), (7, 8)])
def test_constant_and_tiny_images(shape):
    image = rgba_gray(np.full(shape, 80, dtype=np.uint8))
    assert not edges.gradient(image)[..., :3].any()
    assert not edges.gradient(image, 'prewitt')[..., :3].any()
    assert not edges.log_zero_crossing(image)[..., :3].any()
    np.testing.assert_array_equal(edges.hough_lines(image), image)


@pytest.mark.parametrize('function', [edges.gradient, edges.log_zero_crossing, edges.hough_lines])
def test_rgba_immutable_and_hidden_colors_do_not_affect_visible_output(rgba, function):
    original = rgba.copy()
    result = function(rgba)
    assert result.shape == rgba.shape and result.dtype == np.uint8
    np.testing.assert_array_equal(result[..., 3], rgba[..., 3])
    np.testing.assert_array_equal(rgba, original)
    changed = rgba.copy()
    changed[changed[..., 3] == 0, :3] = 0
    visible = rgba[..., 3] > 0
    np.testing.assert_array_equal(function(changed)[visible], result[visible])
    hidden = rgba.copy()
    hidden[..., 3] = 0
    np.testing.assert_array_equal(function(hidden), hidden)
    with pytest.raises(ValueError):
        function(rgba[..., :3])


@pytest.mark.parametrize('function,kwargs', [
    (edges.gradient, {'kind': 'sobel'}), (edges.gradient, {'direction': 'z'}),
    (edges.log_zero_crossing, {'sigma': 0}), (edges.log_zero_crossing, {'sigma': np.nan}),
    (edges.log_zero_crossing, {'threshold': -1}),
    (edges.hough_lines, {'mode': 'other'}), (edges.hough_lines, {'threshold': 0}),
    (edges.hough_lines, {'threshold': 2.3}), (edges.hough_lines, {'min_length': -1}),
    (edges.hough_lines, {'max_gap': np.inf}), (edges.hough_lines, {'line_width': 0}),
    (edges.hough_lines, {'max_lines': 0}), (edges.hough_lines, {'canny_low': 150}),
])
def test_invalid_parameters_are_rejected(function, kwargs):
    with pytest.raises(ValueError):
        function(rgba_gray([[40]]), **kwargs)
