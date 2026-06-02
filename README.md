# AI 视频助手

> 1800+ 平台视频下载 · AI 智能摘要与要点提炼

一个支持 1800+ 平台的视频下载工具，集成 AI 视频总结功能。输入视频链接，即可解析下载视频，并通过 AI 快速提炼视频的核心知识与要点。

![image-20260602001804581](https://gitee.com/h29/drawing-bed/raw/master/img/image-20260602001804581.png)


![image-20260602002250609](https://gitee.com/h29/drawing-bed/raw/master/img/image-20260602002250609.png)

## ✨ 核心功能

**视频下载**
- 支持 B站、YouTube、抖音等 1800+ 平台
- 自动解析视频信息（标题、封面、时长、播放量）
- 多画质选择，一键下载
- SSE 实时推送下载进度

**AI 视频总结**
- **摘要** — 150 字以内的速览推荐语，快速判断是否值得细看
- **要点** — 按主题分组的技术要点与知识洞察提炼
- **思维导图** — 视频内容的层级结构化展示
- **Q&A 问答** — 基于视频内容的智能对话
- 全程 SSE 流式输出，逐字渲染

## 🛠 技术栈

| 层级 | 技术 |
|------|------|
| 下载核心 | yt-dlp |
| 后端 | FastAPI + Uvicorn + Pydantic |
| 前端 | Vue 3 + Naive UI + Vite |
| AI | OpenAI 兼容 API（语音转文字 + 流式总结） |
| 实时通信 | SSE（sse-starlette） |
| 音频处理 | ffmpeg + pydub |

## 🚀 快速开始

### 环境要求

- Python 3.10+
- Node.js 18+
- ffmpeg

### 1. 配置后端

```bash
cd backend
pip install -r requirements.txt
```

创建 `backend/.env` 文件，配置 AI 模型：

```env
OPENAI_API_KEY=your-api-key
OPENAI_BASE_URL=https://api-endpoint/v1
MODEL_NAME=model-name
```

### 2. 启动后端

```bash
cd backend
python main.py
# 或
uvicorn main:app --host 0.0.0.0 --port 8000
```

### 3. 启动前端

```bash
cd frontend
npm install
npm run dev
```

访问 `http://localhost:5173` 即可使用。

### 4. 生产部署

```bash
cd frontend
npm run build
cd ../backend
python main.py
# 访问 http://localhost:8000
```

## 📁 项目结构

```
VideoDownload/
├── backend/
│   ├── main.py              # FastAPI 入口 + SSE 端点
│   ├── downloader.py        # yt-dlp 视频解析与下载
│   ├── subtitles.py         # 字幕提取（yt-dlp + B站专用 API）
│   ├── summarizer.py        # AI 流式总结与问答
│   ├── transcription.py     # Whisper 语音转文字（字幕回退）
│   ├── pipeline.py          # 流程编排
│   ├── models.py            # 数据模型
│   ├── config.py            # 配置管理
│   └── requirements.txt     # Python 依赖
├── frontend/
│   ├── src/
│   │   ├── App.vue          # 主应用
│   │   ├── api.js           # API 调用 + SSE 解析
│   │   └── components/
│   │       ├── UrlInput.vue         # 链接输入
│   │       ├── VideoInfo.vue        # 视频信息卡片
│   │       ├── QualitySelect.vue    # 画质选择
│   │       ├── DownloadProgress.vue # 下载进度条
│   │       ├── AiSummary.vue        # AI 总结面板
│   │       └── MindMap.vue          # 思维导图渲染
│   ├── index.html
│   ├── package.json
│   └── vite.config.js
└── README.md
```

## 🔌 API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/parse` | 解析视频信息 |
| POST | `/api/download` | 启动下载任务 |
| GET | `/api/progress/{task_id}` | SSE 下载进度流 |
| POST | `/api/summarize` | AI 视频总结（SSE 流式） |
| POST | `/api/chat` | AI 问答（SSE 流式） |
| GET | `/api/file/{task_id}` | 下载已完成的文件 |

## ⚙️ 代理配置

如需访问 YouTube 等平台，设置环境变量：

```bash
export HTTP_PROXY=http://127.0.0.1:7890
export HTTPS_PROXY=http://127.0.0.1:7890
```

## 🍪 B站 Cookies 配置

B站未登录状态下会触发 412 反爬限制，且最高仅 480p。配置 Cookies 可解决：

1. 浏览器登录 B站
2. 安装浏览器插件 [Get cookies.txt LOCALLY](https://chrome.google.com/webstore/detail/cclelndahbckbenkjhflpdbgdldlbecc)
3. 在 B站任意页面点击插件 → **Export** → 保存为 `cookies.txt`
4. 将文件放到 `backend/cookies.txt`
5. 重启后端即可

> Cookies 过期后重新导出一次即可。支持 B站 App 分享的短链接（`b23.tv`），会自动解析为完整链接。

## 📱 手机端使用

本工具支持手机端访问，有两种方式：

**局域网访问**（同一 WiFi 下）
> 若是校园网，可以通过电脑/手机开热点

```bash
# 启动后端（默认监听 0.0.0.0:8000）
cd backend
python main.py
```

手机浏览器访问 `http://电脑局域网IP:8000`。如遇无法访问，需放行 Windows 防火墙：

```powershell
netsh advfirewall firewall add rule name="VideoAI 8000" dir=in action=allow protocol=tcp localport=8000
```

**内网穿透**（任意网络，有风险，不建议！！！）

使用 [cpolar](https://www.cpolar.com/)、[ngrok](https://ngrok.com/) 等工具将本地服务暴露到公网：

```bash
cpolar http 8000
```

获取公网 URL 后，手机随时可访问。

## 📝 已知限制

- 任务数据存储在内存中，服务器重启后丢失
- MVP 阶段面向单用户设计

## 🙏 参考项目

- [free-video-downloader](https://github.com/liyupi/free-video-downloader) — 程序员鱼皮的开源视频下载器项目，本项目在此基础上扩展了 AI 视频要点总结功能
- [yt-dlp](https://github.com/yt-dlp/yt-dlp) — 1800+ 平台视频解析与下载核心
