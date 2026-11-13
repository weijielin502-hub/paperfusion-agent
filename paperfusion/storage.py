"""Bounded workspaces, atomic artifacts and reproducible manifests."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from pathlib import Path

IGNORED = {".git", ".venv", "node_modules", "__pycache__", ".pytest_cache", ".ruff_cache"}


def atomic_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix=".pending-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def write_json(path: Path, value) -> None:
    atomic_text(path, json.dumps(value, ensure_ascii=False, indent=2, default=str) + "\n")


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def digest(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def safe_path(root: Path, relative: str) -> Path:
    name = str(relative)
    rel = Path(name)
    # Windows drive and separator syntax must be rejected on Linux too, where
    # Path("C:/file") would otherwise look like a harmless relative path.
    if ("\\" in name or ":" in name or rel.is_absolute() or rel.drive
            or ".." in rel.parts or not rel.parts):
        raise ValueError("Use a non-empty relative path inside the workspace")
    root = root.resolve()
    cursor = root
    for part in rel.parts:
        cursor = cursor / part
        if cursor.is_symlink() or (hasattr(cursor, "is_junction") and cursor.is_junction()):
            raise ValueError("Links and junctions are not permitted")
    target = cursor.resolve()
    if not target.is_relative_to(root):
        raise ValueError("Path escapes the workspace")
    return target


def manifest(root: Path) -> dict[str, str]:
    result = {}
    for file in sorted(root.rglob("*")):
        rel = file.relative_to(root)
        if any(p in IGNORED for p in rel.parts):
            continue
        safe_path(root, rel.as_posix())
        if file.is_file():
            if file.stat().st_size > 5_000_000:
                raise ValueError(f"File too large for the source workspace: {rel}")
            result[rel.as_posix()] = hashlib.sha256(file.read_bytes()).hexdigest()
    return result


def copy_source(source: Path, target: Path) -> None:
    if target.resolve().is_relative_to(source.resolve()):
        raise ValueError("Run directory must be outside the source project")
    for rel in manifest(source):
        if Path(rel).name.startswith(".env"):
            continue
        dst = safe_path(target, rel)
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(safe_path(source, rel), dst)


def verify_manifest(root: Path, expected: dict[str, str]) -> None:
    if manifest(root) != expected:
        raise ValueError("Workspace differs from its recorded checkpoint; restore it or start a new run")
