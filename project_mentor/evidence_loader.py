"""Load Agent-Tool-Evidence canonical records from the local records directory."""

from __future__ import annotations

import json
import os
import re
import stat
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = PACKAGE_DIR.parent
DEFAULT_RECORDS_DIR = PROJECT_ROOT / "evidence" / "sample"
MAX_RECORD_BYTES = 1_000_000
RECORD_ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,199}\Z")


def get_records_dir() -> Path:
    """Return the configured evidence records directory at call time."""
    configured_dir = os.environ.get("EVIDENCE_RECORDS_DIR", str(DEFAULT_RECORDS_DIR))
    return Path(configured_dir).expanduser().resolve()


def _record_id(filename: str) -> str:
    """Validate a flat evidence record identifier."""
    if not isinstance(filename, str):
        raise ValueError("Evidence record identifier must be a string")

    record_id = filename.removesuffix(".json")
    if not RECORD_ID_PATTERN.fullmatch(record_id):
        raise ValueError(
            "Evidence record identifier must contain only letters, digits, "
            "hyphens, or underscores"
        )
    return record_id


def _record_path(record_id: str) -> Path:
    records_dir = get_records_dir()
    if not records_dir.is_dir():
        raise ValueError(f"Evidence records directory is unavailable: {records_dir}")

    file_path = records_dir / f"{record_id}.json"
    if file_path.is_symlink():
        raise ValueError(f"Evidence record '{record_id}' must not be a symlink")
    if not file_path.is_file():
        raise FileNotFoundError(
            f"Evidence record '{record_id}' not found in {records_dir}"
        )

    try:
        file_path.resolve().relative_to(records_dir)
    except ValueError as exc:
        raise ValueError(
            f"Evidence record '{record_id}' is outside the records directory"
        ) from exc
    return file_path


def list_available_records() -> list[str]:
    """Return sorted list of available record filenames (without .json)."""
    records_dir = get_records_dir()
    if not records_dir.is_dir():
        return []
    return sorted(
        f.stem
        for f in records_dir.iterdir()
        if (
            f.suffix == ".json"
            and not f.is_symlink()
            and f.is_file()
            and RECORD_ID_PATTERN.fullmatch(f.stem)
        )
    )


def load_evidence_record(filename: str) -> dict:
    """Load a canonical evidence record by filename (with or without .json).

    Raises FileNotFoundError if the file does not exist.
    Raises ValueError if the identifier, records directory, or file content is invalid.
    """
    record_id = _record_id(filename)
    file_path = _record_path(record_id)

    try:
        open_flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(file_path, open_flags)
        with os.fdopen(descriptor, "rb") as record_file:
            if not stat.S_ISREG(os.fstat(record_file.fileno()).st_mode):
                raise ValueError(
                    f"Evidence record '{record_id}' must be a regular file"
                )
            raw_json = record_file.read(MAX_RECORD_BYTES + 1)
    except OSError as exc:
        raise ValueError(
            f"Evidence record '{record_id}' could not be read: {exc.strerror}"
        ) from exc

    if len(raw_json) > MAX_RECORD_BYTES:
        raise ValueError(
            f"Evidence record '{record_id}' exceeds the {MAX_RECORD_BYTES}-byte limit"
        )

    try:
        data = json.loads(raw_json)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ValueError(
            f"Evidence record '{record_id}' contains invalid JSON: {exc}"
        ) from exc

    if not isinstance(data, dict):
        raise ValueError(
            f"Evidence record '{record_id}' must be a JSON object, got "
            f"{type(data).__name__}"
        )

    return data
