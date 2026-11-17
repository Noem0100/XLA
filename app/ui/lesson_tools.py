"""Bộ lọc và xử lý ảnh: chọn chức năng, tham số và nguồn ảnh trước khi chạy nền."""
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QComboBox, QLabel, QPushButton, QDialogButtonBox, QScrollArea, QWidget, QFileDialog)

from app.core import enhancement
from app.core.io import load_image
from .canvas import Canvas
from .dialogs import parameter_widget, parameter_value

IMAGE_FILTER = 'Ảnh (*.jpg *.jpeg *.png *.webp *.bmp *.tif *.tiff);;Tất cả (*)'

CHOICE_LABELS = {
    'family': {'gaussian': 'Gaussian', 'butterworth': 'Butterworth', 'ideal': 'Lý tưởng'},
    'psf': {'gaussian': 'Mờ Gaussian', 'motion': 'Mờ chuyển động ngang'},
    'direction': {'magnitude': 'Độ lớn gradient', 'x': 'Đạo hàm theo trục ngang (x)',
                  'y': 'Đạo hàm theo trục dọc (y)'},
    'operation': {'add': 'Cộng', 'subtract': 'Trừ', 'difference': 'Chênh lệch tuyệt đối',
                  'multiply': 'Nhân', 'divide': 'Chia', 'and': 'Giao mặt nạ (AND)',
                  'or': 'Hợp mặt nạ (OR)'},
    'output': {'color': 'Giữ màu vùng chọn, nền đen', 'mask': 'Mặt nạ trắng / đen'},
    'shape': {'rect': 'Hình chữ nhật', 'cross': 'Hình chữ thập', 'ellipse': 'Hình elip'},
    'mode': {'standard': 'Hough chuẩn', 'probabilistic': 'Hough xác suất'},
}
CHANNEL_LABELS = {
    'RGB': ('Đỏ (R)', 'Xanh lá (G)', 'Xanh dương (B)'),
    'CMY': ('Lục lam (C)', 'Đỏ tía (M)', 'Vàng (Y)'),
    'HSV': ('Sắc độ (H)', 'Độ bão hòa (S)', 'Độ sáng (V)'),
    'YCbCr': ('Độ sáng (Y)', 'Sắc sai xanh (Cb)', 'Sắc sai đỏ (Cr)'),
    'Lab': ('Độ sáng (L)', 'Trục xanh lá – đỏ (a)', 'Trục xanh dương – vàng (b)'),
}
RGB_DEFAULTS = {'negative', 'log', 'gamma', 'linear', 'piecewise', 'quantize'}


def lesson_modules():
    """Nạp các nhóm chức năng tại chỗ để tránh phụ thuộc vòng vào cửa sổ."""
    from app.core import analysis, foundations
    return {1: foundations, 2: enhancement, 3: analysis}


def lesson_spec(selection):
    """Lấy mô tả cùng registry mà worker sẽ sử dụng."""
    return lesson_modules()[selection['chapter']].ALGORITHMS[selection['algorithm']]


def process_lesson(source, selection):
    """Chỉ gọi trong worker; ảnh tham chiếu/nhiều khung được đọc ngoài GUI."""
    module = lesson_modules()[selection['chapter']]
    kwargs = {'params': selection['params']}
    if selection.get('reference'):
        kwargs['reference'] = load_image(selection['reference'])
    if selection['chapter'] == 2:
        kwargs['mode'] = selection['mode']
        if selection.get('frames'):
            kwargs['frames'] = (load_image(path) for path in selection['frames'])
    return module.process(source, selection['algorithm'], **kwargs)


