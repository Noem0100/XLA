"""Ví dụ Chương 3 và tính chất tập hợp của các phép toán hình thái học."""
import cv2
import numpy as np
import pytest

from app.core import analysis_morphology as morph


def rgba_gray(values):
    gray = np.asarray(values, dtype=np.uint8)
    return np.dstack((gray, gray, gray, np.full(gray.shape, 255, dtype=np.uint8)))


def binary_image(values):
    return rgba_gray(np.asarray(values, dtype=np.uint8) * 255)


def test_textbook_cross_dilation_and_erosion():
    """Khối 3×3 của trang 40–41: giãn ra 21 ô, co còn đúng tâm."""
    image = binary_image(np.pad(np.ones((3, 3), dtype=np.uint8), 1))
    dilation = morph.morphology(image, 'dilate')[..., 0] > 0
    expected = np.ones((5, 5), dtype=bool)
    expected[[0, 0, 4, 4], [0, 4, 0, 4]] = False
    np.testing.assert_array_equal(dilation, expected)
    erosion = morph.morphology(image, 'erode')[..., 0] > 0
    expected[:] = False
    expected[2, 2] = True
    np.testing.assert_array_equal(erosion, expected)


def test_open_removes_isolated_speck_close_fills_small_hole_boundary_subtracts_erosion():
    gray = np.zeros((11, 11), dtype=np.uint8)
    gray[3:8, 3:8] = 255
    gray[1, 1] = 255
    image = rgba_gray(gray)
    opened = morph.morphology(image, 'open', shape='rect')
    assert opened[1, 1, 0] == 0
    np.testing.assert_array_equal(opened[3:8, 3:8, 0], np.full((5, 5), 255))
    image[5, 5, :3] = 0
    closed = morph.morphology(image, 'close', shape='rect')
    assert closed[5, 5, 0] == 255
    assert closed[1, 1, 0] == 255
    boundary = morph.morphology(opened, 'boundary', shape='rect')
    assert boundary[3, 3, 0] == 255 and boundary[5, 5, 0] == 0
    assert np.count_nonzero(boundary[..., 0]) == 16


def test_open_idempotence_and_containment_close_includes_objects_at_image_border():
    rng = np.random.default_rng(7)
    image = binary_image(rng.integers(0, 2, (17, 19), dtype=np.uint8))
    opened = morph.morphology(image, 'open', shape='rect')
    closed = morph.morphology(image, 'close', shape='rect')
    assert np.all(opened[..., 0] <= image[..., 0])
    assert np.all(closed[..., 0] >= image[..., 0])
    np.testing.assert_array_equal(morph.morphology(opened, 'open', shape='rect'), opened)
    # Đệm ngoài đủ rộng: phép đóng không làm mất hàng trắng sát mép.
    full = binary_image(np.ones((3, 5), dtype=np.uint8))
    np.testing.assert_array_equal(morph.morphology(full, 'close', size=5), full)


def test_kernel_shapes_and_iterations_are_effective():
    image = binary_image(np.pad(np.ones((1, 1), dtype=np.uint8), 3))
    assert np.count_nonzero(morph.morphology(image, shape='cross')[..., 0]) == 5
    assert np.count_nonzero(morph.morphology(image, shape='rect')[..., 0]) == 9
    assert np.count_nonzero(morph.morphology(image, shape='ellipse')[..., 0]) == 5
    assert np.count_nonzero(morph.morphology(image, iterations=2)[..., 0]) == 13


def test_fill_all_closed_holes_preserves_open_and_transparent_background():
    gray = np.zeros((11, 13), dtype=np.uint8)
    gray[1:10, 1:12] = 255
    gray[3:5, 3:5] = 0
    gray[6:8, 8:10] = 0
    gray[1:4, 7] = 0  # Lối mở ra ngoài không được lấp.
    image = rgba_gray(gray)
    filled = morph.fill_holes(image)
    assert np.all(filled[3:5, 3:5, 0] == 255)
    assert np.all(filled[6:8, 8:10, 0] == 255)
    assert np.all(filled[1:4, 7, 0] == 0)
    image[3, 3, 3] = 0  # Một lỗ có alpha=0 được coi là miền nền ngoài.
    assert np.all(morph.fill_holes(image)[3:5, 3:5, 0] == 0)


def test_fill_holes_connectivity_decides_whether_diagonal_gap_is_open():
    gray = np.full((5, 5), 255, dtype=np.uint8)
    gray[[0, 1, 2], [0, 1, 2]] = 0
    image = rgba_gray(gray)
    assert morph.fill_holes(image, connectivity=4)[2, 2, 0] == 255
    assert morph.fill_holes(image, connectivity=8)[2, 2, 0] == 0


