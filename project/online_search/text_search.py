from __future__ import annotations

import contextlib
import io
import urllib.parse
import warnings
from typing import Any


warnings.filterwarnings("ignore", category=RuntimeWarning)


class OnlineTextSearcher:
    _BLOCKED_URL_SUBSTRINGS = (
        "google.com/search",
        "scholar.google.com",
        "bing.com/search",
        "duckduckgo.com",
        "earthobservatory.nasa.gov/search",
        "wikipedia.org/w/index.php?search=",
    )

    def __init__(self) -> None:
        self._clients: list[tuple[str, Any]] = []
        self._fallback_client: tuple[str, Any] | None = None

    def _ensure_clients(self) -> None:
        if self._clients:
            return

        clients: list[tuple[str, Any]] = []

        try:
            from ddgs import DDGS as DDGSRenamed  # type: ignore

            clients.append(("ddgs", DDGSRenamed()))
        except Exception:
            pass

        warnings.filterwarnings(
            "ignore",
            message=r"This package \(`duckduckgo_search`\) has been renamed to `ddgs`!.*",
            category=RuntimeWarning,
        )

        if not clients:
            fallback = self._get_fallback_client()
            if fallback is not None:
                clients.append(fallback)

        if not clients:
            raise RuntimeError("duckduckgo-search is unavailable. Install dependencies and verify network access.")

        self._clients = clients

    def _get_fallback_client(self) -> tuple[str, Any] | None:
        if self._fallback_client is not None:
            return self._fallback_client

        warnings.filterwarnings(
            "ignore",
            message=r"This package \(`duckduckgo_search`\) has been renamed to `ddgs`!.*",
            category=RuntimeWarning,
        )

        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                with contextlib.redirect_stderr(io.StringIO()):
                    from duckduckgo_search import DDGS as DuckDuckGoSearchDDGS

                    self._fallback_client = ("duckduckgo_search", DuckDuckGoSearchDDGS())
        except Exception:
            self._fallback_client = None

        return self._fallback_client

    @staticmethod
    def _expand_query(query: str) -> str:
        q = query.strip()
        q_lower = q.lower()
        extras: list[str] = []

        if any(k in q_lower for k in ["temperature", "hot", "heat", "warmer", "warming"]):
            extras.extend([
                "urban heat island",
                "climate",
                "vegetation loss",
                "satellite",
            ])

        if "bengaluru" in q_lower or "bangalore" in q_lower:
            extras.extend(["Bengaluru", "Karnataka", "city climate"])

        if not extras:
            return q

        return f"{q} {' '.join(extras)}"

    @staticmethod
    def _clean_text(value: Any) -> str:
        return " ".join(str(value or "").split()).strip()

    @classmethod
    def _is_blocked_url(cls, url: str) -> bool:
        lowered = url.lower()
        return any(fragment in lowered for fragment in cls._BLOCKED_URL_SUBSTRINGS)

    @staticmethod
    def _normalized_url_key(url: str) -> str:
        parsed = urllib.parse.urlsplit(url.strip())
        path = parsed.path.rstrip("/")
        return urllib.parse.urlunsplit(
            (parsed.scheme.lower(), parsed.netloc.lower(), path, parsed.query, "")
        )

    @classmethod
    def _format_result(cls, item: dict[str, Any], source: str) -> dict[str, str] | None:
        url = cls._clean_text(item.get("href") or item.get("url"))
        if not url or cls._is_blocked_url(url):
            return None

        title = cls._clean_text(item.get("title"))
        snippet = cls._clean_text(item.get("body") or item.get("snippet") or item.get("description"))

        if not title:
            title = url
        if not snippet:
            snippet = "No summary snippet available."

        return {
            "title": title,
            "url": url,
            "snippet": snippet,
            "source": source,
        }

    @classmethod
    def _dedupe(cls, results: list[dict[str, str]]) -> list[dict[str, str]]:
        seen: set[str] = set()
        out: list[dict[str, str]] = []
        for item in results:
            url = item.get("url", "").strip()
            key = cls._normalized_url_key(url)
            if not key or key in seen:
                continue
            seen.add(key)
            out.append(item)
        return out

    @staticmethod
    def _normalize_image_key(url: str) -> str:
        parsed = urllib.parse.urlsplit(url.strip())
        path = parsed.path.rstrip("/")
        return urllib.parse.urlunsplit(
            (parsed.scheme.lower(), parsed.netloc.lower(), path, parsed.query, "")
        )

    def _search_backend(self, client: Any, query: str, max_results: int, source: str) -> list[dict[str, str]]:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", category=RuntimeWarning)
            raw_results = list(
                client.text(
                    query,
                    region="in-en",
                    safesearch="moderate",
                    max_results=max_results,
                )
            )

        formatted: list[dict[str, str]] = []
        for item in raw_results:
            if not isinstance(item, dict):
                continue
            result = self._format_result(item=item, source=source)
            if result is not None:
                formatted.append(result)

        return formatted

    def _search_image_backend(
        self,
        client: Any,
        query: str,
        max_results: int,
        source: str,
    ) -> list[dict[str, Any]]:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", category=RuntimeWarning)
            raw_results = list(
                client.images(
                    query,
                    region="in-en",
                    safesearch="moderate",
                    max_results=max_results,
                )
            )

        formatted: list[dict[str, Any]] = []
        for item in raw_results:
            if not isinstance(item, dict):
                continue

            image_url = self._clean_text(item.get("image"))
            page_url = self._clean_text(item.get("url"))
            title = self._clean_text(item.get("title"))
            if not image_url:
                continue

            formatted.append(
                {
                    "title": title or image_url,
                    "image_url": image_url,
                    "page_url": page_url,
                    "thumbnail": self._clean_text(item.get("thumbnail")),
                    "width": item.get("width"),
                    "height": item.get("height"),
                    "source": source,
                }
            )

        return formatted

    @classmethod
    def _dedupe_images(cls, results: list[dict[str, Any]]) -> list[dict[str, Any]]:
        seen: set[str] = set()
        out: list[dict[str, Any]] = []
        for item in results:
            url = str(item.get("image_url") or "").strip()
            key = cls._normalize_image_key(url)
            if not key or key in seen:
                continue
            seen.add(key)
            out.append(item)
        return out

    @staticmethod
    def _expand_image_query(query: str) -> list[str]:
        base = " ".join(str(query or "").split()).strip()
        if not base:
            return []

        focused = f"{base} satellite image aerial map"
        if focused == base:
            return [base]
        return [focused, base]

    def search(self, query: str, max_results: int = 8) -> list[dict[str, str]]:
        self._ensure_clients()

        text_query = self._clean_text(query)
        if not text_query:
            return []

        target_results = min(max(max_results, 5), 10)
        search_queries = [text_query]
        expanded_query = self._expand_query(text_query)
        if expanded_query != text_query:
            search_queries.append(expanded_query)

        formatted: list[dict[str, str]] = []
        backend_result_cap = max(target_results * 3, 10)

        for source, client in self._clients:
            for search_query in search_queries:
                try:
                    formatted.extend(
                        self._search_backend(
                            client=client,
                            query=search_query,
                            max_results=backend_result_cap,
                            source=source,
                        )
                    )
                except Exception:
                    continue

                formatted = self._dedupe(formatted)
                if len(formatted) >= target_results:
                    return formatted[:target_results]

        fallback = self._get_fallback_client()
        if fallback is not None and fallback not in self._clients:
            source, client = fallback
            for search_query in search_queries:
                try:
                    formatted.extend(
                        self._search_backend(
                            client=client,
                            query=search_query,
                            max_results=backend_result_cap,
                            source=source,
                        )
                    )
                except Exception:
                    continue

                formatted = self._dedupe(formatted)
                if len(formatted) >= target_results:
                    return formatted[:target_results]

        return self._dedupe(formatted)[:target_results]

    def search_images(self, query: str, max_results: int = 5) -> list[dict[str, Any]]:
        self._ensure_clients()

        search_queries = self._expand_image_query(query)
        if not search_queries:
            return []

        target_results = max(max_results, 1)
        backend_result_cap = max(target_results * 3, 10)
        formatted: list[dict[str, Any]] = []

        for source, client in self._clients:
            for search_query in search_queries:
                try:
                    formatted.extend(
                        self._search_image_backend(
                            client=client,
                            query=search_query,
                            max_results=backend_result_cap,
                            source=source,
                        )
                    )
                except Exception:
                    continue

                formatted = self._dedupe_images(formatted)
                if len(formatted) >= target_results:
                    return formatted[:target_results]

        fallback = self._get_fallback_client()
        if fallback is not None and fallback not in self._clients:
            source, client = fallback
            for search_query in search_queries:
                try:
                    formatted.extend(
                        self._search_image_backend(
                            client=client,
                            query=search_query,
                            max_results=backend_result_cap,
                            source=source,
                        )
                    )
                except Exception:
                    continue

                formatted = self._dedupe_images(formatted)
                if len(formatted) >= target_results:
                    return formatted[:target_results]

        return self._dedupe_images(formatted)[:target_results]
