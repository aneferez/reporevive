from __future__ import annotations

import pytest

from app.config import Settings
from app.core.exceptions import PipelineError
from app.intake.archive import extract_zip
from app.security.redaction import REDACTION_MARK

from .helpers import make_zip


def _settings(**overrides) -> Settings:
    return Settings(**overrides)


def test_valid_zip_extracts_and_filters():
    data = make_zip(
        {
            "README.md": b"# demo\n",
            "src/app.py": b"x = 1\n",
            "node_modules/dep/index.js": b"module.exports = 1\n",  # ignored
            "assets/logo.png": b"\x89PNG\r\n\x1a\n",  # binary, skipped
        }
    )
    result = extract_zip(data, _settings())
    paths = {f.path for f in result.files}
    assert "README.md" in paths
    assert "src/app.py" in paths
    assert not any("node_modules" in p for p in paths)
    assert "assets/logo.png" not in paths


def test_single_root_folder_is_stripped():
    data = make_zip({"README.md": b"# demo\n", "src/app.py": b"x=1\n"}, root="proj-main")
    result = extract_zip(data, _settings())
    paths = {f.path for f in result.files}
    assert paths == {"README.md", "src/app.py"}


def test_secret_in_file_is_redacted_and_recorded():
    data = make_zip({"config.py": b"password = 's3cr3t-P@ssw0rd'\n"})
    result = extract_zip(data, _settings())
    body = result.files[0].content
    assert "s3cr3t-P@ssw0rd" not in body
    assert REDACTION_MARK in body
    assert result.secret_hits
    assert result.secret_hits[0].file == "config.py"


def test_path_traversal_is_rejected():
    data = make_zip({"ok.txt": b"fine", "../evil.txt": b"pwned"})
    with pytest.raises(PipelineError) as exc:
        extract_zip(data, _settings())
    assert exc.value.code == "UNSAFE_ARCHIVE_ENTRY"


def test_absolute_path_is_rejected():
    data = make_zip({"/etc/passwd": b"root:x:0:0"})
    with pytest.raises(PipelineError) as exc:
        extract_zip(data, _settings())
    assert exc.value.code == "UNSAFE_ARCHIVE_ENTRY"


def test_symlinks_are_skipped_not_followed():
    data = make_zip({"real.txt": b"hello"}, symlinks={"link.txt": "/etc/passwd"})
    result = extract_zip(data, _settings())
    paths = {f.path for f in result.files}
    assert "real.txt" in paths
    assert "link.txt" not in paths
    assert any("symlink" in n.lower() for n in result.notes)


def test_extracted_size_limit_enforced():
    data = make_zip({"a.txt": b"x" * 100})
    with pytest.raises(PipelineError) as exc:
        extract_zip(data, _settings(max_extracted_bytes=50))
    assert exc.value.code == "ARCHIVE_TOO_LARGE"


def test_oversize_individual_file_is_skipped():
    data = make_zip({"big.txt": b"x" * 100, "small.txt": b"ok"})
    result = extract_zip(data, _settings(max_file_bytes=10))
    paths = {f.path for f in result.files}
    assert "small.txt" in paths
    assert "big.txt" not in paths


def test_file_count_limit_truncates():
    data = make_zip({f"f{i}.txt": b"data" for i in range(5)})
    result = extract_zip(data, _settings(max_analyzed_files=2))
    assert len(result.files) == 2
    assert result.truncated is True


def test_invalid_zip_rejected():
    with pytest.raises(PipelineError) as exc:
        extract_zip(b"this is not a zip", _settings())
    assert exc.value.code == "INVALID_ARCHIVE"
