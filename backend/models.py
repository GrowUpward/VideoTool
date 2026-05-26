from pydantic import BaseModel
from typing import Optional


class ParseRequest(BaseModel):
    url: str


class FormatOption(BaseModel):
    label: str        # e.g. "1080p", "720p", "仅音频"
    value: str        # yt-dlp format string, e.g. "bestvideo[height<=1080]+bestaudio/best"
    ext: str = "mp4"  # output extension


class VideoInfo(BaseModel):
    title: str
    thumbnail: Optional[str] = None
    duration: Optional[int] = None       # seconds
    duration_str: Optional[str] = None   # e.g. "10:23"
    uploader: Optional[str] = None
    view_count: Optional[int] = None
    formats: list[FormatOption] = []


class DownloadRequest(BaseModel):
    url: str
    quality: str  # format value from FormatOption


class DownloadTask(BaseModel):
    task_id: str
    status: str = "pending"   # pending, downloading, completed, failed
    percent: float = 0.0
    speed: str = ""
    eta: str = ""
    filename: str = ""
    title: str = ""
    error: str = ""


class SummarizeRequest(BaseModel):
    url: str
    format: str = "summary"   # summary, key_points, mind_map, qa
    force: bool = False        # force re-generate (ignore cache)


class SummaryResult(BaseModel):
    transcript: str = ""
    summary: str = ""
    format: str = "summary"
    cached: bool = False
    error: str = ""


class ChatRequest(BaseModel):
    url: str
    question: str
    subtitle_text: str = ""
