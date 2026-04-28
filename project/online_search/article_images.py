from __future__ import annotations

from datetime import datetime
from io import BytesIO
from pathlib import Path
import re
import shutil
from typing import Any
import urllib.parse

import requests
from bs4 import BeautifulSoup
from PIL import Image


class ArticleImageCollector:
    _HTML_TIMEOUT = (5, 12)
    _IMAGE_TIMEOUT = (5, 20)
    _MIN_IMAGE_WIDTH = 200
    _BLOCKED_IMAGE_SCHEMES = ("data:", "javascript:")
    _BLOCKED_IMAGE_EXTENSIONS = (".svg", ".gif")
    _BLOCKED_IMAGE_HINTS = (
        "logo",
        "icon",
        "sprite",
        "favicon",
        "avatar",
        "scorecardresearch",
        "doubleclick",
        "tracking",
        "pixel",
        "share",
        "header",
        "footer",
        "banner",
        "trending",
        "twitter",
        "facebook",
        "instagram",
        "linkedin",
        "author",
        "profile",
    )
    _IMG_ATTRS = ("src", "data-src", "data-original", "data-lazy-src")

    def __init__(self, temp_root: Path | None = None) -> None:
        self.temp_root = temp_root
        if self.temp_root is not None:
            self.temp_root.mkdir(parents=True, exist_ok=True)
        self._session = requests.Session()
        self._session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
                )
            }
        )

    @staticmethod
    def _slugify_query(query: str) -> str:
        collapsed = re.sub(r"\s+", "_", query.strip().lower())
        cleaned = re.sub(r"[^a-z0-9_]+", "", collapsed).strip("_")
        return cleaned[:24] or "query"

    @staticmethod
    def _normalize_url(url: str, base_url: str | None = None) -> str:
        raw = str(url or "").strip()
        if not raw:
            return ""
        if base_url:
            raw = urllib.parse.urljoin(base_url, raw)
        return raw

    @classmethod
    def _is_valid_image_url(cls, url: str) -> bool:
        lowered = url.lower()
        if not lowered:
            return False
        if lowered.startswith(cls._BLOCKED_IMAGE_SCHEMES):
            return False
        if any(lowered.endswith(ext) for ext in cls._BLOCKED_IMAGE_EXTENSIONS):
            return False
        return not any(hint in lowered for hint in cls._BLOCKED_IMAGE_HINTS)

    @staticmethod
    def _normalize_key(url: str) -> str:
        parsed = urllib.parse.urlsplit(url)
        return urllib.parse.urlunsplit(
            (parsed.scheme.lower(), parsed.netloc.lower(), parsed.path.rstrip("/"), parsed.query, "")
        )

    @classmethod
    def _extract_meta_image(cls, soup: BeautifulSoup, page_url: str) -> list[str]:
        out: list[str] = []
        meta_specs = [
            {"property": "og:image"},
            {"name": "og:image"},
            {"property": "og:image:url"},
            {"name": "twitter:image"},
        ]
        for attrs in meta_specs:
            tag = soup.find("meta", attrs=attrs)
            if tag is None:
                continue
            candidate = cls._normalize_url(tag.get("content", ""), base_url=page_url)
            if cls._is_valid_image_url(candidate):
                out.append(candidate)
        return out

    @classmethod
    def _score_image_candidate(cls, candidate_url: str, tag: object) -> int:
        positive_hints = [
            "satellite",
            "map",
            "climate",
            "heat",
            "urban",
            "vegetation",
            "forest",
            "aerial",
            "land",
            "temperature",
            "infrastructure",
        ]
        negative_hints = [
            "logo",
            "author",
            "profile",
            "share",
            "twitter",
            "facebook",
            "instagram",
            "linkedin",
            "avatar",
            "icon",
        ]

        metadata_parts = [candidate_url]
        if hasattr(tag, "get"):
            metadata_parts.extend(
                [
                    str(tag.get("alt", "")),
                    str(tag.get("title", "")),
                    str(tag.get("class", "")),
                    str(tag.get("id", "")),
                ]
            )

        metadata = " ".join(metadata_parts).lower()
        score = sum(2 for hint in positive_hints if hint in metadata)
        score -= sum(3 for hint in negative_hints if hint in metadata)
        return score

    @classmethod
    def _extract_img_candidates(cls, soup: BeautifulSoup, page_url: str, limit: int = 6) -> list[str]:
        scored_candidates: list[tuple[int, str]] = []
        seen: set[str] = set()

        for tag in soup.find_all("img"):
            for attr in cls._IMG_ATTRS:
                candidate = cls._normalize_url(tag.get(attr, ""), base_url=page_url)
                key = cls._normalize_key(candidate)
                if cls._is_valid_image_url(candidate) and key not in seen:
                    seen.add(key)
                    scored_candidates.append((cls._score_image_candidate(candidate, tag), candidate))

            srcset = str(tag.get("srcset", "")).strip()
            if not srcset:
                continue

            for chunk in srcset.split(","):
                candidate = cls._normalize_url(chunk.strip().split(" ")[0], base_url=page_url)
                key = cls._normalize_key(candidate)
                if cls._is_valid_image_url(candidate) and key not in seen:
                    seen.add(key)
                    scored_candidates.append((cls._score_image_candidate(candidate, tag), candidate))

        scored_candidates.sort(key=lambda item: item[0], reverse=True)
        return [candidate for _, candidate in scored_candidates[:limit]]

    def extract_image_urls(
        self,
        references: list[dict],
        max_results: int = 5,
        extra_candidates: int = 10,
    ) -> list[str]:
        target_candidates = max(max_results + extra_candidates, max_results)
        collected: list[str] = []
        seen: set[str] = set()

        for item in references:
            article_url = str(item.get("url") or "").strip()
            if not article_url:
                continue

            try:
                response = self._session.get(article_url, timeout=self._HTML_TIMEOUT)
                response.raise_for_status()
            except requests.RequestException:
                continue

            content_type = str(response.headers.get("Content-Type", "")).lower()
            if "text/html" not in content_type:
                continue

            try:
                soup = BeautifulSoup(response.text, "html.parser")
            except Exception:
                continue

            candidates = self._extract_img_candidates(soup=soup, page_url=article_url, limit=4)
            candidates.extend(self._extract_meta_image(soup=soup, page_url=article_url))

            for candidate in candidates:
                key = self._normalize_key(candidate)
                if not key or key in seen:
                    continue
                seen.add(key)
                collected.append(candidate)
                if len(collected) >= target_candidates:
                    return collected

        return collected

    def fetch_images_in_memory(
        self,
        image_candidates: list[dict[str, Any]],
        max_results: int = 3,
    ) -> list[dict[str, Any]]:
        loaded: list[dict[str, Any]] = []

        for candidate in image_candidates:
            if len(loaded) >= max_results:
                break

            image_url = str(candidate.get("image_url") or candidate.get("url") or "").strip()
            if not image_url or not self._is_valid_image_url(image_url):
                continue

            try:
                response = self._session.get(image_url, timeout=self._IMAGE_TIMEOUT)
                response.raise_for_status()
            except requests.RequestException:
                continue

            content_type = str(response.headers.get("Content-Type", "")).split(";")[0].strip().lower()
            if not content_type.startswith("image/") or content_type.endswith("svg+xml"):
                continue

            try:
                image = Image.open(BytesIO(response.content)).convert("RGB")
            except Exception:
                continue

            width, height = image.size
            if width < self._MIN_IMAGE_WIDTH or height < self._MIN_IMAGE_WIDTH:
                del image
                continue

            loaded.append(
                {
                    **candidate,
                    "image_url": image_url,
                    "image": image,
                    "width": width,
                    "height": height,
                }
            )

        return loaded

    def create_query_directory(self, query: str) -> Path:
        if self.temp_root is None:
            raise RuntimeError("Offline download directory is not configured.")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        query_dir = self.temp_root / f"{self._slugify_query(query)}_{timestamp}"
        query_dir.mkdir(parents=True, exist_ok=True)
        return query_dir

    def download_images(
        self,
        query: str,
        image_candidates: list[dict[str, Any]],
        max_results: int = 5,
    ) -> tuple[Path, list[dict[str, Any]]]:
        query_dir = self.create_query_directory(query=query)
        downloaded: list[dict[str, Any]] = []

        for candidate in image_candidates:
            if len(downloaded) >= max_results:
                break

            image_url = str(candidate.get("image_url") or candidate.get("url") or "").strip()
            if not image_url:
                continue

            try:
                response = self._session.get(image_url, timeout=self._IMAGE_TIMEOUT)
                response.raise_for_status()
            except requests.RequestException:
                continue

            content_type = str(response.headers.get("Content-Type", "")).split(";")[0].strip().lower()
            if not content_type.startswith("image/") or content_type.endswith("svg+xml"):
                continue

            try:
                image = Image.open(BytesIO(response.content)).convert("RGB")
            except Exception:
                continue

            width, height = image.size
            if width < self._MIN_IMAGE_WIDTH or height < self._MIN_IMAGE_WIDTH:
                continue

            output_path = query_dir / f"img_{len(downloaded) + 1}.jpg"
            try:
                image.save(output_path, format="JPEG", quality=92)
            except Exception:
                continue

            downloaded.append(
                {
                    **candidate,
                    "image_url": image_url,
                    "path": output_path,
                    "width": width,
                    "height": height,
                }
            )

        return query_dir, downloaded

    def cleanup_query_directory(self, query_dir: Path | None) -> None:
        if query_dir is not None and query_dir.exists():
            shutil.rmtree(query_dir, ignore_errors=True)
        if self.temp_root is not None:
            self.temp_root.mkdir(parents=True, exist_ok=True)
