# Minh Đăng Photo

Ứng dụng chỉnh sửa ảnh desktop phục vụ báo cáo môn **Xử lý ảnh**, viết bằng Python. Giao diện tiếng Việt, nền tối, chạy cục bộ; source tách riêng giao diện, điều phối trạng thái và thuật toán. Mở thư mục này trong **Visual Studio Code** (không phải Visual Studio).

## 1. Bắt đầu nhanh

**Windows:** cài Python 3.12 64-bit → giải nén → chạy `setup_windows.bat` một lần → chạy `run_windows.bat`.

**Linux:** tạo `.venv`, cài `requirements.txt` theo mục 4 → chạy `bash run_linux.sh`.

Sau khi mở app: **Mở ảnh → assets/anh_demo.jpg → kéo Độ sáng → Áp dụng điều chỉnh → Xuất ảnh**.

Tài liệu chi tiết: `docs/Bao_cao_Minh_Dang_Photo.docx`. Ảnh chụp giao diện thật: `docs/Giao_dien_app.png`.

## 2. Tính năng thực sự có trong source

| Nhóm | Công cụ |
|---|---|
| Ánh sáng | Phơi sáng, độ sáng, tương phản, highlights, shadows, gamma, black point, white point, tự cân sáng |
| Màu | Saturation, vibrance, nhiệt độ, tint, gray-world white balance, màu chọn lọc theo hue, curves RGB/R/G/B, fade |
| Hình học | Crop kéo chuột, crop tỉ lệ ở tâm, xoay tùy góc, lật ngang/dọc, resize Lanczos giữ tỉ lệ hoặc tự do |
| Bộ lọc | Gaussian, median, bilateral, NLM, unsharp mask, CLAHE, cartoon, phác thảo, Canny, Otsu, âm bản, vignette |
| Preset | Chân dung, phong cảnh, điện ảnh, vintage, đen trắng, sepia; chỉnh cường độ |
| Cọ cục bộ | Tô/tẩy mask; tăng/giảm sáng vùng, làm mịn, làm mờ, Telea xóa chi tiết nhỏ, xóa alpha bằng cọ; feather |
| Sáng tạo | Chữ tiếng Việt từ font TTF/OTF, watermark, PNG sticker/overlay, độ đậm ảnh phủ, khung màu, collage lưới |
| Quy trình | Histogram cột RGB và độ sáng, so sánh trước/sau theo chức năng, zoom/pan, so sánh ảnh gốc, undo/redo, khôi phục gốc, dự án .mdphoto, xử lý hàng loạt |
| File | Đọc JPEG/PNG/WebP/TIFF/BMP, chuẩn hóa EXIF orientation, chuyển ICC hợp lệ sang sRGB; xuất 5 định dạng |

Đây là project môn học có bộ công cụ chỉnh ảnh truyền thống, **không phải bản sao đầy đủ Snapseed, Lightroom hoặc Picsart**. Không có AI sinh ảnh/xóa nền tự động, RAW/DNG, HDR 16/32 bit, chỉnh lens/perspective, catalog, đồng bộ cloud, quản lý layer/mask lâu dài hoặc công cụ làm đẹp khuôn mặt chuyên sâu. Curves nhập nút bằng số, chưa kéo nút trên biểu đồ. Chữ và sticker được gộp vào ảnh khi áp dụng; sửa bằng Undo rồi chèn lại. HSL trên giao diện dùng HSV bên trong (độ sáng là Value). Telea không tái tạo chính xác các vật thể lớn.

## 3. Cài đặt Windows từng bước

Mục tiêu: Windows 10/11 **64-bit**, Python **3.11 hoặc 3.12**. Khuyến nghị Python 3.12, RAM 8 GB, màn hình từ 1366×768. Đã kiểm thử tự động trên Linux/Python 3.12 và Windows/Python 3.11.9 với Qt offscreen; vẫn cần thử thao tác trực tiếp trên màn hình Windows.

