from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://www.veselerozpravky.sk"
SHOWS_URL = f"{BASE_URL}/zoznam-rozpravok/"
USER_AGENT = "sdilej-search-app/1.0"
_VIDEO_ID_RE = re.compile(r'videoId\s*=\s*["\']([A-Za-z0-9_-]{6,})["\']')
_YOUTUBE_IMAGE_RE = re.compile(r"img\.youtube\.com/vi/([^/]+)/", re.IGNORECASE)
_EPISODE_PREFIX_RE = re.compile(r"^\s*(\d+)\.\s*(.+)$")
_DURATION_RE = re.compile(r"\b(\d{1,2}:\d{2}(?::\d{2})?)\b")


@dataclass(frozen=True)
class KidsCatalogShow:
    slug: str
    title: str
    url: str
    episode_count: int | None = None
    thumbnail_url: str | None = None

    def to_dict(self) -> dict:
        return {
            "slug": self.slug,
            "title": self.title,
            "url": self.url,
            "episode_count": self.episode_count,
            "thumbnail_url": self.thumbnail_url,
        }


@dataclass(frozen=True)
class KidsCatalogEpisode:
    title: str
    url: str
    episode_number: int | None = None
    duration: str | None = None
    thumbnail_url: str | None = None
    youtube_url: str | None = None

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "url": self.url,
            "episode_number": self.episode_number,
            "duration": self.duration,
            "thumbnail_url": self.thumbnail_url,
            "youtube_url": self.youtube_url,
        }


class KidsCatalogError(RuntimeError):
    pass


class VeseleRozpravkyClient:
    def __init__(self, timeout_seconds: int = 20) -> None:
        self.timeout_seconds = timeout_seconds
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT})

    def list_shows(self) -> list[dict]:
        soup = self._get_soup(SHOWS_URL)
        shows: list[KidsCatalogShow] = []
        seen: set[str] = set()
        for heading in soup.select("h2.media-heading"):
            anchor = self._nearest_anchor(heading)
            if not anchor:
                continue
            url = self._absolute_url(anchor.get("href"))
            slug = self._slug_from_url(url)
            if not slug or slug in seen:
                continue
            title = self._clean_text(heading.get_text(" ", strip=True))
            if not title:
                continue
            seen.add(slug)
            shows.append(
                KidsCatalogShow(
                    slug=slug,
                    title=title,
                    url=url,
                    episode_count=self._parse_episode_count(anchor.get_text(" ", strip=True)),
                    thumbnail_url=self._extract_image(anchor),
                )
            )
        return [item.to_dict() for item in shows]

    def get_show(self, slug: str) -> dict:
        safe_slug = self._clean_slug(slug)
        if not safe_slug:
            raise KidsCatalogError("Show slug is required.")
        url = f"{BASE_URL}/{safe_slug}/"
        soup = self._get_soup(url)
        title_heading = soup.select_one("h1")
        raw_title = self._clean_text(title_heading.get_text(" ", strip=True) if title_heading else safe_slug)
        title = re.sub(r"\s+-\s+(?:video|online).*", "", raw_title, flags=re.IGNORECASE).strip() or raw_title

        episodes: list[KidsCatalogEpisode] = []
        seen: set[str] = set()
        for heading in soup.select("h2.media-heading"):
            anchor = self._nearest_anchor(heading)
            if not anchor:
                continue
            episode_url = self._absolute_url(anchor.get("href"))
            episode_slug = self._slug_from_url(episode_url)
            if not episode_slug or episode_slug == safe_slug or episode_slug in seen:
                continue
            text = self._clean_text(heading.get_text(" ", strip=True))
            number, episode_title = self._parse_episode_title(text)
            duration = self._parse_duration(anchor.get_text(" ", strip=True))
            seen.add(episode_slug)
            episodes.append(
                KidsCatalogEpisode(
                    title=episode_title,
                    url=episode_url,
                    episode_number=number,
                    duration=duration,
                    thumbnail_url=self._extract_image(anchor),
                )
            )

        return {
            "slug": safe_slug,
            "title": title,
            "url": url,
            "episode_count": len(episodes),
            "episodes": [item.to_dict() for item in episodes],
        }

    def resolve_episode(self, episode_url: str) -> dict:
        url = self._absolute_url(episode_url)
        if urlparse(url).netloc.lower() != urlparse(BASE_URL).netloc.lower():
            raise KidsCatalogError("Only veselerozpravky.sk episode URLs can be resolved.")
        soup = self._get_soup(url)
        html = str(soup)
        match = _VIDEO_ID_RE.search(html) or _YOUTUBE_IMAGE_RE.search(html)
        if not match:
            raise KidsCatalogError("No YouTube video id was found on this episode page.")
        video_id = match.group(1)
        title = self._clean_text((soup.select_one("h1") or soup.select_one("title")).get_text(" ", strip=True))
        return {
            "title": title,
            "url": url,
            "youtube_video_id": video_id,
            "youtube_url": f"https://www.youtube.com/watch?v={video_id}",
            "thumbnail_url": f"https://img.youtube.com/vi/{video_id}/0.jpg",
        }

    def _get_soup(self, url: str) -> BeautifulSoup:
        try:
            response = self.session.get(url, timeout=self.timeout_seconds)
            response.raise_for_status()
        except requests.RequestException as exc:
            raise KidsCatalogError(f"Failed to load kids catalog page: {exc}") from exc
        return BeautifulSoup(response.text, "lxml")

    def _nearest_anchor(self, node):
        parent = node
        for _ in range(5):
            if parent is None:
                return None
            if getattr(parent, "name", None) == "a" and parent.get("href"):
                return parent
            found = parent.find("a", href=True) if hasattr(parent, "find") else None
            if found:
                return found
            parent = parent.parent
        return None

    def _absolute_url(self, value: str | None) -> str:
        if not value:
            raise KidsCatalogError("Missing URL.")
        return urljoin(BASE_URL, value)

    def _slug_from_url(self, value: str) -> str:
        parts = [part for part in urlparse(value).path.split("/") if part]
        return parts[-1] if parts else ""

    def _clean_slug(self, value: str) -> str:
        return re.sub(r"[^a-z0-9-]+", "", value.strip().lower())

    def _clean_text(self, value: str) -> str:
        return re.sub(r"\s+", " ", value or "").strip()

    def _parse_episode_count(self, value: str) -> int | None:
        match = re.search(r"\b(\d+)\s+čast", value or "", re.IGNORECASE)
        return int(match.group(1)) if match else None

    def _parse_duration(self, value: str) -> str | None:
        match = _DURATION_RE.search(value or "")
        return match.group(1) if match else None

    def _parse_episode_title(self, value: str) -> tuple[int | None, str]:
        match = _EPISODE_PREFIX_RE.match(value or "")
        if not match:
            return None, self._clean_text(value)
        return int(match.group(1)), self._clean_text(match.group(2))

    def _extract_image(self, node) -> str | None:
        image = node.find("img") if hasattr(node, "find") else None
        if image and image.get("src"):
            return self._absolute_url(image.get("src"))
        return None