def test_grayscale_min_max_and_top_hat_preserve_constant_background():
    image = rgba_gray(np.full((7, 7), 80, dtype=np.uint8))
    image[3, 3, :3] = 200
    assert morph.morphology(image, 'erode', grayscale=True)[3, 3, 0] == 80
    assert morph.morphology(image, 'dilate', grayscale=True)[3, 2, 0] == 200
    top_hat = morph.morphology(image, 'top_hat', grayscale=True)
    assert top_hat[3, 3, 0] == 120
    assert np.count_nonzero(top_hat[..., 0]) == 1
    image[0, 0, 3] = 0
    eroded = morph.morphology(image, 'erode', grayscale=True)
    assert eroded[0, 1, 0] == 80  # Alpha=0 không trở thành số 0 kéo tối láng giềng.


@pytest.mark.parametrize('rotation,corner', [(0, (2, 2)), (90, (6, 2)), (180, (6, 6)), (270, (2, 6))])
def test_hit_or_miss_finds_requested_corner(rotation, corner):
    image = binary_image(np.pad(np.ones((5, 5), dtype=np.uint8), 2))
    result = morph.hit_or_miss(image, rotation=rotation)[..., 0]
    assert result[corner] == 255
    assert np.count_nonzero(result) == 1


@pytest.mark.parametrize('shape', ['rect', 'cross', 'ellipse'])
def test_distance_skeleton_matches_definition_by_successive_erosion(shape):
    """Đối chiếu công thức hợp (co−mở) độc lập với cách tối ưu bằng khoảng cách."""
    gray = np.zeros((13, 15), dtype=np.uint8)
    gray[1:12, 2:13] = 255
    gray[0, 0] = 255
    gray[2, 8] = 0
    image = rgba_gray(gray)
    kernels = {'rect': cv2.MORPH_RECT, 'cross': cv2.MORPH_CROSS, 'ellipse': cv2.MORPH_ELLIPSE}
    kernel = cv2.getStructuringElement(kernels[shape], (3, 3))
    current = gray.copy()
    expected = np.zeros_like(gray)
    while current.any():
        eroded = cv2.erode(current, kernel, borderType=cv2.BORDER_CONSTANT, borderValue=0)
        opened = cv2.dilate(eroded, kernel, borderType=cv2.BORDER_CONSTANT, borderValue=0)
        expected |= cv2.subtract(current, opened)
        current = eroded
    np.testing.assert_array_equal(morph.skeleton(image, shape=shape)[..., 0], expected)


def test_threshold_invert_and_hidden_pixels_are_excluded_from_foreground():
    image = rgba_gray([[0, 127, 128, 255]])
    np.testing.assert_array_equal(morph.morphology(image, size=1)[0, :, 0], [0, 0, 255, 255])
    np.testing.assert_array_equal(morph.morphology(image, size=1, invert=True)[0, :, 0], [255, 255, 0, 0])
    image = rgba_gray([[0, 255, 0], [0, 255, 0], [0, 0, 0]])
    image[:2, 1, 3] = 0
    assert not morph.morphology(image, 'dilate')[..., :3].any()


@pytest.mark.parametrize('shape', [(1, 1), (1, 5), (5, 1)])
def test_tiny_images(shape):
    image = rgba_gray(np.full(shape, 200, dtype=np.uint8))
    for operation in ('dilate', 'erode', 'open', 'close'):
        np.testing.assert_array_equal(morph.morphology(image, operation, grayscale=True), image)
    np.testing.assert_array_equal(morph.morphology(image, 'close'), binary_image(np.ones(shape)))
    assert morph.fill_holes(image).shape == image.shape
    assert morph.hit_or_miss(image).shape == image.shape
    assert morph.skeleton(image).shape == image.shape


@pytest.mark.parametrize('function', [morph.morphology, morph.fill_holes, morph.hit_or_miss, morph.skeleton])
def test_rgba_immutability_hidden_colors_and_validation(rgba, function):
    original = rgba.copy()
    result = function(rgba)
    assert result.shape == rgba.shape and result.dtype == np.uint8
    np.testing.assert_array_equal(result[..., 3], rgba[..., 3])
    np.testing.assert_array_equal(rgba, original)
    changed = rgba.copy()
    changed[changed[..., 3] == 0, :3] = 255
    np.testing.assert_array_equal(function(changed), result)
    hidden = rgba.copy()
    hidden[..., 3] = 0
    np.testing.assert_array_equal(function(hidden), hidden)
    with pytest.raises(ValueError):
        function(rgba[..., :3])


@pytest.mark.parametrize('function,kwargs', [
    (morph.morphology, {'size': 2}), (morph.morphology, {'shape': 'triangle'}),
    (morph.morphology, {'operation': 'other'}), (morph.morphology, {'iterations': 0}),
    (morph.morphology, {'iterations': 1.2}), (morph.morphology, {'grayscale': 'yes'}),
    (morph.morphology, {'threshold': np.nan}), (morph.fill_holes, {'threshold': 256}),
    (morph.fill_holes, {'connectivity': 6}), (morph.fill_holes, {'invert': 1}),
    (morph.hit_or_miss, {'rotation': 45}), (morph.skeleton, {'shape': 'unknown'}),
])
def test_invalid_parameters(function, kwargs):
    with pytest.raises(ValueError):
        function(rgba_gray([[40]]), **kwargs)
