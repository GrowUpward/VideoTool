import json
from pathlib import Path

from config import BASE_DIR
from subtitles import extract_subtitles, get_last_error as get_subtitle_error
from summarizer import summarize
from transcription import transcribe_audio, get_last_error as get_transcribe_error

CACHE_DIR = BASE_DIR / "cache"
CACHE_DIR.mkdir(exist_ok=True)


def _cache_path(url: str, format_type: str) -> Path:
    """Generate a cache file path from URL + format type."""
    import hashlib

    url_hash = hashlib.md5(url.encode()).hexdigest()[:12]
    return CACHE_DIR / f"{url_hash}_{format_type}.json"


def get_cached_result(url: str, format_type: str) -> dict | None:
    """Return cached summary if it exists."""
    path = _cache_path(url, format_type)
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return None
    return None


def save_cache(url: str, format_type: str, result: dict):
    """Save summary result to cache."""
    path = _cache_path(url, format_type)
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")


def run_summary_pipeline(url: str, format_type: str = "summary", force: bool = False) -> dict:
    """Run subtitles -> transcription fallback -> summarization."""
    if not force:
        cached = get_cached_result(url, format_type)
        if cached:
            cached["cached"] = True
            return cached

    subtitle_data = extract_subtitles(url)
    transcript = subtitle_data.get("full_text", "") if subtitle_data else ""

    if not transcript:
        transcript = transcribe_audio(url)
        if transcript:
            subtitle_data = {
                "has_subtitle": True, "language": "", "subtitle_type": "none",
                "segments": [], "full_text": transcript,
            }

    if not transcript:
        subtitle_err = get_subtitle_error()
        transcribe_err = get_transcribe_error()
        detail_parts = []
        if subtitle_err:
            detail_parts.append(f"字幕提取错误: {subtitle_err}")
        if transcribe_err:
            detail_parts.append(f"语音转录错误: {transcribe_err}")
        detail = "；".join(detail_parts)
        return {
            "error": (
                "无法获取视频内容。可能原因：1) 视频没有字幕 2) 当前模型或接口不支持转录 "
                "3) 平台需要 cookies 才能抓取字幕。建议先测试带字幕的公开视频。"
                + (f" 详细信息：{detail}" if detail else "")
            ),
            "transcript": "",
            "summary": "",
            "format": format_type,
            "cached": False,
            "subtitle_data": subtitle_data or {},
        }

    try:
        summary_text = summarize(transcript, format_type)
    except Exception as e:
        return {
            "error": f"AI 总结失败: {e}",
            "transcript": transcript,
            "summary": "",
            "format": format_type,
            "cached": False,
            "subtitle_data": subtitle_data,
        }

    result = {
        "transcript": transcript,
        "summary": summary_text,
        "format": format_type,
        "cached": False,
        "error": "",
        "subtitle_data": subtitle_data,
    }
    save_cache(url, format_type, result)
    return result
