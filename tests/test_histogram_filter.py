"""Kiểm tra thao tác chọn gam màu từ histogram và lớp lọc xem trước trên ảnh."""
import time

import numpy as np
import pytest
from PySide6.QtCore import Qt, QRectF, QTimer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from app.core import adjustments, filters
from app.ui.histogram import Histogram
from app.ui.window import MainWindow


@pytest.fixture(scope='module')
def qt_app():
    """Giữ QApplication cho các thao tác chuột, bàn phím và worker Qt."""
    return QApplication.instance() or QApplication([])


@pytest.fixture
def color_image():
    """Ảnh gồm ba màu cơ bản, alpha bán trong suốt và một pixel bị ẩn."""
    row = [[255, 0, 0, 255], [0, 255, 0, 255],
           [0, 0, 255, 128], [255, 255, 255, 0]]
    return np.array([row, row], dtype=np.uint8)


@pytest.fixture
def editor(qt_app, color_image):
    """Đóng cửa sổ sau mỗi kiểm thử mà không mở hộp thoại lưu tài liệu."""
    window = MainWindow()
    window.set_document(color_image, 'gam_mau.png')
    window.alert = lambda message: pytest.fail(str(message))
    yield window
    window.reset_sliders()
    window.doc.mark_saved()
    window.close()


def pixmap_rgba(item):
    """Đọc màu thực sự được đưa vào canvas, kể cả alpha của từng pixel."""
    image = item.pixmap().toImage()
    return np.array([[image.pixelColor(x, y).getRgb() for x in range(image.width())]
                     for y in range(image.height())], dtype=np.uint8)


def assert_visible_pixels(actual, expected):
    """So sánh alpha chính xác và RGB nhìn thấy với sai số làm tròn của Qt."""
    np.testing.assert_array_equal(actual[..., 3], expected[..., 3])
    visible = expected[..., 3] > 0
    np.testing.assert_allclose(actual[..., :3][visible], expected[..., :3][visible], atol=1)


def wait_done(app, window):
    """Bơm vòng lặp sự kiện cho đến khi tác vụ nền kết thúc."""
    deadline = time.monotonic() + 15
    while window.busy and time.monotonic() < deadline:
        app.processEvents()
        QTest.qWait(10)
    assert not window.busy


def test_chart_clicks_and_keys_emit_only_user_selections(qt_app, color_image):
    """Biểu đồ chưa có ảnh không kích hoạt; đặt viền bằng mã không phát signal."""
    histogram = Histogram()
    histogram.resize(340, histogram.height())
    histogram.show()
    qt_app.processEvents()
    selected = []
    histogram.channel_selected.connect(selected.append)
    try:
        QTest.mouseClick(histogram.charts[0], Qt.MouseButton.LeftButton)
        QTest.keyClick(histogram.charts[0], Qt.Key.Key_Return)
        assert selected == []
        histogram.set_selected_channel(2)
        assert histogram.selected_channel == 2 and selected == []
        histogram.set_image(color_image)
        for channel, chart in enumerate(histogram.charts):
            QTest.mouseClick(chart, Qt.MouseButton.LeftButton)
            assert selected[-1] == channel
        assert selected == [0, 1, 2, 3]
        for key in (Qt.Key.Key_Enter, Qt.Key.Key_Return, Qt.Key.Key_Space):
            QTest.keyClick(histogram.charts[1], key)
        assert selected == [0, 1, 2, 3, 1, 1, 1]
        QTest.mouseClick(histogram.charts[0], Qt.MouseButton.RightButton)
        histogram.set_selected_channel(None)
        assert histogram.selected_channel is None
        assert selected == [0, 1, 2, 3, 1, 1, 1]
    finally:
        histogram.close()


@pytest.mark.parametrize('channel', [0, 1, 2, 3])
def test_color_preview_retains_selected_gamut_and_original_alpha(editor, color_image, channel):
    """Chọn gam giữ màu tương ứng, chuyển gam khác sang xám và giữ nguyên tài liệu."""
    original_counts = editor.histogram.values.copy()
    editor.canvas.mask[0, 0] = 255
    mask = editor.canvas.mask.copy()
    rectangle = QRectF(0, 0, 2, 1)
    editor.canvas.rectangle.setRect(rectangle)
    editor.canvas.set_mode('crop')
    editor.toggle_histogram_filter(channel)
    expected = color_image.copy()
    gray_levels = [54, 182, 18]
    for index, gray in enumerate(gray_levels):
        if channel == 3 or index != channel:
            expected[:, index, :3] = gray
    assert editor.color_filter_channel == channel
    assert editor.histogram.selected_channel == channel
    assert editor.canvas.filter_layer.isVisible()
    assert not editor.canvas.photo.isVisible()
    assert_visible_pixels(pixmap_rgba(editor.canvas.filter_layer), expected)
    np.testing.assert_array_equal(editor.doc.current, color_image)
    np.testing.assert_array_equal(editor.histogram.values, original_counts)
    np.testing.assert_array_equal(editor.canvas.mask, mask)
    assert editor.canvas.rectangle.rect() == rectangle
    assert editor.canvas.mode == 'crop'
    assert len(editor.doc.entries) == 1 and not editor.doc.dirty
    editor.toggle_histogram_filter(channel)
    assert editor.color_filter_channel is None
    assert editor.histogram.selected_channel is None
    assert not editor.canvas.filter_layer.isVisible()
    assert editor.canvas.photo.isVisible()
    assert_visible_pixels(pixmap_rgba(editor.canvas.photo), color_image)


