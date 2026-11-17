"""Kiểm thử bất biến dữ liệu và kết quả đã biết, không chỉ smoke test."""
import io
import json
import zipfile
import numpy as np
import pytest
from PIL import Image
from app.core import adjustments as a, filters as f, geometry as g, retouch as r
from app.core.io import load_image, export_image, save_project, load_project, atomic_write
from app.core.document import Document
from app.core.batch import batch_export


@pytest.mark.parametrize('kind', ['Gaussian', 'Median', 'Bilateral', 'Khử nhiễu NLM', 'Làm nét', 'CLAHE', 'Canny', 'Otsu', 'Âm bản', 'Cartoon', 'Phác thảo'])
def test_filter_contract(rgba, kind):
    """Các bộ lọc giữ alpha, kích thước, dtype và không sửa nguồn."""
    backup = rgba.copy()
    output = f.spatial(rgba, kind, 8)
    assert output.shape == rgba.shape and output.dtype == np.uint8
    np.testing.assert_array_equal(output[..., 3], rgba[..., 3])
    np.testing.assert_array_equal(rgba, backup)


@pytest.mark.parametrize('name', f.PRESETS)
def test_preset_zero_identity(rgba, name):
    """Cường độ 0 của mọi preset phải là phép đồng nhất."""
    np.testing.assert_array_equal(f.preset(rgba, name, 0), rgba)


@pytest.mark.parametrize('key,value', [(k, 20 if k not in ('gamma', 'white') else 180) for k in a.DEFAULTS])
def test_adjust_contract(rgba, key, value):
    """Từng điều chỉnh phải giữ alpha và không ghi đè nguồn."""
    backup = rgba.copy()
    output = a.adjust(rgba, {key: value})
    assert output.shape == rgba.shape and output.dtype == np.uint8
    np.testing.assert_array_equal(output[..., 3], rgba[..., 3])
    np.testing.assert_array_equal(rgba, backup)


def test_identity_and_exposure(rgba):
    """Mặc định khôi phục pixel; +1 EV nhân đôi RGB trong không gian mã hóa."""
    np.testing.assert_allclose(a.adjust(rgba, {}), rgba, atol=1)
    flat = np.full((2, 2, 4), 50, np.uint8)
    np.testing.assert_allclose(a.adjust(flat, {'exposure': 100})[..., :3], 100, atol=1)
    with pytest.raises(ValueError):
        a.adjust(rgba, {'black': 200, 'white': 100})


def test_curves_known(rgba):
    """LUT đảo mức x thành 255-x; kênh R không tác động G/B/A."""
    result = a.curve(rgba, [(0, 255), (255, 0)], 'R')
    np.testing.assert_array_equal(result[..., 0], 255 - rgba[..., 0])
    np.testing.assert_array_equal(result[..., 1:], rgba[..., 1:])
    with pytest.raises(ValueError):
        a.curve(rgba, [(0, 0), (0, 255)])


def test_hsl_gray_and_red():
    """Mask hue không làm đổi ảnh xám; dịch đỏ 120 độ thành xanh lá."""
    gray = np.array([[[100, 100, 100, 255]]], np.uint8)
    np.testing.assert_allclose(a.hsl(gray, 0, 90, 100, 50), gray, atol=1)
    red = np.array([[[255, 0, 0, 255]]], np.uint8)
    np.testing.assert_allclose(a.hsl(red, 0, 120, 0, 0), [[[0, 255, 0, 255]]], atol=1)


def test_auto_tone_and_balance():
    """Ảnh phẳng không chia 0; gray world cân được một mẫu lệch màu."""
    flat = np.full((20, 20, 4), 80, np.uint8)
    np.testing.assert_array_equal(a.auto_tone(flat), flat)
    cast = np.full((4, 4, 4), [60, 120, 180, 255], np.uint8)
    np.testing.assert_array_equal(a.white_balance(cast)[..., :3], np.full((4, 4, 3), 120, np.uint8))


def test_geometry(rgba):
    """Crop đảo góc đúng; flip hai lần đồng nhất; xoay 90 đổi kích thước."""
    np.testing.assert_array_equal(g.crop(rgba, (20, 20, 5, 5)), rgba[5:20, 5:20])
    np.testing.assert_array_equal(g.flip(g.flip(rgba)), rgba)
    assert g.rotate(rgba, 90).shape == (64, 48, 4)
    assert g.resize(rgba, 32, 24).shape == (24, 32, 4)
    assert g.border(rgba, 2, '#ffffff').shape == (52, 68, 4)
    for box in [(0, 0, 0, 0), (90, 80, 100, 90)]:
        with pytest.raises(ValueError):
            g.crop(rgba, box)
    with pytest.raises(ValueError):
        g.resize(rgba, 10000, 10000)


