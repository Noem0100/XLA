"""Kiểm tra số đếm histogram và đồng bộ với các thao tác chỉnh ảnh."""
import numpy as np
import pytest
from PySide6.QtWidgets import QApplication

from app.core import adjustments, geometry
from app.ui.histogram import Histogram
from app.ui.window import MainWindow


@pytest.fixture(scope='module')
def qt_app():
    """Giữ QApplication trong suốt các kiểm thử widget của mô-đun."""
    return QApplication.instance() or QApplication([])


def test_rgb_and_brightness_counts_ignore_hidden_pixels(qt_app):
    """Màu cơ bản có đúng 256 bin; alpha nhỏ vẫn được đếm, alpha=0 bị bỏ."""
    image = np.array([[[0, 0, 0, 255], [255, 255, 255, 255],
                       [255, 0, 0, 255], [0, 255, 0, 255],
                       [0, 0, 255, 1], [17, 33, 49, 0]]], dtype=np.uint8)
    chart = Histogram()
    chart.set_image(image)
    expected = np.zeros((4, 256), dtype=np.int64)
    expected[:3, 0] = 3
    expected[:3, 255] = 2
    expected[3, [0, 255, 54, 182, 18]] = 1
    assert chart.pixel_count == 5
    np.testing.assert_array_equal(chart.values, expected)
    np.testing.assert_array_equal(chart.values.sum(axis=1), [5] * 4)
    chart.close()


def test_reference_keeps_its_own_counts_and_can_be_cleared(qt_app):
    """So sánh ảnh khác kích thước giữ số đếm gốc và không sửa dữ liệu nguồn."""
    before = np.full((2, 3, 4), 255, dtype=np.uint8)
    after = np.zeros((1, 2, 4), dtype=np.uint8)
    after[..., 3] = 255
    chart = Histogram()
    chart.set_reference(before)
    chart.set_context('Cắt ảnh')
    chart.set_image(after)
    assert chart.reference_pixel_count == 6
    assert chart.pixel_count == 2
    np.testing.assert_array_equal(chart.reference_values[:, 255], [6] * 4)
    np.testing.assert_array_equal(chart.values[:, 0], [2] * 4)
    assert chart.context.text() == 'Cắt ảnh'
    np.testing.assert_array_equal(before, np.full((2, 3, 4), 255, dtype=np.uint8))
    counts = chart.values.copy()
    chart.set_reference(None)
    assert chart.reference_values is None and chart.reference_pixel_count == 0
    np.testing.assert_array_equal(chart.values, counts)
    chart.close()


@pytest.mark.parametrize('logarithmic', [False, True])
def test_enlarged_histogram_preserves_an_independent_snapshot(qt_app, logarithmic):
    """Biểu đồ phóng to giữ dữ liệu, thang và tên khi panel nguồn đổi ảnh."""
    source = Histogram()
    enlarged = Histogram()
    before = np.full((2, 3, 4), 255, dtype=np.uint8)
    after = np.array([[[30, 70, 120, 255], [90, 10, 25, 255]]], dtype=np.uint8)
    source.set_reference(before)
    source.set_image(after)
    source.set_context('Tăng tương phản')
    source.log_scale.setChecked(logarithmic)
    enlarged.copy_from(source)
    counts, reference = source.values.copy(), source.reference_values.copy()
    np.testing.assert_array_equal(enlarged.values, counts)
    np.testing.assert_array_equal(enlarged.reference_values, reference)
    assert not np.shares_memory(enlarged.values, source.values)
    assert not np.shares_memory(enlarged.reference_values, source.reference_values)
    assert enlarged.pixel_count == 2 and enlarged.reference_pixel_count == 6
    assert enlarged.context.text() == 'Tăng tương phản'
    assert enlarged.sample_label.text() == source.sample_label.text()
    assert enlarged.log_scale.isChecked() == logarithmic

    source.set_image(before)
    source.set_reference(None)
    source.set_context('Ảnh khác')
    source.log_scale.setChecked(not logarithmic)
    np.testing.assert_array_equal(enlarged.values, counts)
    np.testing.assert_array_equal(enlarged.reference_values, reference)
    assert enlarged.context.text() == 'Tăng tương phản'
    assert enlarged.log_scale.isChecked() == logarithmic
    empty = Histogram()
    enlarged.copy_from(empty)
    assert enlarged.values is None and enlarged.reference_values is None
    assert enlarged.pixel_count == 0 and enlarged.reference_pixel_count == 0
    source.close()
    enlarged.close()
    empty.close()


