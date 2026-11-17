"""Mô phỏng kiểm thử toàn diện 100% nút bấm & chức năng trên giao diện Minh Đăng Photo."""
import os
import sys
import time
import random
import tempfile
from pathlib import Path
import numpy as np
from PySide6.QtCore import QTimer, QRectF
from PySide6.QtWidgets import (
    QApplication, QPushButton, QDialog, QMessageBox, QFileDialog, QComboBox
)

from app.core import adjustments, filters, geometry, retouch
from app.core.io import load_image, export_image
from app.ui.window import MainWindow, ADJUSTERS, IMAGE_FILTER


def load_app_stylesheet(app: QApplication):
    """Nạp stylesheet giống main.py nếu có."""
    for candidate in Path("app").rglob("*.qss"):
        try:
            app.setStyleSheet(candidate.read_text(encoding="utf-8"))
            return
        except Exception:
            pass
    try:
        for mod_path in Path("app/ui").glob("*.py"):
            text = mod_path.read_text(encoding="utf-8")
            if "QMainWindow" in text and "{" in text and "background" in text:
                ns = {}
                exec(compile(text, str(mod_path), "exec"), ns)
                for val in ns.values():
                    if isinstance(val, str) and "QMainWindow" in val:
                        app.setStyleSheet(val)
                        return
    except Exception:
        pass


def load_from_paths(paths, limit=4):
    """Nạp danh sách file ảnh hoặc lấy ngẫu nhiên ảnh từ các thư mục được chỉ định."""
    exts = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}
    candidates = []
    seen = set()

    for raw in paths:
        p = Path(raw).expanduser().resolve()
        if not p.exists():
            continue
        if p.is_file() and p.suffix.lower() in exts and p not in seen:
            seen.add(p)
            candidates.append(p)
        elif p.is_dir():
            for child in p.rglob("*"):
                if (
                    child.is_file()
                    and child.suffix.lower() in exts
                    and ".venv" not in child.parts
                    and "__pycache__" not in child.parts
                    and child.resolve() not in seen
                ):
                    seen.add(child.resolve())
                    candidates.append(child.resolve())
                    if len(candidates) >= 80:
                        break

    if len(candidates) > limit:
        candidates = random.sample(candidates, limit)

    loaded = []
    for p in candidates:
        try:
            img = load_image(str(p))
            h, w = img.shape[:2]
            if min(h, w) >= 150:
                loaded.append((p.name, img, str(p)))
                print(f"[DỮ LIỆU THẬT] Đã nạp: {p} ({w}x{h} px)")
        except Exception as exc:
            print(f"[BỎ QUA] Không đọc được {p.name}: {exc}")
    return loaded


def choose_test_images(cli_args):
    """Cho phép chọn ảnh qua tham số dòng lệnh, hộp thoại chọn file, hoặc lấy ngẫu nhiên."""
    if cli_args:
        imgs = load_from_paths(cli_args, limit=4)
        if imgs:
            return imgs

    default_dir = str(Path("../..").resolve()) if Path("../..").exists() else str(Path.home() / "Downloads")
    picked_paths, _ = QFileDialog.getOpenFileNames(
        None,
        "Chọn 1–4 ảnh bất kỳ để chạy test (Bấm Cancel để tự lấy ngẫu nhiên)",
        default_dir,
        IMAGE_FILTER,
    )
    if picked_paths:
        imgs = load_from_paths(picked_paths, limit=4)
        if imgs:
            return imgs

    print("[CHẾ ĐỘ NGẪU NHIÊN] Đang bốc ngẫu nhiên ảnh khác nhau từ thư mục trên máy...")
    default_roots = [
        Path("../..").resolve(),
        Path.home() / "Downloads",
        Path.home() / "Pictures",
        Path(".").resolve(),
    ]
    return load_from_paths(default_roots, limit=3)