class LessonDialog(QDialog):
    """Form thay đổi theo registry; kết quả chỉ chứa tham số và đường dẫn."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Bộ lọc và xử lý ảnh')
        self.resize(690, 690)
        self.setMinimumWidth(540)
        self.modules = lesson_modules()
        self.widgets = {}
        self.reference_path = None
        self.frame_paths = []
        layout = QVBoxLayout(self)
        intro = QLabel('Chọn chức năng và điều chỉnh tham số theo ảnh. '
                       'Áp dụng lên ảnh đang mở ở độ phân giải đầy đủ; Ctrl+Z để hoàn tác.')
        intro.setWordWrap(True)
        layout.addWidget(intro)
        selectors = QFormLayout()
        self.chapter = QComboBox()
        self.chapter.addItem('Màu sắc và biến đổi ảnh', 1)
        self.chapter.addItem('Nâng cao chất lượng ảnh', 2)
        self.chapter.addItem('Phát hiện biên và phân vùng', 3)
        self.group = QComboBox()
        self.algorithm = QComboBox()
        for title, widget in [('Danh mục', self.chapter), ('Nhóm', self.group), ('Chức năng', self.algorithm)]:
            selectors.addRow(title, widget)
        layout.addLayout(selectors)
        self.description = QLabel()
        self.description.setWordWrap(True)
        self.description.setTextFormat(Qt.TextFormat.PlainText)
        self.description.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self.description)
        area = QScrollArea()
        area.setWidgetResizable(True)
        content = QWidget()
        self.form = QFormLayout(content)
        self.form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        area.setWidget(content)
        layout.addWidget(area, 1)
        self.mode_row = QWidget()
        mode_form = QFormLayout(self.mode_row)
        mode_form.setContentsMargins(0, 0, 0, 0)
        self.mode = QComboBox()
        self.mode.addItem('Độ sáng · giữ màu ảnh', 'luminance')
        self.mode.addItem('Xử lý riêng từng kênh RGB', 'rgb')
        self.mode.addItem('Chuyển sang ảnh xám', 'grayscale')
        mode_form.addRow('Xử lý màu', self.mode)
        self.mode_note = QLabel()
        self.mode_note.setWordWrap(True)
        mode_form.addRow(self.mode_note)
        self.mode.currentIndexChanged.connect(self.update_mode_note)
        layout.addWidget(self.mode_row)
        self.reference_row = QWidget()
        reference_layout = QHBoxLayout(self.reference_row)
        reference_layout.setContentsMargins(0, 0, 0, 0)
        choose_reference = QPushButton('Chọn ảnh tham chiếu…')
        choose_reference.clicked.connect(self.choose_reference)
        self.reference_label = QLabel('Chưa chọn ảnh')
        self.reference_label.setWordWrap(True)
        reference_layout.addWidget(choose_reference)
        reference_layout.addWidget(self.reference_label, 1)
        layout.addWidget(self.reference_row)
        self.frames_row = QWidget()
        frames_layout = QHBoxLayout(self.frames_row)
        frames_layout.setContentsMargins(0, 0, 0, 0)
        choose_frames = QPushButton('Chọn thêm ảnh cùng cảnh…')
        choose_frames.clicked.connect(self.choose_frames)
        self.frames_label = QLabel('Chưa chọn ảnh bổ sung')
        frames_layout.addWidget(choose_frames)
        frames_layout.addWidget(self.frames_label, 1)
        layout.addWidget(self.frames_row)
        self.error = QLabel()
        self.error.setWordWrap(True)
        self.error.setStyleSheet('color: #b42318;')
        layout.addWidget(self.error)
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Apply | QDialogButtonBox.StandardButton.Cancel)
        self.apply_button = self.buttons.button(QDialogButtonBox.StandardButton.Apply)
        self.apply_button.clicked.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)
        self.chapter.currentIndexChanged.connect(self.change_chapter)
        self.group.currentIndexChanged.connect(self.change_group)
        self.algorithm.currentIndexChanged.connect(self.change_algorithm)
        self.change_chapter()
        self.chapter.setCurrentIndex(self.chapter.findData(2))
        self.group.setCurrentText(self.registry()['gaussian'].group)
        self.algorithm.setCurrentIndex(self.algorithm.findData('gaussian'))

    def registry(self):
        return self.modules[self.chapter.currentData()].ALGORITHMS

    def change_chapter(self, unused=None):
        self.group.blockSignals(True)
        self.group.clear()
        self.group.addItems(list(dict.fromkeys(spec.group for spec in self.registry().values())))
        self.group.blockSignals(False)
        self.change_group()

    def change_group(self, unused=None):
        self.algorithm.blockSignals(True)
        self.algorithm.clear()
        for key, spec in self.registry().items():
            if spec.group == self.group.currentText():
                self.algorithm.addItem(spec.title, key)
        self.algorithm.blockSignals(False)
        self.change_algorithm()

    def change_algorithm(self, unused=None):
        self.error.clear()
        self.widgets.clear()
        while self.form.rowCount():
            self.form.removeRow(0)
        spec = self.registry()[self.algorithm.currentData()]
        self.description.setText(spec.description)
        for key, title, value, minimum, maximum in spec.fields:
            if isinstance(value, list):
                widget = QComboBox()
                for choice in value:
                    widget.addItem(CHOICE_LABELS.get(key, {}).get(choice, str(choice)), choice)
            elif self.chapter.currentData() == 1 and self.algorithm.currentData() == 'channel' and key == 'channel':
                widget = QComboBox()
                title = 'Kênh màu'
            else:
                widget = parameter_widget(value, minimum, maximum)
            if isinstance(value, int) and 'lẻ' in title.lower():
                widget.setSingleStep(2)
            self.widgets[key] = widget
            self.form.addRow(title, widget)
        if not spec.fields:
            self.form.addRow(QLabel('Chức năng này không cần nhập thêm tham số.'))
        if self.chapter.currentData() == 1 and self.algorithm.currentData() == 'channel':
            self.widgets['space'].currentIndexChanged.connect(self.update_channel_choices)
            self.update_channel_choices()
        if 'family' in self.widgets and 'order' in self.widgets:
            self.widgets['family'].currentIndexChanged.connect(self.update_parameter_dependencies)
        if 'psf' in self.widgets and 'sigma' in self.widgets:
            self.widgets['psf'].currentIndexChanged.connect(self.update_parameter_dependencies)
        if self.algorithm.currentData() == 'nearest':
            self.widgets['size'].valueChanged.connect(self.update_parameter_dependencies)
        self.update_parameter_dependencies()
        self.mode.setCurrentIndex(self.mode.findData('rgb' if self.algorithm.currentData() in RGB_DEFAULTS else 'luminance'))
        self.update_mode_note()
        self.mode_row.setVisible(self.chapter.currentData() == 2 and not spec.gray_only)
        self.reference_row.setVisible(spec.reference)
        self.frames_row.setVisible(spec.frames)
        self.apply_button.setText('Xem phổ Fourier' if spec.diagnostic else 'Áp dụng vào ảnh')

    def update_mode_note(self, unused=None):
        """Nêu rõ chế độ màu quyết định công thức áp dụng lên dữ liệu nào."""
        notes = {
            'luminance': 'Chỉ xử lý độ sáng, sau đó ghép lại màu gốc. Màu ảnh được giữ gần với ban đầu.',
            'rgb': 'Áp dụng cùng công thức riêng lên R, G, B. Màu ảnh có thể thay đổi; âm bản đảo cả ba kênh.',
            'grayscale': 'Chuyển ảnh sang thang xám trước khi xử lý. Kết quả không còn màu.',
        }
        self.mode_note.setText(notes[self.mode.currentData()])

    def update_channel_choices(self, unused=None):
        """Hiển thị tên kênh đúng thứ tự của không gian màu đã chọn."""
        widget = self.widgets['channel']
        previous = widget.currentData()
        widget.clear()
        for index, title in enumerate(CHANNEL_LABELS[self.widgets['space'].currentData()]):
            widget.addItem(title, index)
        widget.setCurrentIndex(previous if previous is not None else 0)

    def update_parameter_dependencies(self, unused=None):
        """Chỉ cho chỉnh tham số mà thuật toán đang chọn thực sự sử dụng."""
        if 'family' in self.widgets and 'order' in self.widgets:
            active = self.widgets['family'].currentData() == 'butterworth'
            self.widgets['order'].setEnabled(active)
            self.widgets['order'].setToolTip('Bậc n chỉ dùng cho hàm truyền Butterworth.')
        if 'psf' in self.widgets and 'sigma' in self.widgets:
            self.widgets['sigma'].setEnabled(self.widgets['psf'].currentData() == 'gaussian')
            self.widgets['sigma'].setToolTip('Sigma chỉ dùng cho mô hình mờ Gaussian.')
        if self.algorithm.currentData() == 'nearest':
            self.widgets['neighbors'].setMaximum(self.widgets['size'].value() ** 2)

    def parameter_values(self):
        """Giữ mã tham số gốc dù lựa chọn trên giao diện được dịch sang tiếng Việt."""
        return {key: widget.currentData() if isinstance(widget, QComboBox) else parameter_value(widget)
                for key, widget in self.widgets.items()}

    def choose_reference(self):
        path, _ = QFileDialog.getOpenFileName(self, 'Chọn ảnh tham chiếu / ảnh thứ hai', '', IMAGE_FILTER)
        if path:
            self.reference_path = path
            self.reference_label.setText(Path(path).name)
            self.reference_label.setToolTip(path)
            self.error.clear()

    def choose_frames(self):
        paths, _ = QFileDialog.getOpenFileNames(self, 'Chọn ảnh cùng kích thước và đã căn chỉnh', '', IMAGE_FILTER)
        if paths:
            self.frame_paths = paths
            self.frames_label.setText(f'{len(paths)} ảnh bổ sung + ảnh đang chỉnh')
            self.frames_label.setToolTip('\n'.join(paths))
            self.error.clear()

    def selection(self):
        spec = self.registry()[self.algorithm.currentData()]
        return {'chapter': self.chapter.currentData(), 'algorithm': self.algorithm.currentData(),
                'params': self.parameter_values(),
                'mode': 'grayscale' if spec.gray_only else self.mode.currentData(),
                'reference': self.reference_path if spec.reference else None,
                'frames': list(self.frame_paths) if spec.frames else []}

    def accept(self):
        spec = self.registry()[self.algorithm.currentData()]
        values = self.parameter_values()
        for key, title, value, minimum, maximum in spec.fields:
            if isinstance(value, int) and 'lẻ' in title.lower() and values[key] % 2 == 0:
                self.error.setText(f'{title} phải là số lẻ.')
                self.widgets[key].setFocus()
                return
        if spec.reference and not self.reference_path:
            self.error.setText('Hãy chọn ảnh tham chiếu trước khi áp dụng.')
            return
        if spec.frames and not self.frame_paths:
            self.error.setText('Hãy chọn ít nhất một ảnh bổ sung cùng cảnh, cùng kích thước.')
            return
        super().accept()


def choose_lesson(parent):
    """Hủy dialog không khởi chạy thuật toán hoặc thay đổi tài liệu."""
    dialog = LessonDialog(parent)
    try:
        return dialog.selection() if dialog.exec() == QDialog.DialogCode.Accepted else None
    finally:
        dialog.deleteLater()


class AnalysisPreview(QDialog):
    """Ảnh phân tích được xem riêng, không ghi vào lịch sử chỉnh sửa."""
    def __init__(self, parent, image, title):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setWindowTitle(title)
        self.resize(820, 640)
        layout = QVBoxLayout(self)
        note = QLabel('Phổ Fourier để quan sát tần số. Ảnh đang chỉnh và lịch sử được giữ nguyên. '
                      'Cuộn chuột để phóng to, kéo để di chuyển.')
        note.setWordWrap(True)
        layout.addWidget(note)
        self.canvas = Canvas()
        self.canvas.set_image(image)
        layout.addWidget(self.canvas, 1)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.close)
        layout.addWidget(buttons)
        QTimer.singleShot(0, self.canvas.fit_image)
