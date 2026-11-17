"""Điều phối giao diện desktop; thuật toán nằm trong app/core."""
from pathlib import Path
import numpy as np
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QShortcut, QKeySequence
from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QFrame,
    QLabel, QPushButton, QScrollArea, QTabWidget, QSlider, QSpinBox, QComboBox,
    QListWidget, QFileDialog, QMessageBox, QCheckBox, QSplitter, QProgressBar,
    QDialog, QDialogButtonBox)
from app.core import adjustments, filters, geometry, retouch, enhancement_spatial
from app.core.io import load_image, export_image, load_project, save_project, from_png
from app.core.batch import batch_export
from .canvas import Canvas
from .image_page import ImagePage
from .histogram import Histogram
from .dialogs import parameters
from .worker import Worker
from .lesson_tools import choose_lesson, lesson_spec, process_lesson, AnalysisPreview

IMAGE_FILTER = 'Ảnh (*.jpg *.jpeg *.png *.webp *.bmp *.tif *.tiff);;Tất cả (*)'
ADJUSTERS = [
    ('exposure', 'Phơi sáng · EV × 100', -300, 300),
    ('brightness', 'Độ sáng', -100, 100), ('contrast', 'Tương phản', -100, 100),
    ('highlights', 'Vùng sáng', -100, 100), ('shadows', 'Vùng tối', -100, 100),
    ('saturation', 'Bão hòa', -100, 100), ('vibrance', 'Độ rực màu', -100, 100),
    ('temperature', 'Nhiệt độ · lạnh / ấm', -100, 100), ('tint', 'Sắc · tím / xanh', -100, 100),
    ('gamma', 'Gamma × 100', 10, 300), ('black', 'Điểm đen', 0, 250),
    ('white', 'Điểm trắng', 5, 255), ('fade', 'Fade', 0, 100)]


def button(text, callback, primary=False):
    """Tạo nút thống nhất và nối signal clicked với callable không tham số."""
    item = QPushButton(text)
    if primary:
        item.setObjectName('primary')
    item.clicked.connect(lambda checked=False: callback())
    return item


def scroll_panel(layout):
    """Bọc layout trong vùng cuộn để dùng được trên màn hình laptop."""
    content = QWidget()
    content.setLayout(layout)
    area = QScrollArea()
    area.setWidgetResizable(True)
    area.setWidget(content)
    return area


