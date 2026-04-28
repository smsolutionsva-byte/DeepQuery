from __future__ import annotations

from pathlib import Path


class ReverseImageSearcher:
    _BLOCKED_RESULT_HINTS = (
        "danbooru",
        "gelbooru",
        "anime-pictures",
        "yande.re",
        "sankakucomplex",
        "e-shuushuu",
        "konachan",
        "zerochan",
    )

    def __init__(self) -> None:
        self._client = None

    def _ensure_client(self) -> None:
        if self._client is not None:
            return

        try:
            from PicImageSearch.sync import Iqdb as IqdbSync
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(
                "PicImageSearch is unavailable. Install requirements and verify network access."
            ) from exc

        self._client = IqdbSync()

    def search(self, image_path: Path, top_k: int = 5, include_portal_links: bool = False) -> list[dict]:
        self._ensure_client()
        assert self._client is not None

        try:
            resp = self._client.search(file=str(image_path))
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(f"Reverse image search failed for {image_path}: {exc}") from exc

        results: list[dict] = []
        raw_results = list(getattr(resp, "raw", []) or [])

        for item in raw_results[:top_k]:
            url = getattr(item, "url", "")
            if not url:
                continue
            if any(blocked in str(url).lower() for blocked in self._BLOCKED_RESULT_HINTS):
                continue
            results.append(
                {
                    "url": url,
                    "source": getattr(item, "source", ""),
                    "similarity": getattr(item, "similarity", ""),
                    "thumbnail": getattr(item, "thumbnail", ""),
                    "description": getattr(item, "content", ""),
                }
            )

        if include_portal_links:
            for attr in ["saucenao_url", "ascii2d_url", "tineye_url", "google_url", "url"]:
                link = getattr(resp, attr, "")
                if link:
                    results.append(
                        {
                            "url": link,
                            "source": attr,
                            "similarity": "",
                            "thumbnail": "",
                            "description": "search portal link",
                        }
                    )

        return results[: max(top_k, 5)]

    def search_by_url(self, image_url: str, top_k: int = 5, include_portal_links: bool = False) -> list[dict]:
        self._ensure_client()
        assert self._client is not None

        try:
            resp = self._client.search(url=str(image_url))
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(f"Reverse image search failed for URL {image_url}: {exc}") from exc

        results: list[dict] = []
        raw_results = list(getattr(resp, "raw", []) or [])

        for item in raw_results[:top_k]:
            url = getattr(item, "url", "")
            if not url:
                continue
            if any(blocked in str(url).lower() for blocked in self._BLOCKED_RESULT_HINTS):
                continue
            results.append(
                {
                    "url": url,
                    "source": getattr(item, "source", ""),
                    "similarity": getattr(item, "similarity", ""),
                    "thumbnail": getattr(item, "thumbnail", ""),
                    "description": getattr(item, "content", ""),
                }
            )

        if include_portal_links:
            for attr in ["saucenao_url", "ascii2d_url", "tineye_url", "google_url", "url"]:
                link = getattr(resp, attr, "")
                if link:
                    results.append(
                        {
                            "url": link,
                            "source": attr,
                            "similarity": "",
                            "thumbnail": "",
                            "description": "search portal link",
                        }
                    )

        return results[: max(top_k, 5)]
