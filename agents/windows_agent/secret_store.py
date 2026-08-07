import ctypes
import os

from ctypes import wintypes
from pathlib import Path


CRYPTPROTECT_UI_FORBIDDEN = 0x01

DEFAULT_SECRET_DIRECTORY = Path(
    os.getenv(
        "PROGRAMDATA",
        r"C:\ProgramData",
    )
) / "AutomationPlatform"

DEFAULT_AGENT_API_KEY_FILE = (
    DEFAULT_SECRET_DIRECTORY
    / "windows_agent_api_key.bin"
)


class DATA_BLOB(ctypes.Structure):
    _fields_ = [
        ("cbData", wintypes.DWORD),
        (
            "pbData",
            ctypes.POINTER(ctypes.c_byte),
        ),
    ]


crypt32 = ctypes.windll.crypt32
kernel32 = ctypes.windll.kernel32


def _bytes_to_blob(
    value: bytes,
) -> tuple[DATA_BLOB, ctypes.Array]:
    buffer = ctypes.create_string_buffer(value)

    blob = DATA_BLOB(
        len(value),
        ctypes.cast(
            buffer,
            ctypes.POINTER(ctypes.c_byte),
        ),
    )

    return blob, buffer


def protect_secret(
    plaintext: str,
) -> bytes:
    """
    Encrypt a secret using Windows DPAPI
    for the current Windows user.
    """

    cleaned_plaintext = plaintext.strip()

    if not cleaned_plaintext:
        raise ValueError(
            "Secret value is required."
        )

    plaintext_bytes = cleaned_plaintext.encode(
        "utf-8"
    )

    input_blob, input_buffer = _bytes_to_blob(
        plaintext_bytes
    )

    output_blob = DATA_BLOB()

    success = crypt32.CryptProtectData(
        ctypes.byref(input_blob),
        None,
        None,
        None,
        None,
        CRYPTPROTECT_UI_FORBIDDEN,
        ctypes.byref(output_blob),
    )

    # Keep input buffer alive until the native call completes.
    _ = input_buffer

    if not success:
        raise ctypes.WinError()

    try:
        return ctypes.string_at(
            output_blob.pbData,
            output_blob.cbData,
        )

    finally:
        kernel32.LocalFree(
            output_blob.pbData
        )


def unprotect_secret(
    encrypted_value: bytes,
) -> str:
    """
    Decrypt a Windows DPAPI-protected secret
    for the current Windows user.
    """

    if not encrypted_value:
        raise ValueError(
            "Encrypted secret is required."
        )

    input_blob, input_buffer = _bytes_to_blob(
        encrypted_value
    )

    output_blob = DATA_BLOB()

    success = crypt32.CryptUnprotectData(
        ctypes.byref(input_blob),
        None,
        None,
        None,
        None,
        CRYPTPROTECT_UI_FORBIDDEN,
        ctypes.byref(output_blob),
    )

    _ = input_buffer

    if not success:
        raise ctypes.WinError()

    try:
        plaintext_bytes = ctypes.string_at(
            output_blob.pbData,
            output_blob.cbData,
        )

        return plaintext_bytes.decode(
            "utf-8"
        )

    finally:
        kernel32.LocalFree(
            output_blob.pbData
        )


def save_agent_api_key(
    api_key: str,
    secret_file: Path = DEFAULT_AGENT_API_KEY_FILE,
) -> Path:
    """
    Encrypt and save the Agent API key.
    """

    encrypted_value = protect_secret(
        api_key
    )

    secret_file.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    secret_file.write_bytes(
        encrypted_value
    )

    return secret_file


def load_agent_api_key(
    secret_file: Path = DEFAULT_AGENT_API_KEY_FILE,
) -> str:
    """
    Load and decrypt the stored Agent API key.
    """

    if not secret_file.is_file():
        raise FileNotFoundError(
            f"Agent API key file was not found: "
            f"{secret_file}"
        )

    encrypted_value = secret_file.read_bytes()

    api_key = unprotect_secret(
        encrypted_value
    ).strip()

    if not api_key:
        raise ValueError(
            "Stored Agent API key is empty."
        )

    return api_key