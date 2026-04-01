from __future__ import annotations

import re
import unicodedata
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from .dataclass_compat import dataclass
from .models import Category, DetailProbeResponse, LanguageScope, SearchResponse, SearchResult, SortMode

BASE_URL = "https://sdilej.cz"
SEARCH_ENTRYPOINT = f"{BASE_URL}/sk/s"
AUTOCOMPLETE_ENDPOINT = f"{BASE_URL}/autocomplete.php"
LOGIN_PAGE_URL = f"{BASE_URL}/prihlasit"

CATEGORY_SEGMENT: dict[Category, str] = {
    "all": "-",
    "video": "video-",
    "audio": "audio-",
    "archive": "archive-",
    "image": "image-",
}

SORT_SUFFIX: dict[SortMode, str] = {
    "relevance": "",
    "downloads": "3",
    "newest": "4",
    "size_desc": "1",
    "size_asc": "2",
}

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/123.0.0.0 Safari/537.36"
    )
}

_DURATION_RE = re.compile(r"D[eé]lka\s*:\s*([0-9]{1,2}:[0-9]{2}(?::[0-9]{2})?)", re.IGNORECASE)
_YEAR_RE = re.compile(r"(?<!\d)(19\d{2}|20\d{2})(?!\d)")
_SUBTITLE_HINT_RE = re.compile(r"(?<![a-z0-9])(?:tit(?:ulky)?|sub(?:title)?s?)(?![a-z0-9])")
_DUB_HINT_RE = re.compile(r"(?<![a-z0-9])(?:dab(?:ing)?|dub)(?![a-z0-9])")
_FILE_ID_RE = re.compile(r"^/(\d+)/")

# Common language codes typically present in filenames on sdilej.
_DETECTABLE_LANGUAGE_CODES = (
    "SK",
    "CZ",
    "CS",
    "EN",
    "DE",
    "HU",
    "PL",
    "IT",
    "FR",
    "ES",
    "RU",
)

# Free-form values users can type in language input.
_LANGUAGE_INPUT_ALIASES = {
    "slovak": "SK",
    "slovensky": "SK",
    "slovencina": "SK",
    "slovencina jazyk": "SK",
    "czech": "CZ",
    "cesky": "CZ",
    "english": "EN",
    "german": "DE",
    "hungarian": "HU",
    "polish": "PL",
    "italian": "IT",
    "french": "FR",
    "spanish": "ES",
    "russian": "RU",
}

# Additional language words that can appear in names (normalized to ascii lowercase).
_LANGUAGE_WORD_ALIASES: dict[str, tuple[str, ...]] = {
    "SK": ("slovak", "slovensky", "slovencina"),
    "CZ": ("czech", "cesky", "cestina", "cechy"),
    "CS": ("czech", "cesky", "cestina", "ceskoslovensky"),
    "EN": ("english", "anglicky"),
    "DE": ("german", "nemecky"),
    "HU": ("hungarian", "madarsky"),
    "PL": ("polish", "polsky"),
    "IT": ("italian", "italsky"),
    "FR": ("french", "francuzsky"),
    "ES": ("spanish", "spanelsky"),
    "RU": ("russian", "rusky"),
}


class SdilejClientError(RuntimeError):
    pass


@dataclass(slots=True)
class ParsedMeta:
    size: str | None
    duration: str | None


@dataclass(slots=True)
class LanguageMatch:
    matched: bool
    is_dub: bool
    is_subtitle: bool