1. Tải Python từ <https://www.python.org/downloads/>. Chọn bản 3.12 64-bit tương thích Windows. Trong trình cài, bật **Add python.exe to PATH** và **Python Launcher**.
2. Cài VS Code từ <https://code.visualstudio.com/>. Mở Extensions, cài **Python** và **Python Debugger** của Microsoft.
3. Giải nén ZIP. Không chạy trực tiếp bên trong cửa sổ ZIP. Có thể đặt project tại `D:\DuAn\MinhDangPhoto`.
4. VS Code → **File → Open Folder** → chọn thư mục chứa `main.py`, `requirements.txt`, `app`.
5. **Terminal → New Terminal**. Kiểm tra:

```powershell
py -3.12 --version
```

6. Tạo môi trường riêng và cài thư viện:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Nếu dùng Python 3.11, đổi riêng dòng tạo môi trường thành `py -3.11 -m venv .venv`.
Không cần `Activate.ps1`, vì vậy không cần thay đổi ExecutionPolicy.

7. Chạy:

```powershell
.\.venv\Scripts\python.exe main.py
```

8. Để chạy F5: **Ctrl+Shift+P → Python: Select Interpreter → Enter interpreter path** → chọn `.venv\Scripts\python.exe`. Mở `main.py`, nhấn **F5**, chọn cấu hình **Minh Đăng Photo**. File `.vscode/launch.json` đã có sẵn.
9. Những lần sau chỉ cần `run_windows.bat` hoặc F5. Cần Internet khi cài thư viện; chỉnh ảnh không cần Internet.

## 4. Cài đặt Linux từng bước

Ví dụ Ubuntu 24.04 desktop x86_64, Python 3.12. Các bản phân phối khác có tên gói khác. Không cài vào Python hệ thống bằng `sudo pip`.

```bash
sudo apt update
sudo apt install python3 python3-venv python3-pip libgl1 libegl1 libxkbcommon-x11-0 libxcb-cursor0 libxcb-xinerama0 libxcb-icccm4 libxcb-image0 libxcb-keysyms1 libxcb-render-util0
```

Mở thư mục project trong VS Code, sau đó tại terminal của thư mục chứa `main.py`:

```bash
python3 --version
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python main.py
```

Hoặc chạy `bash run_linux.sh`. Chọn interpreter `.venv/bin/python` trong VS Code để dùng F5. Cần phiên desktop Linux có màn hình; terminal SSH thuần không hiển thị cửa sổ. Nếu Wayland gặp lỗi hiển thị, thử `QT_QPA_PLATFORM=xcb .venv/bin/python main.py` trong phiên desktop có XWayland.

## 5. Cách sử dụng chi tiết

### Chỉnh ánh sáng và màu

- Bấm **Mở ảnh**, chọn một file hỗ trợ. Ảnh giới hạn **20 triệu pixel** để tránh quá tải bộ nhớ.
- Panel bên phải **Chỉnh** có 13 thanh trượt; kéo thanh cuộn để thấy gamma/levels/fade.
- Phơi sáng 100 tương ứng +1 EV trong phép biến đổi mã màu của app; Gamma 100 là 1.0. Đây là mô phỏng trên sRGB 8 bit, không phải xử lý RAW tuyến tính.
- Preview dùng ảnh cạnh dài tối đa 1000 px và chờ 160 ms sau thay đổi; nhấn **Áp dụng điều chỉnh** để tính trên ảnh đủ độ phân giải.
- **Đặt lại thanh trượt** hủy preview, không xóa các bước đã áp dụng. Phải áp dụng hoặc hủy preview trước khi dùng công cụ khác/lưu/xuất.
- Điểm trắng phải lớn hơn điểm đen. Dữ liệu vượt khoảng 0–255 bị clip, không thể phục hồi chi tiết đã cháy.
- **Giữ để xem ảnh gốc** chỉ so sánh với file khi mở, không phải với bước chỉnh trước đó.

