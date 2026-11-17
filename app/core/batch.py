"""Xử lý từng file độc lập và không ghi đè ảnh nguồn."""
from pathlib import Path
from .io import load_image, export_image
from .filters import preset
from .geometry import resize


def batch_export(paths, folder, look='Nguyên bản', longest=1920, extension='.jpg'):
    """Preset + thu nhỏ + xuất tên tránh trùng; trả danh sách thành công/lỗi."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    results = []
    for path in paths:
        try:
            image = preset(load_image(path), look)
            h, w = image.shape[:2]
            if longest and max(h, w) > longest:
                scale = longest / max(h, w)
                image = resize(image, max(1, round(w * scale)), max(1, round(h * scale)))
            target = folder / (Path(path).stem + '_edited' + extension)
            number = 1
            while target.exists() or target.resolve() == Path(path).resolve():
                target = folder / (Path(path).stem + f'_edited_{number}' + extension)
                number += 1
            export_image(image, target)
            results.append((str(path), str(target), None))
        except Exception as exc:
            results.append((str(path), None, str(exc)))
    return results
