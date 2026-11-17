"""Tích hợp bộ lọc, tham số, worker, lịch sử, tài liệu và dialog Qt."""
import time

import numpy as np
import pytest
from PySide6.QtCore import QThread
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialog

from app.core import enhancement
from app.ui import lesson_tools
from app.ui import window as window_module
from app.ui.lesson_tools import LessonDialog, AnalysisPreview
from app.ui.window import MainWindow


@pytest.fixture(scope='module')
def qt_app():
    return QApplication.instance() or QApplication([])


def wait_done(app, window):
    deadline = time.monotonic() + 15
    while window.busy and time.monotonic() < deadline:
        app.processEvents()
        QTest.qWait(10)
    assert not window.busy


@pytest.fixture
def editor(qt_app, rgba):
    window = MainWindow()
    window.set_document(rgba, 'bai_hoc.png')
    window.errors = []
    window.alert = window.errors.append
    yield window
    wait_done(qt_app, window)
    for preview in window.findChildren(AnalysisPreview):
        preview.close()
    window.reset_sliders()
    window.doc.mark_saved()
    window.close()


def choice(algorithm, params=None, chapter=2, **kwargs):
    return {'chapter': chapter, 'algorithm': algorithm, 'params': params or {},
            'mode': 'rgb', 'reference': None, 'frames': [], **kwargs}


def select(dialog, chapter, key):
    dialog.chapter.setCurrentIndex(dialog.chapter.findData(chapter))
    dialog.group.setCurrentText(dialog.modules[chapter].ALGORITHMS[key].group)
    dialog.algorithm.setCurrentIndex(dialog.algorithm.findData(key))


def test_dynamic_dialog_precision_and_required_images(qt_app, monkeypatch):
    dialog = LessonDialog()
    try:
        assert dialog.chapter.count() == 3
        select(dialog, 2, 'inverse')
        epsilon = dialog.widgets['epsilon']
        assert epsilon.minimum() == .0001
        epsilon.setValue(.0001)
        assert dialog.selection()['params']['epsilon'] == .0001
        select(dialog, 2, 'frequency_low')
        dialog.widgets['cutoff'].setValue(.001)
        assert dialog.selection()['params']['cutoff'] == .001
        select(dialog, 2, 'negative')
        assert dialog.selection()['params'] == {}
        assert not dialog.mode_row.isHidden()
        select(dialog, 2, 'otsu')
        assert dialog.mode_row.isHidden()
        select(dialog, 2, 'average')
        dialog.accept()
        assert dialog.result() == QDialog.DialogCode.Rejected
        assert 'ít nhất một ảnh' in dialog.error.text()
        select(dialog, 2, 'match')
        dialog.accept()
        assert 'tham chiếu' in dialog.error.text()
        monkeypatch.setattr(lesson_tools.QFileDialog, 'getOpenFileName', lambda *a, **kw: ('/tmp/reference.png', ''))
        dialog.choose_reference()
        assert dialog.selection()['reference'] == '/tmp/reference.png'
        select(dialog, 2, 'negative')
        assert dialog.selection()['reference'] is None
        dialog.accept()
        assert dialog.result() == QDialog.DialogCode.Accepted
    finally:
        dialog.close()


def test_named_channels_and_translated_parameters_route_real_values(qt_app, rgba):
    """Tên kênh rõ ràng phải chọn đúng dữ liệu, không gửi nhãn dịch vào core."""
    dialog = LessonDialog()
    try:
        assert 'Bài học' not in dialog.windowTitle()
        assert all('Chương' not in dialog.chapter.itemText(i) for i in range(dialog.chapter.count()))
        select(dialog, 1, 'channel')
        channel = dialog.widgets['channel']
        assert channel.itemText(0) == 'Đỏ (R)'
        channel.setCurrentIndex(1)
        result, _ = lesson_tools.process_lesson(rgba, dialog.selection())
        np.testing.assert_array_equal(result[..., 0], rgba[..., 1])
        dialog.widgets['space'].setCurrentIndex(dialog.widgets['space'].findData('HSV'))
        assert channel.currentText() == 'Độ bão hòa (S)'
        assert dialog.selection()['params'] == {'space': 'HSV', 'channel': 1}
        select(dialog, 1, 'arithmetic')
        operation = dialog.widgets['operation']
        operation.setCurrentIndex(operation.findData('difference'))
        assert operation.currentText() == 'Chênh lệch tuyệt đối'
        assert dialog.selection()['params']['operation'] == 'difference'
        select(dialog, 2, 'negative')
        assert dialog.selection()['mode'] == 'rgb'
        result, _ = lesson_tools.process_lesson(rgba, dialog.selection())
        np.testing.assert_array_equal(result[..., :3], 255 - rgba[..., :3])
        np.testing.assert_array_equal(result[..., 3], rgba[..., 3])
        select(dialog, 2, 'gaussian')
        assert dialog.selection()['mode'] == 'luminance'
    finally:
        dialog.close()


