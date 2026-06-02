import asyncio
import re
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

import yt_dlp

from config import BASE_DIR, DOWNLOAD_DIR, HTTP_PROXY, HTTPS_PROXY
from models import VideoInfo, FormatOption, DownloadTask

executor = ThreadPoolExecutor(max_workers=4)

# In-memory progress store: task_id -> DownloadTask
progress_store: dict[str, DownloadTask] = {}


def extract_url(text: str) -> str:
    """从分享文本中提取 URL（如 B 站 App 分享格式：'【标题】 https://b23.tv/xxx'），并解析短链接。"""
    match = re.search(r'https?://[^\s"\'】）)]+', text.strip())
    url = match.group(0) if match else text.strip()
    # 解析短链接
    if "b23.tv" in url:
        try:
            resp = http_requests.head(url, allow_redirects=True, timeout=10)
            url = resp.url
        except Exception:
            pass
    return url


def format_duration(seconds) -> str:
    if not seconds:
        return "未知"
    seconds = int(seconds)
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def _build_ydl_opts(extra: Optional[dict] = None) -> dict:
    opts = {
        "quiet": True,
        "no_warnings": True,
        "restrictfilenames": True,
        "windowsfilenames": True,
    }
    # B 站 Cookies（解决 412 反爬）
    cookiefile = BASE_DIR / "cookies.txt"
    if cookiefile.exists():
        opts["cookiefile"] = str(cookiefile)
    if HTTP_PROXY:
        opts["proxy"] = HTTP_PROXY
    elif HTTPS_PROXY:
        opts["proxy"] = HTTPS_PROXY
    if extra:
        opts.update(extra)
    return opts


def _extract_info(url: str) -> dict:
    opts = _build_ydl_opts()
    with yt_dlp.YoutubeDL(opts) as ydl:
        return ydl.extract_info(url, download=False)


def _parse_formats(info: dict) -> list[FormatOption]:
    """Extract unique resolution options from yt-dlp format list."""
    formats = info.get("formats", [])
    resolutions = set()
    options = []

    for f in formats:
        height = f.get("height")
        if height and f.get("vcodec", "none") != "none":
            resolutions.add(int(height))

    # Sort resolutions descending
    for h in sorted(resolutions, reverse=True):
        label = f"{h}p"
        if h >= 2160:
            label = f"4K ({h}p)"
        elif h >= 1440:
            label = f"2K ({h}p)"
        fmt = f"bestvideo[height<={h}]+bestaudio/best[height<={h}]/best"
        options.append(FormatOption(label=label, value=fmt))

    # Audio-only option
    options.append(FormatOption(label="仅音频 (MP3)", value="bestaudio/best", ext="mp3"))

    # Fallback: if no video formats found, offer "best"
    if not options or len(options) == 1:
        options.insert(0, FormatOption(label="最佳画质", value="best"))

    return options


def parse_video_info(url: str) -> VideoInfo:
    url = extract_url(url)
    info = _extract_info(url)
    formats = _parse_formats(info)
    dur = info.get("duration")
    vc = info.get("view_count")
    thumbnail = info.get("thumbnail") or ""
    # B站封面有防盗链，通过后端代理加载
    if thumbnail:
        from urllib.parse import quote
        thumbnail = f"/api/proxy/thumbnail?url={quote(thumbnail, safe='')}"

    return VideoInfo(
        title=info.get("title", "未知标题"),
        thumbnail=thumbnail or None,
        duration=int(dur) if dur else None,
        duration_str=format_duration(dur),
        uploader=info.get("uploader") or info.get("channel", "未知"),
        view_count=int(vc) if vc else None,
        formats=formats,
    )


def _progress_hook(task_id: str):
    def hook(d):
        task = progress_store.get(task_id)
        if not task:
            return
        if d["status"] == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            downloaded = d.get("downloaded_bytes", 0)
            task.percent = (downloaded / total * 100) if total else 0
            task.speed = d.get("_speed_str", "")
            task.eta = d.get("_eta_str", "")
            task.status = "downloading"
        elif d["status"] == "finished":
            task.percent = 100
            task.status = "completed"
            task.filename = d.get("filename", "")
    return hook


def _download_sync(task_id: str, url: str, quality: str):
    task = progress_store[task_id]
    task.status = "downloading"

    is_audio = quality == "bestaudio/best"
    ext = "mp3" if is_audio else "mp4"
    outtmpl = str(DOWNLOAD_DIR / "%(title)s.%(ext)s")

    ydl_opts = _build_ydl_opts({
        "format": quality,
        "outtmpl": outtmpl,
        "progress_hooks": [_progress_hook(task_id)],
    })

    if is_audio:
        ydl_opts["postprocessors"] = [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192",
        }]
    else:
        ydl_opts["merge_output_format"] = "mp4"

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            task.title = info.get("title", task.title)
            # Determine final filename
            if is_audio:
                task.filename = ydl.prepare_filename(info).rsplit(".", 1)[0] + ".mp3"
            else:
                task.filename = ydl.prepare_filename(info).rsplit(".", 1)[0] + ".mp4"
        task.status = "completed"
        task.percent = 100
    except Exception as e:
        task.status = "failed"
        task.error = str(e)


async def start_download(url: str, quality: str) -> str:
    url = extract_url(url)
    task_id = str(uuid.uuid4())
    progress_store[task_id] = DownloadTask(task_id=task_id)
    loop = asyncio.get_event_loop()
    loop.run_in_executor(executor, _download_sync, task_id, url, quality)
    return task_id


def get_task(task_id: str) -> Optional[DownloadTask]:
    return progress_store.get(task_id)
