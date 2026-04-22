"""AI content generation using LLM APIs."""

import os
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional
from openai import AsyncOpenAI

ai_router = APIRouter()


class GenerateRequest(BaseModel):
    topic: str
    style: str = "种草推荐"
    tone: str = "活泼"
    word_count: int = 300
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    model: str = "gpt-4o-mini"


class GenerateResponse(BaseModel):
    success: bool
    title: str = ""
    body: str = ""
    tags: list[str] = []
    message: str = ""


class TopicSuggestion(BaseModel):
    topic: str
    reason: str
    estimated_engagement: str


class TopicResponse(BaseModel):
    success: bool
    suggestions: list[TopicSuggestion] = []
    message: str = ""


@ai_router.post("/generate", response_model=GenerateResponse)
async def generate_content(req: GenerateRequest):
    """Generate Xiaohongshu post content using AI."""
    try:
        api_key = req.api_key or os.getenv("OPENAI_API_KEY", "")
        if not api_key:
            return GenerateResponse(success=False, message="未配置 API Key")

        client = AsyncOpenAI(
            api_key=api_key,
            base_url=req.base_url if req.base_url else None,
        )

        prompt = f"""你是一个小红书内容创作专家。请根据以下要求生成一篇小红书笔记：

主题：{req.topic}
风格：{req.style}
语气：{req.tone}
字数：约{req.word_count}字

请按以下 JSON 格式返回（不要包含 markdown 代码块标记）：
{{
    "title": "标题（带emoji，吸引眼球）",
    "body": "正文内容（自然分段，适当使用emoji）",
    "tags": ["标签1", "标签2", "标签3", "标签4", "标签5"]
}}"""

        response = await client.chat.completions.create(
            model=req.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.8,
        )

        import json

        text = response.choices[0].message.content.strip()
        text = text.replace("```json", "").replace("```", "").strip()
        data = json.loads(text)

        return GenerateResponse(
            success=True,
            title=data.get("title", ""),
            body=data.get("body", ""),
            tags=data.get("tags", []),
        )
    except Exception as e:
        return GenerateResponse(success=False, message=str(e))


@ai_router.post("/suggest_topics", response_model=TopicResponse)
async def suggest_topics(
    niche: str,
    recent_titles: list[str] = [],
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    model: str = "gpt-4o-mini",
):
    """Suggest content topics based on niche and past performance."""
    try:
        key = api_key or os.getenv("OPENAI_API_KEY", "")
        if not key:
            return TopicResponse(success=False, message="未配置 API Key")

        client = AsyncOpenAI(api_key=key, base_url=base_url if base_url else None)

        recent_str = "\n".join(f"- {t}" for t in recent_titles) if recent_titles else "暂无历史内容"

        prompt = f"""你是小红书运营专家。基于以下信息推荐5个高潜力选题：

领域：{niche}
已发布内容：
{recent_str}

请按 JSON 数组格式返回（不要包含 markdown 代码块标记）：
[
    {{"topic": "选题标题", "reason": "推荐理由", "estimated_engagement": "预估互动量级"}}
]"""

        response = await client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.9,
        )

        import json

        text = response.choices[0].message.content.strip()
        text = text.replace("```json", "").replace("```", "").strip()
        data = json.loads(text)

        return TopicResponse(
            success=True,
            suggestions=[TopicSuggestion(**s) for s in data],
        )
    except Exception as e:
        return TopicResponse(success=False, message=str(e))


@ai_router.post("/generate_reply")
async def generate_reply(
    comment_text: str,
    note_title: str = "",
    tone: str = "友好",
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    model: str = "gpt-4o-mini",
):
    """Generate AI reply for a comment."""
    try:
        key = api_key or os.getenv("OPENAI_API_KEY", "")
        if not key:
            return {"success": False, "message": "未配置 API Key"}

        client = AsyncOpenAI(api_key=key, base_url=base_url if base_url else None)

        prompt = f"""你是小红书博主。请为以下评论生成一个{tone}的回复。

笔记标题：{note_title}
评论内容：{comment_text}

要求：
- 自然真实，不要太官方
- 简短有趣，1-2句话
- 适当使用emoji

请直接返回回复文本，不要有其他格式。"""

        response = await client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.8,
        )

        reply = response.choices[0].message.content.strip()
        return {"success": True, "reply": reply}
    except Exception as e:
        return {"success": False, "message": str(e)}