class MainWindow(QMainWindow):
    """Controller của ứng dụng; không đặt công thức xử lý điểm ảnh trong UI."""
    def __init__(self):
        """Khởi tạo nhiều trang ảnh cùng bốn cột công cụ, ảnh, thông số, lịch sử."""
        super().__init__()
        self.setWindowTitle('PhotoPremium · Phòng chỉnh ảnh')
        self.resize(1440, 920)
        self.setMinimumSize(1180, 720)
        self.doc = None
        self.active_page = None
        self.busy = False
        self.task = None
        self.source_name = 'Chưa mở ảnh'
        self.preview_base = None
        self.histogram_context = 'Chưa mở ảnh'
        self.histogram_reference_key = None
        self.histogram_reference = None
        self.comparing_original = False
        self.color_filter_channel = None
        self.color_filter_mode = 'channel'
        self.display_source = None
        self.histogram_detail = None
        self.sliders = {}
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(160)
        self.timer.timeout.connect(self.preview)
        root = QWidget()
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(18, 14, 18, 10)
        header = QHBoxLayout()
        brand = QLabel('PHOTOPremium')
        brand.setObjectName('brand')
        header.addWidget(brand)
        header.addStretch()
        header.addWidget(button('Mở ảnh / nhiều ảnh  Ctrl+O', self.open_image))
        header.addWidget(button('Mở dự án', self.open_project))
        header.addWidget(button('Lưu dự án', self.save))
        header.addWidget(button('Xuất ảnh  Ctrl+E', self.export, True))
        outer.addLayout(header)
        subtitle = QLabel('DESKTOP PHOTO EDITOR     /     Xử lý ảnh bằng Python · NumPy · OpenCV')
        subtitle.setObjectName('section')
        outer.addWidget(subtitle)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter = splitter
        outer.addWidget(splitter, 1)
        splitter.addWidget(self.build_tools())
        center = QWidget()
        layout = QVBoxLayout(center)
        layout.setContentsMargins(8, 0, 8, 0)
        top = QHBoxLayout()
        self.file_label = QLabel('Mở một bức ảnh để bắt đầu')
        top.addWidget(self.file_label, 1)
        self.compare = QPushButton('Giữ để xem ảnh gốc')
        self.compare.pressed.connect(lambda: self.show_original(True))
        self.compare.released.connect(lambda: self.show_original(False))
        top.addWidget(self.compare)
        layout.addLayout(top)
        self.filter_bar = QFrame()
        filter_layout = QHBoxLayout(self.filter_bar)
        filter_layout.setContentsMargins(0, 0, 0, 0)
        self.filter_label = QLabel()
        self.filter_label.setWordWrap(True)
        filter_layout.addWidget(self.filter_label, 1)
        filter_layout.addWidget(button('Áp dụng lớp lọc', self.apply_histogram_filter, True))
        filter_layout.addWidget(button('Tắt lớp lọc', lambda: self.set_histogram_filter(None)))
        layout.addWidget(self.filter_bar)
        self.filter_bar.hide()
        self.empty_canvas = Canvas()
        self.canvas = self.empty_canvas
        layout.addWidget(self.empty_canvas, 1)
        self.document_tabs = QTabWidget()
        self.document_tabs.setDocumentMode(True)
        self.document_tabs.setTabsClosable(True)
        self.document_tabs.setMovable(True)
        self.document_tabs.setUsesScrollButtons(True)
        self.document_tabs.currentChanged.connect(self.switch_document)
        self.document_tabs.tabCloseRequested.connect(self.close_document)
        layout.addWidget(self.document_tabs, 1)
        self.document_tabs.hide()
        lower = QHBoxLayout()
        lower.addWidget(button('−', lambda: self.canvas.scale(.8, .8)))
        lower.addWidget(button('+', lambda: self.canvas.scale(1.25, 1.25)))
        lower.addWidget(button('Vừa màn hình', lambda: self.canvas.fit_image()))
        lower.addWidget(button('1:1', lambda: self.canvas.resetTransform()))
        lower.addStretch()
        lower.addWidget(button('↶  Hoàn tác', self.undo))
        lower.addWidget(button('↷  Làm lại', self.redo))
        layout.addLayout(lower)
        self.hint = QLabel('Kéo ảnh bằng công cụ Di chuyển. Cuộn chuột để phóng to / thu nhỏ.')
        self.hint.setWordWrap(True)
        layout.addWidget(self.hint)
        splitter.addWidget(center)
        splitter.addWidget(self.build_properties())
        splitter.addWidget(self.build_history())
        splitter.setSizes([215, 675, 310, 200])
        splitter.setCollapsible(0, False)
        splitter.setCollapsible(1, False)
        splitter.setCollapsible(2, False)
        splitter.setCollapsible(3, False)
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setMaximumWidth(160)
        self.progress.hide()
        self.statusBar().addPermanentWidget(self.progress)
        self.statusBar().showMessage('Sẵn sàng · Ảnh được xử lý cục bộ trên máy tính')
        for keys, action in [('Ctrl+O', self.open_image), ('Ctrl+S', self.save), ('Ctrl+E', self.export),
                             ('Ctrl+Z', self.undo), ('Ctrl+Shift+Z', self.redo),
                             ('Ctrl+W', lambda: self.close_document(self.document_tabs.currentIndex()))]:
            shortcut = QShortcut(QKeySequence(keys), self)
            shortcut.activated.connect(action)

    def build_tools(self):
        """Tạo thanh công cụ cuộn, gom thao tác theo mục đích sử dụng."""
        frame = QFrame()
        frame.setObjectName('panel')
        frame.setMinimumWidth(215)
        frame.setMaximumWidth(245)
        box = QVBoxLayout(frame)
        tools = QVBoxLayout()
        groups = [
            ('KHÔNG GIAN ẢNH', [('Di chuyển / Zoom', lambda: self.mode('pan')),
                               ('Chọn vùng cắt', lambda: self.mode('crop')),
                               ('Cắt vùng đã chọn', self.do_crop), ('Cắt theo tỉ lệ', self.ratio_crop),
                               ('Xoay / Nắn thẳng', self.do_rotate), ('Lật ngang', lambda: self.run_image('Lật ngang', geometry.flip)),
                               ('Lật dọc', lambda: self.run_image('Lật dọc', lambda a: geometry.flip(a, False))),
                               ('Đổi kích thước', self.do_resize)]),
            ('ÁNH SÁNG VÀ CHI TIẾT', [('Tự cân sáng', lambda: self.run_image('Tự cân sáng', adjustments.auto_tone)),
                                     ('Cân bằng trắng', lambda: self.run_image('Gray world', adjustments.white_balance)),
                                     ('Đường cong Curves', self.do_curve), ('Màu chọn lọc HSL', self.do_hsl),
                                     ('Bộ lọc và xử lý ảnh', self.do_lesson),
                                     ('Hiệu ứng / Khử nhiễu nhanh', self.do_filter),
                                     ('So sánh chất lượng ảnh', self.do_quality),
                                     ('Tối góc Vignette', self.do_vignette)]),
            ('SÁNG TẠO', [('Cọ / Sửa vùng ảnh', self.brush_tab), ('Chèn chữ / Watermark', self.do_text),
                         ('Sticker / Ảnh phủ', self.do_overlay), ('Thêm khung viền', self.do_border),
                         ('Ghép ảnh Collage', self.do_collage)]),
            ('DỰ ÁN', [('Mở nhiều ảnh thành các tab', self.open_image),
                        ('Xuất hàng loạt theo preset', self.do_batch),
                        ('Khôi phục ảnh gốc', self.restore), ('Hướng dẫn nhanh', self.help)])]
        for title, actions in groups:
            label = QLabel(title)
            label.setObjectName('section')
            tools.addWidget(label)
            for text, callback in actions:
                tools.addWidget(button(text, callback))
            tools.addSpacing(10)
        tools.addStretch()
        box.addWidget(scroll_panel(tools))
        return frame

    def build_properties(self):
        """Tạo histogram màu/độ sáng theo chức năng cùng các công cụ chỉnh ảnh."""
        frame = QFrame()
        frame.setObjectName('panel')
        frame.setMinimumWidth(295)
        frame.setMaximumWidth(370)
        box = QVBoxLayout(frame)
        histogram_header = QHBoxLayout()
        label = QLabel('HISTOGRAM RGB / ĐỘ SÁNG')
        label.setObjectName('section')
        label.setWordWrap(True)
        histogram_header.addWidget(label, 1)
        enlarge = button('Xem lớn', self.show_histogram_detail)
        enlarge.setStyleSheet('padding: 4px 6px; font-size: 11px;')
        histogram_header.addWidget(enlarge)
        self.histogram_toggle = QPushButton('Ẩn')
        self.histogram_toggle.setCheckable(True)
        self.histogram_toggle.setChecked(True)
        self.histogram_toggle.setStyleSheet('padding: 4px 6px; font-size: 11px;')
        self.histogram_toggle.toggled.connect(self.toggle_histogram)
        histogram_header.addWidget(self.histogram_toggle)
        box.addLayout(histogram_header)
        self.histogram = Histogram()
        self.histogram.channel_selected.connect(self.toggle_histogram_filter)
        self.histogram.filter_mode_changed.connect(self.set_histogram_filter_mode)
        box.addWidget(self.histogram)
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        box.addWidget(self.tabs, 1)
        adjust_box = QVBoxLayout()
        note = QLabel('Xem trước nhanh. Nhấn Áp dụng để xử lý ảnh đủ độ phân giải.')
        note.setWordWrap(True)
        adjust_box.addWidget(note)
        for key, title, minimum, maximum in ADJUSTERS:
            row = QHBoxLayout()
            row.addWidget(QLabel(title), 1)
            spin = QSpinBox()
            spin.setRange(minimum, maximum)
            spin.setValue(adjustments.DEFAULTS[key])
            spin.setFixedWidth(72)
            row.addWidget(spin)
            adjust_box.addLayout(row)
            slider = QSlider(Qt.Orientation.Horizontal)
            slider.setRange(minimum, maximum)
            slider.setValue(adjustments.DEFAULTS[key])
            slider.valueChanged.connect(spin.setValue)
            spin.valueChanged.connect(slider.setValue)
            slider.valueChanged.connect(self.adjustment_changed)
            self.sliders[key] = slider
            adjust_box.addWidget(slider)
        adjust_box.addStretch()
        self.tabs.addTab(scroll_panel(adjust_box), 'Chỉnh')
        effects = QVBoxLayout()
        effects.addWidget(QLabel('BỘ MÀU'))
        self.look = QComboBox()
        self.look.addItems(filters.PRESETS)
        effects.addWidget(self.look)
        self.strength = QSpinBox()
        self.strength.setRange(0, 100)
        self.strength.setValue(100)
        effects.addWidget(QLabel('Cường độ preset (%)'))
        effects.addWidget(self.strength)
        effects.addWidget(button('Áp dụng preset', self.apply_preset, True))
        explanation = QLabel('Preset là tổ hợp phép chỉnh màu, không dùng AI. Có thể hoàn tác sau khi áp dụng.')
        explanation.setWordWrap(True)
        effects.addWidget(explanation)
        effects.addStretch()
        self.tabs.addTab(scroll_panel(effects), 'Màu')
        brush = QVBoxLayout()
        self.brush_mode = QComboBox()
        self.brush_mode.addItems(['Làm sáng vùng', 'Làm tối vùng', 'Làm mịn vùng', 'Làm mờ vùng', 'Xóa chi tiết Telea', 'Xóa nền bằng cọ'])
        brush.addWidget(self.brush_mode)
        brush.addWidget(QLabel('Đường kính cọ (pixel ảnh)'))
        size = QSpinBox()
        self.brush_size_control = size
        size.setRange(1, 1000)
        size.setValue(40)
        size.valueChanged.connect(lambda value: setattr(self.canvas, 'brush_size', value))
        brush.addWidget(size)
        erase = QCheckBox('Tẩy vùng mask đã tô')
        self.brush_eraser_control = erase
        erase.toggled.connect(lambda value: setattr(self.canvas, 'eraser', value))
        brush.addWidget(erase)
        self.brush_amount = QSpinBox()
        self.brush_amount.setRange(1, 100)
        self.brush_amount.setValue(25)
        brush.addWidget(QLabel('Cường độ'))
        brush.addWidget(self.brush_amount)
        self.feather = QSpinBox()
        self.feather.setRange(0, 100)
        self.feather.setValue(5)
        brush.addWidget(QLabel('Độ mềm biên σ (pixel)'))
        brush.addWidget(self.feather)
        brush.addWidget(button('Bật cọ vẽ mask', lambda: self.mode('brush')))
        brush.addWidget(button('Áp dụng vào vùng tô', self.apply_brush, True))
        brush.addWidget(button('Xóa vùng chọn / mask', lambda: self.canvas.clear_selection()))
        note = QLabel('Vùng đỏ chỉ là mask, không xuất vào ảnh. Telea dùng mask cứng và bán kính 3 px; thích hợp xóa chi tiết nhỏ. Xóa nền là thao tác bằng cọ, không tự nhận diện chủ thể.')
        note.setWordWrap(True)
        brush.addWidget(note)
        brush.addStretch()
        self.tabs.addTab(scroll_panel(brush), 'Cọ')
        box.addWidget(button('Áp dụng điều chỉnh', self.apply_adjustments, True))
        box.addWidget(button('Đặt lại thanh trượt', self.reset_adjustments))
        return frame

    def build_history(self):
        """Đặt lịch sử của tab hiện tại ở cột ngoài cùng bên phải."""
        frame = QFrame()
        frame.setObjectName('panel')
        frame.setMinimumWidth(180)
        frame.setMaximumWidth(300)
        box = QVBoxLayout(frame)
        heading = QLabel('LỊCH SỬ CHỈNH SỬA')
        heading.setObjectName('section')
        box.addWidget(heading)
        self.history_source = QLabel('Chưa mở ảnh')
        self.history_source.setWordWrap(True)
        box.addWidget(self.history_source)
        note = QLabel('Chọn bước để xem histogram trước / sau. Nhấn “Về bước đã chọn” để khôi phục ảnh.')
        note.setWordWrap(True)
        box.addWidget(note)
        self.history = QListWidget()
        self.history.setToolTip('Chọn một bước để xem histogram trước/sau của chức năng đó. Ảnh đang chỉnh được giữ nguyên.')
        self.history.currentRowChanged.connect(self.inspect_histogram_step)
        box.addWidget(self.history, 1)
        box.addWidget(button('Về bước đã chọn', self.restore_history_step))
        box.addWidget(button('↶ Hoàn tác', self.undo))
        box.addWidget(button('↷ Làm lại', self.redo))
        limit = QLabel('Tối đa 20 trạng thái / ảnh')
        limit.setWordWrap(True)
        box.addWidget(limit)
        return frame

    def adjustment_changed(self, unused=None):
        """Đánh dấu preview trên tab ngay khi kéo thanh trượt rồi hẹn dựng ảnh."""
        self.timer.start()
        self.update_tab_title()

    def update_tab_title(self):
        """Dấu sao chỉ thuộc tài liệu đang được thay đổi."""
        if self.active_page is None or self.doc is None:
            return
        index = self.document_tabs.indexOf(self.active_page)
        changed = self.doc.dirty or self.pending() or self.color_filter_channel is not None
        self.document_tabs.setTabText(index, self.source_name + (' *' if changed else ''))
        self.document_tabs.setTabToolTip(index, self.source_name)

    def alert(self, message):
        """Thông báo lỗi có thể phục hồi; giữ nguyên tài liệu hiện tại."""
        QMessageBox.warning(self, 'Minh Đăng Photo', str(message))

    def values(self):
        """Thu thập tham số hiện tại từ các thanh trượt."""
        return {key: slider.value() for key, slider in self.sliders.items()}

    def pending(self):
        """Kiểm tra có điều chỉnh đang xem trước nhưng chưa commit."""
        return self.doc is not None and self.values() != adjustments.DEFAULTS

    def ready(self, allow_pending=False):
        """Chặn thao tác khi bận, chưa có ảnh hoặc còn preview chưa áp dụng."""
        if self.busy:
            return False
        if self.doc is None:
            self.alert('Hãy mở ảnh trước.')
            return False
        if not allow_pending and self.pending():
            self.alert('Hãy nhấn Áp dụng điều chỉnh hoặc Đặt lại thanh trượt trước thao tác này.')
            return False
        return True

    def start_task(self, label, function, callback):
        """Chạy tác vụ nền và khóa chỉnh sửa tới khi luồng finished."""
        if self.busy:
            return
        self.timer.stop()
        self.busy = True
        self.centralWidget().setEnabled(False)
        self.progress.show()
        self.statusBar().showMessage(label + '…')
        self.task = Worker(function, self)
        self.task.result.connect(callback)
        self.task.error.connect(self.alert)
        self.task.finished.connect(self.finish_task)
        self.task.start()

    def finish_task(self):
        """Mở lại UI sau tác vụ, dọn worker mà không hủy thread đang chạy."""
        self.busy = False
        self.centralWidget().setEnabled(True)
        self.progress.hide()
        self.statusBar().showMessage('Sẵn sàng · Cuộn chuột để zoom · Ctrl+Z để hoàn tác')
        self.task.deleteLater()
        self.task = None

    def run_image(self, label, function):
        """Chụp ảnh đầu vào, xử lý nền và commit khi kết quả thành công."""
        if self.ready():
            source = self.doc.current.copy()
            self.start_task(label, lambda: function(source), lambda result: self.commit(result, label))

    def commit(self, result, label):
        """Thêm kết quả vào document, bỏ mask cũ và cập nhật panel."""
        self.doc.commit(result, label)
        self.reset_sliders()
        self.canvas.clear_selection()
        self.refresh()

    def refresh(self):
        """Dựng preview ≤ 1000px, cập nhật ảnh, histogram và lịch sử."""
        if not self.doc:
            return
        image = self.doc.current
        h, w = image.shape[:2]
        self.preview_base = self.histogram_sample(image)
        self.set_canvas_image(image)
        self.file_label.setText(f'{self.source_name}   ·   {w} × {h} px' + ('   *' if self.doc.dirty else ''))
        self.history_source.setText(self.source_name)
        self.update_tab_title()
        self.history.blockSignals(True)
        self.history.clear()
        for i, (_, label, _) in enumerate(self.doc.entries):
            self.history.addItem(('● ' if i == self.doc.index else '  ') + label)
        self.history.setCurrentRow(self.doc.index)
        self.history.blockSignals(False)
        self.inspect_histogram_step(self.doc.index)

    @staticmethod
    def histogram_sample(image):
        """Thu nhỏ cạnh dài về 1000px; mọi số liệu histogram tính trên mẫu này."""
        h, w = image.shape[:2]
        scale = min(1, 1000 / max(h, w))
        if scale == 1:
            return image
        return geometry.resize(image, max(1, round(w * scale)), max(1, round(h * scale)))

    def update_histogram(self, image, context, reference=None):
        """Đồng bộ bốn biểu đồ và tên chức năng với ảnh đang được phân tích."""
        self.histogram_context = context
        self.histogram.set_context(context)
        self.histogram.set_reference(reference)
        self.histogram.set_image(image)
        if self.histogram_detail is not None:
            self.histogram_detail.copy_from(self.histogram)

    def set_canvas_image(self, image, logical_size=None):
        """Ghi nhận ảnh trước lớp lọc và đồng bộ lớp xem màu sau mỗi thay đổi."""
        self.display_source = image
        self.canvas.set_image(image, logical_size)
        self.render_histogram_filter()

    def render_histogram_filter(self):
        """Xem riêng kênh RGB hoặc giữ gam; chưa ghi vào tài liệu."""
        channel = self.color_filter_channel
        visible = channel is not None and not self.comparing_original
        self.filter_bar.setVisible(visible)
        if not visible or self.display_source is None:
            self.canvas.set_color_filter(None)
            return
        sample = self.histogram_sample(self.display_source)
        operation = filters.channel_view if self.color_filter_mode == 'channel' else filters.color_range
        self.canvas.set_color_filter(operation(sample, channel))
        names = ['đỏ (R)', 'xanh lá (G)', 'xanh dương (B)', 'độ sáng (Y′)']
        action = 'Tách kênh ' if self.color_filter_mode == 'channel' else 'Giữ gam '
        self.filter_label.setText('Xem trước: ' + action + names[channel] + ' · Chưa áp dụng')
        self.filter_label.setToolTip('Tách kênh: giữ giá trị kênh được chọn, hai kênh kia bằng 0.\n'
                                    'Giữ gam: giữ vùng thuộc gam màu, chuyển màu khác sang xám.\n'
                                    'Y′ là ảnh độ sáng xám. Áp dụng lớp lọc để lưu kết quả vào ảnh.')

    def set_histogram_filter(self, channel):
        """Chọn hoặc tắt lớp lọc, đồng bộ các histogram mà không đổi số liệu."""
        self.histogram.set_selected_channel(channel)
        self.color_filter_channel = channel
        if self.histogram_detail is not None:
            self.histogram_detail.set_selected_channel(channel)
        self.render_histogram_filter()
        self.update_tab_title()

    def set_histogram_filter_mode(self, mode):
        """Đồng bộ cách lọc giữa biểu đồ chính, cửa sổ lớn và tab hiện tại."""
        if mode not in ('channel', 'gamut') or self.busy:
            return
        self.color_filter_mode = mode
        self.histogram.set_filter_mode(mode)
        if self.histogram_detail is not None:
            self.histogram_detail.set_filter_mode(mode)
        self.render_histogram_filter()

    def toggle_histogram_filter(self, channel):
        """Bấm histogram để bật gam tương ứng; bấm lại cùng bảng để tắt."""
        if self.doc is None or self.busy or self.comparing_original:
            return
        if self.history.currentRow() != self.doc.index:
            self.history.setCurrentRow(self.doc.index)
        self.set_histogram_filter(None if self.color_filter_channel == channel else channel)

    def apply_histogram_filter(self):
        """Áp dụng cả điều chỉnh đang xem và lớp giữ gam trên ảnh đủ độ phân giải."""
        channel = self.color_filter_channel
        if channel is None or self.comparing_original or not self.ready(True):
            return
        params = self.values()
        if params['white'] <= params['black']:
            self.alert('Điểm trắng phải lớn hơn điểm đen.')
            return
        source = self.doc.current.copy()
        pending = self.pending()
        prefix = 'Tách kênh ' if self.color_filter_mode == 'channel' else 'Giữ gam '
        names = [prefix + 'đỏ', prefix + 'xanh lá', prefix + 'xanh dương', 'Độ sáng (ảnh xám)']
        operation = filters.channel_view if self.color_filter_mode == 'channel' else filters.color_range
        label = names[channel] + (' + điều chỉnh' if pending else '')
        self.start_task(label,
                        lambda: operation(adjustments.adjust(source, params) if pending else source, channel),
                        lambda result: self.finish_histogram_filter(result, label))

    def finish_histogram_filter(self, result, label):
        """Chỉ bỏ lớp xem thử khi xử lý thành công rồi thêm kết quả vào lịch sử."""
        self.set_histogram_filter(None)
        self.commit(result, label)

    def toggle_histogram(self, visible):
        """Thu gọn biểu đồ để dành chỗ cho thanh trượt trên màn hình nhỏ."""
        self.histogram.setVisible(visible)
        self.histogram_toggle.setText('Ẩn' if visible else 'Hiện')

    def show_histogram_detail(self):
        """Mở bốn biểu đồ lớn để đọc rõ các cột và thống kê từng mức."""
        if self.doc is None:
            self.alert('Hãy mở ảnh trước.')
            return
        dialog = QDialog(self)
        dialog.setWindowTitle('Histogram · ' + self.histogram_context)
        dialog.resize(900, 620)
        layout = QVBoxLayout(dialog)
        histogram = Histogram(dialog)
        histogram.setMinimumHeight(440)
        histogram.setMaximumHeight(16777215)
        histogram.copy_from(self.histogram)
        histogram.channel_selected.connect(self.toggle_histogram_filter)
        histogram.filter_mode_changed.connect(self.set_histogram_filter_mode)
        self.histogram_detail = histogram
        layout.addWidget(histogram, 1)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        try:
            dialog.exec()
        finally:
            self.histogram_detail = None
            dialog.deleteLater()

    def inspect_histogram_step(self, row):
        """Xem trước/sau của một bước lịch sử mà không thay trạng thái tài liệu."""
        if self.doc is None or not 0 <= row < len(self.doc.entries):
            return
        if self.comparing_original:
            return
        if self.pending() and row == self.doc.index:
            self.preview()
            return
        _, label, encoded = self.doc.entries[row]
        image = self.preview_base if row == self.doc.index else self.histogram_sample(from_png(encoded))
        reference = None
        if row > 0:
            serial, _, previous = self.doc.entries[row - 1]
            if self.histogram_reference_key != serial:
                self.histogram_reference = self.histogram_sample(from_png(previous))
                self.histogram_reference_key = serial
            reference = self.histogram_reference
        context = label if row == self.doc.index else f'Lịch sử: {label} (bước {row + 1})'
        self.update_histogram(image, context, reference)

    def reset_sliders(self):
        """Đưa về mặc định; timer bị dừng sau signal đồng bộ spin/slider."""
        for key, value in adjustments.DEFAULTS.items():
            self.sliders[key].setValue(value)
        self.timer.stop()

    def restore_history_step(self):
        """Quay lại snapshot được chọn và giữ nhánh làm lại cho đến lần chỉnh mới."""
        if not self.ready():
            return
        row = self.history.currentRow()
        if not 0 <= row < len(self.doc.entries):
            return
        self.doc.current = from_png(self.doc.entries[row][2])
        self.doc.index = row
        self.canvas.clear_selection()
        self.refresh()

    def reset_adjustments(self):
        """Hủy preview, không thay ảnh đã commit."""
        if not self.busy:
            self.reset_sliders()
            self.refresh()

    def preview(self):
        """Debounce preview nhanh trên ảnh thu nhỏ; chưa ghi vào undo."""
        if self.doc is None or self.busy or self.comparing_original:
            return
        try:
            params = self.values()
            result = adjustments.adjust(self.preview_base, params)
            h, w = self.doc.current.shape[:2]
            self.set_canvas_image(result, (w, h))
            titles = [title.split(' · ')[0] for key, title, _, _ in ADJUSTERS
                      if params[key] != adjustments.DEFAULTS[key]]
            if titles:
                self.update_histogram(result, 'Xem trước: ' + ', '.join(titles), self.preview_base)
            else:
                self.inspect_histogram_step(self.doc.index)
            self.statusBar().showMessage('Bản xem trước · Nhấn Áp dụng điều chỉnh để lưu thay đổi vào ảnh')
        except ValueError as exc:
            self.statusBar().showMessage(str(exc))

    def apply_adjustments(self):
        """Chạy pipeline cùng tham số trên ảnh đủ độ phân giải."""
        if self.ready(True) and self.pending():
            params = self.values()
            if params['white'] <= params['black']:
                self.alert('Điểm trắng phải lớn hơn điểm đen.')
                return
            source = self.doc.current.copy()
            titles = [title.split(' · ')[0] for key, title, _, _ in ADJUSTERS
                      if params[key] != adjustments.DEFAULTS[key]]
            label = 'Điều chỉnh: ' + ', '.join(titles)
            self.start_task('Điều chỉnh ánh sáng và màu', lambda: adjustments.adjust(source, params),
                            lambda result: self.commit(result, label))

    def save_page_state(self):
        """Lưu trạng thái thanh trượt và công cụ hiện tại vào tab đang hoạt động."""
        page = self.active_page
        if page is None:
            return
        page.source_name = self.source_name
        page.adjustment_values = self.values()
        page.filter_channel = self.color_filter_channel
        page.filter_mode = self.color_filter_mode
        page.history_row = self.history.currentRow()
        page.property_tab = self.tabs.currentIndex()
        page.preset_index = self.look.currentIndex()
        page.preset_strength = self.strength.value()
        page.brush_index = self.brush_mode.currentIndex()
        page.brush_amount = self.brush_amount.value()
        page.feather = self.feather.value()
        page.hint = self.hint.text()

    def switch_document(self, index):
        """Chuyển đổi giữa các tab ảnh và khôi phục trạng thái giao diện của tab đó."""
        if self.busy:
            return
        self.timer.stop()
        if self.active_page is not None and self.document_tabs.indexOf(self.active_page) != -1:
            self.save_page_state()
        page = self.document_tabs.widget(index) if 0 <= index < self.document_tabs.count() else None
        if page is None:
            self.active_page = None
            self.doc = None
            self.canvas = self.empty_canvas
            self.source_name = 'Chưa mở ảnh'
            self.color_filter_channel = None
            self.histogram.set_selected_channel(None)
            self.histogram.values = None
            self.histogram.pixel_count = 0
            self.histogram.set_reference(None)
            self.histogram.set_context('Chưa mở ảnh')
            self.histogram._update_charts()
            self.filter_bar.hide()
            self.document_tabs.hide()
            self.empty_canvas.show()
            self.file_label.setText('Mở một bức ảnh để bắt đầu')
            self.history_source.setText('Chưa mở ảnh')
            self.history.clear()
            self.reset_sliders()
            return
        first_open = getattr(page, 'shape', None) is None
        self.active_page = page
        self.canvas = page
        self.doc = page.document
        self.source_name = getattr(page, 'source_name', 'Ảnh')
        self.histogram_reference_key = None
        self.histogram_reference = None
        self.comparing_original = False
        self.color_filter_channel = getattr(page, 'filter_channel', None)
        self.color_filter_mode = getattr(page, 'filter_mode', 'channel')
        self.histogram.set_filter_mode(self.color_filter_mode)
        self.histogram.set_selected_channel(self.color_filter_channel)
        for key, value in getattr(page, 'adjustment_values', adjustments.DEFAULTS).items():
            if key in self.sliders:
                self.sliders[key].setValue(value)
        self.timer.stop()
        self.tabs.setCurrentIndex(getattr(page, 'property_tab', 0))
        self.look.setCurrentIndex(getattr(page, 'preset_index', 0))
        self.strength.setValue(getattr(page, 'preset_strength', 100))
        self.brush_mode.setCurrentIndex(getattr(page, 'brush_index', 0))
        self.brush_amount.setValue(getattr(page, 'brush_amount', 25))
        self.feather.setValue(getattr(page, 'feather', 5))
        self.brush_size_control.setValue(getattr(page, 'brush_size', 40))
        self.brush_eraser_control.setChecked(getattr(page, 'eraser', False))
        self.hint.setText(getattr(page, 'hint', 'Kéo ảnh bằng công cụ Di chuyển. Cuộn chuột để phóng to / thu nhỏ.'))
        self.refresh()
        history_row = getattr(page, 'history_row', self.doc.index)
        if 0 <= history_row < len(self.doc.entries) and history_row != self.doc.index:
            self.history.setCurrentRow(history_row)
        if self.pending():
            self.preview()
        if first_open:
            page.set_mode('pan')
            page.fit_image()

    def close_document(self, index):
        """Đóng một tab ảnh; hỏi xác nhận nếu tab đó có thay đổi chưa lưu."""
        if self.busy or not 0 <= index < self.document_tabs.count():
            return
        page = self.document_tabs.widget(index)
        unsaved = ((self.doc.dirty or self.pending() or self.color_filter_channel is not None)
                   if page is self.active_page else getattr(page, 'unsaved', False))
        if unsaved:
            reply = QMessageBox.question(
                self, 'Thay đổi chưa lưu dự án',
                f'Đóng "{getattr(page, "source_name", "ảnh")}" sẽ bỏ các thay đổi chưa lưu trong phiên này.\nẢnh đã xuất trên đĩa vẫn được giữ. Tiếp tục?',
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No)
            if reply != QMessageBox.StandardButton.Yes:
                return
        if page is self.active_page:
            self.active_page = None
        self.document_tabs.removeTab(index)
        page.deleteLater()
        if self.document_tabs.count() == 0:
            self.switch_document(-1)

    def confirm_discard(self):
        """Hỏi trước khi thoát ứng dụng nếu còn bất kỳ tab nào chưa lưu."""
        if self.busy:
            return False
        self.save_page_state()
        has_unsaved = any(getattr(self.document_tabs.widget(i), 'unsaved', False)
                          for i in range(self.document_tabs.count()))
        if not has_unsaved and self.doc is not None:
            has_unsaved = self.doc.dirty or self.pending()
        if has_unsaved:
            return QMessageBox.question(
                self, 'Thay đổi chưa lưu dự án',
                'Thoát ứng dụng sẽ bỏ các thay đổi chưa lưu trong phiên này.\nẢnh đã xuất trên đĩa vẫn được giữ. Tiếp tục?',
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes
        return True

    def set_document(self, image, name, original=None, created=False):
        """Mở ảnh hoặc dự án mới trong một tab độc lập."""
        page = ImagePage(image, name, original, created)
        page.brush_size = self.brush_size_control.value()
        page.eraser = self.brush_eraser_control.isChecked()
        self.empty_canvas.hide()
        self.document_tabs.show()
        index = self.document_tabs.addTab(page, name)
        self.document_tabs.setCurrentIndex(index)
        if self.active_page is not page:
            self.switch_document(index)

    def open_image(self):
        """Chọn một hoặc nhiều ảnh và nạp mỗi ảnh thành một tab mới."""
        if self.busy:
            return
        paths, _ = QFileDialog.getOpenFileNames(self, 'Mở ảnh', '', IMAGE_FILTER)
        if paths:
            self.start_task('Đọc ảnh', lambda: [(Path(path).name, load_image(path)) for path in paths],
                            self.open_loaded_images)

    def open_loaded_images(self, items):
        """Tạo tab cho từng ảnh đã nạp thành công."""
        for name, image in items:
            self.set_document(image, name)

    def open_project(self):
        """Nạp .mdphoto gồm bản gốc và bản chỉnh vào một tab mới."""
        if self.busy:
            return
        path, _ = QFileDialog.getOpenFileName(self, 'Mở dự án', '', 'Minh Đăng Photo (*.mdphoto)')
        if path:
            self.start_task('Mở dự án', lambda: load_project(path),
                            lambda pair: self.set_document(pair[1], Path(path).name, pair[0]))

    def save(self):
        """Lưu dự án đủ hai ảnh bằng ghi nguyên tử; chưa lưu undo stack."""
        if not self.ready():
            return
        if self.color_filter_channel is not None:
            self.alert('Nhấn Áp dụng lớp lọc hoặc Tắt lớp lọc trước khi lưu dự án.')
            return
        path, _ = QFileDialog.getSaveFileName(self, 'Lưu dự án', 'Chinh_anh.mdphoto', 'Minh Đăng Photo (*.mdphoto)')
        if path:
            if not path.lower().endswith('.mdphoto'):
                path += '.mdphoto'
            self.start_task('Lưu dự án', lambda: save_project(path, self.doc.original, self.doc.current, self.doc.labels()), self.saved)

    def saved(self, unused):
        """Ghi nhận lưu dự án thành công và bỏ dấu sao trên tên tài liệu."""
        self.doc.mark_saved()
        self.refresh()

    def export(self):
        """Chọn chất lượng và định dạng; xuất ảnh đủ độ phân giải hiện tại."""
        if not self.ready():
            return
        if self.color_filter_channel is not None:
            self.alert('Nhấn Áp dụng lớp lọc hoặc Tắt lớp lọc trước khi xuất ảnh.')
            return
        options = parameters(self, 'Xuất ảnh', [('quality', 'Chất lượng JPEG / WebP', 95, 1, 100)],
                             'PNG giữ trong suốt. JPEG/BMP chuyển nền trong suốt thành trắng. Không giữ EXIF/GPS.')
        if not options:
            return
        path, selected = QFileDialog.getSaveFileName(self, 'Xuất ảnh', 'Anh_da_chinh.png',
                       'PNG (*.png);;JPEG (*.jpg);;WebP (*.webp);;TIFF (*.tiff);;BMP (*.bmp)')
        if path:
            if not Path(path).suffix:
                extension = {'PNG': '.png', 'JPEG': '.jpg', 'WebP': '.webp', 'TIFF': '.tiff', 'BMP': '.bmp'}[selected.split()[0]]
                path += extension
            self.start_task('Xuất ảnh', lambda: export_image(self.doc.current, path, options['quality']),
                            lambda _: QMessageBox.information(self, 'Xuất thành công', f'Đã lưu ảnh:\n{path}'))

    def undo(self):
        """Hoàn tác một trạng thái và xóa mask không còn tương ứng."""
        if self.ready():
            self.doc.undo()
            self.canvas.clear_selection()
            self.refresh()

    def redo(self):
        """Khôi phục trạng thái vừa hoàn tác nếu nhánh redo còn tồn tại."""
        if self.ready():
            self.doc.redo()
            self.canvas.clear_selection()
            self.refresh()

    def show_original(self, enabled):
        """Giữ nút để xem ảnh gốc; không sửa document hoặc lịch sử."""
        if self.doc and not self.busy:
            self.canvas.overlay.setVisible(not enabled)
            self.canvas.rectangle.setVisible(not enabled)
            if enabled:
                self.timer.stop()
                self.comparing_original = True
                self.compare_state = (self.canvas.mask.copy(), self.canvas.rectangle.rect(), self.canvas.transform())
                self.set_canvas_image(self.doc.original)
                self.update_histogram(self.histogram_sample(self.doc.original), 'Đang xem ảnh gốc')
            else:
                self.comparing_original = False
                if self.pending():
                    self.preview()
                else:
                    self.set_canvas_image(self.doc.current)
                    self.inspect_histogram_step(self.history.currentRow())
                if hasattr(self, 'compare_state'):
                    self.canvas.mask, rectangle, transform = self.compare_state
                    self.canvas.rectangle.setRect(rectangle)
                    self.canvas.setTransform(transform)
                    self.canvas.show_mask()

    def mode(self, mode):
        """Chọn chế độ chuột và hiển thị hướng dẫn đúng công cụ."""
        if self.ready():
            self.canvas.set_mode(mode)
            self.hint.setText({'pan': 'Kéo để di chuyển ảnh. Cuộn chuột để zoom.',
                               'crop': 'Kéo chuột trái chọn vùng, sau đó nhấn Cắt vùng đã chọn.',
                               'brush': 'Tô vùng cần sửa. Mask đỏ không nằm trong ảnh xuất. Nhấn Áp dụng vào vùng tô.'}[mode])

    def do_crop(self):
        """Đọc crop box của canvas và gọi module hình học."""
        box = self.canvas.crop_box()
        self.run_image('Cắt ảnh', lambda image: geometry.crop(image, box))

    def ratio_crop(self):
        """Tính crop ở tâm theo tỉ lệ chuẩn, sau đó cắt trên ảnh thật."""
        if not self.ready():
            return
        p = parameters(self, 'Cắt theo tỉ lệ', [('ratio', 'Tỉ lệ', ['1:1', '4:3', '3:2', '16:9', '9:16', '2:3'], 0, 0)], 'Cắt ở tâm ảnh. Muốn tự chọn vị trí, dùng Chọn vùng cắt.')
        if p:
            a, b = map(int, p['ratio'].split(':'))
            h, w = self.doc.current.shape[:2]
            cw, ch = min(w, h * a / b), min(h, w * b / a)
            box = ((w - cw) / 2, (h - ch) / 2, (w + cw) / 2, (h + ch) / 2)
            self.run_image('Cắt ' + p['ratio'], lambda image: geometry.crop(image, box))

    def do_rotate(self):
        """Nhập góc xoay tùy ý; góc dương ngược chiều kim đồng hồ."""
        if self.ready():
            p = parameters(self, 'Xoay / Nắn thẳng', [('degrees', 'Góc xoay (độ)', 90.0, -180, 180)], 'Sau khi nắn thẳng, dùng Crop để bỏ các góc trong suốt.')
            if p:
                self.run_image('Xoay ảnh', lambda image: geometry.rotate(image, p['degrees']))

    def do_resize(self):
        """Thu kích thước, tùy chọn khóa tỉ lệ tính chiều cao từ chiều rộng."""
        if not self.ready():
            return
        h, w = self.doc.current.shape[:2]
        p = parameters(self, 'Đổi kích thước', [('w', 'Chiều rộng', w, 1, 20000), ('h', 'Chiều cao', h, 1, 20000),
                        ('ratio', 'Tỉ lệ', ['Giữ tỉ lệ theo chiều rộng', 'Tự do'], 0, 0)])
        if p:
            height = max(1, round(h * p['w'] / w)) if p['ratio'].startswith('Giữ') else p['h']
            self.run_image('Resize Lanczos', lambda image: geometry.resize(image, p['w'], height))

    def do_curve(self):
        """Phân tích chuỗi nút X:Y thành LUT; báo lỗi nhập thay vì crash."""
        if not self.ready():
            return
        p = parameters(self, 'Đường cong Curves', [('channel', 'Kênh', ['RGB', 'R', 'G', 'B'], 0, 0),
                        ('points', 'Các nút X:Y', '0:0, 64:48, 128:128, 192:208, 255:255', 0, 0)],
                       'Ví dụ đường cong chữ S tăng tương phản. Các tọa độ thuộc 0–255; phân cách bằng dấu phẩy.')
        if p:
            try:
                points = [tuple(map(int, item.strip().split(':'))) for item in p['points'].split(',')]
                if any(len(pair) != 2 for pair in points):
                    raise ValueError('Mỗi nút cần đúng hai số X:Y.')
            except ValueError as exc:
                self.alert(str(exc))
                return
            self.run_image('Curves ' + p['channel'], lambda image: adjustments.curve(image, points, p['channel']))

    def do_hsl(self):
        """Chọn dải hue và thông số chỉnh chọn lọc trong không gian HSV."""
        if self.ready():
            p = parameters(self, 'Màu chọn lọc HSL', [('center', 'Dải màu', ['Đỏ', 'Vàng', 'Xanh lá', 'Cyan', 'Xanh dương', 'Tím'], 0, 0),
                ('hue', 'Dịch hue (độ)', 0, -90, 90), ('sat', 'Bão hòa (%)', 0, -100, 100), ('light', 'Độ sáng (%)', 0, -100, 100)],
                'Công cụ giao diện HSL được triển khai bằng HSV; Độ sáng điều chỉnh Value, không phải Lightness của HSL chuẩn.')
            if p:
                center = ['Đỏ', 'Vàng', 'Xanh lá', 'Cyan', 'Xanh dương', 'Tím'].index(p['center']) * 60
                self.run_image('Màu chọn lọc', lambda image: adjustments.hsl(image, center, p['hue'], p['sat'], p['light']))

    def do_filter(self):
        """Chọn thuật toán lọc hoặc công cụ phân tích phục vụ báo cáo."""
        if self.ready():
            p = parameters(self, 'Bộ lọc và thuật toán', [('kind', 'Thuật toán', ['Làm nét', 'Gaussian', 'Median', 'Bilateral', 'Khử nhiễu NLM', 'CLAHE', 'Cartoon', 'Phác thảo', 'Canny', 'Otsu', 'Âm bản'], 0, 0),
                      ('amount', 'Cường độ', 10, 1, 50)], 'NLM có thể mất nhiều thời gian trên ảnh lớn. Canny/Otsu tạo ảnh phân tích; có thể Ctrl+Z để quay lại.')
            if p:
                self.run_image(p['kind'], lambda image: filters.spatial(image, p['kind'], p['amount']))

    def do_vignette(self):
        """Thu cường độ tối góc và gọi vignette."""
        if self.ready():
            p = parameters(self, 'Tối góc', [('amount', 'Cường độ (%)', 40, 0, 100)])
            if p:
                self.run_image('Vignette', lambda image: filters.vignette(image, p['amount']))

    def do_lesson(self):
        """Chọn thuật toán trong registry và xử lý ảnh đủ độ phân giải ở worker."""
        if not self.ready():
            return
        selection = choose_lesson(self)
        if selection is None:
            return
        spec = lesson_spec(selection)
        label = f'Chương {selection["chapter"]} · {spec.title}'
        source = self.doc.current.copy()
        self.start_task(label, lambda: process_lesson(source, selection),
                        lambda output: self.finish_lesson(output, label, spec.diagnostic))

    def finish_lesson(self, output, label, diagnostic=False):
        """Lưu kết quả có undo; ảnh phổ chỉ được mở trong cửa sổ phân tích."""
        result, info = output
        if diagnostic:
            self.show_lesson_diagnostic(result, label)
            return
        self.commit(result, label + (f' · {info}' if info else ''))
        if info:
            self.hint.setText(info + ' · Ctrl+Z để hoàn tác.')

    def show_lesson_diagnostic(self, image, label):
        """Parent giữ dialog trong lúc mở, đóng sẽ giải phóng ảnh phân tích."""
        dialog = AnalysisPreview(self, image, label)
        dialog.show()

    def do_quality(self):
        """Đánh giá ảnh hiện tại với tham chiếu cùng kích thước trong luồng nền."""
        if not self.ready():
            return
        path, _ = QFileDialog.getOpenFileName(self, 'Chọn ảnh chuẩn cùng kích thước để đánh giá', '', IMAGE_FILTER)
        if not path:
            return
        source = self.doc.current.copy()
        self.start_task('Đánh giá chất lượng ảnh',
                        lambda: enhancement_spatial.quality_metrics(source, load_image(path)),
                        lambda result: self.show_quality(result, Path(path).name))

    def show_quality(self, result, reference_name):
        """Chỉ số so với tham chiếu là thông tin; không thêm một bước chỉnh ảnh."""
        psnr = '∞ (trùng khớp)' if np.isinf(result['psnr']) else f'{result["psnr"]:.4f} dB'
        QMessageBox.information(self, 'Đánh giá chất lượng ảnh',
            f'Tham chiếu: {reference_name}\n\nMSE: {result["mse"]:.4f}\n'
            f'PSNR: {psnr}\nSSIM: {result["ssim"]:.6f}\n\n'
            'MSE thấp, PSNR và SSIM cao thể hiện mức giống ảnh tham chiếu hơn. '
            'Chỉ so sánh pixel nhìn thấy chung; ảnh phải cùng kích thước và đã căn chỉnh. '
            'Các chỉ số không tự kết luận ảnh đẹp hơn.')

    def apply_preset(self):
        """Áp dụng preset và cường độ đang chọn trên panel màu."""
        name, strength = self.look.currentText(), self.strength.value()
        self.run_image(name, lambda image: filters.preset(image, name, strength))

    def brush_tab(self):
        """Mở panel cọ và bật chế độ tô mask."""
        if self.ready():
            self.tabs.setCurrentIndex(2)
            self.mode('brush')

    def apply_brush(self):
        """Chụp mask và thông số trước khi chạy tác vụ cục bộ."""
        if self.ready():
            mask = self.canvas.mask.copy()
            name, amount, feather = self.brush_mode.currentText(), self.brush_amount.value(), self.feather.value()
            self.run_image(name, lambda image: retouch.local_edit(image, mask, name, amount, feather))

    def do_text(self):
        """Thu chữ, vị trí, màu, font hệ thống rồi raster vào ảnh."""
        if not self.ready():
            return
        font, _ = QFileDialog.getOpenFileName(self, 'Chọn font hỗ trợ tiếng Việt (TTF / OTF)',
                            'C:/Windows/Fonts' if Path('C:/Windows/Fonts').exists() else '/usr/share/fonts', 'Font (*.ttf *.otf)')
        if not font:
            return
        h, w = self.doc.current.shape[:2]
        p = parameters(self, 'Chèn chữ / Watermark', [('text', 'Nội dung', 'Minh Đăng Photo', 0, 0),
            ('x', 'X từ bên trái', min(40, w - 1), 0, w - 1), ('y', 'Y từ phía trên', min(40, h - 1), 0, h - 1),
            ('size', 'Cỡ chữ (pixel)', max(12, w // 25), 8, 1000), ('color', 'Màu HEX', '#ffffff', 0, 0)],
            'Chữ được gộp vào ảnh sau khi áp dụng. Muốn sửa, Ctrl+Z rồi chèn lại.')
        if p:
            self.run_image('Chèn chữ', lambda image: retouch.text_layer(image, p['text'], p['x'], p['y'], p['size'], p['color'], font))

    def do_overlay(self):
        """Chọn sticker/ảnh thứ hai và tham số alpha compositing."""
        if not self.ready():
            return
        path, _ = QFileDialog.getOpenFileName(self, 'Chọn PNG trong suốt hoặc ảnh phủ', '', IMAGE_FILTER)
        if not path:
            return
        h, w = self.doc.current.shape[:2]
        p = parameters(self, 'Sticker / Ảnh phủ', [('x', 'X', 0, -w, w), ('y', 'Y', 0, -h, h),
            ('width', 'Chiều rộng (pixel)', max(1, w // 3), 1, 20000), ('opacity', 'Độ đậm (%)', 100, 0, 100)])
        if p:
            self.run_image('Ảnh phủ', lambda image: retouch.overlay(image, load_image(path), p['x'], p['y'], p['width'], p['opacity']))

    def do_border(self):
        """Thu độ dày và màu của khung bên ngoài ảnh."""
        if self.ready():
            p = parameters(self, 'Khung ảnh', [('size', 'Độ dày (pixel)', 30, 1, 1000), ('color', 'Màu HEX', '#ffffff', 0, 0)])
            if p:
                self.run_image('Khung viền', lambda image: geometry.border(image, p['size'], p['color']))

    def do_collage(self):
        """Ghép nhiều ảnh thành một tab tài liệu mới."""
        if self.busy:
            return
        paths, _ = QFileDialog.getOpenFileNames(self, 'Chọn tối đa 12 ảnh để ghép', '', IMAGE_FILTER)
        if not paths:
            return
        if len(paths) > 12:
            self.alert('Hãy chọn tối đa 12 ảnh.')
            return
        p = parameters(self, 'Ghép ảnh dạng lưới', [('columns', 'Số cột', 2, 1, 4), ('cell', 'Cỡ ô vuông', 600, 100, 1200), ('gap', 'Khoảng cách', 16, 0, 100)],
                       'Mỗi ảnh được cắt vừa ô vuông ở tâm. Kết quả tạo tài liệu mới.')
        if p:
            self.start_task('Ghép ảnh', lambda: retouch.collage([load_image(path) for path in paths], p['columns'], p['cell'], p['gap']),
                            lambda image: self.set_document(image, 'Collage', created=True))

    def do_batch(self):
        """Chọn tập ảnh, preset, cạnh dài và thư mục đích, xuất tuần tự."""
        if self.busy:
            return
        paths, _ = QFileDialog.getOpenFileNames(self, 'Chọn ảnh xử lý hàng loạt', '', IMAGE_FILTER)
        if not paths:
            return
        folder = QFileDialog.getExistingDirectory(self, 'Chọn thư mục lưu kết quả')
        if not folder:
            return
        p = parameters(self, 'Xử lý hàng loạt', [('look', 'Preset', filters.PRESETS, 0, 0), ('longest', 'Cạnh dài tối đa (0 giữ nguyên)', 1920, 0, 10000),
                          ('extension', 'Định dạng', ['.jpg', '.png', '.webp'], 0, 0)], 'Áp dụng preset riêng cho từng file nguồn. Không sử dụng các thanh trượt của ảnh đang mở. Không ghi đè file đã có.')
        if p:
            self.start_task('Xuất hàng loạt', lambda: batch_export(paths, folder, p['look'], p['longest'], p['extension']), self.batch_done)

    def batch_done(self, results):
        """Báo số ảnh thành công và lỗi từng file thay vì che giấu lỗi batch."""
        errors = [f'{Path(source).name}: {error}' for source, _, error in results if error]
        message = f'Thành công {len(results) - len(errors)}/{len(results)} ảnh.'
        if errors:
            message += '\n\n' + '\n'.join(errors)
        QMessageBox.information(self, 'Kết quả hàng loạt', message)

    def restore(self):
        """Khôi phục ảnh gốc như một bước có thể undo, không xóa lịch sử."""
        if self.ready():
            self.commit(self.doc.original.copy(), 'Khôi phục ảnh gốc')

    def help(self):
        """Hướng dẫn quy trình và các giới hạn ngay trong app."""
        QMessageBox.information(self, 'Hướng dẫn nhanh',
            '1. Mở ảnh JPG/PNG/WebP/BMP/TIFF.\n'
            '2. Kéo thanh trượt → Áp dụng điều chỉnh.\n'
            '3. Crop: kéo chọn → Cắt vùng đã chọn.\n'
            '4. Cọ: chọn hiệu ứng → tô vùng đỏ → Áp dụng vào vùng tô.\n'
            '5. Ctrl+Z hoàn tác; Ctrl+Shift+Z làm lại.\n'
            '6. Lưu .mdphoto để giữ bản gốc và bản đã chỉnh.\n'
            '7. Xuất ảnh PNG/JPEG/WebP/TIFF/BMP.\n\n'
            'Bài học: mở Thuật toán bài học để chọn biến đổi mức xám, histogram, '
            'lọc không gian/tần số, phát hiện biên, phân đoạn và hình thái học. '
            'Mỗi thuật toán có mô tả, tham số và trang bài giảng. Phổ Fourier xem riêng; '
            'các kết quả áp dụng đều hoàn tác được. Đánh giá MSE/PSNR/SSIM cần ảnh chuẩn cùng kích thước.\n\n'
            'Giới hạn: 20 triệu pixel/ảnh; RGBA 8 bit sRGB. Chữ/sticker gộp vào ảnh. '
            'Dự án không giữ undo qua lần mở lại. Không có RAW, AI sinh ảnh, nhận diện chủ thể, '
            'layer chuyên nghiệp, lens correction hoặc đồng bộ đám mây.\n\n'
            'Xem README.md và tài liệu Word trong thư mục docs để cài đặt và hiểu thuật toán.')

    def closeEvent(self, event):
        """Không đóng khi luồng còn chạy; hỏi khi có thay đổi chưa lưu."""
        if self.busy:
            self.statusBar().showMessage('Đợi tác vụ hoàn thành trước khi đóng ứng dụng.')
            event.ignore()
        elif self.confirm_discard():
            event.accept()
        else:
            event.ignore()
