"""Validation pure utilities: response-content + file pre-flight checks.

Taxonomy layer (utility): stateless functions, taxonomy imports only.
"""

from __future__ import annotations

import os
from pathlib import Path

from modules.shared.src.taxonomy_core_constant import CHALLENGE_KEYWORDS
from modules.shared.src.taxonomy_domain_error import (
    AuthRequiredError,
    FileValidationError,
    OutputValidationError,
)


def validate_response_content(text: str) -> None:
    """Validate AI response text for server error pages or CAPTCHA challenges."""
    if not text or not text.strip():
        raise OutputValidationError("Response content is empty")

    text_lower = text.lower()
    for kw in CHALLENGE_KEYWORDS:
        if kw in text_lower and len(text) < 500:
            if "verify you are human" in text_lower or "attention required!" in text_lower:
                raise AuthRequiredError(f"CAPTCHA / Bot detection challenge detected: '{kw}'")
            raise OutputValidationError(f"Server error or challenge page detected in output: '{kw}'")


def validate_file(filepath: object, max_size_mb: float = 100.0) -> int:
    """Perform pre-flight sanity and security validation on file.

    Args:
        filepath: Path to the target file.
        max_size_mb: Maximum allowed file size in megabytes.

    Returns:
        File size in bytes.

    Raises:
        FileValidationError: If the file is invalid or exceeds size limits.

    """
    if not isinstance(filepath, (str, Path)):
        raise FileValidationError(f"Invalid path: {filepath}")
    path = Path(filepath)

    if not path.exists():
        raise FileValidationError(f"File does not exist: {path}")
    if not path.is_file():
        raise FileValidationError(f"Path is not a regular file: {path}")
    if not os.access(path, os.R_OK):
        raise FileValidationError(f"File is not readable: {path}")

    size_bytes = path.stat().st_size
    max_bytes = int(max_size_mb * 1024 * 1024)
    if size_bytes > max_bytes:
        raise FileValidationError(
            f"File size ({size_bytes / (1024 * 1024):.2f}MB) exceeds maximum limit of {max_size_mb:.2f}MB: {path}"
        )

    return size_bytes
