from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from setuptools import Command, find_packages, setup


def read_requirements(requirements_path: Path) -> list[str]:
    if not requirements_path.exists():
        return []

    lines: list[str] = []
    for line in requirements_path.read_text(encoding="utf-8").splitlines():
        text = line.strip()
        if not text or text.startswith("#"):
            continue
        lines.append(text)
    return lines


class InitProjectCommand(Command):
    description = "Install requirements, validate runtime, create dataset placeholder, and warm up models."
    user_options: list[tuple[str, str, str]] = []

    def initialize_options(self) -> None:
        pass

    def finalize_options(self) -> None:
        pass

    def run(self) -> None:
        project_root = Path(__file__).resolve().parent
        requirements_file = project_root / "requirements.txt"

        print("[setup] Installing requirements...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", str(requirements_file)])

        print("[setup] Checking PyTorch / GPU availability...")
        import torch

        print(f"[setup] torch version: {torch.__version__}")
        print(f"[setup] cuda available: {torch.cuda.is_available()}")
        if torch.cuda.is_available():
            print(f"[setup] gpu name: {torch.cuda.get_device_name(0)}")

        print("[setup] Creating dataset folder structure...")
        from utils.file_loader import ensure_dataset_structure

        ensure_dataset_structure(project_root)

        print("[setup] Preparing FAISS index placeholder...")
        search_index_dir = project_root / "search_index"
        search_index_dir.mkdir(parents=True, exist_ok=True)
        placeholder = search_index_dir / "index_meta.json"
        if not placeholder.exists():
            placeholder.write_text(
                '{\n  "dimension": 0,\n  "image_paths": [],\n  "signature": {"count": 0, "digest": ""}\n}\n',
                encoding="utf-8",
            )

        output_dir = project_root / "output"
        output_dir.mkdir(parents=True, exist_ok=True)

        print("[setup] Downloading / warming CLIP model...")
        try:
            from models.clip_model import ClipEmbedder

            clip = ClipEmbedder(batch_size=1)
            _ = clip.encode_text("satellite image")
            print("[setup] CLIP model is ready.")
        except Exception as exc:  # noqa: BLE001
            print(f"[setup] Warning: failed to warm CLIP model: {exc}")

        print("[setup] Downloading / warming BLIP model...")
        try:
            from PIL import Image

            from models.blip_model import BlipCaptioner

            captioner = BlipCaptioner()
            dummy = output_dir / "_setup_dummy.jpg"
            Image.new("RGB", (32, 32), color=(128, 128, 128)).save(dummy)
            _ = captioner.caption_image(dummy)
            dummy.unlink(missing_ok=True)
            print("[setup] BLIP model is ready.")
        except Exception as exc:  # noqa: BLE001
            print(f"[setup] Warning: failed to warm BLIP model: {exc}")

        print("[setup] Setup completed.")


ROOT = Path(__file__).resolve().parent
REQUIREMENTS = read_requirements(ROOT / "requirements.txt")

setup(
    name="satellite-image-intelligence",
    version="0.1.0",
    description="Modular local satellite image intelligence pipeline",
    packages=find_packages(),
    py_modules=["main"],
    install_requires=REQUIREMENTS,
    cmdclass={"init_project": InitProjectCommand},
)
