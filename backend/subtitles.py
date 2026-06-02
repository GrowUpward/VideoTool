import json
import re
import tempfile
from pathlib import Path

import requests
import yt_dlp

from config import HTTP_PROXY, HTTPS_PROXY

_last_error = ""

_EMPTY_RESULT = {
    "has_subtitle": False,
    "language": "",
    "subtitle_type": "none",
    "segments": [],
    "full_text": "",
}


def get_last_error() -> str:
    return _last_error


def _time_to_seconds(time_str: str) -> float:
    """Convert HH:MM:SS.mmm or HH:MM:SS,mmm to seconds."""
    time_str = time_str.replace(",", ".")
    parts = time_str.split(":")
    hours = int(parts[0])
    minutes = int(parts[1])
    seconds = float(parts[2])
    return hours * 3600 + minutes * 60 + seconds


def _build_opts() -> dict:
    from config import BASE_DIR
    opts = {
        "quiet": True,
        "no_warnings": True,
        "writesubtitles": True,
        "writeautomaticsub": True,
        "subtitleslangs": ["zh-Hans", "zh", "en", "zh-CN"],
        "subtitlesformat": "vtt",
        "skip_download": True,
    }
    cookiefile = BASE_DIR / "cookies.txt"
    if cookiefile.exists():
        opts["cookiefile"] = str(cookiefile)
    if HTTP_PROXY:
        opts["proxy"] = HTTP_PROXY
    elif HTTPS_PROXY:
        opts["proxy"] = HTTPS_PROXY
    return opts


def _build_info_opts() -> dict:
    """Metadata-first mode to avoid direct subtitle file download limits."""
    from config import BASE_DIR
    opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
    }
    cookiefile = BASE_DIR / "cookies.txt"
    if cookiefile.exists():
        opts["cookiefile"] = str(cookiefile)
    if HTTP_PROXY:
        opts["proxy"] = HTTP_PROXY
    elif HTTPS_PROXY:
        opts["proxy"] = HTTPS_PROXY
    return opts


def _parse_srt_segments(srt_text: str) -> list[dict]:
    """Parse SRT text into structured segments with timestamps."""
    segments = []
    blocks = re.split(r"\n\n+", srt_text)
    time_pattern = re.compile(
        r"(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})"
    )
    seen_texts = set()

    for block in blocks:
        lines = block.strip().split("\n")
        time_match = None
        text_lines = []
        for line in lines:
            m = time_pattern.search(line)
            if m:
                time_match = m
            elif time_match and line.strip() and not line.strip().isdigit():
                clean = re.sub(r"<[^>]+>", "", line.strip())
                if clean:
                    text_lines.append(clean)

        if time_match and text_lines:
            text = " ".join(text_lines)
            if text in seen_texts:
                continue
            seen_texts.add(text)
            start = _time_to_seconds(time_match.group(1))
            end = _time_to_seconds(time_match.group(2))
            segments.append({
                "start": round(start, 2),
                "end": round(end, 2),
                "text": text,
            })

    return segments


def _parse_vtt_segments(vtt_text: str) -> list[dict]:
    """Parse VTT text into structured segments with timestamps."""
    segments = []
    blocks = re.split(r"\n\n+", vtt_text)
    time_pattern = re.compile(
        r"(\d{2}:\d{2}:\d{2}\.\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}\.\d{3})"
    )
    seen_texts = set()

    for block in blocks:
        lines = block.strip().split("\n")
        time_match = None
        text_lines = []
        for line in lines:
            m = time_pattern.search(line)
            if m:
                time_match = m
            elif time_match and line.strip() and not line.strip().isdigit():
                clean = re.sub(r"<[^>]+>", "", line.strip())
                if clean:
                    text_lines.append(clean)

        if time_match and text_lines:
            text = " ".join(text_lines)
            if text in seen_texts:
                continue
            seen_texts.add(text)
            start = _time_to_seconds(time_match.group(1))
            end = _time_to_seconds(time_match.group(2))
            segments.append({
                "start": round(start, 2),
                "end": round(end, 2),
                "text": text,
            })

    return segments


def _parse_json3_segments(json3_text: str) -> list[dict]:
    """Parse YouTube json3 subtitle format into structured segments."""
    segments = []
    seen_texts = set()
    try:
        data = json.loads(json3_text)
    except (json.JSONDecodeError, ValueError):
        return segments

    events = data.get("events", [])
    for event in events:
        segs = event.get("segs", [])
        if not segs:
            continue
        text_parts = []
        for seg in segs:
            utf8 = seg.get("utf8", "")
            if utf8 and utf8 != "\n":
                text_parts.append(utf8)
        text = "".join(text_parts).strip()
        if not text:
            continue
        if text in seen_texts:
            continue
        seen_texts.add(text)

        start_ms = event.get("tStartMs", 0)
        duration_ms = event.get("dDurationMs", 0)
        start = round(start_ms / 1000, 2)
        end = round((start_ms + duration_ms) / 1000, 2)
        segments.append({"start": start, "end": end, "text": text})

    return segments


