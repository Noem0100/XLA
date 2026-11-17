"""Fixture ảnh tổng hợp có gradient, nhiễu và alpha biến đổi."""
import os
import sys
from pathlib import Path
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
import pytest


@pytest.fixture
def rgba():
    """Ảnh kiểm thử xác định được nhờ random seed cố định."""
    image = np.random.default_rng(42).integers(0, 256, (48, 64, 4), dtype=np.uint8)
    image[..., 3] = np.arange(64, dtype=np.uint8)[None, :] * 4
    return image