class SdilejClient:
    def __init__(self, timeout_seconds: int = 20) -> None:
        self.timeout_seconds = timeout_seconds
        self.session = requests.Session()
        self.session.headers.update(DEFAULT_HEADERS)

    def autocomplete(self, term: str, limit: int = 10) -> list[str]:
        term = term.strip()
        if len(term) < 2:
            return []

        response = self.session.get(
            AUTOCOMPLETE_ENDPOINT,
            params={"q": term},
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()

        suggestions = [line.strip() for line in response.text.splitlines() if line.strip()]
        return suggestions[:limit]

    def login(self, login: str, password: str) -> tuple[bool, str]:
        login_value = login.strip()
        if not login_value or not password:
            raise SdilejClientError("Both login and password are required for account login.")

        page = self.session.get(LOGIN_PAGE_URL, timeout=self.timeout_seconds)
        page.raise_for_status()
        soup = BeautifulSoup(page.text, "lxml")

        form = soup.select_one("form#loginform")
        if form is None:
            if self._is_logged_in_html(page.text):
                return True, "Login form not found and logged-in markers were detected."
            return False, "Login form not found."

        action = urljoin(BASE_URL, form.get("action", "/sql.php"))
        payload: dict[str, str] = {}
        for hidden in form.select("input[type='hidden'][name]"):
            payload[hidden.get("name", "").strip()] = hidden.get("value", "")

        # Login page includes a global csrf field (outside login form).
        if "csrf" not in payload:
            global_csrf = soup.select_one("input[type='hidden'][name='csrf']")
            if global_csrf:
                payload["csrf"] = global_csrf.get("value", "")

        payload["login"] = login_value
        payload["heslo"] = password

        submit = self.session.post(
            action,
            data=payload,
            headers={
                "Origin": BASE_URL,
                "Referer": page.url,
            },
            timeout=self.timeout_seconds,
            allow_redirects=True,
        )
        submit.raise_for_status()

        if self._is_logged_in_html(submit.text):
            return True, "Login successful."

        # Follow-up check against homepage with the same authenticated session.
        check = self.session.get(BASE_URL, timeout=self.timeout_seconds)
        check.raise_for_status()
        if self._is_logged_in_html(check.text):
            return True, "Login successful."

        reason = self._extract_login_error(submit.text) or self._extract_login_error(check.text)
        if reason:
            return False, reason
        return False, "Login failed; credentials were not accepted."

    def _is_logged_in_html(self, html: str) -> bool:
        soup = BeautifulSoup(html, "lxml")
        if soup.select_one("a[href*='logout.php']"):
            return True

        body = soup.body
        if body:
            body_classes = {cls.strip().lower() for cls in (body.get("class") or []) if cls}
            if "user-logged-in" in body_classes:
                return True

        topmenu = soup.select_one("#topmenu")
        if topmenu:
            topmenu_classes = {cls.strip().lower() for cls in (topmenu.get("class") or []) if cls}
            if "is-logged-in" in topmenu_classes:
                return True

        return False

    def _extract_login_error(self, html: str) -> str | None:
        soup = BeautifulSoup(html, "lxml")
        error_box = soup.select_one("div.alert.alert-danger")
        if not error_box:
            return None

        text = " ".join(error_box.get_text(" ", strip=True).split())
        if not text:
            return None
        return f"Login failed: {text}"

    def search(
        self,
        query: str,
        category: Category = "all",
        sort: SortMode = "relevance",
        max_results: int = 150,
        language: str | None = None,
        language_scope: LanguageScope = "any",
        strict_dubbing: bool = False,
        release_year: int | None = None,
    ) -> SearchResponse:
        normalized_query = query.strip()

        if category not in CATEGORY_SEGMENT:
            raise SdilejClientError(f"Unsupported category: {category}")
        if sort not in SORT_SUFFIX:
            raise SdilejClientError(f"Unsupported sort mode: {sort}")
        if language_scope not in {"any", "audio", "subtitles"}:
            raise SdilejClientError(f"Unsupported language scope: {language_scope}")
        if release_year is not None and (release_year < 1900 or release_year > 2099):
            raise SdilejClientError("Release year must be between 1900 and 2099.")

        normalized_language = self._normalize_language_input(language)
        if strict_dubbing and not normalized_language:
            raise SdilejClientError("strict_dubbing=true requires language to be set.")
        effective_query = self._resolve_effective_query(
            query=normalized_query,
            language=normalized_language,
            release_year=release_year,
        )

        slug = self._resolve_slug(effective_query)
        segment = f"{CATEGORY_SEGMENT[category]}{SORT_SUFFIX[sort]}"
        search_url = f"{BASE_URL}/{slug}/s/{segment}"

        response = self.session.get(search_url, timeout=self.timeout_seconds)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "lxml")
        cards = soup.select("div.videobox")

        all_results: list[SearchResult] = []
        for card in cards:
            result = self._parse_card(card)
            if result is not None:
                all_results.append(result)
        all_results = self._dedupe_results(all_results)

        filtered_results = self._apply_language_filter(
            all_results,
            language=normalized_language,
            scope=language_scope,
            strict_dubbing=strict_dubbing,
        )
        filtered_results = self._apply_year_filter(filtered_results, release_year=release_year)

        limited_results = filtered_results[:max_results]

        return SearchResponse(
            query=normalized_query,
            effective_query=effective_query,
            slug=slug,
            category=category,
            sort=sort,
            language=normalized_language,
            language_scope=language_scope,
            strict_dubbing=strict_dubbing,
            release_year=release_year,
            search_url=search_url,
            unfiltered_result_count=len(all_results),
            result_count=len(limited_results),
            results=limited_results,
        )

    def probe_detail(self, detail_url: str, run_preflight: bool = True) -> DetailProbeResponse:
        if not detail_url.strip():
            raise SdilejClientError("detail_url must not be empty.")

        absolute_url = self._normalize_detail_url(detail_url)
        response = self.session.get(absolute_url, timeout=self.timeout_seconds)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "lxml")

        title = self._extract_detail_title(soup)
        size, duration, resolution = self._extract_detail_badges(soup)
        fast_url, slow_url = self._extract_download_buttons(soup, absolute_url)
        selected_url = slow_url or fast_url

        preflight_status_code = None
        preflight_location = None
        preflight_content_type = None
        preflight_content_length = None
        preflight_accept_ranges = None

        if run_preflight and selected_url:
            preflight = self._preflight_download_target(selected_url)
            preflight_status_code = preflight.status_code
            preflight_location = preflight.location
            preflight_content_type = preflight.content_type
            preflight_content_length = preflight.content_length
            preflight_accept_ranges = preflight.accept_ranges

        return DetailProbeResponse(
            file_id=self._extract_file_id(absolute_url),
            detail_url=absolute_url,
            title=title,
            size=size,
            duration=duration,
            resolution=resolution,
            download_fast_url=fast_url,
            download_slow_url=slow_url,
            selected_download_url=selected_url,
            preflight_status_code=preflight_status_code,
            preflight_location=preflight_location,
            preflight_content_type=preflight_content_type,
            preflight_content_length=preflight_content_length,
            preflight_accept_ranges=preflight_accept_ranges,
        )

    def normalize_language(self, language: str | None) -> str | None:
        return self._normalize_language_input(language)

    def language_match_priority(
        self,
        *,
        title: str,
        language: str | None,
        scope: LanguageScope = "any",
        strict_dubbing: bool = False,
    ) -> int:
        normalized_language = self._normalize_language_input(language)
        if normalized_language is None:
            return 0

        match = self._match_language(title, normalized_language)
        if not match.matched:
            return 0

        if strict_dubbing:
            return 30 if match.is_dub else 0

        if scope == "subtitles":
            return 30 if match.is_subtitle else 0

        if scope == "audio":
            if match.is_dub:
                return 30
            if not match.is_subtitle:
                return 20
            return 5

        # any
        if match.is_dub:
            return 30
        if match.is_subtitle:
            return 15
        return 20

    def _resolve_slug(self, query: str) -> str:
        response = self.session.get(
            SEARCH_ENTRYPOINT,
            params={"q": query},
            allow_redirects=False,
            timeout=self.timeout_seconds,
        )

        location = response.headers.get("Location", "")
        if response.status_code in {301, 302, 303, 307, 308} and location:
            match = re.match(r"^/([^/]+)/s/?$", location)
            if match:
                return match.group(1)

        return self._fallback_slug(query)

    def _fallback_slug(self, query: str) -> str:
        ascii_text = (
            unicodedata.normalize("NFKD", query)
            .encode("ascii", "ignore")
            .decode("ascii")
            .lower()
        )
        collapsed = re.sub(r"[^a-z0-9]+", "-", ascii_text)
        return collapsed.strip("-") or "s"

    def _parse_card(self, card) -> SearchResult | None:
        link_tag = card.select_one("a[href]")
        if link_tag is None:
            return None

        detail_url = urljoin(BASE_URL, link_tag.get("href", "").strip())
        if not detail_url:
            return None

        title_tag = card.select_one(".videobox-title a")
        title = ""
        if title_tag and title_tag.get_text(strip=True):
            title = title_tag.get_text(strip=True)
        elif link_tag.get("title"):
            title = link_tag.get("title", "").strip()
        if not title:
            title = detail_url.rsplit("/", 1)[-1]

        image_tag = card.select_one("img.img-responsive")
        thumbnail_url = None
        if image_tag and image_tag.get("src"):
            thumbnail_url = urljoin(BASE_URL, image_tag.get("src", "").strip())

        meta_line = card.select_one(".videobox-desc p:nth-of-type(2)")
        parsed_meta = self._parse_meta(meta_line.get_text(" ", strip=True) if meta_line else "")

        extension = self._extract_extension(detail_url)
        file_id = self._extract_file_id(detail_url)
        years = self._extract_years(title)
        language_signals = self._extract_language_signals(title)

        return SearchResult(
            file_id=file_id,
            title=title,
            detail_url=detail_url,
            thumbnail_url=thumbnail_url,
            size=parsed_meta.size,
            duration=parsed_meta.duration,
            is_playable=bool(card.select_one("span.playable")),
            extension=extension,
            detected_years=years,
            primary_year=years[0] if years else None,
            detected_languages=language_signals.detected_languages,
            has_dub_hint=language_signals.has_dub_hint,
            has_subtitle_hint=language_signals.has_subtitle_hint,
        )

    def _parse_meta(self, text: str) -> ParsedMeta:
        if not text:
            return ParsedMeta(size=None, duration=None)

        size = None
        duration = None

        if "/" in text:
            size_part = text.split("/", 1)[0].strip()
            size = size_part or None

        duration_match = _DURATION_RE.search(text)
        if duration_match:
            duration = duration_match.group(1)

        return ParsedMeta(size=size, duration=duration)

    def _extract_extension(self, detail_url: str) -> str | None:
        path = urlparse(detail_url).path
        filename = path.rsplit("/", 1)[-1]
        if "." not in filename:
            return None
        ext = filename.rsplit(".", 1)[-1].lower()
        return ext if ext else None

    def _normalize_language_input(self, language: str | None) -> str | None:
        if language is None:
            return None

        raw = language.strip()
        if not raw:
            return None

        normalized = self._normalize_match_text(raw)
        alias_hit = _LANGUAGE_INPUT_ALIASES.get(normalized)
        if alias_hit:
            return alias_hit

        if re.fullmatch(r"[A-Za-z]{2,3}", raw):
            return raw.upper()

        raise SdilejClientError(
            "Language must be a 2-3 letter code (e.g. SK, EN) or a known language name."
        )

    def _apply_language_filter(
        self,
        results: list[SearchResult],
        language: str | None,
        scope: LanguageScope,
        strict_dubbing: bool,
    ) -> list[SearchResult]:
        if language is None:
            return results

        filtered: list[SearchResult] = []
        for result in results:
            match = self._match_language(result.title, language)
            if self._language_scope_match(match, scope, strict_dubbing):
                filtered.append(result)
        return filtered

    def _apply_year_filter(
        self,
        results: list[SearchResult],
        release_year: int | None,
    ) -> list[SearchResult]:
        if release_year is None:
            return results

        filtered: list[SearchResult] = []
        for result in results:
            if release_year in result.detected_years:
                filtered.append(result)
        return filtered

    def _language_scope_match(
        self,
        match: LanguageMatch,
        scope: LanguageScope,
        strict_dubbing: bool,
    ) -> bool:
        if not match.matched:
            return False

        if strict_dubbing:
            return match.is_dub

        if scope == "any":
            return True

        if scope == "audio":
            # Bare markers like "CZ EN SK" are treated as usable audio-language hints.
            return match.is_dub or not match.is_subtitle

        if scope == "subtitles":
            return match.is_subtitle

        return False

    def _extract_language_signals(self, title: str):
        detected: list[str] = []
        has_dub_hint = False
        has_subtitle_hint = False

        for code in _DETECTABLE_LANGUAGE_CODES:
            lang_match = self._match_language(title, code)
            if lang_match.matched:
                detected.append(code)
            has_dub_hint = has_dub_hint or lang_match.is_dub
            has_subtitle_hint = has_subtitle_hint or lang_match.is_subtitle

        return _LanguageSignals(
            detected_languages=detected,
            has_dub_hint=has_dub_hint,
            has_subtitle_hint=has_subtitle_hint,
        )

    def _match_language(self, text: str, language_code: str) -> LanguageMatch:
        normalized_text = self._normalize_match_text(text)
        code = language_code.lower()

        escaped = re.escape(code)
        has_generic_code = bool(re.search(rf"(?<![a-z0-9]){escaped}(?![a-z0-9])", normalized_text))

        has_dub_inline = bool(
            re.search(rf"(?<![a-z0-9]){escaped}(?:dab(?:ing)?|dub)(?![a-z0-9])", normalized_text)
        )
        has_dub_prefix = bool(
            re.search(rf"(?<![a-z0-9])(?:dab(?:ing)?|dub)[-_ ]*{escaped}(?![a-z0-9])", normalized_text)
        )

        has_sub_inline = bool(
            re.search(
                rf"(?<![a-z0-9]){escaped}(?:tit(?:ulky)?|sub(?:title)?s?)(?![a-z0-9])",
                normalized_text,
            )
        )
        has_sub_prefix = bool(
            re.search(
                rf"(?<![a-z0-9])(?:tit(?:ulky)?|sub(?:title)?s?)[-_ ]*{escaped}(?![a-z0-9])",
                normalized_text,
            )
        )

        has_dub_hint = bool(has_dub_inline or has_dub_prefix)
        has_subtitle_hint = bool(has_sub_inline or has_sub_prefix)

        has_alias_word = False
        for alias in _LANGUAGE_WORD_ALIASES.get(language_code.upper(), ()):  # noqa: SIM118
            if re.search(rf"(?<![a-z0-9]){re.escape(alias)}(?![a-z0-9])", normalized_text):
                has_alias_word = True
                break

        is_dub = has_dub_hint
        is_sub = has_subtitle_hint

        # If global words appear (e.g. "dabing", "titulky"), use them as context
        # for generic markers like "... SK".
        if has_generic_code or has_alias_word:
            if not is_dub and _DUB_HINT_RE.search(normalized_text):
                is_dub = True
            if not is_sub and _SUBTITLE_HINT_RE.search(normalized_text):
                is_sub = True

        matched = bool(has_generic_code or has_alias_word or is_dub or is_sub)
        return LanguageMatch(matched=matched, is_dub=is_dub, is_subtitle=is_sub)

    def _normalize_match_text(self, text: str) -> str:
        return (
            unicodedata.normalize("NFKD", text)
            .encode("ascii", "ignore")
            .decode("ascii")
            .lower()
        )

    def _extract_years(self, title: str) -> list[int]:
        years: list[int] = []
        for match in _YEAR_RE.finditer(title):
            value = int(match.group(1))
            if value not in years:
                years.append(value)
        return years

    def _resolve_effective_query(
        self,
        query: str,
        language: str | None,
        release_year: int | None,
    ) -> str:
        if query:
            return query

        parts: list[str] = []
        if language:
            parts.append(language.lower())
        if release_year is not None:
            parts.append(str(release_year))

        effective_query = " ".join(parts).strip()
        if effective_query:
            return effective_query

        raise SdilejClientError(
            "Provide at least one of: query, language, or release_year."
        )

    def _extract_file_id(self, detail_url: str) -> int | None:
        parsed = urlparse(detail_url)
        match = _FILE_ID_RE.match(parsed.path)
        if not match:
            return None
        return int(match.group(1))

    def _dedupe_results(self, results: list[SearchResult]) -> list[SearchResult]:
        deduped: list[SearchResult] = []
        seen_file_ids: set[int] = set()
        seen_urls: set[str] = set()

        for result in results:
            if result.file_id is not None:
                if result.file_id in seen_file_ids:
                    continue
                seen_file_ids.add(result.file_id)
                deduped.append(result)
                continue

            if result.detail_url in seen_urls:
                continue
            seen_urls.add(result.detail_url)
            deduped.append(result)

        return deduped

    def _normalize_detail_url(self, detail_url: str) -> str:
        url = detail_url.strip()
        if url.startswith("http://") or url.startswith("https://"):
            return url
        if url.startswith("/"):
            return urljoin(BASE_URL, url)
        raise SdilejClientError("detail_url must be absolute or start with '/'.")

    def _extract_detail_title(self, soup: BeautifulSoup) -> str | None:
        h1 = soup.select_one("h1")
        if h1 and h1.get_text(strip=True):
            return h1.get_text(strip=True)
        title_tag = soup.select_one("title")
        if title_tag and title_tag.get_text(strip=True):
            return title_tag.get_text(strip=True)
        return None

    def _extract_detail_badges(self, soup: BeautifulSoup) -> tuple[str | None, str | None, str | None]:
        badges = [item.get_text(" ", strip=True) for item in soup.select("span.meta-badge")]
        badges = [item for item in badges if item]
        size = badges[0] if len(badges) > 0 else None
        duration = badges[1] if len(badges) > 1 else None
        resolution = badges[2] if len(badges) > 2 else None
        return size, duration, resolution

    def _extract_download_buttons(
        self,
        soup: BeautifulSoup,
        detail_url: str,
    ) -> tuple[str | None, str | None]:
        fast_url = None
        slow_url = None

        for container in soup.select("div.detail-buttons"):
            for link in container.select("a[href]"):
                classes = link.get("class", [])
                href = link.get("href", "").strip()
                if not href:
                    continue
                absolute_href = urljoin(detail_url, href)

                class_set = set(classes)
                text = link.get_text(" ", strip=True).lower()

                if "btn-success" in class_set or "rychle" in text:
                    fast_url = absolute_href
                if "btn-danger" in class_set or "pomalu" in text:
                    slow_url = absolute_href

        return fast_url, slow_url

    def _preflight_download_target(self, url: str):
        response = self.session.get(
            url,
            allow_redirects=False,
            timeout=self.timeout_seconds,
            stream=True,
        )
        status_code = response.status_code
        location = response.headers.get("Location")
        content_type = response.headers.get("Content-Type")
        content_length_raw = response.headers.get("Content-Length")
        accept_ranges = response.headers.get("Accept-Ranges")
        response.close()

        content_length = None
        if content_length_raw and content_length_raw.isdigit():
            content_length = int(content_length_raw)

        return _PreflightResult(
            status_code=status_code,
            location=location,
            content_type=content_type,
            content_length=content_length,
            accept_ranges=accept_ranges,
        )


@dataclass(slots=True)
class _LanguageSignals:
    detected_languages: list[str]
    has_dub_hint: bool
    has_subtitle_hint: bool


@dataclass(slots=True)
class _PreflightResult:
    status_code: int
    location: str | None
    content_type: str | None
    content_length: int | None
    accept_ranges: str | None