def _fetch_text(url: str) -> str | None:
    proxies = None
    if HTTP_PROXY or HTTPS_PROXY:
        proxies = {"http": HTTP_PROXY or HTTPS_PROXY, "https": HTTPS_PROXY or HTTP_PROXY}
    try:
        resp = requests.get(url, timeout=20, proxies=proxies)
        if resp.ok and resp.text.strip():
            return resp.text
    except Exception:
        return None
    return None


def _parse_subtitle_text(raw: str, ext: str = "") -> list[dict]:
    """Parse subtitle text into segments based on format."""
    ext_l = (ext or "").lower()
    if "json3" in ext_l:
        return _parse_json3_segments(raw)
    if "vtt" in ext_l or raw.lstrip().startswith("WEBVTT"):
        return _parse_vtt_segments(raw)
    return _parse_srt_segments(raw)


def _is_bilibili_url(url: str) -> bool:
    return "bilibili.com" in url or "b23.tv" in url


def _resolve_short_url(url: str) -> str:
    """解析短链接（如 b23.tv）获取真实 URL。"""
    try:
        resp = requests.head(url, allow_redirects=True, timeout=10)
        return resp.url
    except Exception:
        return url


def _extract_bilibili(url: str) -> dict:
    """Bilibili-specific subtitle extraction via dm/view API."""
    try:
        # 短链接先解析为完整 URL
        if "b23.tv" in url:
            url = _resolve_short_url(url)
        m = re.search(r"(BV[a-zA-Z0-9]+)", url)
        if not m:
            return _EMPTY_RESULT
        bvid = m.group(1)

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": f"https://www.bilibili.com/video/{bvid}",
        }

        proxies = None
        if HTTP_PROXY or HTTPS_PROXY:
            proxies = {"http": HTTP_PROXY or HTTPS_PROXY, "https": HTTPS_PROXY or HTTP_PROXY}

        view_resp = requests.get(
            f"https://api.bilibili.com/x/web-interface/view?bvid={bvid}",
            headers=headers, timeout=15, proxies=proxies,
        )
        view_data = view_resp.json().get("data", {})
        cid = view_data.get("cid")
        aid = view_data.get("aid")
        if not cid or not aid:
            return _EMPTY_RESULT

        dm_resp = requests.get(
            f"https://api.bilibili.com/x/v2/dm/view?aid={aid}&oid={cid}&type=1",
            headers=headers, timeout=15, proxies=proxies,
        )
        dm_data = dm_resp.json().get("data", {})
        subtitle_list = dm_data.get("subtitle", {}).get("subtitles", [])

        if not subtitle_list:
            return _EMPTY_RESULT

        best = subtitle_list[0]
        for s in subtitle_list:
            lang = s.get("lan", "")
            if lang in ("zh", "zh-Hans"):
                best = s
                break

        sub_type = "auto" if best.get("lan", "").startswith("ai-") else "manual"

        sub_url = best.get("subtitle_url", "")
        if sub_url.startswith("//"):
            sub_url = "https:" + sub_url
        if sub_url.startswith("http://"):
            sub_url = "https://" + sub_url[7:]
        if not sub_url:
            return _EMPTY_RESULT

        sub_resp = requests.get(sub_url, headers=headers, timeout=15, proxies=proxies)
        sub_json = sub_resp.json()
        body = sub_json.get("body", [])

        segments = []
        for item in body:
            content = item.get("content", "").strip()
            if not content:
                continue
            segments.append({
                "start": round(item.get("from", 0), 2),
                "end": round(item.get("to", 0), 2),
                "text": content,
            })

        full_text = " ".join(seg["text"] for seg in segments)
        return {
            "has_subtitle": True,
            "language": best.get("lan", "zh"),
            "subtitle_type": sub_type,
            "segments": segments,
            "full_text": full_text,
        }
    except Exception:
        return _EMPTY_RESULT