def test_toggle_filter_preserves_latest_slider_preview_and_compare(editor, qt_app, color_image):
    """Chuyển hoặc bỏ gam không mất preview thanh trượt; xem gốc tạm ẩn lớp lọc."""
    editor.toggle_histogram_filter(0)
    editor.sliders['brightness'].setValue(20)
    editor.preview()
    editor.timer.stop()
    expected_preview = adjustments.adjust(color_image, {'brightness': 20})
    expected_filter = filters.color_range(expected_preview, 0)
    assert_visible_pixels(pixmap_rgba(editor.canvas.filter_layer), expected_filter)
    preview_counts = editor.histogram.values.copy()
    editor.toggle_histogram_filter(1)
    expected_green = filters.color_range(expected_preview, 1)
    assert_visible_pixels(pixmap_rgba(editor.canvas.filter_layer), expected_green)
    assert editor.color_filter_channel == 1
    np.testing.assert_array_equal(editor.histogram.values, preview_counts)
    editor.show_original(True)
    assert not editor.canvas.filter_layer.isVisible()
    assert editor.canvas.photo.isVisible()
    assert_visible_pixels(pixmap_rgba(editor.canvas.photo), color_image)
    editor.show_original(False)
    assert editor.color_filter_channel == 1
    assert editor.canvas.filter_layer.isVisible()
    assert not editor.canvas.photo.isVisible()
    assert_visible_pixels(pixmap_rgba(editor.canvas.filter_layer), expected_green)
    np.testing.assert_array_equal(editor.histogram.values, preview_counts)
    editor.toggle_histogram_filter(1)
    assert_visible_pixels(pixmap_rgba(editor.canvas.photo), expected_preview)
    assert editor.pending()
    np.testing.assert_array_equal(editor.doc.current, color_image)


def test_apply_filter_combines_sliders_and_supports_undo_redo(editor, qt_app, color_image):
    """Áp dụng tạo một bước đủ độ phân giải với cả chỉnh sáng và chọn gam màu."""
    editor.sliders['brightness'].setValue(20)
    editor.preview()
    editor.timer.stop()
    editor.toggle_histogram_filter(2)
    expected = filters.color_range(adjustments.adjust(color_image, {'brightness': 20}), 2)
    editor.apply_histogram_filter()
    wait_done(qt_app, editor)
    np.testing.assert_array_equal(editor.doc.current, expected)
    np.testing.assert_array_equal(editor.doc.current[..., 3], color_image[..., 3])
    assert len(editor.doc.entries) == 2
    assert not editor.pending() and editor.doc.dirty
    assert editor.color_filter_channel is None
    assert not editor.canvas.filter_layer.isVisible()
    assert editor.canvas.photo.isVisible()
    editor.undo()
    np.testing.assert_array_equal(editor.doc.current, color_image)
    editor.redo()
    np.testing.assert_array_equal(editor.doc.current, expected)
    assert editor.color_filter_channel is None


def test_loading_another_document_clears_filter(editor, color_image):
    """Ảnh mới không kế thừa lớp lọc và trạng thái kênh của ảnh trước."""
    editor.toggle_histogram_filter(0)
    other = color_image[:, ::-1].copy()
    editor.set_document(other, 'anh_khac.png')
    assert editor.color_filter_channel is None
    assert editor.histogram.selected_channel is None
    assert editor.canvas.photo.isVisible()
    assert not editor.canvas.filter_layer.isVisible()
    assert_visible_pixels(pixmap_rgba(editor.canvas.photo), other)


def test_enlarged_histogram_selects_and_syncs_filter(editor, qt_app):
    """Chọn gam trong cửa sổ phóng to đồng bộ với biểu đồ nhỏ và lớp ảnh."""
    errors = []

    def interact():
        """Thao tác bên trong vòng lặp modal và luôn đóng hộp thoại sau kiểm tra."""
        dialog = qt_app.activeModalWidget()
        try:
            assert dialog is not None
            enlarged = dialog.findChild(Histogram)
            assert enlarged is not None
            QTest.mouseClick(enlarged.charts[0], Qt.MouseButton.LeftButton)
            assert editor.color_filter_channel == 0
            assert editor.histogram.selected_channel == 0
            assert enlarged.selected_channel == 0
            QTest.mouseClick(enlarged.charts[1], Qt.MouseButton.LeftButton)
            assert editor.color_filter_channel == 1
            assert editor.histogram.selected_channel == 1
            assert enlarged.selected_channel == 1
            QTest.mouseClick(enlarged.charts[1], Qt.MouseButton.LeftButton)
            assert editor.color_filter_channel is None
            assert editor.histogram.selected_channel is None
            assert enlarged.selected_channel is None
        except Exception as exc:
            errors.append(exc)
        finally:
            if dialog is not None:
                dialog.reject()

    QTimer.singleShot(0, interact)
    editor.show_histogram_detail()
    assert not errors, errors
