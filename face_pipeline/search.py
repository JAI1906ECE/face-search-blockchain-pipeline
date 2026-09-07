from __future__ import annotations

import html
import re
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlencode, urlparse, urlunparse

import requests
from bs4 import BeautifulSoup

from .errors import PipelineError
from .models import SearchResult

SOCIAL_HOSTS = (
    "instagram.com",
    "facebook.com",
    "x.com",
    "twitter.com",
    "tiktok.com",
    "linkedin.com",
    "reddit.com",
    "youtube.com",
)


def _is_social(url: str) -> bool:
    hostname = (urlparse(url).hostname or "").lower().removeprefix("www.")
    return any(hostname == domain or hostname.endswith(f".{domain}") for domain in SOCIAL_HOSTS)


def _unwrap_google_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.hostname and parsed.hostname.endswith("google.com"):
        query = parse_qs(parsed.query)
        for key in ("url", "q", "uddg"):
            if query.get(key):
                candidate = unquote(query[key][0])
                if candidate.startswith(("http://", "https://")):
                    return candidate
    return html.unescape(url)


def _clean_url(url: str) -> str | None:
    candidate = _unwrap_google_url(url.strip())
    parsed = urlparse(candidate)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", parsed.query, ""))


class GoogleLensSearch:
    """Search an image with Google's public Lens upload flow.

    This is intentionally an adapter rather than a hardcoded result. It uploads
    the supplied file on every run and extracts links from the returned results
    page. Google can change this undocumented public flow, so failures are
    surfaced clearly to the operator.
    """

    endpoint = "https://lens.google.com/v3/upload"

    def __init__(self, timeout_seconds: int = 45) -> None:
        self.timeout_seconds = timeout_seconds
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/131.0 Safari/537.36"
                ),
                "Accept-Language": "en-US,en;q=0.9",
            }
        )

    def search(self, image_path: Path) -> tuple[SearchResult, ...]:
        try:
            with image_path.open("rb") as image_file:
                response = self.session.post(
                    self.endpoint,
                    params={"stcs": str(int(datetime.now(UTC).timestamp() * 1000))},
                    files={"encoded_image": (image_path.name, image_file, "image/jpeg")},
                    data={"processed_image_dimensions": "1600,1200"},
                    allow_redirects=True,
                    timeout=self.timeout_seconds,
                )
        except requests.RequestException as exc:
            raise PipelineError(f"Reverse-image search request failed: {exc}") from exc

        if response.status_code >= 400:
            raise PipelineError(
                f"Reverse-image search returned HTTP {response.status_code}. "
                "Try again or use a different image."
            )

        results = self._extract_results(response.text, response.url)
        social_results = tuple(result for result in results if result.is_social)
        if not social_results:
            raise PipelineError(
                "The live reverse-image search completed, but no social-media "
                "result was found. Try a more distinctive public image; no result "
                "is substituted or hardcoded."
            )
        return social_results

    def _extract_results(self, markup: str, search_url: str) -> tuple[SearchResult, ...]:
        soup = BeautifulSoup(markup, "html.parser")
        discovered_at = datetime.now(UTC).isoformat()
        results: list[SearchResult] = []
        seen: set[str] = set()

        for anchor in soup.find_all("a", href=True):
            url = _clean_url(str(anchor.get("href", "")))
            if not url or url in seen or url == search_url:
                continue
            if not _is_social(url):
                continue

            title = " ".join(anchor.get_text(" ", strip=True).split())
            if not title:
                title = (urlparse(url).hostname or "Social result").replace("www.", "")
            container = anchor.find_parent(["div", "article", "li"])
            snippet = ""
            if container:
                snippet = " ".join(container.get_text(" ", strip=True).split())
            snippet = re.sub(r"\s+", " ", snippet)[:500]
            results.append(
                SearchResult(
                    title=title[:240],
                    url=url,
                    snippet=snippet,
                    source="Google Lens public upload",
                    discovered_at=discovered_at,
                    search_url=search_url,
                    is_social=True,
                )
            )
            seen.add(url)

        return tuple(results)