"""Histogram cột RGB và độ sáng, so sánh trước/sau bằng QPainter."""
import numpy as np
from PySide6.QtCore import Qt, QPointF, QRectF, Signal
from PySide6.QtGui import QPainter, QColor, QPolygonF, QPen
from PySide6.QtWidgets import (QWidget, QLabel, QCheckBox, QVBoxLayout,
                               QHBoxLayout, QGridLayout, QToolTip, QComboBox)


def histogram_data(image):
    """Đếm 256 mức RGBA; Y' là độ sáng xấp xỉ trên mã sRGB, bỏ alpha=0."""
    rgb = image[..., :3][image[..., 3] > 0]
    counts = np.zeros((4, 256), dtype=np.int64)
    if rgb.size:
        for channel in range(3):
            counts[channel] = np.bincount(rgb[:, channel], minlength=256)
        brightness = np.rint(rgb @ np.array([.2126, .7152, .0722])).astype(np.uint8)
        counts[3] = np.bincount(brightness, minlength=256)
    return counts, len(rgb)


class _ChannelChart(QWidget):
    """Vẽ một kênh bằng cột màu và đường tham chiếu xám cùng thang phần trăm."""
    def __init__(self, owner, channel, title, color):
        """Ghi nhận kênh cần vẽ và bật theo dõi chuột để đọc từng mức."""
        super().__init__(owner)
        self.owner = owner
        self.channel = channel
        self.title = title
        self.color = QColor(color)
        self.setMinimumHeight(98)
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAccessibleName(f'Histogram {title}')

    def mousePressEvent(self, event):
        """Yêu cầu chọn kênh khi bấm chuột trái trên histogram có dữ liệu."""
        if event.button() == Qt.MouseButton.LeftButton and self.owner.values is not None:
            self.setFocus(Qt.FocusReason.MouseFocusReason)
            self.owner.channel_selected.emit(self.channel)
            event.accept()
            return
        super().mousePressEvent(event)

    def keyPressEvent(self, event):
        """Cho phép kích hoạt kênh bằng Enter hoặc Space khi biểu đồ có focus."""
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            if self.owner.values is not None and not event.isAutoRepeat():
                self.owner.channel_selected.emit(self.channel)
            event.accept()
            return
        super().keyPressEvent(event)

    def focusInEvent(self, event):
        """Hiện viền focus để nhận biết biểu đồ đang được chọn bằng bàn phím."""
        super().focusInEvent(event)
        self.update()

    def focusOutEvent(self, event):
        """Vẽ lại viền khi focus chuyển sang thành phần khác."""
        super().focusOutEvent(event)
        self.update()

    def plot_rect(self):
        """Chừa lề cho nhãn trục và thống kê bên dưới biểu đồ."""
        return QRectF(29, 24, max(1, self.width() - 34), max(1, self.height() - 61))

    def paintEvent(self, event):
        """Vẽ 256 cột, trục mức màu và thống kê trung bình/độ lệch chuẩn."""
        painter = QPainter(self)
        selected = self.owner.selected_channel == self.channel
        painter.fillRect(self.rect(), QColor('#e2f3ec' if selected else '#f8fafc'))
        if selected or self.hasFocus():
            painter.setPen(QPen(QColor('#147d68' if selected else '#3685c3'),
                                2 if selected else 1,
                                Qt.PenStyle.SolidLine if selected else Qt.PenStyle.DashLine))
            painter.drawRect(QRectF(1, 1, self.width() - 2, self.height() - 2))
        font = painter.font()
        font.setPointSizeF(8)
        painter.setFont(font)
        painter.setPen(QColor('#233044'))
        painter.drawText(QRectF(5, 2, self.width() - 10, 18), self.title)
        plot = self.plot_rect()
        current = self.owner.values
        if current is None:
            painter.setPen(QColor('#627083'))
            painter.drawText(plot, Qt.AlignmentFlag.AlignCenter, 'Chưa có ảnh')
            return
        count = self.owner.pixel_count
        percentages = current[self.channel] * (100 / count) if count else np.zeros(256)
        reference = self.owner.reference_values
        reference_count = self.owner.reference_pixel_count
        before = reference[self.channel] * (100 / reference_count) if reference_count else np.zeros(256)
        maximum = max(float(percentages.max()), float(before.max()), .01)
        logarithmic = self.owner.log_scale.isChecked()
        transform = np.log1p if logarithmic else lambda value: value
        ceiling = transform(maximum)
        heights = transform(percentages) / ceiling * plot.height()
        painter.setPen(QPen(QColor('#d7e0ea'), 1))
        painter.drawRect(plot)
        painter.drawLine(QPointF(plot.left(), plot.center().y()), QPointF(plot.right(), plot.center().y()))
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        width = plot.width() / 256
        for level, height in enumerate(heights):
            if height > 0:
                painter.fillRect(QRectF(plot.left() + level * width,
                                        plot.bottom() - height, width, height), self.color)
        if reference is not None and reference_count:
            before_heights = transform(before) / ceiling * plot.height()
            points = QPolygonF([QPointF(plot.left() + (level + .5) * width,
                                       plot.bottom() - height) for level, height in enumerate(before_heights)])
            painter.setPen(QPen(QColor('#7a8798'), 1, Qt.PenStyle.DashLine))
            painter.drawPolyline(points)
        painter.setPen(QColor('#52647a'))
        top_label = f'{maximum:.0f}%' if maximum >= 10 else f'{maximum:.2g}%'
        painter.drawText(QRectF(0, plot.top() - 5, 27, 15), Qt.AlignmentFlag.AlignRight, top_label)
        painter.drawText(QRectF(0, plot.bottom() - 9, 27, 15), Qt.AlignmentFlag.AlignRight, '0%')
        for level in (0, 128, 255):
            x = plot.left() + level / 255 * plot.width()
            left = min(max(plot.left(), x - 11), plot.right() - 22)
            painter.drawText(QRectF(left, plot.bottom() + 2, 22, 14),
                             Qt.AlignmentFlag.AlignCenter, str(level))
        if count:
            levels = np.arange(256)
            mean = float(current[self.channel] @ levels / count)
            deviation = np.sqrt(float(current[self.channel] @ (levels - mean) ** 2 / count))
            statistics = f'TB {mean:.1f}  ·  σ {deviation:.1f}'
        else:
            statistics = 'Không có pixel'
        painter.drawText(QRectF(3, self.height() - 17, self.width() - 6, 16),
                         Qt.AlignmentFlag.AlignCenter, statistics)

    def mouseMoveEvent(self, event):
        """Đọc số pixel và phần trăm tại mức màu đang được trỏ chuột."""
        plot = self.plot_rect()
        if self.owner.values is None or not plot.contains(event.position()):
            QToolTip.hideText()
            return
        level = min(255, max(0, int((event.position().x() - plot.left()) / plot.width() * 256)))
        current = int(self.owner.values[self.channel, level])
        count = self.owner.pixel_count
        percentage = 100 * current / count if count else 0
        text = f'{self.title} · Mức {level}\nSau: {current:,} pixel ({percentage:.3f}%)'
        if self.owner.reference_values is not None:
            before = int(self.owner.reference_values[self.channel, level])
            before_count = self.owner.reference_pixel_count
            percentage = 100 * before / before_count if before_count else 0
            text += f'\nTrước: {before:,} pixel ({percentage:.3f}%)'
        text += '\n' + self.owner.filter_description(self.channel)
        text += '\nBấm hoặc nhấn Enter, Space để bật/tắt xem trước.'
        QToolTip.showText(event.globalPosition().toPoint(), text, self)

    def leaveEvent(self, event):
        """Ẩn thông số khi chuột rời biểu đồ."""
        QToolTip.hideText()
        super().leaveEvent(event)


