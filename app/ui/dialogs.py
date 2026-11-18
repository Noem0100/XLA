"""Hộp thoại tham số, thông báo và xác nhận dùng chung trong ứng dụng."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QFormLayout, QDialogButtonBox,
                               QSpinBox, QComboBox, QLineEdit, QLabel, QDoubleSpinBox,
                               QMessageBox, QTextEdit)


def show_message(parent, title, message, *, kind='information', hint='', details=''):
    """Hiển thị nội dung thuần văn bản; tách chi tiết lỗi khỏi hướng dẫn chính."""
    dialog = QMessageBox(parent)
    dialog.setWindowTitle(title)
    dialog.setTextFormat(Qt.TextFormat.PlainText)
    dialog.setIcon({'information': QMessageBox.Icon.Information,
                    'warning': QMessageBox.Icon.Warning,
                    'critical': QMessageBox.Icon.Critical}[kind])
    dialog.setText(str(message))
    if hint:
        dialog.setInformativeText(hint)
    dialog.setStandardButtons(QMessageBox.StandardButton.Ok)
    dialog.button(QMessageBox.StandardButton.Ok).setText('Đóng' if kind == 'information' else 'Đã hiểu')
    if details:
        dialog.setDetailedText(details)
        for button in dialog.buttons():
            if dialog.buttonRole(button) == QMessageBox.ButtonRole.ActionRole:
                button.setText('Xem chi tiết')
                button.clicked.connect(lambda checked=False, button=button: button.setText(
                    'Ẩn chi tiết' if dialog.findChild(QTextEdit).isVisible() else 'Xem chi tiết'))
    try:
        dialog.exec()
    finally:
        dialog.deleteLater()


def show_error(parent, message):
    """Diễn giải lỗi thường gặp, giữ thông tin kỹ thuật trong phần chi tiết."""
    raw = str(message).strip()
    error_type, separator, reason = raw.partition(':')
    explanations = {
        'FileNotFoundError': 'Không tìm thấy tệp hoặc thư mục. Hãy kiểm tra đường dẫn và chọn lại.',
        'PermissionError': 'Không có quyền truy cập tệp hoặc thư mục. Hãy kiểm tra quyền truy cập hoặc chọn vị trí khác.',
        'UnidentifiedImageError': 'Không đọc được ảnh này. Hãy chọn tệp ảnh JPG, PNG, WebP, BMP hoặc TIFF hợp lệ.',
        'BadZipFile': 'Không mở được dự án. Hãy chọn tệp .mdphoto hợp lệ; tệp hiện tại có thể đã bị hỏng.',
        'MemoryError': 'Không đủ bộ nhớ để xử lý ảnh. Hãy đóng bớt ảnh hoặc giảm kích thước ảnh rồi thử lại.',
        'OSError': 'Không thể đọc hoặc ghi tệp. Hãy kiểm tra tệp, quyền truy cập và dung lượng trống rồi thử lại.',
    }
    details = ''
    if error_type in explanations:
        message, details = explanations[error_type], raw
    elif separator and error_type == 'ValueError':
        message = reason.strip()
    elif separator and (error_type.endswith('Error') or error_type == 'error'):
        message = 'Thao tác chưa hoàn tất. Hãy kiểm tra ảnh và các thông số rồi thử lại.'
        details = raw
    else:
        message = raw
    show_message(parent, 'Chưa thể thực hiện thao tác', message or 'Thao tác chưa hoàn tất. Vui lòng thử lại.',
                 kind='warning', details=details)


def confirm_action(parent, title, message, confirm_text, *, hint=''):
    """Chỉ xác nhận khi bấm nút hành động; Enter, Escape và đóng cửa sổ đều hủy."""
    dialog = QMessageBox(parent)
    dialog.setWindowTitle(title)
    dialog.setIcon(QMessageBox.Icon.Warning)
    dialog.setTextFormat(Qt.TextFormat.PlainText)
    dialog.setText(message)
    if hint:
        dialog.setInformativeText(hint)
    confirm = dialog.addButton(confirm_text, QMessageBox.ButtonRole.DestructiveRole)
    cancel = dialog.addButton('Tiếp tục chỉnh sửa', QMessageBox.ButtonRole.RejectRole)
    dialog.setDefaultButton(cancel)
    dialog.setEscapeButton(cancel)
    try:
        dialog.exec()
        return dialog.clickedButton() is confirm
    finally:
        dialog.deleteLater()


def parameter_widget(value, minimum, maximum, *, decimals=4, step=None, suffix=''):
    """Tạo ô nhập, cho phép đặt đơn vị và bước chỉnh riêng cho tham số số."""
    if isinstance(value, list):
        widget = QComboBox()
        widget.addItems(value)
    elif isinstance(value, int):
        widget = QSpinBox()
        widget.setRange(minimum, maximum)
        widget.setValue(value)
    elif isinstance(value, float):
        widget = QDoubleSpinBox()
        widget.setDecimals(decimals)
        widget.setRange(minimum, maximum)
        widget.setSingleStep(minimum if 0 < minimum < .01 else .01)
        widget.setValue(value)
    else:
        widget = QLineEdit(str(value))
    if isinstance(widget, (QSpinBox, QDoubleSpinBox)):
        widget.setSuffix(suffix)
        if step is not None:
            widget.setSingleStep(step)
    return widget


def parameter_value(widget):
    """Đọc giá trị của widget dùng chung giữa dialog nhỏ và công cụ bài học."""
    if isinstance(widget, QComboBox):
        return widget.currentText()
    if isinstance(widget, (QSpinBox, QDoubleSpinBox)):
        return widget.value()
    return widget.text()


def parameters(parent, title, fields, note='', *, field_options=None, accept_text='Áp dụng'):
    """Dựng form; field_options đặt đơn vị, độ chính xác, bước chỉnh theo key."""
    dialog = QDialog(parent)
    dialog.setWindowTitle(title)
    dialog.setMinimumWidth(430)
    layout = QVBoxLayout(dialog)
    if note:
        label = QLabel(note)
        label.setTextFormat(Qt.TextFormat.PlainText)
        label.setWordWrap(True)
        layout.addWidget(label)
    form = QFormLayout()
    widgets = {}
    for key, label, value, minimum, maximum in fields:
        widget = parameter_widget(value, minimum, maximum, **(field_options or {}).get(key, {}))
        widgets[key] = widget
        form.addRow(label, widget)
    layout.addLayout(form)
    buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
    buttons.button(QDialogButtonBox.StandardButton.Ok).setText(accept_text)
    buttons.button(QDialogButtonBox.StandardButton.Cancel).setText('Hủy')
    buttons.accepted.connect(dialog.accept)
    buttons.rejected.connect(dialog.reject)
    layout.addWidget(buttons)
    if dialog.exec() != QDialog.DialogCode.Accepted:
        return None
    return {key: parameter_value(widget) for key, widget in widgets.items()}