def _extract_subtitles_via_metadata(url: str) -> dict | None:
    """Try to read subtitle URLs from metadata first, then fetch and parse."""
    global _last_error
    opts = _build_info_opts()
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False)

    candidates = []
    subtitles = info.get("subtitles") or {}
    auto_subs = info.get("automatic_captions") or {}
    lang_priority = ["zh-Hans", "zh-CN", "zh", "en"]

    # Manual subtitles first
    for lang in lang_priority:
        tracks = subtitles.get(lang) or []
        for t in tracks:
            if t.get("url"):
                candidates.append((lang, t.get("ext", ""), t["url"], "manual"))
    # Then auto subtitles
    for lang in lang_priority:
        tracks = auto_subs.get(lang) or []
        for t in tracks:
            if t.get("url"):
                candidates.append((lang, t.get("ext", ""), t["url"], "auto"))

    # Fallback: any language
    for lang, tracks in subtitles.items():
        if lang == "danmaku":
            continue
        for t in tracks:
            if t.get("url"):
                candidates.append((lang, t.get("ext", ""), t["url"], "manual"))
    for lang, tracks in auto_subs.items():
        for t in tracks:
            if t.get("url"):
                candidates.append((lang, t.get("ext", ""), t["url"], "auto"))

    # Prefer json3 > srv3 > vtt > srt
    format_order = {"json3": 0, "srv3": 1, "vtt": 2, "srt": 3, "ttml": 4}
    candidates.sort(key=lambda c: format_order.get(c[1].lower(), 99))

    for lang, ext, sub_url, sub_type in candidates:
        raw = _fetch_text(sub_url)
        if not raw:
            continue
        segments = _parse_subtitle_text(raw, ext)
        if segments:
            full_text = " ".join(seg["text"] for seg in segments)
            return {
                "has_subtitle": True,
                "language": lang,
                "subtitle_type": sub_type,
                "segments": segments,
                "full_text": full_text,
            }

    _last_error = "元数据中未找到可用字幕轨道或字幕 URL 无法访问"
    return None


def extract_subtitles(url: str) -> dict:
    """Extract subtitles from a video URL.

    Returns a dict with keys: has_subtitle, language, subtitle_type, segments, full_text.
    """
    global _last_error
    _last_error = ""

    # 解析短链接（如 b23.tv）
    if "b23.tv" in url:
        url = _resolve_short_url(url)

    # Bilibili-specific extraction
    if _is_bilibili_url(url):
        result = _extract_bilibili(url)
        if result["has_subtitle"]:
            return result

    # Step 1: metadata-first strategy
    try:
        result = _extract_subtitles_via_metadata(url)
        if result:
            return result
    except Exception as e:
        _last_error = str(e)

    # Step 2: legacy subtitle file download fallback
    tmpdir = tempfile.mkdtemp()
    try:
        opts = _build_opts()
        opts["outtmpl"] = str(Path(tmpdir) / "%(id)s.%(ext)s")
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)

        video_id = info.get("id", "video")
        # Look for subtitle files by language priority
        for suffix in [".zh-Hans.vtt", ".zh.vtt", ".en.vtt", ".zh-CN.vtt",
                       ".zh-Hans.srt", ".zh.srt", ".en.srt", ".zh-CN.srt"]:
            sub_file = Path(tmpdir) / f"{video_id}{suffix}"
            if sub_file.exists():
                raw = sub_file.read_text(encoding="utf-8", errors="replace")
                ext = sub_file.suffix.lstrip(".")
                segments = _parse_subtitle_text(raw, ext)
                if segments:
                    full_text = " ".join(seg["text"] for seg in segments)
                    lang = suffix.split(".")[1] if "." in suffix else ""
                    return {
                        "has_subtitle": True,
                        "language": lang,
                        "subtitle_type": "auto",
                        "segments": segments,
                        "full_text": full_text,
                    }

        # Check for any subtitle file
        for f in Path(tmpdir).glob("*.vtt"):
            raw = f.read_text(encoding="utf-8", errors="replace")
            segments = _parse_vtt_segments(raw)
            if segments:
                full_text = " ".join(seg["text"] for seg in segments)
                return {
                    "has_subtitle": True,
                    "language": "",
                    "subtitle_type": "auto",
                    "segments": segments,
                    "full_text": full_text,
                }
        for f in Path(tmpdir).glob("*.srt"):
            raw = f.read_text(encoding="utf-8", errors="replace")
            segments = _parse_srt_segments(raw)
            if segments:
                full_text = " ".join(seg["text"] for seg in segments)
                return {
                    "has_subtitle": True,
                    "language": "",
                    "subtitle_type": "auto",
                    "segments": segments,
                    "full_text": full_text,
                }

    except Exception as e:
        _last_error = _last_error or str(e)

    return _EMPTY_RESULT
