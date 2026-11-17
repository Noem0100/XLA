"""Kiểm thử tích hợp Qt offscreen; không thay cho thao tác trên cửa sổ thật."""
import time
import numpy as np
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest
from app.ui.window import MainWindow
from app.core import geometry


def wait_done(app, window):
    """Bơm event loop tới khi worker hoàn tất hoặc hết thời gian."""
    deadline = time.monotonic() + 15
    while window.busy and time.monotonic() < deadline:
        app.processEvents()
        QTest.qWait(10)
    assert not window.busy


def test_ui_edit_compare_and_undo(rgba):
    """Slider preview, worker commit, undo/redo và compare giữ mask."""
    app = QApplication.instance() or QApplication([])
    w = MainWindow(); w.show(); app.processEvents()
    w.set_document(rgba, 'test.png')
    errors = []
    w.alert = errors.append
    w.sliders['brightness'].setValue(20)
    w.preview()
    assert w.pending() and not w.doc.dirty
    np.testing.assert_array_equal(w.doc.current, rgba)
    w.apply_adjustments()
    wait_done(app, w)
    assert not w.pending() and w.doc.dirty and not errors
    changed = w.doc.current.copy()
    w.undo(); np.testing.assert_array_equal(w.doc.current, rgba)
    w.redo(); np.testing.assert_array_equal(w.doc.current, changed)
    w.commit(geometry.crop(changed, (0, 0, 32, 24)), 'crop')
    w.canvas.mask[4:8, 4:8] = 255
    before = w.canvas.mask.copy()
    w.show_original(True); w.show_original(False)
    np.testing.assert_array_equal(w.canvas.mask, before)
    w.doc.mark_saved(); w.close()


def test_canvas_mouse_mapping(rgba):
    """Crop et cọ dùng pixel ảnh dù viewport đang fit/zoom."""
    app = QApplication.instance() or QApplication([])
    w = MainWindow(); w.show(); app.processEvents()
    w.set_document(np.tile(rgba, (4, 4, 1)), 'mouse.png')
    app.processEvents(); w.canvas.fit_image()
    from PySide6.QtCore import QPointF
    p1 = w.canvas.mapFromScene(QPointF(30, 30))
    p2 = w.canvas.mapFromScene(QPointF(90, 80))
    w.mode('crop')
    QTest.mousePress(w.canvas.viewport(), Qt.MouseButton.LeftButton, pos=p1)
    QTest.mouseMove(w.canvas.viewport(), p2)
    QTest.mouseRelease(w.canvas.viewport(), Qt.MouseButton.LeftButton, pos=p2)
    np.testing.assert_allclose(w.canvas.crop_box(), (30, 30, 90, 80), atol=1)
    w.mode('brush')
    w.canvas.brush_size = 10
    QTest.mousePress(w.canvas.viewport(), Qt.MouseButton.LeftButton, pos=p1)
    QTest.mouseMove(w.canvas.viewport(), p2)
    QTest.mouseRelease(w.canvas.viewport(), Qt.MouseButton.LeftButton, pos=p2)
    assert w.canvas.mask[30, 30] > 0 and w.canvas.mask[80, 90] > 0
    assert w.canvas.mask[0, 0] == 0
    w.close()


def test_tool_dispatch_and_failure(rgba, monkeypatch):
    """Các dialog gọi đúng core; worker lỗi giữ nguyên ảnh và mở lại UI."""
    import app.ui.window as module
    app = QApplication.instance() or QApplication([])
    w = MainWindow(); w.set_document(rgba, 'tools.png'); errors=[]; w.alert=errors.append
    tools = [
        (w.do_curve, {'channel': 'RGB', 'points': '0:0, 128:150, 255:255'}),
        (w.do_hsl, {'center': 'Đỏ', 'hue': 20, 'sat': 10, 'light': 5}),
        (w.do_filter, {'kind': 'CLAHE', 'amount': 10}),
        (w.do_vignette, {'amount': 30}),
        (w.do_rotate, {'degrees': 15}),
        (w.do_resize, {'w': 40, 'h': 30, 'ratio': 'Giữ tỉ lệ theo chiều rộng'}),
        (w.ratio_crop, {'ratio': '1:1'}),
        (w.do_border, {'size': 3, 'color': '#fff'})]
    for method, params in tools:
        monkeypatch.setattr(module, 'parameters', lambda *args, p=params, **kwargs: p)
        method(); wait_done(app, w)
    assert not errors and len(w.doc.entries) == 9
    before=w.doc.current.copy()
    w.run_image('Lỗi kiểm thử', lambda image: geometry.resize(image, 0, 0))
    wait_done(app, w)
    assert len(errors) == 1 and w.centralWidget().isEnabled()
    np.testing.assert_array_equal(w.doc.current, before)
    w.doc.mark_saved(); w.close()