@pytest.mark.parametrize('mode', ['Làm sáng vùng', 'Làm tối vùng', 'Làm mịn vùng', 'Làm mờ vùng', 'Xóa chi tiết Telea', 'Xóa nền bằng cọ'])
def test_mask_locality(rgba, mode):
    """Không feather: pixel ngoài mask giữ nguyên với mọi chế độ cọ."""
    mask = np.zeros(rgba.shape[:2], np.uint8)
    mask[10:20, 10:20] = 255
    output = r.local_edit(rgba, mask, mode, 20, 0)
    np.testing.assert_array_equal(output[mask == 0], rgba[mask == 0])
    if mode == 'Xóa nền bằng cọ':
        assert np.all(output[..., 3][mask > 0] == 0)


def test_empty_mask_rejected(rgba):
    with pytest.raises(ValueError):
        r.local_edit(rgba, np.zeros(rgba.shape[:2], np.uint8), 'Làm sáng vùng')


def test_overlay_and_collage(rgba):
    """Overlay opacity 0 đồng nhất; collage đúng kích thước và alpha."""
    np.testing.assert_array_equal(r.overlay(rgba, rgba, 5, 5, 20, 0), rgba)
    output = r.collage([rgba, rgba, rgba], 2, 100, 5)
    assert output.shape == (215, 215, 4)
    assert np.all(output[..., 3] == 255)


def test_history_branch_and_limit(rgba):
    """Undo/redo nhánh mới, trạng thái đã lưu và giới hạn bộ nhớ."""
    d = Document(rgba)
    d.commit(g.flip(rgba), 'flip')
    assert d.dirty and d.undo() and not d.dirty
    assert d.redo()
    d.mark_saved()
    assert not d.dirty
    d.undo()
    d.commit(a.adjust(rgba, {'brightness': 20}), 'bright')
    assert not d.redo() and d.dirty
    d.max_steps = 2
    for i in range(5):
        d.commit(rgba, str(i))
    assert len(d.entries) == 2
    d.max_bytes = 1
    d.commit(rgba, 'last')
    assert len(d.entries) == 1 and not d.undo()


@pytest.mark.parametrize('extension', ['.png', '.jpg', '.webp', '.bmp', '.tiff'])
def test_export_roundtrip(rgba, tmp_path, extension):
    """Đường dẫn Unicode và xuất/mở lại các định dạng hỗ trợ."""
    path = tmp_path / ('Ảnh thử nghiệm' + extension)
    export_image(rgba, path)
    output = load_image(path)
    assert output.shape == rgba.shape
    if extension in ('.png', '.tiff'):
        np.testing.assert_array_equal(output, rgba)
    if extension in ('.jpg', '.bmp'):
        assert np.all(output[..., 3] == 255)


def test_exif_orientation(tmp_path):
    """EXIF rotate 90 độ phải đổi W/H khi load."""
    image = Image.new('RGB', (20, 10), 'red')
    exif = Image.Exif(); exif[274] = 6
    path = tmp_path / 'orientation.jpg'
    image.save(path, exif=exif)
    assert load_image(path).shape == (20, 10, 4)


def test_project_and_atomic(rgba, tmp_path):
    """Dự án roundtrip chính xác; writer lỗi không phá file đã có."""
    path = tmp_path / 'test.mdphoto'
    modified = g.flip(rgba)
    save_project(path, rgba, modified, ['flip'])
    original, current = load_project(path)
    np.testing.assert_array_equal(original, rgba)
    np.testing.assert_array_equal(current, modified)
    before = path.read_bytes()
    def fail(temporary):
        raise RuntimeError('simulated disk failure')
    with pytest.raises(RuntimeError):
        atomic_write(path, fail)
    assert path.read_bytes() == before
    with zipfile.ZipFile(tmp_path / 'bad.mdphoto', 'w') as archive:
        archive.writestr('manifest.json', json.dumps({'version': 999}))
        archive.writestr('original.png', b'bad')
        archive.writestr('current.png', b'bad')
    with pytest.raises(ValueError):
        load_project(tmp_path / 'bad.mdphoto')


def test_batch_collision_and_error(rgba, tmp_path):
    """Batch giữ nguồn, tránh trùng tên và tiếp tục khi một ảnh bị lỗi."""
    path = tmp_path / 'input.png'
    export_image(rgba, path)
    before = path.read_bytes()
    result = batch_export([path, path, tmp_path / 'missing.png'], tmp_path, longest=32, extension='.png')
    assert result[0][2] is None and result[1][2] is None and result[2][2]
    assert result[0][1] != result[1][1]
    assert load_image(result[0][1]).shape == (24, 32, 4)
    assert path.read_bytes() == before


def test_text_unicode_and_alpha(rgba):
    """Chèn chữ có dấu bằng font thực; thiếu font phải báo lỗi rõ."""
    from pathlib import Path
    fonts = [Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'), Path('C:/Windows/Fonts/arial.ttf')]
    font = next((str(path) for path in fonts if path.exists()), None)
    if font is None:
        pytest.skip('Không tìm thấy font kiểm thử trên hệ thống này')
    out = r.text_layer(rgba, 'Ảnh', 1, 1, 16, '#ffffff', font)
    assert out.shape == rgba.shape and not np.array_equal(out, rgba)
    with pytest.raises(ValueError):
        r.text_layer(rgba, 'Ảnh', 1, 1, 16, '#fff', '')
