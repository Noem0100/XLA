"""Registry parameters must reach the existing analysis algorithms unchanged."""
import numpy as np
import pytest

from app.core import analysis


def gray_image(values):
    gray = np.asarray(values, dtype=np.uint8)
    return np.dstack((gray, gray, gray, np.full(gray.shape, 255, dtype=np.uint8)))


@pytest.mark.parametrize('algorithm', list(analysis.ALGORITHMS))
def test_every_registered_algorithm_runs_with_its_dialog_defaults(algorithm):
    """The picker must import and run every entry without unsupported keyword errors."""
    image = gray_image(np.tile([20, 20, 90, 90, 160, 160, 220, 220], (8, 1)))
    before = image.copy()
    fields = analysis.fields_for_image(algorithm, image.shape)
    params = {key: value[0] if isinstance(value, list) else value
              for key, _, value, _, _ in fields}
    result, info = analysis.process(image, algorithm, params)
    assert result.dtype == np.uint8 and result.shape == image.shape
    assert isinstance(info, str)
    np.testing.assert_array_equal(result[..., 3], image[..., 3])
    np.testing.assert_array_equal(image, before)


def test_region_coordinates_use_width_for_x_and_height_for_y():
    """A non-square image exposes swapped axes and rejects out-of-bounds seeds."""
    original = analysis.ALGORITHMS['region_grow'].fields
    fields = {key: (value, low, high) for key, _, value, low, high
              in analysis.fields_for_image('region_grow', (3, 7, 4))}
    assert fields['seed_x'] == (3, 0, 6)
    assert fields['seed_y'] == (1, 0, 2)
    assert analysis.ALGORITHMS['region_grow'].fields == original
    image = gray_image([[20] * 7] * 3)
    image[2, 6, :3] = 100
    result, info = analysis.process(image, 'region_grow', {'seed_x': 6, 'seed_y': 2, 'tolerance': 0})
    assert np.count_nonzero(result[..., 0]) == 1 and result[2, 6, 0] == 255
    assert '(6, 2)' in info
    with pytest.raises(ValueError):
        analysis.process(image, 'region_grow', {'seed_x': 7})
    with pytest.raises(ValueError):
        analysis.process(image, 'region_grow', {'seed_y': 3})


def test_morphology_operation_and_boolean_parameters_reach_core():
    image = gray_image([[0, 0, 0], [0, 255, 0], [0, 0, 0]])
    dilated, _ = analysis.process(image, 'dilate', {'shape': 'cross', 'grayscale': False})
    expected = np.array([[0, 255, 0], [255, 255, 255], [0, 255, 0]], dtype=np.uint8)
    np.testing.assert_array_equal(dilated[..., 0], expected)
    eroded, _ = analysis.process(image, 'erode')
    assert not eroded[..., :3].any()


def test_region_information_is_not_discarded():
    image = gray_image([[0, 0, 255], [0, 0, 0], [255, 0, 0]])
    result, info = analysis.process(image, 'components', {'connectivity': 4, 'output': 'binary'})
    np.testing.assert_array_equal(result, image)
    assert '2 vùng' in info


def test_invalid_algorithm_and_parameters_raise_clear_errors():
    image = gray_image([[10]])
    with pytest.raises(ValueError, match='không tồn tại'):
        analysis.process(image, 'missing')
    with pytest.raises(ValueError, match='Tham số'):
        analysis.process(image, 'prewitt', {'operation': 'wrong'})
