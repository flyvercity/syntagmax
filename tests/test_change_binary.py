# SPDX-License-Identifier: MIT

import hashlib
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from syntagmax.change_binary import (
    ImageProperties,
    compute_file_hash,
    extract_image_properties,
    format_file_size,
)


def test_compute_file_hash_happy_path(tmp_path):
    """Test compute_file_hash with a regular file smaller than the 8KB chunk size."""
    file_path = tmp_path / "small_file.txt"
    content = b"Hello, World!"
    file_path.write_bytes(content)

    expected_hash = hashlib.sha256(content).hexdigest()
    assert compute_file_hash(file_path) == expected_hash


def test_compute_file_hash_large_file(tmp_path):
    """Test compute_file_hash with a file larger than the 8KB chunk size to verify chunked reading."""
    file_path = tmp_path / "large_file.bin"
    # Create 10KB of random data
    content = b"A" * 10240
    file_path.write_bytes(content)

    expected_hash = hashlib.sha256(content).hexdigest()
    assert compute_file_hash(file_path) == expected_hash


def test_compute_file_hash_nonexistent():
    """Test compute_file_hash returns None for a nonexistent file path."""
    assert compute_file_hash(Path("does_not_exist_12345.txt")) is None


def test_compute_file_hash_directory(tmp_path):
    """Test compute_file_hash returns None if path points to a directory."""
    assert compute_file_hash(tmp_path) is None


def test_compute_file_hash_os_error(tmp_path):
    """Test compute_file_hash handles OSError when opening/reading files."""
    file_path = tmp_path / "error_file.txt"
    file_path.write_bytes(b"some content")

    with patch("builtins.open", side_effect=OSError("Permission denied")):
        assert compute_file_hash(file_path) is None


def test_extract_image_properties_nonexistent():
    """Test extract_image_properties returns None for a nonexistent file path."""
    assert extract_image_properties(Path("does_not_exist_12345.png")) is None


def test_extract_image_properties_directory(tmp_path):
    """Test extract_image_properties returns None for a directory."""
    assert extract_image_properties(tmp_path) is None


def test_extract_image_properties_stat_error(tmp_path):
    """Test extract_image_properties handles OSError during file stat."""
    file_path = tmp_path / "stat_error.png"
    file_path.write_bytes(b"data")

    # Mock path.stat to raise OSError (rather than patching the whole class Path.stat, which breaks exists())
    with patch.object(Path, "stat", side_effect=OSError("Failed to stat")) as mock_stat:
        # Since path.exists() will call stat internally and we want exists() to return True,
        # we can mock exists() and is_file() on a mock or just mock stat to succeed for exists,
        # or mock path.stat specifically on the instance. Let's patch 'exists' and 'is_file' to return True,
        # but have stat raise OSError.
        with patch.object(Path, "exists", return_value=True):
            with patch.object(Path, "is_file", return_value=True):
                assert extract_image_properties(file_path) is None


def test_extract_image_properties_pillow_not_installed(tmp_path):
    """Test extract_image_properties behavior when Pillow is not installed/imported."""
    file_path = tmp_path / "test_img.png"
    content = b"not a real image but exists"
    file_path.write_bytes(content)

    # Force an ImportError when importing PIL
    with patch.dict(sys.modules, {"PIL": None}):
        props = extract_image_properties(file_path)
        assert props is not None
        assert props.size_bytes == len(content)
        assert props.width is None
        assert props.height is None


def test_extract_image_properties_pillow_installed_happy_path(tmp_path):
    """Test extract_image_properties successfully extracts dimensions when Pillow is mocked."""
    file_path = tmp_path / "test_mocked_img.png"
    content = b"dummy image data"
    file_path.write_bytes(content)

    # Create the correct structure for sys.modules and PIL attributes
    mock_pil = MagicMock()
    mock_image = MagicMock()
    mock_pil.Image = mock_image

    mock_img_context = MagicMock()
    mock_img_context.__enter__.return_value = mock_img_context
    mock_img_context.size = (800, 600)
    mock_image.open.return_value = mock_img_context

    with patch.dict(sys.modules, {"PIL": mock_pil, "PIL.Image": mock_image}):
        props = extract_image_properties(file_path)
        assert props is not None
        assert props.size_bytes == len(content)
        assert props.width == 800
        assert props.height == 600


def test_extract_image_properties_pillow_exception(tmp_path):
    """Test extract_image_properties when Pillow open raises an exception (e.g. corrupt image)."""
    file_path = tmp_path / "corrupt_img.png"
    content = b"corrupt data"
    file_path.write_bytes(content)

    # Mock PIL.Image.open to raise an exception
    mock_pil = MagicMock()
    mock_image = MagicMock()
    mock_pil.Image = mock_image
    mock_image.open.side_effect = Exception("Unidentified image file")

    with patch.dict(sys.modules, {"PIL": mock_pil, "PIL.Image": mock_image}):
        props = extract_image_properties(file_path)
        assert props is not None
        assert props.size_bytes == len(content)
        assert props.width is None
        assert props.height is None


def test_format_file_size():
    """Test format_file_size with various size thresholds (B, KB, MB, GB)."""
    # Bytes
    assert format_file_size(0) == "0 B"
    assert format_file_size(512) == "512 B"
    assert format_file_size(1023) == "1023 B"

    # Kilobytes
    assert format_file_size(1024) == "1.0 KB"
    assert format_file_size(1536) == "1.5 KB"
    assert format_file_size(1024 * 1024 - 1) == "1024.0 KB"

    # Megabytes
    assert format_file_size(1024 * 1024) == "1.0 MB"
    assert format_file_size(int(1024 * 1024 * 1.5)) == "1.5 MB"
    assert format_file_size(1024 * 1024 * 1024 - 1) == "1024.0 MB"

    # Gigabytes
    assert format_file_size(1024 * 1024 * 1024) == "1.0 GB"
    assert format_file_size(int(1024 * 1024 * 1024 * 2.7)) == "2.7 GB"
    assert format_file_size(1024 * 1024 * 1024 * 1024) == "1024.0 GB"
