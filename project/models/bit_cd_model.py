from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image


class BitCDModel:
    def __init__(
        self,
        bit_repo_path: Path,
        output_dir: Path,
        project_name: str = "BIT_LEVIR",
        checkpoint_name: str = "best_ckpt.pt",
    ) -> None:
        self.bit_repo_path = bit_repo_path
        self.output_dir = output_dir
        self.project_name = project_name
        self.checkpoint_name = checkpoint_name

        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _bit_assets_ready(self) -> tuple[bool, str]:
        demo_path = self.bit_repo_path / "demo.py"
        ckpt_path = self.bit_repo_path / "checkpoints" / self.project_name / self.checkpoint_name

        if not self.bit_repo_path.exists():
            return False, f"BIT-CD repository not found at: {self.bit_repo_path}"
        if not demo_path.exists():
            return False, f"BIT-CD demo entrypoint not found: {demo_path}"
        if not ckpt_path.exists():
            return False, f"BIT-CD checkpoint not found: {ckpt_path}"

        return True, ""

    def _save_runtime_pair(self, image_a: Path, image_b: Path) -> tuple[str, str, bool]:
        samples_dir = self.bit_repo_path / "samples"
        (samples_dir / "A").mkdir(parents=True, exist_ok=True)
        (samples_dir / "B").mkdir(parents=True, exist_ok=True)
        (samples_dir / "list").mkdir(parents=True, exist_ok=True)

        pair_name = f"runtime_pair_{int(time.time())}.png"
        list_file = samples_dir / "list" / "demo.txt"

        with Image.open(image_a) as img_a:
            img_a.convert("RGB").save(samples_dir / "A" / pair_name)
        with Image.open(image_b) as img_b:
            img_b.convert("RGB").save(samples_dir / "B" / pair_name)

        previous = ""
        had_previous = list_file.exists()
        if list_file.exists():
            previous = list_file.read_text(encoding="utf-8")

        list_file.write_text(pair_name + "\n", encoding="utf-8")
        return pair_name, previous, had_previous

    def _restore_demo_list(self, previous_content: str) -> None:
        list_file = self.bit_repo_path / "samples" / "list" / "demo.txt"
        list_file.write_text(previous_content, encoding="utf-8")

    def _run_bit_demo(self) -> subprocess.CompletedProcess[str]:
        cmd = [
            sys.executable,
            "demo.py",
            "--project_name",
            self.project_name,
            "--checkpoint_root",
            "checkpoints",
            "--checkpoint_name",
            self.checkpoint_name,
            "--output_folder",
            str(self.output_dir),
        ]
        return subprocess.run(
            cmd,
            cwd=str(self.bit_repo_path),
            capture_output=True,
            text=True,
            check=False,
        )

    def _fallback_change_map(self, image_a: Path, image_b: Path, output_path: Path) -> Path:
        with Image.open(image_a) as a_img, Image.open(image_b) as b_img:
            a = a_img.convert("RGB")
            b = b_img.convert("RGB").resize(a.size)

            a_arr = np.asarray(a, dtype=np.float32)
            b_arr = np.asarray(b, dtype=np.float32)
            diff = np.mean(np.abs(a_arr - b_arr), axis=2)
            mask = diff > 35.0

            overlay = np.asarray(b, dtype=np.uint8).copy()
            overlay[mask] = [255, 0, 0]
            result = Image.fromarray(overlay)
            result.save(output_path)

        return output_path

    def detect_changes(
        self,
        image_a: Path,
        image_b: Path,
        output_name: str = "highlighted_changes.png",
    ) -> tuple[Path, bool, str]:
        output_path = self.output_dir / output_name

        assets_ok, error_msg = self._bit_assets_ready()
        if not assets_ok:
            fallback = self._fallback_change_map(image_a, image_b, output_path)
            return fallback, False, f"{error_msg}. Used fallback pixel-difference map instead."

        pair_name = ""
        previous_list = ""
        had_previous_list = False
        try:
            pair_name, previous_list, had_previous_list = self._save_runtime_pair(image_a=image_a, image_b=image_b)
            result = self._run_bit_demo()
            if result.returncode != 0:
                fallback = self._fallback_change_map(image_a, image_b, output_path)
                msg = (
                    "BIT-CD inference failed. "
                    f"stderr: {result.stderr.strip() or 'no stderr'}. "
                    "Used fallback pixel-difference map instead."
                )
                return fallback, False, msg

            bit_output = self.output_dir / pair_name
            if not bit_output.exists():
                fallback = self._fallback_change_map(image_a, image_b, output_path)
                return fallback, False, "BIT-CD finished but output file was not generated. Used fallback map."

            with Image.open(bit_output) as pred:
                pred.convert("L").save(output_path)
            if bit_output != output_path and bit_output.exists():
                bit_output.unlink(missing_ok=True)
            return output_path, True, "BIT-CD change map generated successfully."

        except Exception as exc:  # noqa: BLE001
            fallback = self._fallback_change_map(image_a, image_b, output_path)
            return fallback, False, f"BIT-CD pipeline error: {exc}. Used fallback map."

        finally:
            if had_previous_list:
                self._restore_demo_list(previous_list)
