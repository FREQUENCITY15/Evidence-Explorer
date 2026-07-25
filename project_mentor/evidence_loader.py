"""Load Agent-Tool-Evidence canonical records from the local records directory."""

from __future__ import annotations

import json
import os
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = PACKAGE_DIR.parent

DEFAULT_RECORDS_DIR = os.environ.get(
    "EVIDENCE_RECORDS_DIR",
    str(PROJECT_ROOT / "evidence" / "sample"),
)


def get_records_dir() -> Path:
    """Return the absolute path to the evidence records directory."""
    return Path(DEFAULT_RECORDS_DIR).resolve()


def list_available_records() -> list[str]:
    """Return sorted list of available record filenames (without .json)."""
    records_dir = get_records_dir()
    if not records_dir.is_dir():
        return []
    return sorted(
        f.stem
        for f in records_dir.iterdir()
        if f.suffix == ".json" and not f.name.startswith(".")
    )


def load_evidence_record(filename: str) -> dict:
    """Load a canonical evidence record by filename (with or without .json).

    Raises FileNotFoundError if the file does not exist.
    Raises ValueError if the file is not valid JSON.
    """
    records_dir = get_records_dir()
    clean = filename.removesuffix(".json")
    file_path = records_dir / f"{clean}.json"

    if not file_path.is_file():
        raise FileNotFoundError(
            f"Evidence record '{clean}' not found in {records_dir}"
        )

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Evidence record '{clean}' contains invalid JSON: {exc}"
        ) from exc

    if not isinstance(data, dict):
        raise ValueError(
            f"Evidence record '{clean}' must be a JSON object, got {type(data).__name__}"
        )

    return data
