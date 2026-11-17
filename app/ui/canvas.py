"""Canvas Qt: zoom/pan, crop và tô mask theo tọa độ pixel ảnh."""
import cv2
import numpy as np
from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import QImage, QPixmap, QPen, QColor, QPainter, QBrush
from PySide6.QtWidgets import QGraphicsView, QGraphicsScene, QGraphicsPixmapItem, QGraphicsRectItem, QGraphicsPathItem
from PySide6.QtGui import QPainterPath


def pixmap(array):
    """Sao chép RGBA NumPy vào QImage để không giữ con trỏ bộ nhớ tạm."""
    array = np.ascontiguousarray(array)
    h, w = array.shape[:2]
    return QPixmap.fromImage(QImage(array.data, w, h, array.strides[0], QImage.Format.Format_RGBA8888).copy())


class Canvas(QGraphicsView):
    """Scene dùng đơn vị pixel ảnh; ánh xạ chuột bằng mapToScene."""
    def __init__(self):
        """Khởi tạo item ảnh, mask, crop và nét cọ tạm thời."""
        super().__init__()
        self.scene_ = QGraphicsScene(self)
        self.setScene(self.scene_)
        self.photo = QGraphicsPixmapItem()
        self.scene_.addItem(self.photo)
        self.filter_layer = QGraphicsPixmapItem()
        self.filter_layer.setZValue(.5)
        self.filter_layer.hide()
        self.scene_.addItem(self.filter_layer)
        self.overlay = QGraphicsPixmapItem()
        self.overlay.setZValue(1)
        self.scene_.addItem(self.overlay)
        self.rectangle = QGraphicsRectItem()
        self.rectangle.setPen(QPen(QColor('#147d68'), 2, Qt.PenStyle.DashLine))
        self.rectangle.setZValue(3)
        self.scene_.addItem(self.rectangle)
        self.stroke_item = QGraphicsPathItem()
        self.stroke_item.setZValue(2)
        self.scene_.addItem(self.stroke_item)
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        self.setBackgroundBrush(QColor('#e8edf3'))
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setMinimumSize(320, 300)
        self.setFrameShape(QGraphicsView.Shape.NoFrame)
        self.mode = 'pan'
        self.brush_size = 40
        self.eraser = False
        self.mask = None
        self.shape = None
        self.start = None
        self.last = None
        self.set_mode('pan')

    def set_image(self, array, logical_size=None):
        """Hiển thị preview hoặc ảnh thật, giữ hệ tọa độ ảnh gốc."""
        size = logical_size or (array.shape[1], array.shape[0])
        new_shape = (size[1], size[0])
        changed = new_shape != self.shape
        self.set_color_filter(None)
        self.photo.setPixmap(pixmap(array))
        self.photo.setScale(size[0] / array.shape[1])
        self.scene_.setSceneRect(QRectF(0, 0, *size))
        if changed:
            self.shape = new_shape
            self.clear_selection()
            self.fit_image()

    def set_color_filter(self, array):
        """Hiển thị lớp lọc thay ảnh nền, giữ alpha, mask và tọa độ ảnh."""
        if array is None:
            self.filter_layer.hide()
            self.filter_layer.setPixmap(QPixmap())
            self.photo.show()
            return
        self.filter_layer.setPixmap(pixmap(array))
        self.filter_layer.setScale(self.shape[1] / array.shape[1])
        self.photo.hide()
        self.filter_layer.show()

    def clear_selection(self):
        """Xóa cả mask và crop khi hoàn tất hoặc hủy thao tác."""
        if self.shape:
            self.mask = np.zeros(self.shape, np.uint8)
        self.overlay.setPixmap(QPixmap())
        self.rectangle.setRect(QRectF())
        self.stroke_item.setPath(QPainterPath())

    def fit_image(self):
        """Fit toàn ảnh vào viewport và giữ tỉ lệ."""
        self.fitInView(self.scene_.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def set_mode(self, mode):
        """Chọn pan, crop hoặc brush và đặt cursor tương ứng."""
        self.mode = mode
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag if mode == 'pan' else QGraphicsView.DragMode.NoDrag)
        self.setCursor(Qt.CursorShape.CrossCursor if mode != 'pan' else Qt.CursorShape.OpenHandCursor)

    def crop_box(self):
        """Lấy hộp crop trong tọa độ pixel, không dùng tọa độ màn hình."""
        r = self.rectangle.rect()
        return (round(r.left()), round(r.top()), round(r.right()), round(r.bottom()))

    def point(self, event):
        """Ánh xạ và clamp con trỏ vào biên hình học của ảnh."""
        p = self.mapToScene(event.position().toPoint())
        h, w = self.shape
        return QPointF(max(0, min(w, p.x())), max(0, min(h, p.y())))

    def wheelEvent(self, event):
        """Zoom bằng con lăn với giới hạn hệ số để tránh mất ảnh."""
        factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
        scale = self.transform().m11() * factor
        if .01 <= scale <= 32:
            self.scale(factor, factor)

    def mousePressEvent(self, event):
        """Bắt đầu vùng crop hoặc một nét cọ; pan giao cho Qt."""
        if self.shape and event.button() == Qt.MouseButton.LeftButton and self.mode != 'pan':
            self.start = self.point(event)
            self.last = self.start
            if self.mode == 'crop':
                self.rectangle.setRect(QRectF(self.start, self.start))
            else:
                self.path = QPainterPath(self.start)
                self.stroke_item.setPen(QPen(QColor(255, 100, 100, 100), self.brush_size, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
                self.paint_segment(self.start)
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        """Cập nhật hình chọn hoặc nội suy nét mask giữa hai vị trí chuột."""
        if self.start is not None and self.shape:
            p = self.point(event)
            if self.mode == 'crop':
                self.rectangle.setRect(QRectF(self.start, p).normalized())
            elif self.mode == 'brush':
                self.paint_segment(p)
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def paint_segment(self, point):
        """cv2.line nối hai mẫu chuột để cọ không bị đứt khi di chuyển nhanh."""
        cv2.line(self.mask, (round(self.last.x()), round(self.last.y())),
                 (round(point.x()), round(point.y())), 0 if self.eraser else 255,
                 self.brush_size, cv2.LINE_AA)
        self.path.lineTo(point)
        self.stroke_item.setPath(self.path)
        self.last = point

    def mouseReleaseEvent(self, event):
        """Kết thúc cọ, dựng lớp phủ đỏ giảm kích thước cho preview."""
        if self.start is not None:
            if self.mode == 'brush':
                self.paint_segment(self.point(event))
                self.show_mask()
            self.start = None
            self.last = None
            event.accept()
        else:
            super().mouseReleaseEvent(event)

    def show_mask(self):
        """Hiển thị mask màu đỏ alpha 35%, độc lập với ảnh xuất."""
        h, w = self.mask.shape
        scale = min(1, 1200 / max(h, w))
        reduced = cv2.resize(self.mask, (max(1, round(w * scale)), max(1, round(h * scale))))
        rgba = np.zeros((*reduced.shape, 4), np.uint8)
        rgba[..., 0] = 255
        rgba[..., 1] = 80
        rgba[..., 3] = reduced * .35
        self.overlay.setPixmap(pixmap(rgba))
        self.overlay.setScale(w / reduced.shape[1])
        self.stroke_item.setPath(QPainterPath())

    def drawBackground(self, painter, rect):
        """Nền tối và caro trong phạm vi ảnh để nhận biết trong suốt."""
        super().drawBackground(painter, rect)
        if self.shape:
            tile = QPixmap(32, 32)
            tile.fill(QColor('#ffffff'))
            p = QPainter(tile)
            p.fillRect(0, 0, 16, 16, QColor('#dce3eb'))
            p.fillRect(16, 16, 16, 16, QColor('#dce3eb'))
            p.end()
            painter.fillRect(self.scene_.sceneRect(), QBrush(tile))
