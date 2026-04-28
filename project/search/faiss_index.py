from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable, List, Tuple

import faiss
import numpy as np


class FaissIndexManager:
    def __init__(self, index_dir: Path, embedding_dim: int) -> None:
        self.index_dir = index_dir
        self.embedding_dim = embedding_dim
        self.index_path = self.index_dir / "image_index.faiss"
        self.meta_path = self.index_dir / "index_meta.json"
        self.index_dir.mkdir(parents=True, exist_ok=True)
        self._index: faiss.Index | None = None
        self._image_paths: list[str] = []

    @staticmethod
    def _l2_normalize(vectors: np.ndarray) -> np.ndarray:
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        norms = np.clip(norms, 1e-12, None)
        return vectors / norms

    @property
    def has_persisted_index(self) -> bool:
        return self.index_path.exists() and self.meta_path.exists()

    def has_loaded_index(self) -> bool:
        return self._index is not None and self._index.ntotal > 0

    def load(self) -> None:
        if not self.has_persisted_index:
            return

        self._index = faiss.read_index(str(self.index_path))
        metadata = json.loads(self.meta_path.read_text(encoding="utf-8"))
        self._image_paths = metadata.get("image_paths", [])

    def save(self, signature: dict) -> None:
        if self._index is None:
            raise RuntimeError("Cannot save FAISS index before it is built.")

        faiss.write_index(self._index, str(self.index_path))
        payload = {
            "dimension": self.embedding_dim,
            "image_paths": self._image_paths,
            "signature": signature,
        }
        self.meta_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def is_stale(self, signature: dict) -> bool:
        if not self.meta_path.exists():
            return True

        metadata = json.loads(self.meta_path.read_text(encoding="utf-8"))
        old_sig = metadata.get("signature", {})
        return old_sig.get("digest") != signature.get("digest") or old_sig.get("count") != signature.get("count")

    def build(self, embeddings: np.ndarray, image_paths: Iterable[Path], signature: dict) -> None:
        if embeddings.size == 0:
            self._index = None
            self._image_paths = []
            if self.index_path.exists():
                self.index_path.unlink()
            payload = {
                "dimension": self.embedding_dim,
                "image_paths": [],
                "signature": signature,
            }
            self.meta_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            return

        vectors = embeddings.astype("float32", copy=False)
        vectors = self._l2_normalize(vectors)

        index = faiss.IndexFlatIP(self.embedding_dim)
        index.add(vectors)

        self._index = index
        self._image_paths = [str(p) for p in image_paths]
        self.save(signature=signature)

    def search(self, query_embedding: np.ndarray, top_k: int = 5) -> List[Tuple[str, float]]:
        if self._index is None or self._index.ntotal == 0:
            return []

        query = np.asarray(query_embedding, dtype="float32").reshape(1, -1)
        query = self._l2_normalize(query)

        k = min(top_k, len(self._image_paths))
        scores, indices = self._index.search(query, k)

        results: list[tuple[str, float]] = []
        for idx, score in zip(indices[0], scores[0]):
            if idx < 0 or idx >= len(self._image_paths):
                continue
            results.append((self._image_paths[idx], float(score)))
        return results