def test_only_effective_filter_parameters_are_editable(qt_app):
    """Tham số không được thuật toán sử dụng phải rõ trạng thái trên form."""
    dialog = LessonDialog()
    try:
        select(dialog, 2, 'frequency_low')
        assert not dialog.widgets['order'].isEnabled()
        family = dialog.widgets['family']
        family.setCurrentIndex(family.findData('butterworth'))
        assert dialog.widgets['order'].isEnabled()
        assert dialog.selection()['params']['family'] == 'butterworth'
        family.setCurrentIndex(family.findData('ideal'))
        assert not dialog.widgets['order'].isEnabled()
        select(dialog, 2, 'inverse')
        assert dialog.widgets['sigma'].isEnabled()
        dialog.widgets['psf'].setCurrentIndex(dialog.widgets['psf'].findData('motion'))
        assert not dialog.widgets['sigma'].isEnabled()
        select(dialog, 2, 'nearest')
        dialog.widgets['size'].setValue(3)
        assert dialog.widgets['neighbors'].maximum() == 9
        dialog.widgets['size'].setValue(5)
        assert dialog.widgets['neighbors'].maximum() == 25
        dialog.widgets['size'].setValue(4)
        dialog.accept()
        assert dialog.result() == QDialog.DialogCode.Rejected
        assert 'phải là số lẻ' in dialog.error.text()
    finally:
        dialog.close()


def test_lesson_guards_and_cancel_preserve_document(editor, rgba, monkeypatch):
    calls = []
    monkeypatch.setattr(window_module, 'choose_lesson', lambda parent: calls.append(parent))
    editor.do_lesson()
    assert calls == [editor] and not editor.busy
    editor.sliders['brightness'].setValue(10)
    editor.do_lesson()
    assert calls == [editor] and editor.errors
    assert len(editor.doc.entries) == 1
    np.testing.assert_array_equal(editor.doc.current, rgba)
    editor.reset_sliders()
    old_document = editor.doc
    editor.doc = None
    editor.do_lesson()
    assert len(calls) == 1 and 'mở ảnh' in editor.errors[-1]
    editor.doc = old_document


def test_no_parameter_lesson_commits_alpha_histogram_and_undo(editor, qt_app, rgba, monkeypatch):
    monkeypatch.setattr(window_module, 'choose_lesson', lambda parent: choice('negative'))
    original_histogram = editor.histogram.values.copy()
    editor.do_lesson()
    wait_done(qt_app, editor)
    expected = rgba.copy()
    expected[..., :3] = 255 - expected[..., :3]
    np.testing.assert_array_equal(editor.doc.current, expected)
    np.testing.assert_array_equal(editor.histogram.reference_values, original_histogram)
    assert not editor.errors and len(editor.doc.entries) == 2
    assert 'Âm bản' in editor.histogram_context and 'Chương' not in editor.histogram_context
    editor.undo()
    np.testing.assert_array_equal(editor.doc.current, rgba)
    editor.redo()
    np.testing.assert_array_equal(editor.doc.current, expected)


def test_lesson_reference_and_frames_load_in_worker(editor, qt_app, rgba, monkeypatch):
    second = rgba.copy()
    second[..., :3] //= 2
    loads = []

    def load(path):
        loads.append(path)
        assert QThread.currentThread() != qt_app.thread()
        return second.copy()

    monkeypatch.setattr(lesson_tools, 'load_image', load)
    monkeypatch.setattr(window_module, 'choose_lesson', lambda parent: choice('match', reference='reference.png'))
    editor.do_lesson()
    wait_done(qt_app, editor)
    expected, _ = enhancement.process(rgba, 'match', mode='rgb', reference=second)
    np.testing.assert_array_equal(editor.doc.current, expected)
    assert loads == ['reference.png'] and not editor.errors
    editor.undo()
    monkeypatch.setattr(window_module, 'choose_lesson', lambda parent: choice('average', frames=['a.png', 'b.png']))
    editor.do_lesson()
    wait_done(qt_app, editor)
    expected, _ = enhancement.process(rgba, 'average', mode='rgb', frames=[second, second])
    np.testing.assert_array_equal(editor.doc.current, expected)
    assert loads == ['reference.png', 'a.png', 'b.png'] and not editor.errors