class FullFeatureSimulator:
    """Tự động bấm từng nút & điều khiển từng widget trên giao diện thật."""

    def __init__(self, win: MainWindow, images):
        self.win = win
        self.images = images
        self.work_dir = Path(tempfile.mkdtemp(prefix="MinhDangPhoto_FullTest_"))
        self.font_path = self._find_system_font()
        self.report = []
        self.queue = []
        self.wait_ticks = 0

        self.open_files_queue = []
        self.open_file_queue = []
        self.save_file_queue = []
        self.dir_queue = []
        self._patch_file_dialogs()

        self.dialog_combo_override = None
        self.modal_seen_at = {}
        self.modal_timer = QTimer(win)
        self.modal_timer.setInterval(120)
        self.modal_timer.timeout.connect(self._handle_popups)
        self.modal_timer.start()

        self.step_timer = QTimer(win)
        self.step_timer.setInterval(100)
        self.step_timer.timeout.connect(self._tick)

        self._build_plan()

    @staticmethod
    def _find_system_font():
        for font_dir in [Path("/usr/share/fonts"), Path.home() / ".local/share/fonts"]:
            if font_dir.exists():
                for ext in ("*.ttf", "*.otf"):
                    fonts = list(font_dir.rglob(ext))
                    if fonts:
                        for preferred in ("DejaVuSans", "NotoSans", "LiberationSans", "Ubuntu"):
                            for f in fonts:
                                if preferred.lower() in f.name.lower():
                                    return str(f)
                        return str(fonts[0])
        return ""

    def _patch_file_dialogs(self):
        orig_open_names = QFileDialog.getOpenFileNames
        orig_open_name = QFileDialog.getOpenFileName
        orig_save_name = QFileDialog.getSaveFileName
        orig_get_dir = QFileDialog.getExistingDirectory

        def fake_open_names(*args, **kwargs):
            if self.open_files_queue:
                return self.open_files_queue.pop(0), ""
            return orig_open_names(*args, **kwargs)

        def fake_open_name(*args, **kwargs):
            if self.open_file_queue:
                return self.open_file_queue.pop(0), ""
            return orig_open_name(*args, **kwargs)

        def fake_save_name(*args, **kwargs):
            if self.save_file_queue:
                return self.save_file_queue.pop(0), "PNG (*.png)"
            return orig_save_name(*args, **kwargs)

        def fake_get_dir(*args, **kwargs):
            if self.dir_queue:
                return self.dir_queue.pop(0)
            return orig_get_dir(*args, **kwargs)

        QFileDialog.getOpenFileNames = staticmethod(fake_open_names)
        QFileDialog.getOpenFileName = staticmethod(fake_open_name)
        QFileDialog.getSaveFileName = staticmethod(fake_save_name)
        QFileDialog.getExistingDirectory = staticmethod(fake_get_dir)

    def _handle_popups(self):
        now = time.monotonic()
        modal = QApplication.activeModalWidget()
        if modal is not None:
            mid = id(modal)
            if mid not in self.modal_seen_at:
                self.modal_seen_at[mid] = now
                if self.dialog_combo_override is not None:
                    combos = modal.findChildren(QComboBox)
                    if combos:
                        idx = self.dialog_combo_override
                        if isinstance(idx, str):
                            pos = combos[0].findText(idx)
                            if pos >= 0:
                                combos[0].setCurrentIndex(pos)
                        elif 0 <= idx < combos[0].count():
                            combos[0].setCurrentIndex(idx)
                    self.dialog_combo_override = None
                return
            if now - self.modal_seen_at[mid] >= 0.45:
                self.modal_seen_at.pop(mid, None)
                if isinstance(modal, QMessageBox):
                    yes_btn = modal.button(QMessageBox.StandardButton.Yes)
                    if yes_btn is not None:
                        yes_btn.click()
                    else:
                        modal.accept()
                elif isinstance(modal, QDialog):
                    modal.accept()
                else:
                    modal.close()

        for child in self.win.findChildren(QDialog):
            if child.isVisible() and not child.isModal():
                cid = id(child)
                if cid not in self.modal_seen_at:
                    self.modal_seen_at[cid] = now
                elif now - self.modal_seen_at[cid] >= 0.65:
                    self.modal_seen_at.pop(cid, None)
                    child.close()

    def click_btn(self, label_part):
        for btn in self.win.findChildren(QPushButton):
            txt = btn.text().strip()
            if txt == label_part or label_part in txt:
                btn.setFocus()
                btn.click()
                return True
        raise RuntimeError(f"Không tìm thấy nút '{label_part}'")

    def add(self, category, name, delay_ticks, fn, combo_choice=None):
        self.queue.append((category, name, delay_ticks, fn, combo_choice))

    def _prepare_real_files_on_disk(self):
        saved_paths = []
        for idx, (name, img, _) in enumerate(self.images):
            p = self.work_dir / f"real_{idx+1}_{Path(name).stem}.png"
            export_image(img, str(p), 95)
            saved_paths.append(str(p))
        if len(saved_paths) == 1:
            p2 = self.work_dir / "real_2_flipped.png"
            export_image(geometry.flip(self.images[0][1], True), str(p2), 95)
            saved_paths.append(str(p2))
        return saved_paths

    def _build_plan(self):
        disk_imgs = self._prepare_real_files_on_disk()
        proj_file = str(self.work_dir / "Du_an_kiem_thu.mdphoto")
        export_file = str(self.work_dir / "Anh_xuat_cuoi_cung.png")
        batch_dir = str(self.work_dir / "batch_output")
        os.makedirs(batch_dir, exist_ok=True)

        # 1. MỞ NHIỀU ẢNH & ĐA TAB
        def open_multi():
            self.open_files_queue.append(disk_imgs[:2])
            self.click_btn("Mở ảnh / nhiều ảnh")

        self.add("Đa tab & Hiển thị", "Mở nhiều ảnh thành các tab", 14, open_multi)
        self.add("Đa tab & Hiển thị", "Chuyển sang Tab 2 rồi quay lại Tab 1", 10, lambda: (
            self.win.document_tabs.setCurrentIndex(1),
            QTimer.singleShot(400, lambda: self.win.document_tabs.setCurrentIndex(0))
        ))
        self.add("Đa tab & Hiển thị", "Phóng to (+), Thu nhỏ (−), 1:1, Vừa màn hình", 10, lambda: (
            self.click_btn("+"), self.click_btn("−"), self.click_btn("1:1"), self.click_btn("Vừa màn hình")
        ))

        # 2. KHÔNG GIAN ẢNH
        self.add("Không gian ảnh", "Di chuyển / Zoom", 6, lambda: self.click_btn("Di chuyển / Zoom"))
        self.add("Không gian ảnh", "Chọn vùng cắt & Cắt vùng đã chọn", 12, lambda: (
            self.click_btn("Chọn vùng cắt"),
            self.win.canvas.rectangle.setRect(QRectF(
                self.win.doc.current.shape[1] * 0.08,
                self.win.doc.current.shape[0] * 0.08,
                self.win.doc.current.shape[1] * 0.84,
                self.win.doc.current.shape[0] * 0.84,
            )),
            self.click_btn("Cắt vùng đã chọn")
        ))
        self.add("Không gian ảnh", "Cắt theo tỉ lệ (16:9)", 12, lambda: self.click_btn("Cắt theo tỉ lệ"), "16:9")
        self.add("Không gian ảnh", "Xoay / Nắn thẳng", 12, lambda: self.click_btn("Xoay / Nắn thẳng"))
        self.add("Không gian ảnh", "Hoàn tác góc xoay (Ctrl+Z)", 8, lambda: self.click_btn("↶  Hoàn tác"))
        self.add("Không gian ảnh", "Lật ngang", 10, lambda: self.click_btn("Lật ngang"))
        self.add("Không gian ảnh", "Lật dọc", 10, lambda: self.click_btn("Lật dọc"))
        self.add("Không gian ảnh", "Lật dọc lại về chiều thuận", 10, lambda: self.click_btn("Lật dọc"))
        self.add("Không gian ảnh", "Đổi kích thước (Resize Lanczos)", 12, lambda: self.click_btn("Đổi kích thước"))

        # 3. PANEL CHỈNH (13 THANH TRƯỢT)
        test_vals = {
            "exposure": 40, "brightness": 15, "contrast": 22, "highlights": -25,
            "shadows": 30, "saturation": 18, "vibrance": 25, "temperature": 15,
            "tint": -8, "gamma": 110, "black": 8, "white": 248, "fade": 10
        }
        self.add("Panel Chỉnh (13 thanh)", "Kéo thử toàn bộ 13 thanh trượt & Preview", 14, lambda: (
            self.win.tabs.setCurrentIndex(0),
            [self.win.sliders[k].setValue(v) for k, v in test_vals.items()],
            self.win.preview()
        ))
        self.add("Panel Chỉnh (13 thanh)", "Đặt lại thanh trượt", 8, lambda: self.click_btn("Đặt lại thanh trượt"))
        self.add("Panel Chỉnh (13 thanh)", "Kéo sáng/tương phản & Áp dụng điều chỉnh", 14, lambda: (
            self.win.sliders["exposure"].setValue(30),
            self.win.sliders["contrast"].setValue(20),
            self.win.sliders["vibrance"].setValue(25),
            self.click_btn("Áp dụng điều chỉnh")
        ))

        # 4. SO SÁNH GỐC & HISTOGRAM
        self.add("Histogram & So sánh", "Giữ để xem ảnh gốc (Before -> After)", 12, lambda: (
            self.win.compare.pressed.emit(),
            QTimer.singleShot(550, self.win.compare.released.emit)
        ))
        self.add("Histogram & So sánh", "Histogram: Xem lớn", 10, lambda: self.click_btn("Xem lớn"))
        self.add("Histogram & So sánh", "Histogram: Ẩn rồi Hiện biểu đồ", 10, lambda: (
            self.click_btn("Ẩn"),
            QTimer.singleShot(400, lambda: self.click_btn("Hiện"))
        ))
        self.add("Histogram & So sánh", "Histogram: Tách kênh Đỏ (R) & Giữ gam", 12, lambda: (
            self.win.set_histogram_filter_mode("channel"),
            self.win.toggle_histogram_filter(0),
            QTimer.singleShot(450, lambda: self.win.set_histogram_filter_mode("gamut"))
        ))
        self.add("Histogram & So sánh", "Tắt lớp lọc Histogram", 8, lambda: self.click_btn("Tắt lớp lọc"))

        # 5. PANEL MÀU (TẤT CẢ PRESETS)
        for p_idx, preset_name in enumerate(filters.PRESETS):
            self.add("Panel Màu (Presets)", f"Áp dụng preset: {preset_name}", 11,
                     lambda i=p_idx: (
                         self.win.tabs.setCurrentIndex(1),
                         self.win.look.setCurrentIndex(i),
                         self.win.strength.setValue(70),
                         self.click_btn("Áp dụng preset")
                     ))

        # 6. PANEL CỌ (6 CHẾ ĐỘ CỌ + TẨY MASK)
        brush_modes = [
            "Làm sáng vùng", "Làm tối vùng", "Làm mịn vùng",
            "Làm mờ vùng", "Xóa chi tiết Telea", "Xóa nền bằng cọ"
        ]
        for b_idx, b_name in enumerate(brush_modes):
            def run_brush(idx=b_idx):
                self.win.tabs.setCurrentIndex(2)
                self.click_btn("Bật cọ vẽ mask")
                h, w = self.win.doc.current.shape[:2]
                self.win.canvas.mask[int(h*0.35):int(h*0.65), int(w*0.35):int(w*0.65)] = 255
                self.win.canvas.mask[int(h*0.45):int(h*0.55), int(w*0.45):int(w*0.55)] = 0
                self.win.canvas.show_mask()
                self.win.brush_mode.setCurrentIndex(idx)
                self.win.brush_amount.setValue(30)
                self.click_btn("Áp dụng vào vùng tô")

            self.add("Panel Cọ (6 chế độ)", f"Cọ vẽ & áp dụng: {b_name}", 13, run_brush)
            if b_name == "Xóa nền bằng cọ":
                self.add("Panel Cọ (6 chế độ)", "Hoàn tác xóa nền để tiếp tục test", 8,
                         lambda: self.click_btn("↶  Hoàn tác"))

        # 7. ÁNH SÁNG & CHI TIẾT
        self.add("Ánh sáng & Chi tiết", "Tự cân sáng (Auto tone)", 11, lambda: self.click_btn("Tự cân sáng"))
        self.add("Ánh sáng & Chi tiết", "Cân bằng trắng (Gray world)", 11, lambda: self.click_btn("Cân bằng trắng"))
        self.add("Ánh sáng & Chi tiết", "Đường cong Curves", 12, lambda: self.click_btn("Đường cong Curves"))
        self.add("Ánh sáng & Chi tiết", "Màu chọn lọc HSL", 12, lambda: self.click_btn("Màu chọn lọc HSL"))
        self.add("Ánh sáng & Chi tiết", "Bộ lọc và xử lý ảnh (Thuật toán bài học)", 14,
                 lambda: self.click_btn("Bộ lọc và xử lý ảnh"))

        spatial_filters = [
            "Làm nét", "Gaussian", "Median", "Bilateral",
            "CLAHE", "Cartoon", "Phác thảo", "Canny", "Otsu", "Âm bản"
        ]
        for f_name in spatial_filters:
            self.add("Hiệu ứng / Khử nhiễu", f"Bộ lọc không gian: {f_name}", 12,
                     lambda: self.click_btn("Hiệu ứng / Khử nhiễu nhanh"), f_name)
            if f_name in ("Cartoon", "Phác thảo", "Canny", "Otsu", "Âm bản"):
                self.add("Hiệu ứng / Khử nhiễu", f"Hoàn tác hiệu ứng {f_name}", 7,
                         lambda: self.click_btn("↶  Hoàn tác"))

        self.add("Ánh sáng & Chi tiết", "Tối góc Vignette", 11, lambda: self.click_btn("Tối góc Vignette"))

        def run_quality_compare():
            ref_path = str(self.work_dir / "ref_same_size.png")
            blurred = filters.spatial(self.win.doc.current, "Gaussian", 5)
            export_image(blurred, ref_path, 95)
            self.open_file_queue.append(ref_path)
            self.click_btn("So sánh chất lượng ảnh")

        self.add("Ánh sáng & Chi tiết", "So sánh chất lượng ảnh (MSE/PSNR/SSIM)", 13, run_quality_compare)

        # 8. SÁNG TẠO
        if self.font_path:
            def run_text():
                self.open_file_queue.append(self.font_path)
                self.click_btn("Chèn chữ / Watermark")
            self.add("Sáng tạo", f"Chèn chữ / Watermark ({Path(self.font_path).name})", 13, run_text)

        def run_overlay():
            self.open_file_queue.append(disk_imgs[-1])
            self.click_btn("Sticker / Ảnh phủ")

        self.add("Sáng tạo", "Sticker / Ảnh phủ", 13, run_overlay)
        self.add("Sáng tạo", "Thêm khung viền", 11, lambda: self.click_btn("Thêm khung viền"))

        def run_collage():
            self.open_files_queue.append(disk_imgs)
            self.click_btn("Ghép ảnh Collage")

        self.add("Sáng tạo", "Ghép ảnh Collage (Tạo tab mới)", 15, run_collage)

        # 9. LỊCH SỬ & DỰ ÁN
        self.add("Lịch sử & Dự án", "Chọn bước lịch sử & Về bước đã chọn", 10, lambda: (
            self.win.document_tabs.setCurrentIndex(0),
            self.win.history.setCurrentRow(max(0, self.win.history.count() - 2)),
            self.click_btn("Về bước đã chọn")
        ))
        self.add("Lịch sử & Dự án", "Hoàn tác & Làm lại trên lịch sử", 10, lambda: (
            self.click_btn("↶ Hoàn tác"),
            QTimer.singleShot(400, lambda: self.click_btn("↷ Làm lại"))
        ))
        self.add("Lịch sử & Dự án", "Hướng dẫn nhanh", 10, lambda: self.click_btn("Hướng dẫn nhanh"))

        def run_batch():
            self.open_files_queue.append(disk_imgs)
            self.dir_queue.append(batch_dir)
            self.click_btn("Xuất hàng loạt theo preset")

        self.add("Lịch sử & Dự án", "Xuất hàng loạt theo preset", 15, run_batch)

        def run_save_and_reopen_project():
            self.save_file_queue.append(proj_file)
            self.click_btn("Lưu dự án")

        self.add("Lịch sử & Dự án", "Lưu dự án (.mdphoto)", 13, run_save_and_reopen_project)

        def run_open_project():
            self.open_file_queue.append(proj_file)
            self.click_btn("Mở dự án")

        self.add("Lịch sử & Dự án", "Mở lại dự án (.mdphoto) thành tab mới", 13, run_open_project)

        def run_export():
            self.save_file_queue.append(export_file)
            self.click_btn("Xuất ảnh  Ctrl+E")

        self.add("Lịch sử & Dự án", "Xuất ảnh thành phẩm (.png)", 13, run_export)

        self.add("Lịch sử & Dự án", "Khôi phục ảnh gốc (trên Tab 2)", 11, lambda: (
            self.win.document_tabs.setCurrentIndex(1),
            self.click_btn("Khôi phục ảnh gốc")
        ))

    def start(self):
        self.total_steps = len(self.queue)
        self.step_timer.start()

    def _tick(self):
        if self.win.busy or QApplication.activeModalWidget() is not None:
            return
        if self.wait_ticks > 0:
            self.wait_ticks -= 1
            return
        if not self.queue:
            self.step_timer.stop()
            self._print_final_report()
            return

        done = self.total_steps - len(self.queue) + 1
        cat, name, delay, fn, combo_choice = self.queue.pop(0)
        msg = f"[{done}/{self.total_steps}] {cat}: {name}"
        print(f"▶ {msg}")
        self.win.statusBar().showMessage(msg)
        self.win.hint.setText(msg)
        self.dialog_combo_override = combo_choice

        try:
            fn()
            self.report.append((True, cat, name, "OK"))
        except Exception as exc:
            print(f"  [LỖI] {name}: {exc}")
            self.report.append((False, cat, name, str(exc)))

        self.wait_ticks = delay

    def _print_final_report(self):
        passed = sum(1 for ok, *_ in self.report if ok)
        total = len(self.report)
        summary = f"HOÀN TẤT KIỂM THỬ TOÀN BỘ {passed}/{total} CHỨC NĂNG! Bạn có thể tự thao tác tiếp trên giao diện."
        self.win.statusBar().showMessage(summary)
        self.win.hint.setText(summary)

        print("\n" + "=" * 78)
        print(f"BÁO CÁO KIỂM THỬ TOÀN DIỆN GIAO DIỆN MINH ĐĂNG PHOTO ({passed}/{total} PASS)")
        print("=" * 78)
        for ok, cat, name, info in self.report:
            tag = "[PASS]" if ok else "[FAIL]"
            print(f"{tag} {cat:<22} | {name:<42} -> {info}")
        print("=" * 78)
        print(f"Thư mục file kết quả test: {self.work_dir}")
        print(f"Số tab đang mở trên giao diện: {self.win.document_tabs.count()}")
        print("=" * 78)


def main():
    app = QApplication(sys.argv)
    load_app_stylesheet(app)

    images = choose_test_images(sys.argv[1:])
    if not images:
        y, x = np.mgrid[0:720, 0:1080]
        img = np.zeros((720, 1080, 4), dtype=np.uint8)
        img[..., 0] = (x * 255 // 1080).astype(np.uint8)
        img[..., 1] = (y * 255 // 720).astype(np.uint8)
        img[..., 2] = 160
        img[..., 3] = 255
        images = [("Anh_Mau_HD.png", img, "Ảnh tạo mẫu")]

    win = MainWindow()
    win.show()

    sim = FullFeatureSimulator(win, images)
    QTimer.singleShot(500, sim.start)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