@pytest.mark.parametrize('logarithmic', [False, True])
def test_bar_charts_render_empty_and_transparent_images(qt_app, logarithmic):
    """Cả hai thang vẽ được khi chưa mở ảnh và không có pixel nhìn thấy."""
    chart = Histogram()
    chart.resize(340, chart.height())
    chart.log_scale.setChecked(logarithmic)
    chart.show()
    qt_app.processEvents()
    assert not chart.grab().isNull()
    transparent = np.full((2, 3, 4), 127, dtype=np.uint8)
    transparent[..., 3] = 0
    chart.set_reference(transparent)
    chart.set_image(transparent)
    qt_app.processEvents()
    assert chart.pixel_count == 0 and chart.reference_pixel_count == 0
    assert not np.any(chart.values) and not np.any(chart.reference_values)
    assert not chart.grab().isNull()
    chart.close()


@pytest.mark.parametrize('logarithmic', [False, True])
def test_rendered_histogram_contains_colored_bars(qt_app, logarithmic):
    """Các cột RGB thật sự được vẽ, đổi thang không làm thay đổi số đếm."""
    image = np.zeros((1, 256, 4), dtype=np.uint8)
    image[..., :3] = np.arange(256, dtype=np.uint8)[None, :, None]
    image[..., 3] = 255
    chart = Histogram()
    chart.resize(1400, chart.height())
    chart.set_image(image)
    counts = chart.values.copy()
    chart.set_reference(image[:, :128])
    chart.log_scale.setChecked(logarithmic)
    chart.show()
    qt_app.processEvents()
    for channel in chart.charts[:3]:
        rendered = channel.grab().toImage()
        color = channel.color
        assert any(rendered.pixelColor(x, y) == color
                   for y in range(rendered.height())
                   for x in range(rendered.width()))
    np.testing.assert_array_equal(chart.values, counts)
    chart.close()


def test_preview_compare_reset_and_history_histograms(qt_app):
    """Biểu đồ theo đúng preview, ảnh gốc, hoàn tác và từng chức năng trong lịch sử."""
    image = np.empty((4, 6, 4), dtype=np.uint8)
    image[:] = [50, 70, 90, 255]
    window = MainWindow()
    window.set_document(image, 'histogram.png')
    try:
        original_counts = window.histogram.values.copy()
        window.sliders['brightness'].setValue(20)
        window.preview()
        window.timer.stop()
        preview_counts = window.histogram.values.copy()
        assert not np.array_equal(preview_counts, original_counts)
        np.testing.assert_array_equal(window.histogram.reference_values, original_counts)
        np.testing.assert_array_equal(window.doc.current, image)
        window.show_original(True)
        np.testing.assert_array_equal(window.histogram.values, original_counts)
        window.show_original(False)
        np.testing.assert_array_equal(window.histogram.values, preview_counts)
        window.reset_adjustments()
        np.testing.assert_array_equal(window.histogram.values, original_counts)

        brighter = adjustments.adjust(image, {'brightness': 20})
        window.commit(brighter, 'Tăng sáng')
        brighter_counts = window.histogram.values.copy()
        np.testing.assert_array_equal(window.histogram.reference_values, original_counts)
        cropped = geometry.crop(brighter, (0, 0, 3, 2))
        window.commit(cropped, 'Cắt ảnh')
        assert window.histogram.pixel_count == 6
        assert window.histogram.reference_pixel_count == 24
        cropped_counts = window.histogram.values.copy()

        window.history.setCurrentRow(1)
        np.testing.assert_array_equal(window.histogram.values, brighter_counts)
        np.testing.assert_array_equal(window.histogram.reference_values, original_counts)
        np.testing.assert_array_equal(window.doc.current, cropped)
        assert window.canvas.photo.pixmap().size().width() == 3
        assert window.doc.index == 2
        window.show_original(True)
        np.testing.assert_array_equal(window.histogram.values, original_counts)
        window.show_original(False)
        np.testing.assert_array_equal(window.histogram.values, brighter_counts)
        np.testing.assert_array_equal(window.histogram.reference_values, original_counts)
        assert window.history.currentRow() == 1
        assert window.canvas.photo.pixmap().size().width() == 3
        window.history.setCurrentRow(0)
        np.testing.assert_array_equal(window.histogram.values, original_counts)
        assert window.histogram.reference_values is None
        window.undo()
        np.testing.assert_array_equal(window.histogram.values, brighter_counts)
        np.testing.assert_array_equal(window.histogram.reference_values, original_counts)
        window.redo()
        np.testing.assert_array_equal(window.histogram.values, cropped_counts)
        np.testing.assert_array_equal(window.histogram.reference_values, brighter_counts)
    finally:
        window.reset_sliders()
        window.doc.mark_saved()
        window.close()