class Histogram(QWidget):
    """Bốn histogram 256 mức với tham chiếu trước/sau và thang tuyến tính/log."""
    channel_selected = Signal(int)
    filter_mode_changed = Signal(str)

    def __init__(self, parent=None):
        """Tạo lưới bốn kênh gọn cho panel thuộc tính hoặc cửa sổ công cụ."""
        super().__init__(parent)
        self.values = None
        self.pixel_count = 0
        self.reference_values = None
        self.reference_pixel_count = 0
        self.selected_channel = None
        self.filter_mode = 'channel'
        self.setFixedHeight(340)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        header = QHBoxLayout()
        self.context = QLabel('Ảnh hiện tại')
        self.context.setWordWrap(True)
        self.context.setMaximumHeight(32)
        header.addWidget(self.context, 1)
        self.log_scale = QCheckBox('Thang log')
        self.log_scale.setToolTip('Chiều cao = log(1 + tần suất %). Bỏ chọn để dùng thang tuyến tính.')
        self.log_scale.toggled.connect(self._update_charts)
        header.addWidget(self.log_scale)
        layout.addLayout(header)
        mode_row = QHBoxLayout()
        mode_label = QLabel('Khi bấm biểu đồ:')
        mode_row.addWidget(mode_label)
        self.filter_mode_selector = QComboBox()
        self.filter_mode_selector.addItem('Tách kênh RGB', 'channel')
        self.filter_mode_selector.addItem('Giữ gam màu', 'gamut')
        self.filter_mode_selector.setAccessibleName('Cách xem màu từ histogram')
        self.filter_mode_selector.setToolTip(
            'Tách kênh RGB: giữ cường độ của kênh được chọn, đưa hai kênh còn lại về 0.\n'
            'Giữ gam màu: giữ màu của vùng cùng gam, chuyển vùng màu khác sang xám.\n'
            'Biểu đồ độ sáng luôn hiển thị ảnh xám Y\'.')
        self.filter_mode_selector.currentIndexChanged.connect(self._filter_mode_selected)
        mode_label.setBuddy(self.filter_mode_selector)
        mode_row.addWidget(self.filter_mode_selector, 1)
        layout.addLayout(mode_row)
        grid = QGridLayout()
        grid.setSpacing(5)
        self.charts = []
        for index, (title, color) in enumerate([('Đỏ · R', '#c7384c'), ('Xanh lá · G', '#16804a'),
                                                ('Xanh dương · B', '#2864cf'), ("Độ sáng · Y'", '#596678')]):
            chart = _ChannelChart(self, index, title, color)
            self.charts.append(chart)
            grid.addWidget(chart, index // 2, index % 2)
        layout.addLayout(grid, 1)
        self.legend = QLabel('Cột màu: sau · Nét xám: trước · Trục X: 0–255')
        self.legend.setStyleSheet('font-size: 10px;')
        self.legend.setWordWrap(True)
        layout.addWidget(self.legend)
        self.sample_label = QLabel('Mở ảnh để xem phân bố màu và độ sáng.')
        self.sample_label.setStyleSheet('font-size: 10px;')
        self.sample_label.setWordWrap(True)
        layout.addWidget(self.sample_label)
        self.filter_help = QLabel()
        self.filter_help.setStyleSheet('font-size: 10px;')
        self.filter_help.setWordWrap(True)
        layout.addWidget(self.filter_help)
        self._update_filter_help()
        self.setToolTip("Y' ≈ 0,2126R + 0,7152G + 0,0722B trên mã sRGB 8 bit; không phải độ chói tuyến tính.\n"
                        'TB: trung bình; σ: độ lệch chuẩn. Bỏ pixel alpha=0; các pixel còn lại có trọng số bằng nhau.\n'
                        'Tần suất (%) giúp so sánh các ảnh có kích thước khác nhau. Trỏ chuột vào cột để đọc số pixel.')

    def _update_charts(self, unused=None):
        """Yêu cầu vẽ lại bốn kênh khi dữ liệu hoặc thang đo thay đổi."""
        for chart in self.charts:
            chart.update()

    def set_context(self, text):
        """Hiển thị tên chức năng hoặc trạng thái đang được phân tích."""
        self.context.setText(text)
        self.context.setToolTip(text)

    def set_selected_channel(self, channel):
        """Đánh dấu kênh đang xem; cập nhật từ controller mà không phát signal."""
        if channel not in (None, 0, 1, 2, 3):
            raise ValueError('Kênh histogram phải là None hoặc số từ 0 đến 3.')
        self.selected_channel = channel
        self._update_filter_help()
        self._update_charts()

    def filter_description(self, channel):
        """Giải thích đúng phép biến đổi tương ứng với cách xem đang chọn."""
        if channel == 3:
            return "Độ sáng Y': chuyển ảnh sang xám theo độ sáng của từng pixel."
        name = ('đỏ R', 'xanh lá G', 'xanh dương B')[channel]
        if self.filter_mode == 'channel':
            return f'Tách kênh {name}: giữ cường độ kênh này, đưa hai kênh còn lại về 0.'
        return (f'Giữ gam {name}: giữ vùng cùng gam, chuyển các gam khác sang xám. '
                'Ảnh ít màu này sẽ gần như xám.')

    def _update_filter_help(self):
        """Cập nhật giải thích hiển thị và trợ năng khi đổi chế độ hoặc chọn kênh."""
        if self.selected_channel is not None:
            explanation = self.filter_description(self.selected_channel)
        elif self.filter_mode == 'channel':
            explanation = 'Bấm R, G hoặc B để tách kênh màu; Y\' để xem độ sáng. Bấm lại để tắt.'
        else:
            explanation = 'Bấm để giữ một gam màu. Các gam khác thành xám; ảnh ít gam chọn sẽ gần như xám.'
        self.filter_help.setText(explanation)
        for chart in self.charts:
            state = 'Đang bật.' if chart.channel == self.selected_channel else 'Đang tắt.'
            text = self.filter_description(chart.channel) + '\nBấm hoặc nhấn Enter, Space để bật/tắt xem trước.'
            chart.setToolTip(text)
            chart.setAccessibleDescription(f'{state} {text}')

    def set_filter_mode(self, mode):
        """Đồng bộ cách xem màu từ controller mà không phát lại signal."""
        if mode not in ('channel', 'gamut'):
            raise ValueError('Chế độ histogram phải là channel hoặc gamut.')
        self.filter_mode = mode
        previous = self.filter_mode_selector.blockSignals(True)
        self.filter_mode_selector.setCurrentIndex(self.filter_mode_selector.findData(mode))
        self.filter_mode_selector.blockSignals(previous)
        self._update_filter_help()

    def _filter_mode_selected(self, index):
        """Phát yêu cầu đổi cách xem khi người dùng chọn trong danh sách."""
        self.set_filter_mode(self.filter_mode_selector.itemData(index))
        self.filter_mode_changed.emit(self.filter_mode)

    def copy_from(self, other):
        """Sao chép số liệu đang xem sang cửa sổ lớn mà không tính lại ảnh."""
        self.values = None if other.values is None else other.values.copy()
        self.pixel_count = other.pixel_count
        self.reference_values = None if other.reference_values is None else other.reference_values.copy()
        self.reference_pixel_count = other.reference_pixel_count
        self.set_filter_mode(other.filter_mode)
        self.set_selected_channel(other.selected_channel)
        self.set_context(other.context.text())
        self.sample_label.setText(other.sample_label.text())
        self.log_scale.setChecked(other.log_scale.isChecked())
        self._update_charts()

    def set_reference(self, image):
        """Ghi nhận ảnh trước thao tác, hoặc bỏ đường tham chiếu nếu truyền None."""
        if image is None:
            self.reference_values = None
            self.reference_pixel_count = 0
        else:
            self.reference_values, self.reference_pixel_count = histogram_data(image)
        self._update_charts()

    def set_image(self, image):
        """Cập nhật histogram và số pixel mẫu; giữ tên chức năng và ảnh tham chiếu."""
        self.values, self.pixel_count = histogram_data(image)
        self.sample_label.setText(f'{self.pixel_count:,} pixel mẫu · Y: tần suất (%)')
        self._update_charts()
