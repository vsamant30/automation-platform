from io import BytesIO

import pytest

from app.services.script_upload_validator import (
    MAX_SCRIPT_UPLOAD_BYTES,
    validate_script_upload,
)


@pytest.mark.parametrize(
    (
        "script_type",
        "filename",
        "content",
    ),
    [
        (
            "python",
            "automation.py",
            b"print('success')\n",
        ),
        (
            "powershell",
            "automation.ps1",
            b"Write-Output 'success'\n",
        ),
        (
            "batch",
            "automation.cmd",
            b"@echo off\r\necho success\r\n",
        ),
    ],
)
def test_valid_script_is_accepted(
    script_type: str,
    filename: str,
    content: bytes,
) -> None:
    result = validate_script_upload(
        script_type=script_type,
        filename=filename,
        file_object=BytesIO(content),
    )

    assert result.script_type == script_type
    assert result.original_filename == filename
    assert result.content == content


def test_unsupported_script_type_is_rejected() -> None:
    with pytest.raises(
        ValueError,
        match="Unsupported script type",
    ):
        validate_script_upload(
            script_type="executable",
            filename="automation.exe",
            file_object=BytesIO(b"MZ"),
        )


def test_path_like_filename_is_rejected() -> None:
    with pytest.raises(
        ValueError,
        match="invalid path",
    ):
        validate_script_upload(
            script_type="python",
            filename="../automation.py",
            file_object=BytesIO(b"print('test')"),
        )


def test_mismatched_extension_is_rejected() -> None:
    with pytest.raises(
        ValueError,
        match="extension does not match",
    ):
        validate_script_upload(
            script_type="python",
            filename="automation.ps1",
            file_object=BytesIO(b"print('test')"),
        )


def test_oversized_script_is_rejected() -> None:
    oversized_content = (
        b"a" * (MAX_SCRIPT_UPLOAD_BYTES + 1)
    )

    with pytest.raises(
        ValueError,
        match="exceeds the 5 MB",
    ):
        validate_script_upload(
            script_type="python",
            filename="large.py",
            file_object=BytesIO(
                oversized_content
            ),
        )


def test_empty_script_is_rejected() -> None:
    with pytest.raises(
        ValueError,
        match="empty",
    ):
        validate_script_upload(
            script_type="python",
            filename="empty.py",
            file_object=BytesIO(b""),
        )


def test_binary_script_is_rejected() -> None:
    with pytest.raises(
        ValueError,
        match="Binary content",
    ):
        validate_script_upload(
            script_type="python",
            filename="binary.py",
            file_object=BytesIO(
                b"print('test')\x00binary"
            ),
        )


def test_invalid_utf8_is_rejected() -> None:
    with pytest.raises(
        ValueError,
        match="UTF-8",
    ):
        validate_script_upload(
            script_type="python",
            filename="invalid.py",
            file_object=BytesIO(
                b"\xff\xfe\xfa"
            ),
        )


def test_whitespace_only_script_is_rejected() -> None:
    with pytest.raises(
        ValueError,
        match="no executable text",
    ):
        validate_script_upload(
            script_type="python",
            filename="blank.py",
            file_object=BytesIO(
                b"   \r\n\t"
            ),
        )