import asyncio
import json
from collections.abc import AsyncIterable
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from sse_starlette.sse import EventSourceResponse

import requests as http_requests

from models import ParseRequest, DownloadRequest, VideoInfo, SummarizeRequest, SummaryResult, ChatRequest
from downloader import parse_video_info, start_download, get_task, extract_url
from subtitles import extract_subtitles
from summarizer import summarize_stream, chat_stream
from transcription import transcribe_audio, get_last_error as get_transcribe_error
from config import HTTP_PROXY, HTTPS_PROXY

summary_executor = ThreadPoolExecutor(max_workers=2)

app = FastAPI(title="AI 视频助手")

# Paths
FRONTEND_DIST = Path(__file__).parent.parent / "frontend" / "dist"


@app.post("/api/parse", response_model=VideoInfo)
async def parse_video(req: ParseRequest):
    """解析视频链接，返回视频信息和可用画质。"""
    try:
        info = parse_video_info(req.url)
        return info
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"解析失败: {e}")


@app.post("/api/download")
async def download_video(req: DownloadRequest):
    """启动下载任务，返回 task_id。"""
    try:
        task_id = await start_download(req.url, req.quality)
        return {"task_id": task_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"下载启动失败: {e}")


@app.get("/api/proxy/thumbnail")
async def proxy_thumbnail(url: str):
    """代理图片请求，绕过 CDN 防盗链（Referer 检查）。"""
    try:
        proxies = None
        if HTTP_PROXY:
            proxies = {"http": HTTP_PROXY, "https": HTTPS_PROXY or HTTP_PROXY}
        elif HTTPS_PROXY:
            proxies = {"https": HTTPS_PROXY}
        resp = http_requests.get(url, timeout=10, proxies=proxies,
                                  headers={"User-Agent": "Mozilla/5.0"})
        if not resp.ok:
            raise HTTPException(status_code=resp.status_code, detail="图片获取失败")
        return StreamingResponse(
            iter([resp.content]),
            media_type=resp.headers.get("Content-Type", "image/jpeg"),
            headers={"Cache-Control": "public, max-age=86400"},
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"代理失败: {e}")


@app.get("/api/progress/{task_id}")
async def download_progress(task_id: str):
    """SSE 流式推送下载进度。"""

    async def event_generator():
        while True:
            task = get_task(task_id)
            if not task:
                yield f"data: {json.dumps({'status': 'not_found'})}\n\n"
                break
            data = task.model_dump()
            yield f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
            if task.status in ("completed", "failed"):
                break
            await asyncio.sleep(0.5)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/api/summarize")
async def summarize_video(req: SummarizeRequest):
    """AI 视频总结：提取字幕 → 流式 GPT 总结 (SSE)。"""
    req.url = extract_url(req.url)

    async def event_generator():
        loop = asyncio.get_event_loop()

        # 1. Extract subtitles (blocking, run in executor)
        try:
            subtitle_data = await loop.run_in_executor(
                summary_executor, extract_subtitles, req.url
            )
        except Exception as e:
            yield {"event": "error", "data": json.dumps({"message": f"字幕提取失败: {e}"}, ensure_ascii=False)}
            return

        # 2. If no subtitles, try Whisper fallback
        if not subtitle_data.get("has_subtitle"):
            try:
                transcript = await loop.run_in_executor(
                    summary_executor, transcribe_audio, req.url
                )
                if transcript:
                    subtitle_data = {
                        "has_subtitle": True, "language": "", "subtitle_type": "none",
                        "segments": [], "full_text": transcript,
                    }
            except Exception:
                pass

        # 3. Emit subtitle event
        yield {"event": "subtitle", "data": json.dumps(subtitle_data, ensure_ascii=False)}

        if not subtitle_data.get("has_subtitle"):
            transcribe_err = get_transcribe_error()
            detail = f" 详细信息：{transcribe_err}" if transcribe_err else ""
            yield {
                "event": "error",
                "data": json.dumps({"message": "该视频没有可用的字幕，无法生成总结。" + detail}, ensure_ascii=False),
            }
            return

        # 4. Stream summary tokens
        full_text = subtitle_data["full_text"]
        try:
            for token in summarize_stream(full_text, req.format):
                yield {"event": "summary", "data": json.dumps(token, ensure_ascii=False)}
        except Exception as e:
            yield {"event": "error", "data": json.dumps({"message": f"AI 总结失败: {e}"}, ensure_ascii=False)}
            return

        # 5. Done
        yield {"event": "done", "data": "[DONE]"}

    return EventSourceResponse(event_generator())


@app.post("/api/chat")
async def chat_with_video(req: ChatRequest):
    """基于视频内容的 AI 问答 (SSE 流式)。"""
    req.url = extract_url(req.url)

    async def event_generator():
        subtitle_text = req.subtitle_text

        # If no subtitle text provided, extract from URL
        if not subtitle_text.strip():
            loop = asyncio.get_event_loop()
            try:
                subtitle_data = await loop.run_in_executor(
                    summary_executor, extract_subtitles, req.url
                )
                subtitle_text = subtitle_data.get("full_text", "")
            except Exception:
                pass

        if not subtitle_text.strip():
            yield {"event": "error", "data": json.dumps({"message": "无法获取视频字幕内容，无法回答问题"}, ensure_ascii=False)}
            return

        # Stream answer tokens
        try:
            for token in chat_stream(subtitle_text, req.question):
                yield {"event": "answer", "data": json.dumps(token, ensure_ascii=False)}
        except Exception as e:
            yield {"event": "error", "data": json.dumps({"message": f"回答失败: {e}"}, ensure_ascii=False)}
            return

        yield {"event": "done", "data": "[DONE]"}

    return EventSourceResponse(event_generator())


@app.get("/api/file/{task_id}")
async def get_file(task_id: str):
    """下载完成的文件。"""
    task = get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    if task.status != "completed":
        raise HTTPException(status_code=400, detail="下载尚未完成")
    filepath = Path(task.filename)
    if not filepath.exists():
        raise HTTPException(status_code=404, detail="文件不存在")
    return FileResponse(
        filepath,
        filename=filepath.name,
        media_type="application/octet-stream",
    )


# Serve frontend static files (production mode)
if FRONTEND_DIST.exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")

    @app.get("/")
    async def serve_index():
        return FileResponse(FRONTEND_DIST / "index.html")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
