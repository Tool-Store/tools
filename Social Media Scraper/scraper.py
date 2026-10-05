import logging
import re
from typing import Any, Dict, Optional, Tuple
from urllib.parse import urlparse

import requests
import yt_dlp

logger = logging.getLogger(__name__)

JINA_READER_BASE = "https://r.jina.ai/"
REQUEST_TIMEOUT_SECONDS = 30
DEFAULT_MAX_CHARS = 20_000
MAX_CHARS_LIMIT = 100_000
_YOUTUBE_HOSTS = {"youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com", "youtu.be"}
_VTT_TAG = re.compile(r"<[^>]+>")
_VTT_METADATA_PREFIXES = ("WEBVTT", "Kind:", "Language:", "NOTE")


def _validate_http_url(url: str) -> str:
    candidate = (url or "").strip()
    parsed = urlparse(candidate)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ValueError(f"Invalid URL '{url}': expected an absolute http(s) URL such as https://example.com/page")
    return candidate


def _validate_youtube_url(url: str) -> str:
    target_url = _validate_http_url(url)
    if urlparse(target_url).netloc.lower() not in _YOUTUBE_HOSTS:
        raise ValueError(f"Not a YouTube URL: '{url}'. Expected a youtube.com or youtu.be link.")
    return target_url


def _validate_max_chars(max_chars: int) -> int:
    if not 1 <= max_chars <= MAX_CHARS_LIMIT:
        raise ValueError(f"max_chars must be between 1 and {MAX_CHARS_LIMIT}, got {max_chars}")
    return max_chars


def _truncated_result(source_url: str, content: str, max_chars: int) -> Dict[str, Any]:
    return {
        "url": source_url,
        "content": content[:max_chars],
        "truncated": len(content) > max_chars,
        "total_chars": len(content),
    }


def scrape_url(
    url: str,
    max_chars: int = DEFAULT_MAX_CHARS,
    jina_api_key: Optional[str] = None,
) -> Dict[str, Any]:
    """Fetch a public web page through Jina Reader and return it as markdown."""
    target_url = _validate_http_url(url)
    limit = _validate_max_chars(max_chars)
    headers = {"X-Return-Format": "markdown"}
    if jina_api_key:
        headers["Authorization"] = f"Bearer {jina_api_key}"

    resp = requests.get(f"{JINA_READER_BASE}{target_url}", headers=headers, timeout=REQUEST_TIMEOUT_SECONDS)
    if resp.status_code == 429:
        logger.warning("Jina Reader rate limited: url=%s has_api_key=%s", target_url, bool(jina_api_key))
        raise RuntimeError(
            "Jina Reader rate limit reached. Add a Jina API key in activation for higher limits, or retry later."
        )
    if not resp.ok:
        logger.error("Jina Reader request failed: status=%s url=%s", resp.status_code, target_url)
        raise RuntimeError(f"Jina Reader could not read '{target_url}': {resp.status_code} {resp.text[:300]}")
    return _truncated_result(target_url, resp.text, limit)


def _fetch_video_and_subtitles(video_url: str, language: str) -> Tuple[Dict[str, Any], str]:
    """Fetch metadata and subtitles in one yt-dlp session so both requests share its cookies and headers."""
    options = {
        "skip_download": True,
        "quiet": True,
        "no_warnings": True,
        "socket_timeout": REQUEST_TIMEOUT_SECONDS,
    }
    try:
        with yt_dlp.YoutubeDL(options) as ydl:
            video_info = ydl.extract_info(video_url, download=False)
            track_url = _subtitle_track_url(video_info, language)
            vtt = ydl.urlopen(track_url).read().decode("utf-8", errors="replace")
    except yt_dlp.networking.exceptions.HTTPError as exc:
        raise _subtitle_download_error(video_url, exc.status) from exc
    except yt_dlp.utils.DownloadError as exc:
        logger.error("yt-dlp metadata extraction failed: url=%s reason=%s", video_url, exc)
        raise RuntimeError(f"YouTube request failed for '{video_url}': {exc}") from exc
    return video_info, vtt


def _subtitle_download_error(video_url: str, status: int) -> RuntimeError:
    logger.error("Subtitle download failed: status=%s url=%s", status, video_url)
    if status == 429:
        return RuntimeError(
            f"YouTube is rate-limiting this server (HTTP 429) for '{video_url}'. Retry in a few minutes."
        )
    return RuntimeError(f"Could not download subtitles for '{video_url}': HTTP {status}")


def _subtitle_track_url(video_info: Dict[str, Any], language: str) -> str:
    """Prefer uploaded subtitles over auto-captions; both are tried in VTT format."""
    for source in ("subtitles", "automatic_captions"):
        for track in (video_info.get(source) or {}).get(language) or []:
            if track.get("ext") == "vtt" and track.get("url"):
                return track["url"]
    available = sorted(set(video_info.get("subtitles") or {}) | set(video_info.get("automatic_captions") or {}))
    raise RuntimeError(
        f"No '{language}' subtitles for this video. Available languages: {', '.join(available) or 'none'}"
    )


def _vtt_to_text(vtt: str) -> str:
    """Strip VTT timing/markup; auto-captions repeat each line across cues, so drop consecutive duplicates."""
    lines: list[str] = []
    for raw_line in vtt.splitlines():
        line = _VTT_TAG.sub("", raw_line).strip()
        if not line or "-->" in line or line.isdigit() or line.startswith(_VTT_METADATA_PREFIXES):
            continue
        if lines and lines[-1] == line:
            continue
        lines.append(line)
    return "\n".join(lines)


def get_youtube_transcript(url: str, language: str = "en", max_chars: int = DEFAULT_MAX_CHARS) -> Dict[str, Any]:
    """Return a YouTube video's transcript from its subtitles or auto-captions, without downloading video."""
    video_url = _validate_youtube_url(url)
    limit = _validate_max_chars(max_chars)
    language_code = (language or "").strip()
    if not language_code:
        raise ValueError("language is required, e.g. 'en'")

    video_info, vtt = _fetch_video_and_subtitles(video_url, language_code)
    result = _truncated_result(video_url, _vtt_to_text(vtt), limit)
    result.update({"title": video_info.get("title"), "language": language_code})
    return result
