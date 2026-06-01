import os
from pathlib import Path

from openai import OpenAI

# Load .env file if exists
_env_path = Path(__file__).parent / ".env"
if _env_path.exists():
    for line in _env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip())

_client = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        api_key = os.environ.get("OPENAI_API_KEY", "")
        base_url = os.environ.get("OPENAI_BASE_URL", None)
        if not api_key or api_key == "sk-your-key-here":
            raise ValueError("请在 backend/.env 中配置有效的 OPENAI_API_KEY")
        kwargs = {"api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url
        _client = OpenAI(**kwargs)
    return _client


def _resolve_text_model(explicit_model: str | None = None) -> str:
    """Resolve text generation model from env with a safe default."""
    return (
        explicit_model
        or os.environ.get("MODEL_NAME")
        or os.environ.get("OPENAI_MODEL")
        or "gpt-4o-mini"
    )


SYSTEM_PROMPT = """你是一个专业的视频内容分析助手。用户会给你一段视频的字幕/转录文本，你需要根据要求的格式输出总结。
要求：
- 使用与原文相同的语言（中文视频用中文，英文视频用英文）
- 输出结构清晰、内容准确
- 对于思维导图，使用 Markdown 层级标题格式（# ## ### ####）"""

FORMAT_PROMPTS = {
    "summary": """请对以下视频内容生成一份简明摘要，让读者快速判断是否值得细看。

要求：
1. **一句话定位**：用一句话说清楚这个视频讲什么、适合谁看
2. **核心收获**：用 2-3 句话概括看完这个视频能学到什么（不要展开细节）
3. **亮点速览**：列出 3-5 个关键词或短语（不是完整句子），让读者一眼抓住重点

总长度控制在 150 字以内，语气简洁有力，像一篇推荐语而非论文摘要。
不要包含详细步骤、操作流程或大段解释。

<transcript>
{transcript}
</transcript>""",

    "key_points": """请从以下视频内容中提炼关键技术要点和知识洞察。

要求：
- 提取视频中真正有价值的知识、技术、方法论、观点或结论
- 每个要点应是一条可独立理解的知识点，而不是对视频流程的复述
- 用简洁专业的语言表达，每条 1-2 句话
- 如果涉及具体命令/操作，提炼其用途和场景，而非罗列步骤
- 按逻辑主题分组（而非按视频时间顺序），每组一个主题标题
- 总计 8-12 个要点

输出格式示例：
**主题A**
- 要点1
- 要点2

**主题B**
- 要点3

不要输出视频概述、开场白或总结性废话。

<transcript>
{transcript}
</transcript>""",

    "mind_map": """请将以下视频内容转换为思维导图格式。
使用 Markdown 层级标题，规则如下：
- # 是中心主题（视频标题）
- ## 是一级分支（主要章节）
- ### 是二级分支（子话题）
- #### 是三级分支（具体要点）
要求：
- 每个节点文字不超过 15 个字
- 结构层次清晰，不超过 4 层
- 覆盖视频的重要内容

<transcript>
{transcript}
</transcript>""",

    "qa": """请根据以下视频内容生成 8-10 组问答对：
- 问题覆盖视频的核心知识点
- 答案简洁准确，每组 2-3 句话
- 按视频内容顺序排列
- 格式：Q: 问题\nA: 答案

<transcript>
{transcript}
</transcript>""",
}


def summarize(transcript: str, format_type: str = "summary", model: str = None) -> str:
    """Call OpenAI API to summarize the transcript."""
    client = _get_client()
    model = _resolve_text_model(model)

    if len(transcript) > 100000:
        transcript = transcript[:100000] + "\n\n[...转录文本过长，已截断...]"

    prompt = FORMAT_PROMPTS.get(format_type, FORMAT_PROMPTS["summary"]).format(transcript=transcript)

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        max_tokens=4096,
        temperature=0.3,
    )

    content = response.choices[0].message.content
    if not content:
        raise RuntimeError("AI 返回为空，请检查模型可用性与账号配额。")
    return content


def summarize_stream(transcript: str, format_type: str = "summary", model: str = None):
    """Streaming version of summarize - yields tokens incrementally."""
    client = _get_client()
    model = _resolve_text_model(model)

    if len(transcript) > 100000:
        transcript = transcript[:100000] + "\n\n[...转录文本过长，已截断...]"

    prompt = FORMAT_PROMPTS.get(format_type, FORMAT_PROMPTS["summary"]).format(transcript=transcript)

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        max_tokens=4096,
        temperature=0.3,
        stream=True,
    )

    for chunk in response:
        if not chunk.choices:
            continue
        delta = chunk.choices[0].delta
        if delta.content:
            yield delta.content


CHAT_SYSTEM_PROMPT = """你是一个视频内容问答助手。根据提供的视频字幕内容来回答用户的问题。
要求：
- 基于视频内容给出准确、详细的回答
- 如果问题超出视频内容范围，请诚实告知
- 使用与视频字幕相同的语言回答"""


def chat_stream(transcript: str, question: str, model: str = None):
    """Streaming Q&A based on video transcript - yields tokens incrementally."""
    client = _get_client()
    model = _resolve_text_model(model)

    if len(transcript) > 12000:
        transcript = transcript[:12000] + "\n\n[...字幕文本过长，已截断...]"

    prompt = f"""以下是一个视频的字幕内容，请根据这些内容回答用户的问题。

视频字幕内容：
{transcript}

---
用户问题：{question}

请基于视频内容给出准确、详细的回答。如果视频内容中没有相关信息，请诚实说明。"""

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": CHAT_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        max_tokens=2048,
        temperature=0.7,
        stream=True,
    )

    for chunk in response:
        if not chunk.choices:
            continue
        delta = chunk.choices[0].delta
        if delta.content:
            yield delta.content
