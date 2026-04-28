from __future__ import annotations

from pathlib import Path
from typing import Callable, Iterable, Sequence

import numpy as np
import open_clip
import torch
from PIL import Image
from tqdm import tqdm


class ClipEmbedder:
    def __init__(
        self,
        model_name: str = "ViT-B-32",
        pretrained: str = "laion2b_s34b_b79k",
        device: str | None = None,
        batch_size: int = 16,
    ) -> None:
        self.model_name = model_name
        self.pretrained = pretrained
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.batch_size = max(batch_size, 1)

        self.model = None
        self.preprocess = None
        self.tokenizer = open_clip.get_tokenizer(model_name)
        self.embedding_dim: int | None = None

    def _ensure_loaded(self) -> None:
        if self.model is not None and self.preprocess is not None:
            return

        model, _, preprocess = open_clip.create_model_and_transforms(
            self.model_name,
            pretrained=self.pretrained,
            device=self.device,
        )
        model.eval()
        self.model = model
        self.preprocess = preprocess
        self.embedding_dim = int(getattr(model, "text_projection").shape[-1])

    @staticmethod
    def _batched(items: Sequence[Path], batch_size: int) -> Iterable[Sequence[Path]]:
        for i in range(0, len(items), batch_size):
            yield items[i : i + batch_size]

    @staticmethod
    def _normalize(features: torch.Tensor) -> torch.Tensor:
        return features / features.norm(dim=-1, keepdim=True).clamp(min=1e-12)

    def encode_text(self, texts: str | list[str]) -> np.ndarray:
        self._ensure_loaded()
        assert self.model is not None

        if isinstance(texts, str):
            texts = [texts]

        tokens = self.tokenizer(texts).to(self.device)
        with torch.no_grad():
            feats = self.model.encode_text(tokens)
            feats = self._normalize(feats)
        return feats.cpu().numpy().astype("float32")

    def encode_image(self, image_path: Path) -> np.ndarray:
        self._ensure_loaded()
        assert self.model is not None and self.preprocess is not None

        with Image.open(image_path) as img:
            tensor = self.preprocess(img.convert("RGB")).unsqueeze(0).to(self.device)

        with torch.no_grad():
            feats = self.model.encode_image(tensor)
            feats = self._normalize(feats)
        return feats.cpu().numpy().astype("float32")

    def encode_pil_image(self, image: Image.Image) -> np.ndarray:
        self._ensure_loaded()
        assert self.model is not None and self.preprocess is not None

        tensor = self.preprocess(image.convert("RGB")).unsqueeze(0).to(self.device)

        with torch.no_grad():
            feats = self.model.encode_image(tensor)
            feats = self._normalize(feats)
        return feats.cpu().numpy().astype("float32")

    def encode_images(
        self,
        image_paths: list[Path],
        progress_desc: str = "Embedding dataset images",
        progress_callback: Callable[[int, int, Path | None], None] | None = None,
    ) -> tuple[np.ndarray, list[Path]]:
        self._ensure_loaded()
        assert self.model is not None and self.preprocess is not None

        all_embeddings: list[np.ndarray] = []
        valid_paths: list[Path] = []
        total_images = len(image_paths)
        total_batches = (total_images + self.batch_size - 1) // self.batch_size if total_images else 0
        processed_images = 0

        for batch_paths in tqdm(
            self._batched(image_paths, self.batch_size),
            total=total_batches,
            desc=progress_desc,
        ):
            batch_tensors: list[torch.Tensor] = []
            batch_valid_paths: list[Path] = []

            for path in batch_paths:
                try:
                    with Image.open(path) as img:
                        batch_tensors.append(self.preprocess(img.convert("RGB")))
                    batch_valid_paths.append(path)
                except Exception as exc:  # noqa: BLE001
                    print(f"Warning: failed to load image {path}: {exc}")

            if not batch_tensors:
                continue

            batch = torch.stack(batch_tensors, dim=0).to(self.device)
            with torch.no_grad():
                feats = self.model.encode_image(batch)
                feats = self._normalize(feats)
            all_embeddings.append(feats.cpu().numpy().astype("float32"))
            valid_paths.extend(batch_valid_paths)
            processed_images += len(batch_paths)

            if progress_callback is not None:
                current_path = batch_valid_paths[-1] if batch_valid_paths else (batch_paths[-1] if batch_paths else None)
                try:
                    progress_callback(min(processed_images, total_images), total_images, current_path)
                except Exception:
                    pass

            del batch
            if torch.cuda.is_available() and self.device.startswith("cuda"):
                torch.cuda.empty_cache()

        if not all_embeddings:
            dim = self.embedding_dim or 512
            return np.empty((0, dim), dtype="float32"), []

        return np.concatenate(all_embeddings, axis=0), valid_paths
