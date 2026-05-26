import tempfile
from pathlib import Path

import yt_dlp

from config import HTTP_PROXY, HTTPS_PROXY
from summarizer import _get_client


TRANSCRIBE_MODEL = "whisper-1"
_last_error = ""


def get_last_error() -> str:
    return _last_error


def _download_audio(url: str) -> str:
    """Download audio from video URL using yt-dlp, return path to audio file."""
    tmpdir = tempfile.mkdtemp()
    opts = {
        "quiet": True,
        "no_warnings": True,
        "format": "bestaudio/best",
        "outtmpl": str(Path(tmpdir) / "%(id)s.%(ext)s"),
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "64",
        }],
    }
    if HTTP_PROXY:
        opts["proxy"] = HTTP_PROXY
    elif HTTPS_PROXY:
        opts["proxy"] = HTTPS_PROXY

    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)
        video_id = info.get("id", "audio")

    audio_path = Path(tmpdir) / f"{video_id}.mp3"
    if audio_path.exists():
        return str(audio_path)

    for f in Path(tmpdir).glob("*.mp3"):
        return str(f)
    for f in Path(tmpdir).glob("*"):
        if f.is_file():
            return str(f)

    raise RuntimeError("音频提取失败")


def _split_audio(audio_path: str, chunk_minutes: int = 10) -> list[str]:
    """Split audio into chunks for Whisper API."""
    from pydub import AudioSegment

    audio = AudioSegment.from_file(audio_path)
    chunk_ms = chunk_minutes * 60 * 1000
    chunks = []

    for i, start in enumerate(range(0, len(audio), chunk_ms)):
        chunk = audio[start:start + chunk_ms]
        chunk_path = audio_path.replace(".mp3", f"_chunk{i}.mp3")
        chunk.export(chunk_path, format="mp3", bitrate="64k")
        chunks.append(chunk_path)

    return chunks if chunks else [audio_path]


def transcribe_audio(url: str) -> str | None:
    """Download audio and transcribe using OpenAI API. Returns transcript or None."""
    global _last_error
    _last_error = ""
    try:
        audio_path = _download_audio(url)
    except Exception as e:
        _last_error = f"音频下载失败: {e}"
        return None

    try:
        client = _get_client()
    except Exception as e:
        _last_error = f"OpenAI 客户端初始化失败: {e}"
        return None

    file_size = Path(audio_path).stat().st_size
    chunks = _split_audio(audio_path) if file_size > 20 * 1024 * 1024 else [audio_path]

    transcripts = []
    for chunk_path in chunks:
        try:
            with open(chunk_path, "rb") as f:
                try:
                    # Newer API style
                    result = client.audio.transcriptions.create(
                        model=TRANSCRIBE_MODEL,
                        file=f,
                    )
                    text = getattr(result, "text", None) or (result if isinstance(result, str) else "")
                except Exception:
                    # Legacy fallback style
                    f.seek(0)
                    result = client.audio.transcriptions.create(
                        model=TRANSCRIBE_MODEL,
                        file=f,
                        response_format="text",
                    )
                    text = result if isinstance(result, str) else getattr(result, "text", "")

            if text:
                transcripts.append(text)
        except Exception as e:
            _last_error = f"语音转录失败: {e}"
            continue

    for chunk_path in chunks:
        try:
            Path(chunk_path).unlink(missing_ok=True)
        except Exception:
            pass
    try:
        Path(audio_path).unlink(missing_ok=True)
    except Exception:
        pass

    if transcripts:
        return "\n".join(transcripts)
    if not _last_error:
        _last_error = "语音转录失败: 未返回可用文本"
    return None
