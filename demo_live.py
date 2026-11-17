"""Mô phỏng thực tế giao diện Minh Đăng Photo với dữ liệu ảnh thật trên máy."""
import os
import sys
import tempfile
from pathlib import Path
import numpy as np
from PySide6.QtCore import QTimer, QRectF
from PySide6.QtWidgets import QApplication

from app.core import adjustments, filters, geometry, retouch
from app.core.io import load_image, export_image, save_project
from app.ui.window import MainWindow


def load_app_stylesheet(app: QApplication):
    """Nạp theme/stylesheet giống main.py nếu tồn tại."""
    for candidate in Path("app").rglob("*.qss"):
        try:
            app.setStyleSheet(candidate.read_text(encoding="utf-8"))
            return
        except Exception:
            pass
    try:
        main_code = Path("main.py").read_text(encoding="utf-8")
        if "setStyleSheet" in main_code:
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


def find_real_images(limit=3):
    """Tìm ảnh thật trong thư mục cha (Ảnh đi Đồ Sơn / Downloads / Pictures)."""
    exts = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
    search_roots = [
        Path("../..").resolve(),          # ~/Downloads/Ảnh đi Đồ Sơn
        Path.home() / "Downloads",
        Path.home() / "Pictures",
        Path(".").resolve(),
    ]
    found = []
    seen = set()
    for root in search_roots:
        if not root.exists():
            continue
        for p in root.rglob("*"):
            if p.is_file() and p.suffix.lower() in exts and p.resolve() not in seen:
                if ".venv" in p.parts or "__pycache__" in p.parts:
                    continue
                try:
                    img = load_image(str(p))
                    h, w = img.shape[:2]
                    if min(h, w) >= 200:
                        seen.add(p.resolve())
                        found.append((p.name, img, str(p)))
                        print(f"[DỮ LIỆU THẬT] Đã nạp: {p} ({w}x{h} px)")
                        if len(found) >= limit:
                            return found
                except Exception:
                    continue
    return found