@pytest.mark.parametrize('chapter', [1, 3])
def test_other_chapters_route_without_color_mode(editor, qt_app, rgba, monkeypatch, chapter):
    module = lesson_tools.lesson_modules()[chapter]
    key = next(iter(module.ALGORITHMS))
    received = []

    def process(image, algorithm, params=None):
        assert QThread.currentThread() != qt_app.thread()
        received.append((algorithm, params))
        result = image.copy()
        result[..., :3] = 77
        return result, 'Thông tin kết quả'

    monkeypatch.setattr(module, 'process', process)
    monkeypatch.setattr(window_module, 'choose_lesson', lambda parent: choice(key, {'value': 7}, chapter=chapter))
    editor.do_lesson()
    wait_done(qt_app, editor)
    assert received == [(key, {'value': 7})]
    assert not editor.errors and len(editor.doc.entries) == 2
    assert 'Thông tin kết quả' in editor.doc.entries[-1][1]
    assert 'Thông tin kết quả' in editor.hint.text()
    np.testing.assert_array_equal(editor.doc.current[..., 3], rgba[..., 3])


def test_chapter_one_receives_second_image_in_worker(editor, qt_app, rgba, monkeypatch):
    module = lesson_tools.lesson_modules()[1]
    key = next(key for key, spec in module.ALGORITHMS.items() if spec.reference)
    second = rgba[:, ::-1].copy()
    received = []

    def process(image, algorithm, params=None, reference=None):
        assert QThread.currentThread() != qt_app.thread()
        received.append((algorithm, reference))
        return image.copy(), ''

    monkeypatch.setattr(module, 'process', process)
    monkeypatch.setattr(lesson_tools, 'load_image', lambda path: second.copy())
    monkeypatch.setattr(window_module, 'choose_lesson',
                        lambda parent: choice(key, chapter=1, reference='second.png'))
    editor.do_lesson()
    wait_done(qt_app, editor)
    assert not editor.errors and received[0][0] == key
    np.testing.assert_array_equal(received[0][1], second)


def test_diagnostic_and_worker_error_leave_history_untouched(editor, qt_app, rgba, monkeypatch):
    counts = editor.histogram.values.copy()
    monkeypatch.setattr(window_module, 'choose_lesson', lambda parent: choice('spectrum'))
    editor.do_lesson()
    wait_done(qt_app, editor)
    previews = editor.findChildren(AnalysisPreview)
    assert len(previews) == 1 and previews[0].isVisible()
    assert len(editor.doc.entries) == 1 and not editor.doc.dirty
    np.testing.assert_array_equal(editor.histogram.values, counts)
    np.testing.assert_array_equal(editor.doc.current, rgba)
    previews[0].close()
    monkeypatch.setattr(window_module, 'choose_lesson', lambda parent: choice('gamma', {'gamma': -1.}))
    editor.do_lesson()
    wait_done(qt_app, editor)
    assert len(editor.errors) == 1 and editor.centralWidget().isEnabled()
    assert len(editor.doc.entries) == 1
    np.testing.assert_array_equal(editor.doc.current, rgba)


def test_quality_metrics_run_in_worker_without_commit(editor, qt_app, rgba, monkeypatch):
    monkeypatch.setattr(window_module.QFileDialog, 'getOpenFileName', lambda *a, **kw: ('reference.png', ''))

    def load(path):
        assert QThread.currentThread() != qt_app.thread()
        return rgba.copy()

    results = []
    monkeypatch.setattr(window_module, 'load_image', load)
    monkeypatch.setattr(editor, 'show_quality', lambda result, name: results.append((result, name)))
    editor.do_quality()
    wait_done(qt_app, editor)
    assert results[0][1] == 'reference.png'
    assert results[0][0]['mse'] == 0 and np.isinf(results[0][0]['psnr'])
    assert results[0][0]['ssim'] == pytest.approx(1.)
    assert len(editor.doc.entries) == 1 and not editor.doc.dirty and not editor.errors
