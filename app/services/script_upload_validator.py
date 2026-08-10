import re

from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO


MAX_SCRIPT_UPLOAD_BYTES = 5 * 1024 * 1024

ALLOWED_SCRIPT_EXTENSIONS = {
    "python": {".py"},
    "powershell": {".ps1"},
    "batch": {".bat", ".cmd"},
}

SAFE_FILENAME_PATTERN = re.compile(
    r"[A-Za-z0-9][A-Za-z0-9._ -]{0,199}"
)


@dataclass(frozen=True)
class ValidatedScriptUpload:
    script_type: str
    original_filename: str
    file_extension: str
    content: bytes


def validate_script_upload(
    *,
    script_type: str,
    filename: str | None,
    file_object: BinaryIO,
) -> ValidatedScriptUpload:
    cleaned_script_type = (
        script_type.strip().lower()
    )

    allowed_extensions = (
        ALLOWED_SCRIPT_EXTENSIONS.get(
            cleaned_script_type
        )
    )

    if allowed_extensions is None:
        raise ValueError(
            "Unsupported script type."
        )

    original_filename = (
        filename or ""
    ).strip()

    if not original_filename:
        raise ValueError(
            "A script filename is required."
        )

    if (
        "/" in original_filename
        or "\\" in original_filename
        or original_filename in {".", ".."}
    ):
        raise ValueError(
            "Script filename contains an invalid path."
        )

    if not SAFE_FILENAME_PATTERN.fullmatch(
        original_filename
    ):
        raise ValueError(
            "Script filename contains unsupported characters "
            "or is longer than 200 characters."
        )

    file_extension = Path(
        original_filename
    ).suffix.lower()

    if file_extension not in allowed_extensions:
        expected_extensions = ", ".join(
            sorted(allowed_extensions)
        )

        raise ValueError(
            "Script extension does not match its type. "
            f"Expected: {expected_extensions}."
        )

    file_object.seek(0)

    content = file_object.read(
        MAX_SCRIPT_UPLOAD_BYTES + 1
    )

    file_object.seek(0)

    if len(content) > MAX_SCRIPT_UPLOAD_BYTES:
        raise ValueError(
            "Script file exceeds the 5 MB upload limit."
        )

    if not content:
        raise ValueError(
            "Script file is empty."
        )

    if b"\x00" in content:
        raise ValueError(
            "Binary content is not allowed in script files."
        )

    try:
        decoded_content = content.decode(
            "utf-8-sig"
        )

    except UnicodeDecodeError as error:
        raise ValueError(
            "Script file must contain UTF-8 text."
        ) from error

    if not decoded_content.strip():
        raise ValueError(
            "Script file contains no executable text."
        )

    return ValidatedScriptUpload(
        script_type=cleaned_script_type,
        original_filename=original_filename,
        file_extension=file_extension,
        content=content,
    )