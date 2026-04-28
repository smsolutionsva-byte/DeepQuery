from __future__ import annotations

import argparse
import re
import sys
import traceback
from pathlib import Path
from typing import Callable, Optional

from PIL import Image

from models.bit_cd_model import BitCDModel
from models.blip_model import BlipCaptioner
from models.clip_model import ClipEmbedder
from online_search.article_images import ArticleImageCollector
from online_search.reverse_search import ReverseImageSearcher
from online_search.text_search import OnlineTextSearcher
from search.faiss_index import FaissIndexManager
from utils.file_loader import (
    DatasetNotFoundError,
    compute_dataset_signature,
    dataset_preview_paths,
    discover_images,
    ensure_dataset_structure,
    require_dataset_images,
    validate_image_file,
)
from visualization.graphs import GraphBuilder


class SatelliteImageIntelligenceSystem:
    _MAX_URL_IMAGES_PER_QUERY = 3
    _DATASET_PREVIEW_COUNT = 5
    _TOPIC_KEYWORDS = {
        "climate": [
            "heat",
            "temperature",
            "climate",
            "warming",
            "rainfall",
            "urban heat",
            "vegetation",
            "flood",
            "drought",
            "weather",
            "heatwave",
        ],
        "education": [
            "university",
            "college",
            "campus",
            "student",
            "degree",
            "faculty",
            "school",
            "department",
        ],
        "geography": [
            "location",
            "city",
            "country",
            "region",
            "district",
            "state",
            "where is",
            "map",
        ],
        "infrastructure": [
            "roads",
            "road",
            "bridges",
            "bridge",
            "buildings",
            "building",
            "development",
            "vehicles",
            "vehicle",
            "ships",
            "ship",
            "port",
            "harbor",
            "harbour",
            "coast",
            "coastal",
            "infrastructure",
        ],
        "environment": [
            "deforestation",
            "mining",
            "forest",
            "vegetation",
            "land",
            "land cover",
            "land use",
            "illegal mining",
            "unauthorized",
            "suspicious",
        ],
    }
    _TOPIC_PRIORITY = ["education", "environment", "climate", "infrastructure", "geography"]
    _OBJECT_ACTION_KEYWORDS = ["find", "detect", "locate", "identify", "show"]
    _OBJECT_TARGET_KEYWORDS = [
        "bridge",
        "bridges",
        "vehicle",
        "vehicles",
        "ship",
        "ships",
        "road",
        "roads",
        "building",
        "buildings",
    ]
    _CHANGE_KEYWORDS = ["pattern", "change", "movement", "deforestation", "expansion", "ship movement"]
    _PATTERN_KEYWORDS = ["cluster", "clusters", "density", "pattern", "distribution"]
    _RISK_KEYWORDS = ["risk", "flood", "chance", "chances", "probability", "probabilities"]
    _ANOMALY_KEYWORDS = ["illegal", "mining", "unauthorized", "suspicious"]
    _QUERY_TARGET_KEYWORDS = [
        "bridges",
        "bridge",
        "vehicles",
        "vehicle",
        "ships",
        "ship",
        "roads",
        "road",
        "buildings",
        "building",
        "deforestation",
        "expansion",
        "clusters",
        "cluster",
        "density",
        "flood",
        "flooding",
        "mining",
        "forest",
        "vegetation",
        "coast",
        "coastal",
    ]

    def __init__(self, project_root: Path, offline_processing: bool = False, fast_mode: bool = False) -> None:
        self.project_root = project_root
        self.offline_processing = offline_processing
        self.fast_mode = fast_mode
        self.dataset_root = ensure_dataset_structure(project_root)
        self.output_dir = self.project_root / "output"
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.search_index_dir = self.project_root / "search_index"
        self.search_index_dir.mkdir(parents=True, exist_ok=True)

        self.bit_repo_path = self.project_root.parent / "BIT_CD-master"

        self.clip_model: ClipEmbedder | None = None
        self.blip_model: BlipCaptioner | None = None
        self.bit_model: BitCDModel | None = None
        self.reverse_searcher: ReverseImageSearcher | None = None
        self.text_searcher: OnlineTextSearcher | None = None
        self.article_image_collector: ArticleImageCollector | None = None
        self.graph_builder = GraphBuilder()

        self.local_image_paths: list[Path] = []
        self.faiss_manager: FaissIndexManager | None = None

    def _get_clip_model(self) -> ClipEmbedder:
        if self.clip_model is None:
            self.clip_model = ClipEmbedder(batch_size=16)
        return self.clip_model

    def _get_blip_model(self) -> BlipCaptioner:
        if self.blip_model is None:
            self.blip_model = BlipCaptioner()
        return self.blip_model

    def _get_bit_model(self) -> BitCDModel:
        if self.bit_model is None:
            self.bit_model = BitCDModel(
                bit_repo_path=self.bit_repo_path,
                output_dir=self.output_dir / "change_detection",
            )
        return self.bit_model

    def _get_reverse_searcher(self) -> ReverseImageSearcher:
        if self.reverse_searcher is None:
            self.reverse_searcher = ReverseImageSearcher()
        return self.reverse_searcher

    def _get_text_searcher(self) -> OnlineTextSearcher:
        if self.text_searcher is None:
            self.text_searcher = OnlineTextSearcher()
        return self.text_searcher

    def _get_article_image_collector(self) -> ArticleImageCollector:
        if self.article_image_collector is None:
            temp_root = self.project_root / "temp_downloads" if self.offline_processing else None
            self.article_image_collector = ArticleImageCollector(temp_root=temp_root)
        return self.article_image_collector

    def _print_dataset_summary(self, image_paths: list[Path]) -> None:
        print(f"Dataset root: {self.dataset_root}")
        print(f"Total dataset images found: {len(image_paths)}")
        samples = dataset_preview_paths(image_paths, sample_size=self._DATASET_PREVIEW_COUNT)
        if not samples:
            return

        print("Sample image paths:")
        for sample in samples:
            print(f" - {sample}")

    def refresh_local_dataset_index(
        self,
        progress_callback: Callable[[str, int, str, Path | None], None] | None = None,
    ) -> None:
        def emit(stage: str, progress: int, message: str, current_file: Path | None = None) -> None:
            if progress_callback is None:
                return
            try:
                progress_callback(stage, max(0, min(progress, 100)), message, current_file)
            except Exception:
                pass

        if self.local_image_paths:
            emit(
                "scanning",
                6,
                f"Using cached dataset image list ({len(self.local_image_paths)} images).",
                self.local_image_paths[0],
            )
        else:
            emit("scanning", 2, "Scanning dataset directories...")

            def on_scan_progress(scanned_files: int, current_path: Path | None) -> None:
                scan_progress = 2 + min(6, scanned_files // 2500)
                emit(
                    "scanning",
                    scan_progress,
                    f"Scanning dataset files ({scanned_files} checked)...",
                    current_path,
                )

            discovered_paths = discover_images(self.dataset_root, progress_callback=on_scan_progress)
            emit(
                "scanning",
                6,
                f"Discovered {len(discovered_paths)} supported images.",
                discovered_paths[0] if discovered_paths else None,
            )
            self.local_image_paths = require_dataset_images(
                dataset_root=self.dataset_root,
                image_paths=discovered_paths,
            )
        self._print_dataset_summary(self.local_image_paths)
        emit(
            "scanning",
            10,
            f"Dataset validated with {len(self.local_image_paths)} images.",
            self.local_image_paths[0] if self.local_image_paths else None,
        )

        signature = compute_dataset_signature(self.local_image_paths)

        try:
            clip = self._get_clip_model()
            dim = int(clip.encode_text("satellite").shape[1])
            if self.faiss_manager is None:
                self.faiss_manager = FaissIndexManager(index_dir=self.search_index_dir, embedding_dim=dim)

            if self.faiss_manager.has_persisted_index and not self.faiss_manager.is_stale(signature):
                self.faiss_manager.load()
                print("Loaded existing FAISS index for local dataset.")
                emit("indexing", 58, "Loaded existing FAISS index from disk.")
                return

            print("Building / refreshing FAISS index from detected dataset images...")
            emit("indexing", 15, "Building FAISS index from dataset images...")

            def on_embedding_progress(processed: int, total: int, current_path: Path | None) -> None:
                if total <= 0:
                    pct = 45
                else:
                    pct = 15 + int((processed / total) * 35)
                emit(
                    "indexing",
                    pct,
                    f"Embedding dataset images ({processed}/{total})",
                    current_path,
                )

            embeddings, valid_paths = clip.encode_images(
                self.local_image_paths,
                progress_callback=on_embedding_progress,
            )

            if not valid_paths:
                print("Warning: dataset images were found, but none were valid for embedding.")
                self.faiss_manager.build(embeddings=embeddings, image_paths=[], signature=signature)
                emit("indexing", 62, "No valid images were embeddable for indexing.")
                return

            self.faiss_manager.build(embeddings=embeddings, image_paths=valid_paths, signature=signature)
            print(f"FAISS index built with {len(valid_paths)} images.")
            emit("indexing", 62, f"FAISS index refreshed with {len(valid_paths)} images.")

        except Exception as exc:  # noqa: BLE001
            print(f"Model loading failure while preparing local search: {exc}")
            print("Local search disabled for this run; online modules remain available.")
            self.faiss_manager = None
            emit("indexing", 62, f"Local index preparation failed: {exc}")

    def _select_file_with_tkinter(self, title: str) -> Optional[Path]:
        try:
            import tkinter as tk
            from tkinter import filedialog

            root = tk.Tk()
            root.withdraw()
            root.attributes("-topmost", True)
            file_path = filedialog.askopenfilename(
                title=title,
                filetypes=[
                    ("Image files", "*.jpg *.jpeg *.png *.tif *.tiff"),
                    ("All files", "*.*"),
                ],
            )
            root.destroy()
            if not file_path:
                return None
            return Path(file_path)
        except Exception as exc:  # noqa: BLE001
            print(f"Warning: Tkinter file picker unavailable ({exc}). Falling back to CLI path input.")
            return None

    def _prompt_image_path(self, prompt: str) -> Optional[Path]:
        use_picker = input("Use Tkinter file picker? [y/N]: ").strip().lower() in {"y", "yes"}
        if use_picker:
            selected = self._select_file_with_tkinter(title=prompt)
            if selected is not None:
                return selected

        raw = input(f"{prompt} (path): ").strip().strip('"')
        if not raw:
            return None
        return Path(raw)

    def _search_local_with_text(self, query: str, top_k: int = 5) -> list[tuple[Path, float]]:
        self.refresh_local_dataset_index()
        if self.faiss_manager is None or not self.faiss_manager.has_loaded_index():
            return []

        query_embedding = self._get_clip_model().encode_text(query)[0]
        results = self.faiss_manager.search(query_embedding, top_k=top_k)
        return [(Path(p), score) for p, score in results]

    def _search_local_with_image(self, image_path: Path, top_k: int = 5) -> list[tuple[Path, float]]:
        self.refresh_local_dataset_index()
        if self.faiss_manager is None or not self.faiss_manager.has_loaded_index():
            return []

        query_embedding = self._get_clip_model().encode_image(image_path)[0]
        results = self.faiss_manager.search(query_embedding, top_k=top_k)
        return [(Path(p), score) for p, score in results]

    def _generate_captions(self, image_paths: list[Path]) -> dict[str, str]:
        captions: dict[str, str] = {}
        if not image_paths:
            return captions

        captioner = self._get_blip_model()
        for path in image_paths:
            try:
                caption = captioner.caption_image(path)
                captions[str(path)] = caption
            except Exception as exc:  # noqa: BLE001
                captions[str(path)] = f"Captioning failed: {exc}"
        return captions

    def _run_reverse_search(
        self,
        image_path: Path | None = None,
        image_url: str | None = None,
        top_k: int = 5,
        include_portal_links: bool = False,
    ) -> list[dict]:
        try:
            searcher = self._get_reverse_searcher()
            if image_url:
                return searcher.search_by_url(
                    image_url=image_url,
                    top_k=top_k,
                    include_portal_links=include_portal_links,
                )
            if image_path is None:
                return []
            return searcher.search(image_path=image_path, top_k=top_k, include_portal_links=include_portal_links)
        except Exception as exc:  # noqa: BLE001
            print(f"Network failure or reverse search error: {exc}")
            return []

    def _build_graphs(self) -> tuple[list[Path], str]:
        if self.fast_mode:
            return [], "Fast mode enabled: graph generation skipped for this run."

        try:
            if not self.local_image_paths:
                self.local_image_paths = discover_images(self.dataset_root)
            return self.graph_builder.build_timeline_graphs(
                image_paths=self.local_image_paths,
                output_dir=self.output_dir / "graphs",
                prefix="dataset",
                temperature_csv=self.dataset_root / "temperature.csv",
            )
        except Exception as exc:  # noqa: BLE001
            return [], f"Graph generation failed: {exc}"

    def _run_online_text_search(self, query: str, top_k: int = 8) -> list[dict]:
        print("Running real web search...")
        print("Extracting results...")
        try:
            searcher = self._get_text_searcher()
            refs = searcher.search(query=query, max_results=min(max(top_k, 5), 10))
            print(f"Found {len(refs)} valid references.")
            return refs
        except Exception as exc:  # noqa: BLE001
            print(f"Online text search failed: {exc}")
            return []

    def _run_online_image_search(self, query: str, top_k: int = 5) -> list[dict]:
        try:
            searcher = self._get_text_searcher()
            return searcher.search_images(query=query, max_results=top_k)
        except Exception as exc:  # noqa: BLE001
            print(f"Online image search failed: {exc}")
            return []

    def _extract_article_image_urls(self, online_references: list[dict], max_images: int = 5) -> list[str]:
        try:
            collector = self._get_article_image_collector()
            return collector.extract_image_urls(
                references=online_references,
                max_results=max_images,
                extra_candidates=max_images * 2,
            )
        except Exception as exc:  # noqa: BLE001
            print(f"Article image extraction failed: {exc}")
            return []

    def _combine_visual_candidate_urls(
        self,
        article_image_urls: list[str],
        image_search_results: list[dict],
        max_candidates: int = 10,
    ) -> list[dict]:
        collector = self._get_article_image_collector()
        combined: list[dict] = []
        seen: set[str] = set()

        for item in image_search_results:
            if not self._image_result_has_environmental_signal(item):
                continue

            try:
                width = int(item.get("width") or 0)
            except (TypeError, ValueError):
                width = 0
            if width and width < 200:
                continue

            image_url = str(item.get("image_url") or "").strip()
            key = collector._normalize_key(image_url)
            if not image_url or key in seen or not collector._is_valid_image_url(image_url):
                continue
            seen.add(key)
            combined.append(
                {
                    "image_url": image_url,
                    "title": str(item.get("title") or "").strip(),
                    "page_url": str(item.get("page_url") or "").strip(),
                    "source_type": "image_search",
                }
            )
            if len(combined) >= max_candidates:
                return combined

        for image_url in article_image_urls:
            image_url = str(image_url or "").strip()
            key = collector._normalize_key(image_url)
            if not image_url or key in seen or not collector._is_valid_image_url(image_url):
                continue
            seen.add(key)
            combined.append(
                {
                    "image_url": image_url,
                    "title": image_url,
                    "page_url": image_url,
                    "source_type": "article_page",
                }
            )
            if len(combined) >= max_candidates:
                return combined

        return combined

    def _load_visual_images_from_urls(self, image_candidates: list[dict], max_images: int = 3) -> list[dict]:
        if not image_candidates:
            return []

        try:
            collector = self._get_article_image_collector()
            return collector.fetch_images_in_memory(image_candidates=image_candidates, max_results=max_images)
        except Exception as exc:  # noqa: BLE001
            print(f"Image URL loading failed: {exc}")
            return []

    @staticmethod
    def _normalized_query_text(query_text: str) -> str:
        return " ".join(str(query_text or "").lower().split())

    @classmethod
    def _keyword_score(cls, text: str, keywords: list[str]) -> int:
        score = 0
        for keyword in keywords:
            if keyword in text:
                score += 2 if " " in keyword else 1
        return score

    def detect_topic(self, query_text: str) -> str:
        text = self._normalized_query_text(query_text)
        if not text:
            return "general"

        topic_scores = {
            topic: self._keyword_score(text, keywords)
            for topic, keywords in self._TOPIC_KEYWORDS.items()
        }
        best_score = max(topic_scores.values(), default=0)
        if best_score <= 0:
            return "general"

        for topic in self._TOPIC_PRIORITY:
            if topic_scores.get(topic, 0) == best_score:
                return topic
        return "general"

    def detect_task(self, query_text: str) -> str:
        text = self._normalized_query_text(query_text)
        if not text:
            return "INFORMATION_QUERY"

        has_action = any(keyword in text for keyword in self._OBJECT_ACTION_KEYWORDS)
        has_object_target = any(keyword in text for keyword in self._OBJECT_TARGET_KEYWORDS)

        if any(keyword in text for keyword in self._ANOMALY_KEYWORDS):
            return "ANOMALY_DETECTION"
        if any(keyword in text for keyword in self._RISK_KEYWORDS):
            return "RISK_ANALYSIS"
        if any(keyword in text for keyword in self._CHANGE_KEYWORDS):
            return "CHANGE_DETECTION"
        if any(keyword in text for keyword in self._PATTERN_KEYWORDS):
            return "PATTERN_ANALYSIS"
        if has_action and has_object_target:
            return "OBJECT_DETECTION"
        return "INFORMATION_QUERY"

    def _extract_query_targets(self, query_text: str) -> list[str]:
        text = self._normalized_query_text(query_text)
        targets: list[str] = []
        canonical_forms = {
            "bridges": "bridges",
            "bridge": "bridges",
            "vehicles": "vehicles",
            "vehicle": "vehicles",
            "ships": "ships",
            "ship": "ships",
            "roads": "roads",
            "road": "roads",
            "buildings": "buildings",
            "building": "buildings",
            "clusters": "clusters",
            "cluster": "clusters",
            "flooding": "flood",
        }
        for keyword in self._QUERY_TARGET_KEYWORDS:
            canonical = canonical_forms.get(keyword, keyword)
            if keyword in text and canonical not in targets:
                targets.append(canonical)
        return targets[:4]

    @staticmethod
    def _join_labels(items: list[str]) -> str:
        if not items:
            return ""
        if len(items) == 1:
            return items[0]
        if len(items) == 2:
            return f"{items[0]} and {items[1]}"
        return f"{', '.join(items[:-1])}, and {items[-1]}"

    def _should_run_visual_pipeline(self, topic: str, task: str) -> bool:
        if task in {
            "OBJECT_DETECTION",
            "CHANGE_DETECTION",
            "PATTERN_ANALYSIS",
            "RISK_ANALYSIS",
            "ANOMALY_DETECTION",
        }:
            return True
        return topic in {"climate", "environment", "infrastructure"}

    def _should_run_graph_pipeline(self, topic: str, task: str) -> bool:
        if task in {"CHANGE_DETECTION", "PATTERN_ANALYSIS", "RISK_ANALYSIS"}:
            return True
        if task in {"OBJECT_DETECTION", "ANOMALY_DETECTION"}:
            return False
        return topic in {"climate", "environment", "infrastructure"}

    def _build_visual_search_query(self, query: str, topic: str, task: str) -> str:
        base = " ".join(query.split()).strip()
        if not base:
            return query

        if task == "OBJECT_DETECTION":
            return f"{base} aerial image satellite image"
        if task == "CHANGE_DETECTION":
            return f"{base} satellite image map land cover before after"
        if task == "PATTERN_ANALYSIS":
            return f"{base} aerial image map distribution density"
        if task == "RISK_ANALYSIS":
            if "flood" in base.lower():
                return f"{base} flood risk map satellite image"
            return f"{base} risk map satellite image"
        if task == "ANOMALY_DETECTION":
            return f"{base} satellite image land use anomaly mining map"
        if topic in {"climate", "environment"}:
            return f"{base} satellite image map vegetation land cover"
        if topic == "infrastructure":
            return f"{base} aerial image satellite image infrastructure"
        return base

    @staticmethod
    def _caption_has_environmental_signal(caption: str) -> bool:
        keep_keywords = [
            "urban",
            "city",
            "road",
            "bridge",
            "vehicle",
            "ship",
            "vessel",
            "coast",
            "coastal",
            "port",
            "harbor",
            "harbour",
            "satellite",
            "map",
            "vegetation",
            "forest",
            "building",
            "land",
            "infrastructure",
            "aerial",
            "heat",
            "climate",
            "temperature",
            "rooftop",
            "residential",
            "diagram",
            "flood",
            "mining",
            "damage",
            "cluster",
            "density",
            "distribution",
        ]
        lowered = caption.lower()
        return any(keyword in lowered for keyword in keep_keywords)

    @staticmethod
    def _caption_has_rejection_signal(caption: str) -> bool:
        reject_keywords = [
            "person",
            "people",
            "woman",
            "man",
            "logo",
            "banner",
            "advertisement",
            "portrait",
            "face",
            "clothing",
            "shirt",
            "dress",
            "selfie",
        ]
        lowered = caption.lower()
        return any(keyword in lowered for keyword in reject_keywords)

    @staticmethod
    def _image_result_has_environmental_signal(item: dict) -> bool:
        keywords = [
            "urban",
            "bridge",
            "vehicle",
            "ship",
            "coast",
            "coastal",
            "port",
            "harbor",
            "harbour",
            "satellite",
            "map",
            "vegetation",
            "forest",
            "building",
            "land",
            "infrastructure",
            "aerial",
            "heat",
            "climate",
            "temperature",
            "city",
            "road",
            "flood",
            "mining",
            "cluster",
            "density",
            "distribution",
            "damage",
        ]
        text = " ".join(
            [
                str(item.get("title") or ""),
                str(item.get("page_url") or ""),
            ]
        ).lower()
        return any(keyword in text for keyword in keywords)

    def _filter_visual_evidence(
        self,
        loaded_items: list[dict],
        image_captions: dict[str, str],
        max_images: int = 3,
    ) -> tuple[list[dict], dict[str, str]]:
        kept_items: list[dict] = []
        kept_captions: dict[str, str] = {}

        for item in loaded_items:
            image_url = str(item.get("image_url") or "").strip()
            caption = str(image_captions.get(image_url, "") or "").strip()
            metadata_text = " ".join(
                [
                    caption,
                    str(item.get("title") or ""),
                    str(item.get("page_url") or ""),
                    str(item.get("source_type") or ""),
                ]
            )
            is_caption_failure = not caption or caption.lower().startswith("captioning failed:")
            should_reject = (
                is_caption_failure
                or self._caption_has_rejection_signal(metadata_text)
                or not self._caption_has_environmental_signal(metadata_text)
                or len(kept_items) >= max_images
            )

            if should_reject:
                image_obj = item.get("image")
                if image_obj is not None:
                    del image_obj
                continue

            kept_items.append(item)
            kept_captions[image_url] = caption

        return kept_items, kept_captions

    @staticmethod
    def _shorten_text(text: str, limit: int = 180) -> str:
        cleaned = " ".join(text.split()).strip()
        if len(cleaned) <= limit:
            return cleaned

        clipped = cleaned[: limit - 3].rsplit(" ", 1)[0].rstrip(" ,;:")
        return f"{clipped}..."

    @staticmethod
    def _safe_console_text(text: object) -> str:
        value = str(text)
        encoding = getattr(sys.stdout, "encoding", None) or "utf-8"
        return value.encode(encoding, errors="replace").decode(encoding, errors="replace")

    @staticmethod
    def _split_sentences(text: str) -> list[str]:
        cleaned = " ".join(str(text or "").split()).strip()
        if not cleaned:
            return []
        return [segment.strip() for segment in re.split(r"(?<=[.!?])\s+", cleaned) if segment.strip()]

    @staticmethod
    def _is_geographic_noise_sentence(sentence: str) -> bool:
        lowered = sentence.lower()
        blocked_terms = [
            "latitude",
            "longitude",
            "elevation",
            "coordinates",
            "coord",
            "above sea level",
            "north latitude",
            "east longitude",
        ]
        coordinate_patterns = [
            r"\b\d{1,3}\.\d+\s*[ns]\b",
            r"\b\d{1,3}\.\d+\s*[ew]\b",
            r"\b\d{1,3}°\s*\d{1,2}",
            r"\b\d{1,3}\s*km\b",
        ]
        return any(term in lowered for term in blocked_terms) or any(
            re.search(pattern, lowered) for pattern in coordinate_patterns
        )

    def _extract_environmental_sentences(self, online_references: list[dict]) -> list[str]:
        keywords = [
            "temperature",
            "urban",
            "vegetation",
            "deforestation",
            "heat",
            "climate",
            "expansion",
            "pollution",
            "infrastructure",
            "green cover",
            "concrete",
            "warming",
            "tree",
            "land-use",
            "land use",
            "built-up",
        ]

        filtered: list[str] = []
        seen: set[str] = set()

        for item in online_references:
            title = str(item.get("title") or "").strip()
            snippet = str(item.get("snippet") or "").strip()
            candidate_text = f"{title}. {snippet}"

            for sentence in self._split_sentences(candidate_text):
                lowered = sentence.lower()
                if not any(keyword in lowered for keyword in keywords):
                    continue
                if self._is_geographic_noise_sentence(sentence):
                    continue

                cleaned = self._shorten_text(sentence.rstrip("."))
                if not cleaned:
                    continue

                normalized_key = cleaned.lower()
                if normalized_key in seen:
                    continue

                seen.add(normalized_key)
                filtered.append(cleaned)

        return filtered[:5]

    @staticmethod
    def _extract_reasoning_bullets(
        filtered_sentences: list[str],
        visual_captions: dict[str, str],
    ) -> list[str]:
        evidence_text = " ".join(filtered_sentences).lower()
        visual_text = " ".join(visual_captions.values()).lower()
        combined = f"{evidence_text} {visual_text}"

        bullets: list[str] = []

        if any(
            keyword in combined
            for keyword in ["tree", "vegetation", "green cover", "deforestation", "minimal vegetation"]
        ):
            bullets.append("Tree loss and reduced vegetation reduce evaporative cooling.")

        if any(
            keyword in combined
            for keyword in ["urban", "concrete", "infrastructure", "built-up", "construction", "road"]
        ):
            bullets.append("Urban concrete and built infrastructure retain heat.")

        if any(
            keyword in combined
            for keyword in ["expansion", "land-use", "land use", "urbanisation", "urbanization", "warming"]
        ):
            bullets.append("Land-use change and urban expansion increase local temperature.")

        if any(keyword in combined for keyword in ["pollution", "climate", "temperature", "heatwave"]):
            bullets.append("Climate stress and pollution can intensify heat exposure.")

        return bullets[:4]

    @staticmethod
    def _summarize_visual_captions(visual_captions: dict[str, str]) -> str | None:
        visual_text = " ".join(visual_captions.values()).lower()
        if not visual_text:
            return None

        has_urban = any(keyword in visual_text for keyword in ["urban", "building", "infrastructure", "road", "city"])
        has_low_vegetation = any(
            keyword in visual_text
            for keyword in ["minimal vegetation", "little vegetation", "reduced vegetation", "no vegetation"]
        )
        has_vegetation = any(keyword in visual_text for keyword in ["vegetation", "forest", "green", "farmland"])

        if has_urban and has_low_vegetation:
            return "URL-based visual evidence suggests dense built surfaces with limited vegetation."
        if has_urban and has_vegetation:
            return "URL-based visual evidence shows urban development alongside vegetation change."
        if has_urban:
            return "URL-based visual evidence highlights dense urban infrastructure."
        return None

    def _scientific_reasoning(
        self,
        query: str,
        captions: dict[str, str],
        online_references: list[dict],
    ) -> str:
        del query

        filtered_sentences = self._extract_environmental_sentences(online_references)
        bullets = self._extract_reasoning_bullets(
            filtered_sentences=filtered_sentences,
            visual_captions=captions,
        )
        visual_summary = self._summarize_visual_captions(captions)

        lines: list[str] = []

        if bullets:
            lines.append("Retrieved sources indicate:")
            for bullet in bullets:
                lines.append(f"- {bullet}")
            lines.append("These causes align with urban heat island theory.")
        elif filtered_sentences:
            lines.append("Retrieved sources indicate:")
            for sentence in filtered_sentences[:3]:
                lines.append(f"- {sentence.rstrip('.')}.")
        else:
            lines.append("Retrieved sources indicate limited climate-specific evidence in this run.")

        if visual_summary:
            lines.append(visual_summary)

        if online_references:
            lines.append("Conclusion is supported by filtered online references.")
        else:
            lines.append("Conclusion uses available local evidence; online references were unavailable in this run.")

        return "\n".join(lines)

    def _reference_highlights(self, online_references: list[dict], limit: int = 3) -> list[str]:
        highlights: list[str] = []
        for item in online_references:
            title = str(item.get("title") or "").strip()
            snippet = self._shorten_text(str(item.get("snippet") or "").strip())
            if title and snippet:
                highlights.append(f"{title}: {snippet}")
            elif title:
                highlights.append(title)
            elif snippet:
                highlights.append(snippet)

            if len(highlights) >= limit:
                break
        return highlights

    def _education_summary(self, query: str, online_references: list[dict]) -> str:
        lines = [f"{query.strip()} is being treated as an education-related query."]
        highlights = self._reference_highlights(online_references, limit=3)
        if highlights:
            lines.append("Retrieved references suggest the institution or campus context includes:")
            for highlight in highlights:
                lines.append(f"- {highlight}")
        else:
            lines.append("No institutional references were available in this run.")
        return "\n".join(lines)

    def _geography_summary(self, query: str, online_references: list[dict]) -> str:
        lines = [f"{query.strip()} is being treated as a geography or location-related query."]
        highlights = self._reference_highlights(online_references, limit=3)
        if highlights:
            lines.append("Top retrieved location cues include:")
            for highlight in highlights:
                lines.append(f"- {highlight}")
        else:
            lines.append("No geographic references were available in this run.")
        return "\n".join(lines)

    def _infrastructure_summary(
        self,
        query: str,
        online_references: list[dict],
        visual_captions: dict[str, str],
    ) -> str:
        lines = [f"{query.strip()} is being treated as an infrastructure-related query."]
        highlights = self._reference_highlights(online_references, limit=3)
        if highlights:
            lines.append("Retrieved infrastructure context includes:")
            for highlight in highlights:
                lines.append(f"- {highlight}")
        visual_summary = self._summarize_visual_captions(visual_captions)
        if visual_summary:
            lines.append(visual_summary)
        if not highlights and not visual_summary:
            lines.append("No strong infrastructure evidence was available in this run.")
        return "\n".join(lines)

    def _environment_summary(
        self,
        query: str,
        online_references: list[dict],
        visual_captions: dict[str, str],
    ) -> str:
        lines = [f"{query.strip()} is being treated as an environment-related query."]
        filtered_sentences = self._extract_environmental_sentences(online_references)
        if filtered_sentences:
            lines.append("Retrieved environmental signals include:")
            for sentence in filtered_sentences[:3]:
                lines.append(f"- {sentence.rstrip('.')}.")
        visual_summary = self._summarize_visual_captions(visual_captions)
        if visual_summary:
            lines.append(visual_summary)
        if not filtered_sentences and not visual_summary:
            lines.append("No strong environmental evidence was available in this run.")
        return "\n".join(lines)

    def _urban_growth_loss_summary(
        self,
        query: str,
        online_references: list[dict],
        visual_captions: dict[str, str],
    ) -> str | None:
        text = self._normalized_query_text(query)
        if not any(keyword in text for keyword in [
            "bengaluru",
            "bangalore",
            "urban growth",
            "vegetation loss",
            "green cover",
            "urban expansion",
            "vegetation",
        ]):
            return None

        filtered_sentences = self._extract_environmental_sentences(online_references)
        visual_summary = self._summarize_visual_captions(visual_captions)

        lines: list[str] = [
            "The query is focused on urban growth and vegetation loss in a rapidly expanding city.",
            "Rapid urban expansion often replaces green spaces, wetlands, and agricultural land with built infrastructure.",
            "This process typically reduces tree cover, disrupts local drainage, and increases surface heat in the city.",
        ]

        if visual_summary:
            lines.append(visual_summary)

        if filtered_sentences:
            lines.append("Relevant evidence from online references includes:")
            for sentence in filtered_sentences[:3]:
                lines.append(f"- {sentence.rstrip('.')}.")
        elif online_references:
            top_ref = self._reference_highlights(online_references, limit=1)
            if top_ref:
                lines.append("Reference context suggests the city is experiencing a mix of built environment growth and green cover change.")
                lines.append(f"- {top_ref[0]}")

        lines.append(
            "In short, Bengaluru's urban growth is likely linked to increasing built-up area and a corresponding reduction in natural vegetation cover."
        )
        return "\n".join(lines)

    def _generic_reference_summary(self, online_references: list[dict]) -> str:
        highlights = self._reference_highlights(online_references, limit=3)
        if not highlights:
            return "No online references were available to summarize in this run."

        lines = ["Top retrieved references include:"]
        for highlight in highlights:
            lines.append(f"- {highlight}")
        return "\n".join(lines)

    def _task_routing_summary(
        self,
        query: str,
        topic: str,
        task: str,
        online_references: list[dict],
        visual_captions: dict[str, str],
    ) -> tuple[str, str]:
        targets = self._extract_query_targets(query)
        target_text = self._join_labels(targets)
        highlights = self._reference_highlights(online_references, limit=2)
        visual_summary = self._summarize_visual_captions(visual_captions)

        if task == "OBJECT_DETECTION":
            lines = [
                "Routing to object detection model...",
                "Recommended model: YOLOv8.",
            ]
            if target_text:
                lines.append(f"Target objects inferred from query: {target_text}.")
            lines.append(
                "Current text-query mode retrieves references and filtered visual evidence as context; direct detection requires imagery."
            )
            return "Task Routing", "\n".join(lines)

        if task == "CHANGE_DETECTION":
            lines = [
                "Routing to change detection model...",
                "Recommended model: BIT (Bitemporal Image Transformer).",
            ]
            if target_text:
                lines.append(f"Change targets inferred from query: {target_text}.")
            lines.append(
                "Direct BIT execution requires paired temporal images; use change-detection image mode for actual BIT-CD inference."
            )
            if highlights:
                lines.append("Context from retrieved references:")
                for highlight in highlights:
                    lines.append(f"- {highlight}")
            return "Task Routing", "\n".join(lines)

        if task == "PATTERN_ANALYSIS":
            lines = ["Analyzing spatial distribution for the requested pattern."]
            if target_text:
                lines.append(f"Focus entities inferred from query: {target_text}.")
            if visual_summary:
                lines.append(visual_summary)
            if highlights:
                lines.append("Retrieved reference context:")
                for highlight in highlights:
                    lines.append(f"- {highlight}")
            if len(lines) == 1:
                lines.append("Additional imagery or structured detections would improve the pattern analysis.")
            return "Pattern Analysis", "\n".join(lines)

        if task == "RISK_ANALYSIS":
            lines = ["Generating risk analysis..."]
            if "flood" in self._normalized_query_text(query):
                lines[0] = "Generating flood risk analysis..."
            if topic == "climate":
                climate_summary = self._scientific_reasoning(
                    query=query,
                    captions=visual_captions,
                    online_references=online_references,
                )
                lines.append(climate_summary)
            elif highlights:
                lines.append("Retrieved risk context:")
                for highlight in highlights:
                    lines.append(f"- {highlight}")
            lines.append("Current mode provides evidence-based screening; a calibrated predictive risk model is not yet integrated.")
            return "Risk Analysis", "\n".join(lines)

        if task == "ANOMALY_DETECTION":
            lines = [
                "Routing to anomaly detection workflow...",
                "This task looks for unusual or unauthorized spatial patterns such as illegal mining or suspicious land use.",
            ]
            if target_text:
                lines.append(f"Anomaly targets inferred from query: {target_text}.")
            if visual_summary:
                lines.append(visual_summary)
            if highlights:
                lines.append("Retrieved reference context:")
                for highlight in highlights:
                    lines.append(f"- {highlight}")
            lines.append("Dedicated anomaly scoring would require imagery and a trained anomaly detector.")
            return "Anomaly Analysis", "\n".join(lines)

        return "Reference Summary", self._generic_reference_summary(online_references)

    def _generate_context_aware_reasoning(
        self,
        query: str,
        topic: str,
        task: str,
        visual_captions: dict[str, str],
        online_references: list[dict],
    ) -> tuple[str, str]:
        if task != "INFORMATION_QUERY":
            return self._task_routing_summary(
                query=query,
                topic=topic,
                task=task,
                online_references=online_references,
                visual_captions=visual_captions,
            )

        urban_summary = self._urban_growth_loss_summary(
            query=query,
            online_references=online_references,
            visual_captions=visual_captions,
        )
        if urban_summary is not None:
            return "Urban Growth Summary", urban_summary

        if topic == "education":
            return "Institutional Summary", self._education_summary(query, online_references)
        if topic == "climate":
            return "Scientific Reasoning", self._scientific_reasoning(query, visual_captions, online_references)
        if topic == "geography":
            return "Location Summary", self._geography_summary(query, online_references)
        if topic == "infrastructure":
            return "Infrastructure Analysis", self._infrastructure_summary(query, online_references, visual_captions)
        if topic == "environment":
            return "Environmental Summary", self._environment_summary(query, online_references, visual_captions)
        return "Reference Summary", self._generic_reference_summary(online_references)

    def _print_search_output(
        self,
        matches: list[tuple[Path, float]],
        captions: dict[str, str],
        online_references: list[dict],
        graph_paths: list[Path],
        graph_summary: str,
        detected_topic: str | None = None,
        detected_task: str | None = None,
        visual_evidence_paths: list[str] | None = None,
        visual_captions: dict[str, str] | None = None,
        reverse_links: list[dict] | None = None,
        reverse_search_message: str | None = None,
        reasoning_title: str = "Scientific Reasoning",
        reasoning: str | None = None,
    ) -> None:
        visual_evidence_paths = visual_evidence_paths or []
        visual_captions = visual_captions or {}
        reverse_links = reverse_links or []

        if detected_topic is not None:
            print("\n=== Detected Topic ===")
            print(self._safe_console_text(detected_topic))

        if detected_task is not None:
            print("\n=== Detected Task ===")
            print(self._safe_console_text(detected_task))

        print("\n=== Online References ===")
        if not online_references:
            print("No online references found.")
        else:
            for idx, item in enumerate(online_references, start=1):
                title = self._safe_console_text(item.get("title", ""))
                url = self._safe_console_text(item.get("url", ""))
                snippet = self._safe_console_text(item.get("snippet", ""))
                print(f"{idx}. {title}")
                print(f"   {url}")
                if snippet:
                    print(f"   {snippet}")

        print("\n=== Visual Evidence ===")
        if not visual_evidence_paths:
            print("No visual evidence image URLs were processed.")
        else:
            print("Processed Image URLs:")
            for path in visual_evidence_paths:
                print(self._safe_console_text(path))

        print("\n=== Image Captions ===")
        if not visual_captions:
            print("No image captions generated.")
        else:
            for path, caption in visual_captions.items():
                print(f"{self._safe_console_text(path)}:")
                print(f'   "{self._safe_console_text(caption)}"')

        print("\n=== Reverse Image Search Links ===")
        if reverse_search_message:
            print(reverse_search_message)
        elif not reverse_links:
            print("No reverse-search links available.")
        else:
            for idx, item in enumerate(reverse_links, start=1):
                print(f"{idx}. {self._safe_console_text(item.get('url', ''))}")
                source = self._safe_console_text(item.get("source", ""))
                similarity = self._safe_console_text(item.get("similarity", ""))
                if source or similarity:
                    print(f"   source={source} similarity={similarity}")

        print("\n=== Matching Dataset Images ===")
        if not matches:
            print("No local matches found in the indexed dataset.")
        else:
            for idx, (path, score) in enumerate(matches, start=1):
                print(f"{idx}. {self._safe_console_text(path)} (similarity={score:.4f})")

        print("\n=== Generated Captions ===")
        if not captions:
            print("No captions generated.")
        else:
            for path, caption in captions.items():
                print(f"- {self._safe_console_text(path)}: {self._safe_console_text(caption)}")

        print("\n=== Graph Outputs ===")
        if not graph_paths:
            print(self._safe_console_text(graph_summary))
        else:
            for graph in graph_paths:
                print(f"- {self._safe_console_text(graph)}")
            print(self._safe_console_text(graph_summary))

        if reasoning:
            print(f"\n=== {self._safe_console_text(reasoning_title)} ===")
            print(self._safe_console_text(reasoning))

    def run_query_mode_text(self, query: str, top_k: int = 5) -> None:
        filtered_visual_images: list[str] = []
        offline_query_dir: Path | None = None

        detected_topic = self.detect_topic(query)
        detected_task = self.detect_task(query)

        matches = self._search_local_with_text(query=query, top_k=top_k)
        match_paths = [path for path, _ in matches]
        captions = self._generate_captions(match_paths)

        online_references = self._run_online_text_search(query=query, top_k=max(top_k, 8))

        visual_captions: dict[str, str] = {}
        reverse_links: list[dict] = []
        reverse_search_message: str | None = None

        loaded_items: list[dict] = []
        if self._should_run_visual_pipeline(topic=detected_topic, task=detected_task):
            print("Extracting article images...")
            article_image_urls = self._extract_article_image_urls(
                online_references=online_references,
                max_images=8,
            )

            print("Searching image results...")
            image_search_query = self._build_visual_search_query(
                query=query,
                topic=detected_topic,
                task=detected_task,
            )
            image_search_results = self._run_online_image_search(query=image_search_query, top_k=5)

            image_candidates = self._combine_visual_candidate_urls(
                article_image_urls=article_image_urls,
                image_search_results=image_search_results,
                max_candidates=15,
            )

            if self.offline_processing:
                print("Offline processing mode selected. Downloading limited images locally...")
                try:
                    collector = self._get_article_image_collector()
                    offline_query_dir, downloaded_items = collector.download_images(
                        query=query,
                        image_candidates=image_candidates,
                        max_results=self._MAX_URL_IMAGES_PER_QUERY,
                    )
                except Exception as exc:  # noqa: BLE001
                    print(f"Offline image download failed: {exc}")
                    downloaded_items = []

                loaded_items = []
                for item in downloaded_items:
                    path = Path(str(item.get("path") or ""))
                    if not path.exists():
                        continue
                    try:
                        with Image.open(path) as img:
                            loaded_items.append(
                                {
                                    **item,
                                    "image_url": str(item.get("image_url") or ""),
                                    "image": img.convert("RGB"),
                                }
                            )
                    except Exception:
                        continue
            else:
                print("Loading images from URLs...")
                loaded_items = self._load_visual_images_from_urls(
                    image_candidates=image_candidates,
                    max_images=self._MAX_URL_IMAGES_PER_QUERY,
                )

            print("Generating captions from URL images...")
            raw_visual_captions: dict[str, str] = {}
            captioner = self._get_blip_model()
            clip = self._get_clip_model()
            for item in loaded_items:
                image_url = str(item.get("image_url") or "").strip()
                image = item.get("image")
                if image is None or not image_url:
                    continue
                try:
                    _ = clip.encode_pil_image(image)
                    raw_visual_captions[image_url] = captioner.caption_pil_image(image)
                except Exception as exc:  # noqa: BLE001
                    raw_visual_captions[image_url] = f"Captioning failed: {exc}"

            print("Filtering images...")
            filtered_visual_items, visual_captions = self._filter_visual_evidence(
                loaded_items=loaded_items,
                image_captions=raw_visual_captions,
                max_images=self._MAX_URL_IMAGES_PER_QUERY,
            )
            filtered_visual_images = [str(item.get("image_url") or "") for item in filtered_visual_items]

            print("Running reverse search...")
            if filtered_visual_items:
                reverse_links = self._run_reverse_search(
                    image_url=str(filtered_visual_items[0].get("image_url") or ""),
                    top_k=5,
                    include_portal_links=False,
                )
            else:
                reverse_search_message = "No valid image URLs available for reverse search."
        else:
            reverse_search_message = "Visual pipeline skipped for this information query."

        if self._should_run_graph_pipeline(topic=detected_topic, task=detected_task):
            graph_paths, graph_summary = self._build_graphs()
        else:
            graph_paths, graph_summary = [], "Graph pipeline skipped for this query type."

        reasoning_title, reasoning = self._generate_context_aware_reasoning(
            query=query,
            topic=detected_topic,
            task=detected_task,
            visual_captions=visual_captions,
            online_references=online_references,
        )

        self._print_search_output(
            matches=matches,
            captions=captions,
            online_references=online_references,
            detected_topic=detected_topic,
            detected_task=detected_task,
            visual_evidence_paths=filtered_visual_images,
            visual_captions=visual_captions,
            reverse_links=reverse_links,
            reverse_search_message=reverse_search_message,
            graph_paths=graph_paths,
            graph_summary=graph_summary,
            reasoning_title=reasoning_title,
            reasoning=reasoning,
        )

        for item in loaded_items:
            image_obj = item.get("image")
            if image_obj is not None:
                del image_obj

        if offline_query_dir is not None:
            try:
                collector = self._get_article_image_collector()
                collector.cleanup_query_directory(offline_query_dir)
            except Exception as exc:  # noqa: BLE001
                print(f"Offline cleanup failed: {exc}")

    def run_query_mode_image(self, image_path: Path, top_k: int = 5) -> None:
        valid, message = validate_image_file(image_path)
        if not valid:
            print(message)
            return

        matches = self._search_local_with_image(image_path=image_path, top_k=top_k)
        match_paths = [path for path, _ in matches]
        captions = self._generate_captions(match_paths)

        reverse_links = self._run_reverse_search(image_path=image_path, top_k=top_k)
        graph_paths, graph_summary = self._build_graphs()

        self._print_search_output(
            matches=matches,
            captions=captions,
            online_references=[],
            reverse_links=reverse_links,
            graph_paths=graph_paths,
            graph_summary=graph_summary,
        )

    def run_change_detection(self, image_a: Path, image_b: Path) -> None:
        valid_a, msg_a = validate_image_file(image_a)
        valid_b, msg_b = validate_image_file(image_b)
        if not valid_a:
            print(msg_a)
            return
        if not valid_b:
            print(msg_b)
            return

        try:
            bit = self._get_bit_model()
            output_path, used_bit, status_msg = bit.detect_changes(image_a=image_a, image_b=image_b)
            print("\n=== Change Detection Output ===")
            print(status_msg)
            print(f"Saved map: {output_path}")
            print(f"BIT-CD used: {used_bit}")
        except Exception as exc:  # noqa: BLE001
            print(f"Change detection failed: {exc}")
            traceback.print_exc()

    def startup_interface(self, top_k: int = 5) -> None:
        print("\nSatellite Image Intelligence System")
        print("Choose input mode:")
        print("1. Type a text query")
        print("2. Select an image file")
        print("3. Select two images for change detection")

        mode = input("Enter 1 / 2 / 3: ").strip()

        if mode == "1":
            text_query = input("Enter text query: ").strip()
            if not text_query:
                print("Empty query. Exiting.")
                return
            self.run_query_mode_text(query=text_query, top_k=top_k)
            return

        if mode == "2":
            image_path = self._prompt_image_path("Select query image")
            if image_path is None:
                print("No image selected. Exiting.")
                return
            self.run_query_mode_image(image_path=image_path, top_k=top_k)
            return

        if mode == "3":
            image_a = self._prompt_image_path("Select first image (time A)")
            image_b = self._prompt_image_path("Select second image (time B)")
            if image_a is None or image_b is None:
                print("Two images are required for change detection. Exiting.")
                return
            self.run_change_detection(image_a=image_a, image_b=image_b)
            return

        print("Invalid mode selection.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Modular satellite image intelligence system")
    parser.add_argument("--top-k", type=int, default=5, help="Number of top matches for retrieval")
    parser.add_argument(
        "--offline-processing",
        action="store_true",
        help="Enable legacy local image downloads for offline workflows.",
    )
    parser.add_argument(
        "--fast-mode",
        action="store_true",
        help="Enable fast mode to skip graph generation for large dataset workloads.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    project_root = Path(__file__).resolve().parent
    system = SatelliteImageIntelligenceSystem(
        project_root=project_root,
        offline_processing=args.offline_processing,
        fast_mode=args.fast_mode,
    )
    try:
        system.startup_interface(top_k=max(args.top_k, 1))
    except DatasetNotFoundError as exc:
        print(f"Dataset error: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