def make_fallback_images():
    """Tạo ảnh mẫu độ phân giải cao nếu máy không có sẵn file ảnh."""
    y, x = np.mgrid[0:720, 0:1080]
    img1 = np.zeros((720, 1080, 4), dtype=np.uint8)
    img1[..., 0] = np.clip(40 + x * 180 // 1080, 0, 255)
    img1[..., 1] = np.clip(90 + y * 140 // 720, 0, 255)
    img1[..., 2] = np.clip(210 - y * 120 // 720, 0, 255)
    img1[..., 3] = 255

    img2 = np.full((720, 1080, 4), 220, dtype=np.uint8)
    img2[120:600, 180:900, :3] = [215, 110, 75]
    img2[220:500, 320:760, :3] = [65, 155, 185]
    img2[..., 3] = 255
    return [("Mau_Phong_Canh.png", img1, "Ảnh tạo mẫu 1"), ("Mau_Chan_Dung.png", img2, "Ảnh tạo mẫu 2")]


class LiveSimulator:
    """Bộ điều khiển mô phỏng từng bước trực tiếp trên giao diện MainWindow."""

    def __init__(self, win: MainWindow, images):
        self.win = win
        self.images = images
        self.step_idx = 0
        self.wait_ticks = 0
        self.out_dir = Path(tempfile.mkdtemp(prefix="MinhDangPhoto_Demo_"))
        self.steps = [
            ("Bước 1/12: Mở 2 ảnh thật vào 2 tab độc lập", 18, self.step_open_tabs),
            ("Bước 2/12: Kéo thanh trượt Phơi sáng, Tương phản, Nhiệt độ (Xem trước)", 20, self.step_sliders_preview),
            ("Bước 3/12: Nhấn Áp dụng điều chỉnh & ghi Lịch sử", 18, self.step_apply_adjustments),
            ("Bước 4/12: So sánh giữ xem ảnh gốc (Before)", 16, self.step_compare_on),
            ("Bước 4/12: Trả lại ảnh sau chỉnh sửa (After)", 14, self.step_compare_off),
            ("Bước 5/12: Chuyển sang tab Màu & áp dụng Preset", 20, self.step_apply_preset),
            ("Bước 6/12: Chọn vùng cắt (Crop) trên khung hình", 16, self.step_select_crop),
            ("Bước 6/12: Thực hiện Cắt vùng đã chọn", 18, self.step_exec_crop),
            ("Bước 7/12: Bật Cọ vẽ & tô vùng mask đỏ lên ảnh", 18, self.step_draw_brush),
            ("Bước 7/12: Áp dụng làm sáng vào vùng mask vừa tô", 18, self.step_apply_brush),
            ("Bước 8/12: Lọc kênh Đỏ (R) trực tiếp trên Histogram", 16, self.step_hist_channel),
            ("Bước 8/12: Chuyển sang chế độ Giữ gam Đỏ & tắt lớp lọc", 16, self.step_hist_gamut_off),
            ("Bước 9/12: Chạy thuật toán Cân bằng trắng (Gray world)", 18, self.step_white_balance),
            ("Bước 10/12: Kiểm tra Hoàn tác (Undo) & Làm lại (Redo)", 18, self.step_undo_redo),
            ("Bước 11/12: Chuyển sang Tab ảnh 2 & tạo Tab 3 ghép Collage", 22, self.step_switch_and_collage),
            ("Bước 12/12: Xuất ảnh thật & lưu dự án .mdphoto", 10, self.step_export_and_finish),
        ]
        self.timer = QTimer(win)
        self.timer.setInterval(100)  # tick mỗi 100ms
        self.timer.timeout.connect(self.tick)

    def start(self):
        self.timer.start()

    def announce(self, text):
        print(f"▶ {text}")
        self.win.statusBar().showMessage(text)
        self.win.hint.setText(text)

    def tick(self):
        if self.win.busy:
            return
        if self.wait_ticks > 0:
            self.wait_ticks -= 1
            return
        if self.step_idx >= len(self.steps):
            self.timer.stop()
            return
        title, delay, fn = self.steps[self.step_idx]
        self.step_idx += 1
        self.announce(title)
        try:
            fn()
        except Exception as exc:
            print(f"  [LỖI Ở {title}]: {exc}")
        self.wait_ticks = delay

    def step_open_tabs(self):
        for name, img, _ in self.images[:2]:
            self.win.set_document(img, name)
        self.win.document_tabs.setCurrentIndex(0)

    def step_sliders_preview(self):
        self.win.tabs.setCurrentIndex(0)
        self.win.sliders["exposure"].setValue(45)
        self.win.sliders["contrast"].setValue(28)
        self.win.sliders["vibrance"].setValue(30)
        self.win.sliders["temperature"].setValue(18)
        self.win.preview()

    def step_apply_adjustments(self):
        self.win.apply_adjustments()

    def step_compare_on(self):
        self.win.show_original(True)

    def step_compare_off(self):
        self.win.show_original(False)

    def step_apply_preset(self):
        self.win.tabs.setCurrentIndex(1)
        if self.win.look.count() > 1:
            self.win.look.setCurrentIndex(1)
        self.win.strength.setValue(75)
        self.win.apply_preset()

    def step_select_crop(self):
        self.win.mode("crop")
        h, w = self.win.doc.current.shape[:2]
        self.win.canvas.rectangle.setRect(QRectF(w * 0.1, h * 0.1, w * 0.8, h * 0.8))

    def step_exec_crop(self):
        self.win.do_crop()

    def step_draw_brush(self):
        self.win.tabs.setCurrentIndex(2)
        self.win.mode("brush")
        h, w = self.win.doc.current.shape[:2]
        y1, y2 = int(h * 0.3), int(h * 0.7)
        x1, x2 = int(w * 0.3), int(w * 0.7)
        self.win.canvas.mask[y1:y2, x1:x2] = 255
        self.win.canvas.show_mask()

    def step_apply_brush(self):
        self.win.brush_mode.setCurrentIndex(0)
        self.win.brush_amount.setValue(35)
        self.win.apply_brush()

    def step_hist_channel(self):
        self.win.set_histogram_filter_mode("channel")
        self.win.toggle_histogram_filter(0)

    def step_hist_gamut_off(self):
        self.win.set_histogram_filter_mode("gamut")
        QTimer.singleShot(700, lambda: self.win.set_histogram_filter(None))

    def step_white_balance(self):
        self.win.run_image("Gray world", adjustments.white_balance)

    def step_undo_redo(self):
        self.win.undo()
        QTimer.singleShot(700, self.win.redo)

    def step_switch_and_collage(self):
        if self.win.document_tabs.count() > 1:
            self.win.document_tabs.setCurrentIndex(1)
        imgs = [item[1] for item in self.images]
        if len(imgs) == 1:
            imgs = [imgs[0], geometry.flip(imgs[0], True)]
        self.win.start_task(
            "Ghép ảnh Collage",
            lambda: retouch.collage(imgs, 2, 480, 16),
            lambda collage_img: self.win.set_document(collage_img, "Collage_Thuc_Te.png", created=True),
        )

    def step_export_and_finish(self):
        out_img = self.out_dir / "Ket_qua_chinh_sua.png"
        out_proj = self.out_dir / "Du_an_thuc_te.mdphoto"
        export_image(self.win.doc.current, str(out_img), 95)
        save_project(str(out_proj), self.win.doc.original, self.win.doc.current, self.win.doc.labels())

        summary = (
            f"HOÀN TẤT MÔ PHỎNG! Đã xuất ảnh thật tại: {out_img} | "
            f"Bạn có thể tự thao tác tiếp trên {self.win.document_tabs.count()} tab đang mở."
        )
        self.announce(summary)
        print("\n" + "=" * 70)
        print("BÁO CÁO MÔ PHỎNG THỰC TẾ HOÀN TẤT")
        print(f"- Số tab đang mở: {self.win.document_tabs.count()}")
        print(f"- File ảnh xuất thật: {out_img} ({out_img.stat().st_size // 1024} KB)")
        print(f"- File dự án thật:    {out_proj} ({out_proj.stat().st_size // 1024} KB)")
        print("=" * 70)


def main():
    app = QApplication(sys.argv)
    load_app_stylesheet(app)

    images = find_real_images(limit=3)
    if not images:
        print("[THÔNG BÁO] Không tìm thấy file ảnh trên máy, sử dụng ảnh mẫu độ phân giải cao.")
        images = make_fallback_images()

    win = MainWindow()
    win.show()

    sim = LiveSimulator(win, images)
    QTimer.singleShot(600, sim.start)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
