"""Đọc ảnh Unicode, quản lý màu sRGB, xuất nguyên tử và dự án ZIP an toàn."""
import io
import json
import os
import tempfile
import warnings
import zipfile
from pathlib import Path
import numpy as np
from PIL import Image, ImageOps, ImageCms
from .geometry import check_size

FORMATS = {'.jpg': 'JPEG', '.jpeg': 'JPEG', '.png': 'PNG', '.webp': 'WEBP', '.tif': 'TIFF', '.tiff': 'TIFF', '.bmp': 'BMP'}


def load_image(path):
    """Chuẩn hóa EXIF orientation, ICC nếu có và trả RGBA 8 bit."""
    with warnings.catch_warnings():
        warnings.simplefilter('error', Image.DecompressionBombWarning)
        with Image.open(path) as raw:
            check_size(*raw.size)
            image = ImageOps.exif_transpose(raw)
            alpha = image.convert('RGBA').getchannel('A')
            icc = raw.info.get('icc_profile')
            if icc:
                try:
                    profile = ImageCms.ImageCmsProfile(io.BytesIO(icc))
                    # Profile CMYK cần ảnh CMYK; các kiểu còn lại chuyển RGB.
                    base = image if image.mode == 'CMYK' else image.convert('RGB')
                    image = ImageCms.profileToProfile(base, profile, ImageCms.createProfile('sRGB'), outputMode='RGB')
                except (OSError, ValueError, ImageCms.PyCMSError) as exc:
                    raise ValueError('Không đọc được ICC của ảnh. Hãy chuyển sang sRGB trước.') from exc
            image = image.convert('RGBA')
            image.putalpha(alpha)
            return np.array(image)


def png_bytes(image):
    """Mã hóa không mất dữ liệu để lưu lịch sử hoặc dự án."""
    stream = io.BytesIO()
    Image.fromarray(image).save(stream, format='PNG')
    return stream.getvalue()


def from_png(data):
    """Giải mã ảnh trạng thái bằng cùng đường kiểm tra kích thước."""
    return load_image(io.BytesIO(data))


def atomic_write(path, writer):
    """Ghi tệp tạm cùng thư mục rồi os.replace, tránh tệp đích dở dang."""
    path = Path(path)
    handle, temporary = tempfile.mkstemp(prefix='.mdphoto-', dir=path.parent)
    os.close(handle)
    try:
        writer(temporary)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.remove(temporary)


def export_image(image, path, quality=95):
    """Xuất PNG/JPEG/WebP/TIFF/BMP; JPEG/BMP flatten nền trắng, không giữ EXIF."""
    extension = Path(path).suffix.lower()
    if extension not in FORMATS:
        raise ValueError('Đuôi hỗ trợ: .jpg .jpeg .png .webp .tif .tiff .bmp')
    result = Image.fromarray(image)
    if extension in ('.jpg', '.jpeg', '.bmp'):
        background = Image.new('RGBA', result.size, 'white')
        result = Image.alpha_composite(background, result).convert('RGB')
    options = dict(quality=int(quality)) if extension in ('.jpg', '.jpeg', '.webp') else {}
    if extension == '.png':
        options['compress_level'] = 6
    if extension != '.bmp':
        options['icc_profile'] = ImageCms.ImageCmsProfile(ImageCms.createProfile('sRGB')).tobytes()
    atomic_write(path, lambda temporary: result.save(temporary, format=FORMATS[extension], **options))


def save_project(path, original, current, labels):
    """Lưu hai ảnh PNG và manifest; không pickle, không lưu lớp chỉnh sửa rời."""
    def write(temporary):
        """Ghi nội dung ZIP vào tệp tạm được atomic_write quản lý."""
        with zipfile.ZipFile(temporary, 'w', zipfile.ZIP_STORED) as archive:
            archive.writestr('manifest.json', json.dumps({'version': 1, 'history': labels}, ensure_ascii=False))
            archive.writestr('original.png', png_bytes(original))
            archive.writestr('current.png', png_bytes(current))
    atomic_write(path, write)


def load_project(path):
    """Đọc đúng ba entry, giới hạn dữ liệu; tuyệt đối không giải nén đường dẫn."""
    with zipfile.ZipFile(path) as archive:
        names = ['manifest.json', 'original.png', 'current.png']
        limits = [1_000_000, 100_000_000, 100_000_000]
        for name, limit in zip(names, limits):
            if archive.getinfo(name).file_size > limit:
                raise ValueError('Dự án vượt giới hạn kích thước.')
        manifest = json.loads(archive.read('manifest.json'))
        if manifest.get('version') != 1:
            raise ValueError('Phiên bản dự án không được hỗ trợ.')
        return from_png(archive.read('original.png')), from_png(archive.read('current.png'))
