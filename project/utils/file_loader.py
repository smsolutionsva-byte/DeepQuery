from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Callable, Iterable, List, Sequence, Tuple

from PIL import Image

SUPPORTED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".tif", ".tiff"}
DATASET_ROOT_ENV_VAR = "SATINT_DATASET_ROOT"
DEFAULT_DATASET_DIR_CANDIDATES = ("dataset", "INSERT_DATASET")
DEFAULT_PREVIEW_SAMPLE_SIZE = 5


class DatasetNotFoundError(RuntimeError):
    """Raised when the dataset directory is missing or contains no valid images."""


def resolve_dataset_root(project_root: Path) -> Path:
    """Resolve dataset root from env var or known local directory names."""
    env_value = os.getenv(DATASET_ROOT_ENV_VAR, "").strip()
    if env_value:
        candidate = Path(env_value).expanduser()
        if not candidate.is_absolute():
            candidate = project_root / candidate
        return candidate.resolve()

    for folder_name in DEFAULT_DATASET_DIR_CANDIDATES:
        candidate = project_root / folder_name
        if candidate.exists():
            return candidate.resolve()

    # Default to ./dataset when no known folder exists yet.
    return (project_root / DEFAULT_DATASET_DIR_CANDIDATES[0]).resolve()


def ensure_dataset_structure(project_root: Path) -> Path:
    """Create dataset placeholder folders and return the resolved dataset root path."""
    dataset_root = resolve_dataset_root(project_root)
    dataset_root.mkdir(parents=True, exist_ok=True)
    (dataset_root / "images").mkdir(parents=True, exist_ok=True)
    (dataset_root / "paired_images" / "A").mkdir(parents=True, exist_ok=True)
    (dataset_root / "paired_images" / "B").mkdir(parents=True, exist_ok=True)
    return dataset_root


def is_image_file(path: Path) -> bool:
    return path.suffix.lower() in SUPPORTED_IMAGE_EXTENSIONS


def discover_images(
    dataset_root: Path,
    progress_callback: Callable[[int, Path | None], None] | None = None,
) -> List[Path]:
    """Recursively discover supported image files under dataset root."""
    if not dataset_root.exists() or not dataset_root.is_dir():
        return []

    discovered: list[Path] = []
    scanned_files = 0
    last_emitted = 0
    for root, _, files in os.walk(dataset_root):
        if not files:
            continue
        root_path = Path(root)
        for filename in files:
            scanned_files += 1
            candidate = (root_path / filename).resolve()
            if progress_callback is not None and (scanned_files == 1 or scanned_files - last_emitted >= 500):
                try:
                    progress_callback(scanned_files, candidate)
                except Exception:
                    pass
                last_emitted = scanned_files

            suffix = Path(filename).suffix.lower()
            if suffix not in SUPPORTED_IMAGE_EXTENSIONS:
                continue
            discovered.append(candidate)

    if progress_callback is not None:
        current = discovered[-1] if discovered else None
        try:
            progress_callback(scanned_files, current)
        except Exception:
            pass

    discovered.sort(key=lambda path: path.as_posix().lower())
    return discovered


def dataset_preview_paths(image_paths: Sequence[Path], sample_size: int = DEFAULT_PREVIEW_SAMPLE_SIZE) -> list[str]:
    preview_size = max(sample_size, 0)
    return [str(path) for path in image_paths[:preview_size]]


def require_dataset_images(dataset_root: Path, image_paths: Sequence[Path] | None = None) -> list[Path]:
    """Validate dataset directory and raise a clear error when no images are present."""
    if not dataset_root.exists() or not dataset_root.is_dir():
        raise DatasetNotFoundError(f"Dataset directory does not exist: {dataset_root}")

    if image_paths is None:
        image_paths = discover_images(dataset_root)

    if image_paths:
        if isinstance(image_paths, list):
            return image_paths
        return list(image_paths)

    extensions = ", ".join(sorted(SUPPORTED_IMAGE_EXTENSIONS))
    raise DatasetNotFoundError(
        "No supported image files were found in dataset directory "
        f"'{dataset_root}'. Expected recursive files with extensions: {extensions}"
    )


def discover_paired_images(dataset_root: Path) -> List[Tuple[Path, Path]]:
    a_dir = dataset_root / "paired_images" / "A"
    b_dir = dataset_root / "paired_images" / "B"
    if not a_dir.exists() or not b_dir.exists():
        return []

    a_files = {p.name: p for p in a_dir.rglob("*") if p.is_file() and is_image_file(p)}
    b_files = {p.name: p for p in b_dir.rglob("*") if p.is_file() and is_image_file(p)}

    shared_names = sorted(set(a_files.keys()) & set(b_files.keys()))
    if shared_names:
        return [(a_files[name], b_files[name]) for name in shared_names]

    # Fallback: pair by sorted order when names do not match.
    a_sorted = sorted(a_files.values())
    b_sorted = sorted(b_files.values())
    return list(zip(a_sorted, b_sorted))


def compute_dataset_signature(paths: Iterable[Path]) -> dict:
    hasher = hashlib.sha1()
    count = 0
    iterable = paths if isinstance(paths, Sequence) else sorted(paths)
    for path in iterable:
        try:
            stat = path.stat()
        except OSError:
            continue
        payload = f"{path.as_posix()}|{stat.st_mtime_ns}|{stat.st_size}".encode("utf-8")
        hasher.update(payload)
        count += 1

    return {"count": count, "digest": hasher.hexdigest()}


def load_rgb_image(path: Path) -> Image.Image:
    with Image.open(path) as img:
        return img.convert("RGB")


def validate_image_file(path: Path) -> tuple[bool, str | None]:
    if not path.exists():
        return False, f"File not found: {path}"
    if not path.is_file():
        return False, f"Not a file: {path}"
    if not is_image_file(path):
        return False, f"Unsupported image extension for file: {path}"

    try:
        with Image.open(path) as img:
            img.verify()
    except Exception as exc:  # noqa: BLE001
        return False, f"Invalid image file {path}: {exc}"

    return True, None


def user_mode_message(image_count: int) -> str:
    if image_count == 0:
        return "Dataset is empty. Please add images to continue."
    return f"Detected {image_count} local dataset images. Local semantic search enabled."


def env_flag(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}
