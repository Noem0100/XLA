"""Dialog tham số dùng chung; widget chỉ thu thập dữ liệu, không xử lý ảnh."""
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QFormLayout, QDialogButtonBox,
                               QSpinBox, QComboBox, QLineEdit, QLabel, QDoubleSpinBox)


def parameter_widget(value, minimum, maximum):
    """Tạo ô nhập, giữ đủ độ chính xác cho tham số tần số và khôi phục ảnh."""
    if isinstance(value, list):
        widget = QComboBox()
        widget.addItems(value)
    elif isinstance(value, int):
        widget = QSpinBox()
        widget.setRange(minimum, maximum)
        widget.setValue(value)
    elif isinstance(value, float):
        widget = QDoubleSpinBox()
        widget.setDecimals(4)
        widget.setRange(minimum, maximum)
        widget.setSingleStep(minimum if 0 < minimum < .01 else .01)
        widget.setValue(value)
    else:
        widget = QLineEdit(str(value))
    return widget


def parameter_value(widget):
    """Đọc giá trị của widget dùng chung giữa dialog nhỏ và công cụ bài học."""
    if isinstance(widget, QComboBox):
        return widget.currentText()
    if isinstance(widget, (QSpinBox, QDoubleSpinBox)):
        return widget.value()
    return widget.text()


def parameters(parent, title, fields, note=''):
    """Dựng form từ (key, nhãn, mặc định, min, max) hoặc danh sách lựa chọn."""
    dialog = QDialog(parent)
    dialog.setWindowTitle(title)
    dialog.setMinimumWidth(430)
    layout = QVBoxLayout(dialog)
    if note:
        label = QLabel(note)
        label.setWordWrap(True)
        layout.addWidget(label)
    form = QFormLayout()
    widgets = {}
    for key, label, value, minimum, maximum in fields:
        widget = parameter_widget(value, minimum, maximum)
        widgets[key] = widget
        form.addRow(label, widget)
    layout.addLayout(form)
    buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
    buttons.accepted.connect(dialog.accept)
    buttons.rejected.connect(dialog.reject)
    layout.addWidget(buttons)
    if dialog.exec() != QDialog.DialogCode.Accepted:
        return None
    return {key: parameter_value(widget) for key, widget in widgets.items()}
