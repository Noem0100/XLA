# Kết quả kiểm thử

## Lớp lọc gam màu từ histogram, ngày 16/11/2026

Môi trường: Windows, Python 3.11.9 trong `.venv`, Qt offscreen. Lệnh: `.\.venv\Scripts\python.exe -m pytest tests -q`. Kết quả toàn bộ suite: **90 passed in 2.14s**.

Bổ sung 24 trường hợp: 15 kiểm tra bộ lọc giữ gam đỏ/xanh lá/xanh dương, khoảng hue tuần hoàn, chuyển tiếp mềm, độ sáng xám, alpha và dữ liệu nguồn; 9 kiểm tra chuột/bàn phím, chuyển/tắt lớp lọc, thay đổi thanh trượt, crop/mask, so sánh ảnh gốc, áp dụng/hoàn tác/làm lại, mở ảnh mới và đồng bộ cửa sổ histogram lớn.

Đã chụp và xem [giao diện lớp lọc gam màu](Histogram_loc_gam_mau.png) bằng Qt offscreen với bảng màu thử nghiệm. Đã kiểm tra bố cục 1440×920 và 1180×720. Lớp xem thử thay ảnh nền trong canvas thay vì chồng alpha lên ảnh nền; histogram giữ thống kê trước lớp lọc cho đến khi áp dụng. Đây vẫn là kiểm thử offscreen, cần thao tác trực tiếp trước khi nộp.

## Bổ sung histogram cột, ngày 16/11/2026

Môi trường thực thi: Windows, Python 3.11.9 trong `.venv`, Qt offscreen. Lệnh: `.\.venv\Scripts\python.exe -m pytest tests -q`.

Kết quả: **66 passed in 1.94s**. Chín trường hợp bổ sung kiểm tra số đếm 256 mức RGB/Y', loại pixel alpha=0, ảnh trong suốt hoàn toàn, tham chiếu khác kích thước, sao chép số liệu sang cửa sổ lớn, vẽ cột ở thang tuyến tính/log và đồng bộ histogram với preview, ảnh gốc, từng bước lịch sử, crop, hoàn tác/làm lại.

Đã dựng và xem ảnh giao diện Qt offscreen ở 1440×920 và 1180×720; kiểm tra nút Ẩn/Hiện giải phóng diện tích thanh trượt và cửa sổ Xem lớn 900×620. Ảnh kiểm tra: [Giao diện](Histogram_giao_dien.png), [Cửa sổ nhỏ](Histogram_giao_dien_nho.png), [Histogram chi tiết](Histogram_chi_tiet.png). Phiên offscreen cần nạp font Segoe UI từ Windows để chụp chữ; việc này chỉ áp dụng trong bước chụp ảnh kiểm tra.

Đây là kiểm thử tự động/offscreen trên Windows, chưa thay thế việc thao tác trực tiếp với cửa sổ thật và dialog hệ điều hành.

## Kết quả trước khi bổ sung histogram

Ngày 16/11/2026. Môi trường: Linux x86_64, Python 3.12, PySide6 6.8.3, NumPy 2.2.6, Pillow 11.3.0, OpenCV headless 4.11.0.86, pytest 8.3.5.

Lệnh: `QT_QPA_PLATFORM=offscreen python -m pytest tests -q`

Kết quả đã thực thi: **57 passed in 1.47s**. Đây là kết quả suite sau khi bổ sung kiểm thử điều phối công cụ, lỗi worker và chữ tiếng Việt.

- 54 trường hợp core (bao gồm tham số hóa): RGBA/dtype/alpha, mặc định đồng nhất, exposure, LUT đảo kênh, hue, gray world, crop/flip/resize, mask cục bộ, chữ/overlay/collage, lịch sử, Unicode, EXIF, export, dự án/ghi nguyên tử, batch.
- 3 bài kiểm thử UI. Các bài UI là `test_ui_edit_compare_and_undo`, `test_canvas_mouse_mapping`, `test_tool_dispatch_and_failure`.
- Đã chụp và xem giao diện desktop bằng Qt offscreen; screenshot được tạo bằng Qt offscreen, không phải thiết kế giả lập.
- Chưa kiểm thử trực tiếp trên Windows, macOS, ARM; không tuyên bố bảo đảm mọi hệ điều hành/driver/màn hình.

## Đo thời gian minh họa

Một lần chạy trên ảnh demo tổng hợp 1600×1000 (1,6 MP). Chỉ đo hàm xử lý, không tính đọc file, nén lịch sử hoặc vẽ GUI. Không phải benchmark chuẩn, không dự đoán hiệu năng máy người dùng.

| Phép xử lý | Giây |
|---|---:|
| Tone pipeline | 0.114 |
| Gaussian | 0.114 |
| Bilateral | 0.138 |
| CLAHE | 0.218 |
| NLM | 1.068 |

## Kiểm tra trực tiếp trên Windows trước buổi báo cáo

1. Cài đúng Python 3.11/3.12 64-bit, chạy setup và F5.
2. Mở JPG có tên tiếng Việt và PNG trong suốt; kiểm tra crop/cọ/zoom.
3. Chèn chữ có dấu bằng Arial, mở dialog chọn file và đổi kích thước.
4. Export PNG/JPG rồi mở bằng Photos; lưu/mở dự án `.mdphoto`.
5. Chạy bộ test bằng `.venv\Scripts\python.exe -m pytest tests -q`.
6. Thử ở màn hình 1366×768 và mức scale hệ điều hành đang sử dụng.