### Đọc histogram cho từng chức năng

- Panel **HISTOGRAM RGB / ĐỘ SÁNG** có bốn biểu đồ cột: Đỏ (R), Xanh lá (G), Xanh dương (B) và Độ sáng (Y'). Trục ngang là mức 0–255, trục dọc là tần suất pixel (%). Cột tập trung bên trái biểu thị các mức thấp, bên phải là các mức cao. Nhấn **Xem lớn** để đọc biểu đồ trong cửa sổ rộng; **Ẩn / Hiện** để thu gọn panel khi cần thêm chỗ cho thanh trượt.
- Khi kéo thanh trượt, biểu đồ cập nhật theo bản xem trước. Sau khi áp dụng các công cụ như preset, bộ lọc, Curves, HSL, cọ, crop hoặc chèn chữ, histogram tự chuyển sang kết quả của chức năng đó; nét xám biểu thị ảnh trước thao tác. **TB** là giá trị trung bình, **σ** là độ lệch chuẩn. Trỏ chuột vào biểu đồ để xem mức màu, số pixel và tần suất trước/sau.
- Chọn một bước trong **Lịch sử** để xem lại histogram của riêng bước đó cùng ảnh trước nó; thao tác này chỉ đổi biểu đồ. Dùng **Hoàn tác / Làm lại** để đổi ảnh. Giữ nút **Xem ảnh gốc** cũng chuyển histogram sang bản gốc.
- Mặc định dùng thang tuyến tính; bật **Thang log** để nhìn rõ các mức có ít pixel. Tần suất phần trăm giúp so sánh trước/sau ngay cả khi crop hoặc resize làm đổi kích thước ảnh.
- Số liệu tính trên mẫu ảnh có cạnh dài tối đa 1000 px, loại các pixel hoàn toàn trong suốt (alpha = 0); pixel còn lại có trọng số bằng nhau. Y' được xấp xỉ bằng `0,2126R + 0,7152G + 0,0722B` trên mã sRGB 8 bit, không phải độ chói tuyến tính. Đây là thống kê của ảnh kết quả, không phải giá trị của thanh trượt. Với xử lý hàng loạt, mở từng ảnh đã xuất để xem histogram tương ứng.

### Lớp lọc gam màu từ histogram

- Bấm vào bảng **Đỏ**, **Xanh lá** hoặc **Xanh dương** để xem lớp lọc giữ các vùng thuộc gam màu đó và chuyển các màu khác sang xám. Màu gần gam được chọn chuyển tiếp mềm. Bảng đang bật có viền xanh; bấm một bảng khác để đổi gam, bấm lại cùng bảng hoặc **Tắt lớp lọc** để xem ảnh bình thường.
- Bấm bảng **Độ sáng** để xem ảnh thang xám. Có thể chọn histogram bằng phím Tab rồi nhấn Enter hoặc Space; thao tác chọn gam cũng dùng được trong cửa sổ **Xem lớn**.
- Lớp lọc áp dụng lên ảnh đang chỉnh, cập nhật khi kéo thanh trượt và giữ nguyên độ trong suốt, vùng crop và mask cọ. Khi đang xem histogram của bước cũ, bấm chọn gam sẽ trở lại phân tích ảnh đang chỉnh. Giữ nút xem ảnh gốc tạm bỏ lớp lọc; thả nút sẽ khôi phục lớp lọc.
- **Áp dụng lớp lọc** xử lý ảnh đủ độ phân giải, gộp cả các thanh trượt đang xem trước và tạo một bước lịch sử có thể hoàn tác bằng Ctrl+Z. Sau đó bạn có thể lưu/xuất ảnh. Trước khi áp dụng, biểu đồ vẫn thống kê ảnh trước lớp lọc; sau khi áp dụng, biểu đồ cập nhật theo kết quả. Dự án hiện không lưu lớp lọc độc lập để sửa lại qua phiên khác.

### Crop, xoay, resize

- **Chọn vùng cắt** → kéo chuột trái trên ảnh → **Cắt vùng đã chọn**.
- **Cắt theo tỉ lệ** cắt ở giữa ảnh theo 1:1, 4:3, 3:2, 16:9, 9:16 hoặc 2:3.
- **Xoay / Nắn thẳng**: số dương xoay ngược chiều kim đồng hồ; góc trống giữ trong suốt. Crop tiếp để bỏ góc trống.
- **Đổi kích thước**: chế độ giữ tỉ lệ chỉ dùng chiều rộng để suy ra chiều cao; chọn Tự do nếu cần cả hai.
- **Di chuyển / Zoom**: kéo để pan, con lăn để zoom, nút 1:1 để xem một pixel ảnh trên một đơn vị hiển thị Qt.

### Preset và bộ lọc

- Tab **Màu** → chọn preset và cường độ → **Áp dụng preset**.
- **Bộ lọc / Khử nhiễu** → chọn thuật toán và cường độ. NLM chậm hơn trên ảnh lớn; app giữ cửa sổ phản hồi nhưng khóa chỉnh sửa trong lúc xử lý. Chưa có nút hủy tác vụ đang chạy.
- Canny/Otsu là chức năng phân tích cho môn học. Khi áp dụng, ảnh kết quả thay ảnh hiện tại; Ctrl+Z để quay lại.
- **Curves** nhập các nút `X:Y`, ví dụ `0:0, 64:48, 128:128, 192:208, 255:255`. Các X phải khác nhau và cả X/Y trong 0–255.

### Cọ và sửa chi tiết

1. Chọn **Cọ / Sửa vùng ảnh**.
2. Chọn chế độ, đường kính cọ (pixel ảnh), cường độ và feather.
3. Tô chuột trái lên ảnh; màu đỏ thể hiện mask. Bật **Tẩy vùng mask** để xóa phần tô sai.
4. Nhấn **Áp dụng vào vùng tô**. Với Telea, mask là cứng, radius cố định 3 px; cường độ/feather không tác động chế độ này.
5. **Xóa vùng chọn / mask** chỉ xóa vùng đánh dấu, không khôi phục pixel đã chỉnh. Dùng Undo để phục hồi ảnh.
6. **Xóa nền bằng cọ** đưa alpha vùng tô về 0; xuất PNG để giữ trong suốt. Đây là xóa thủ công, không phân đoạn chủ thể bằng AI.

### Chữ, sticker, collage

- **Chèn chữ / Watermark** → chọn font `.ttf`/`.otf` hỗ trợ tiếng Việt. Windows: `C:\Windows\Fonts\arial.ttf`; Linux: `/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf`. Nhập chữ, X/Y, cỡ pixel và màu HEX (`#ffffff`).
- **Sticker / Ảnh phủ** → chọn `assets/sticker_demo.png` hoặc ảnh riêng → X/Y, chiều rộng và độ đậm. Overlay có thể bị cắt khi nằm ngoài canvas.
- **Khung viền** tăng kích thước ảnh ở bốn phía; màu HEX có thể thay đổi.
- **Collage** chọn tối đa 12 file; mỗi ảnh được fit/crop tâm vào ô vuông. Kết quả là tài liệu mới, nên lưu dự án đang chỉnh trước.

### Lưu, xuất và xử lý hàng loạt

- **Ctrl+S / Lưu dự án** lưu `.mdphoto` gồm bản gốc, bản hiện tại và nhãn lịch sử. Khi mở lại, app bắt đầu một lịch sử mới; không khôi phục undo stack hoặc thanh trượt/layer/mask cũ.
- **Ctrl+E / Xuất ảnh** ghi bản hiện tại sau khi áp dụng các chỉnh sửa. JPEG/BMP dùng nền trắng cho vùng trong suốt; PNG/TIFF giữ alpha. Chất lượng chỉ áp dụng JPEG/WebP.
- Ảnh xuất có profile sRGB (trừ BMP), không sao chép EXIF/GPS gốc. Ảnh không có profile được coi là sRGB.
- Xuất ảnh không đánh dấu dự án đã lưu; khi đóng, app vẫn nhắc nếu chưa lưu `.mdphoto`. File ảnh đã xuất vẫn tồn tại.
- **Xử lý hàng loạt**: chọn file → chọn thư mục đích → preset/cạnh dài/định dạng. Batch áp dụng preset riêng, không lấy thanh trượt từ ảnh đang mở. Tên `_edited`, `_edited_1`… tránh trùng; lỗi một file không dừng cả đợt.
- Undo/redo tối đa 20 trạng thái, nén PNG với ngân sách 256 MiB. Khi vượt hạn mức, trạng thái cũ nhất bị bỏ; bản gốc vẫn giữ riêng. RAM tổng còn gồm mảng xử lý, không bị giới hạn ở 256 MiB.

## 6. Phân bổ source

| Đường dẫn | Vai trò |
|---|---|
| `main.py` | Khởi tạo QApplication, theme, MainWindow, event loop |
| `app/ui/window.py` | Bố cục, điều phối nút/slider, mở/lưu, kết nối core |
| `app/ui/canvas.py` | Hiển thị ảnh, map tọa độ, zoom/pan, crop, mask cọ |
| `app/ui/dialogs.py` | Form tham số dùng chung |
| `app/ui/histogram.py` | Histogram cột 256 mức RGB/độ sáng, thống kê và so sánh trước/sau bằng QPainter |
| `app/ui/worker.py` | QThread chạy tác vụ nặng, signal kết quả/lỗi |
| `app/ui/theme.py` | Stylesheet giao diện tối |
| `app/core/adjustments.py` | Tone, gamma, HSV, LUT curves, auto tone, gray world |
| `app/core/filters.py` | Lọc không gian, CLAHE, biên/ngưỡng, preset, vignette |
| `app/core/geometry.py` | Crop, resize, rotate, flip, border, giới hạn pixel |
| `app/core/retouch.py` | Mask, Telea, chữ, alpha compositing, collage |
| `app/core/io.py` | EXIF/ICC, load/export, atomic write, dự án ZIP |
| `app/core/document.py` | Ảnh gốc/hiện tại, dirty flag, undo/redo |
| `app/core/batch.py` | Xử lý danh sách ảnh, chống trùng tên, báo lỗi từng file |
| `tests/` | Kiểm thử core và tích hợp Qt |
| `assets/` | Ảnh tổng hợp, ảnh nhiễu và sticker do project tạo để demo |
| `docs/` | Báo cáo Word, ảnh giao diện, kết quả kiểm thử |
| `.vscode/` | Cấu hình F5 và gợi ý extension |

Tất cả hàm/phương thức do project định nghĩa đều có docstring tiếng Việt. `app/core` không import PySide6, giúp kiểm thử thuật toán độc lập với giao diện.

## 7. Chạy kiểm thử

```powershell
# Windows
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest tests -q
```

```bash
# Linux, Qt chạy ảo không cần mở màn hình
.venv/bin/python -m pip install -r requirements-dev.txt
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests -q
```

Có 90 test case (tính cả tham số hóa). Kiểm tra hợp đồng RGBA, công thức có kết quả biết trước, mask cục bộ, undo/redo, Unicode, EXIF, project, batch, lỗi worker, ánh xạ chuột, số đếm histogram RGB/độ sáng, so sánh trước/sau theo chức năng và lớp lọc gam màu từ histogram. Kết quả môi trường thực hiện nằm trong `docs/KIEM_THU.md`. Cần kiểm thử trực tiếp Windows trước khi nộp trên máy Windows.

## 8. Kịch bản báo cáo khoảng 8 phút

1. **1 phút:** mục tiêu, giao diện và tách UI/core; mở `anh_demo.jpg`.
2. **1 phút:** exposure/contrast, preview rồi apply; trình bày biến đổi điểm ảnh và histogram.
3. **1 phút:** curves chữ S và preset; giải thích LUT/nội suy.
4. **1 phút:** mở `anh_nhieu.png`; so sánh Gaussian với bilateral/median, Undo giữa mỗi phép lọc để cùng đầu vào.
5. **1 phút:** cọ làm sáng một vùng; giải thích mask và alpha blending.
6. **1 phút:** crop theo tỉ lệ, sticker hoặc watermark; liên hệ hình học và alpha compositing.
7. **1 phút:** Canny/Otsu, giải thích phát hiện biên và phân ngưỡng; undo.
8. **1 phút:** lưu `.mdphoto`, xuất PNG, kết quả kiểm thử và hạn chế.

## 9. Lỗi thường gặp

| Triệu chứng | Cách xử lý |
|---|---|
| `python`/`pip` không nhận | Dùng `py -3.12` trên Windows và gọi pip qua `.venv/.../python -m pip` |
| `ModuleNotFoundError` | Cài requirements trong đúng `.venv`; chọn lại Python interpreter trong VS Code |
| F5 mở sai file | Open Folder đúng thư mục có `main.py`, dùng cấu hình Minh Đăng Photo |
| Lỗi PowerShell Activate | Không cần activate; dùng trực tiếp `.venv\Scripts\python.exe` |
| `No matching distribution` | Dùng Python 3.11/3.12 64-bit x86_64 theo hướng dẫn; nâng pip rồi cài lại |
| Linux lỗi `xcb` hoặc thiếu `.so` | Cài các gói Qt runtime ở mục 4; chạy từ desktop, không SSH thuần |
| Có cả `opencv-python` và `headless` | Trong `.venv`: gỡ cả hai rồi cài lại requirements; app dùng Qt của PySide6 |
| Ảnh quá lớn | Thu nhỏ bản sao dưới 20 MP trước khi mở; không sửa ảnh nguồn |
| Đen/trắng bị gắt | Giảm contrast hoặc chỉnh black/white; white phải lớn hơn black |
| Chữ tiếng Việt bị ô vuông | Chọn Arial/DejaVuSans có hỗ trợ glyph tiếng Việt |
| Không thấy thanh gamma hoặc batch | Cuộn panel phải/trái; nút Apply cố định bên dưới tab |
| Xuất mà không thấy preview | Cần Apply trước; app chủ động chặn xuất khi còn chỉnh chưa commit |
| ICC bị lỗi | Dùng công cụ khác xuất lại sRGB rồi mở bản sao; app không âm thầm bỏ profile lỗi |
| Ảnh trong suốt có viền sau lọc | Bộ lọc RGB chưa dùng premultiplied alpha; xử lý nền trong suốt cần thận trọng |
| Chạy NLM lâu | Dùng ảnh nhỏ hơn để demo; chờ worker hoàn thành, chưa có hủy tác vụ |

## 10. Nguồn tham khảo và giấy phép

- Qt for Python: <https://doc.qt.io/qtforpython-6/>
- OpenCV smoothing: <https://docs.opencv.org/4.x/d4/d13/tutorial_py_filtering.html>
- OpenCV histogram/CLAHE: <https://docs.opencv.org/4.x/d5/daf/tutorial_py_histogram_equalization.html>
- OpenCV inpainting: <https://docs.opencv.org/4.x/df/d3d/tutorial_py_inpainting.html>
- Pillow: <https://pillow.readthedocs.io/en/stable/>

Phiên bản thư viện được ghim để tái lập môi trường thử nghiệm, không phải khẳng định là phiên bản mới nhất. Source project cấp phép MIT (xem LICENSE); thư viện bên thứ ba giữ giấy phép riêng (PySide6/Qt có điều kiện LGPL/GPL/commercial tùy thành phần). Source không kèm binary thư viện hoặc font hệ thống.
# XLA
