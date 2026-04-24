"""AI content generation using LLM APIs - with data-driven prompt injection."""

import json
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
    account_id: Optional[str] = None
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    model: str = "gpt-4o-mini"
    trending_titles: list[str] = []
    direction_name: str = ""
    direction_keywords: list[str] = []


class GenerateResponse(BaseModel):
    success: bool
    title: str = ""
    body: str = ""
    tags: list[str] = []
    score: int = 0
    score_breakdown: dict = {}
    message: str = ""


class TopicSuggestion(BaseModel):
    topic: str
    reason: str
    estimated_engagement: str
    confidence: float = 0.0


class TopicResponse(BaseModel):
    success: bool
    suggestions: list[TopicSuggestion] = []
    data_driven: bool = False
    message: str = ""


def _build_data_context(account_id: Optional[str], trending: list[str]) -> str:
    """Build rich context from historical data and trending content."""
    sections = []

    if account_id:
        try:
            from core.analyzer import _load_history, _extract_pattern
            notes = _load_history(account_id)
            if notes:
                for n in notes:
                    n.calc_engagement()
                pattern = _extract_pattern(notes)

                sections.append(f"""【历史数据分析 - 基于 {len(notes)} 篇笔记】
- 高互动笔记平均标题长度：{pattern.avg_title_length} 字
- 高互动笔记平均正文字数：{int(pattern.avg_word_count)} 字
- Emoji使用率：{pattern.emoji_usage_rate}%
- 最佳互动率：{pattern.best_engagement_rate}%
- 平均互动率：{pattern.avg_engagement_rate}%
- 高频标签：{', '.join(pattern.top_tags[:8])}
- 爆款标题示例：
{chr(10).join(f'  ★ {t}' for t in pattern.best_titles[:5])}""")
        except Exception:
            pass

    if trending:
        sections.append(f"""【当前热门内容参考】
{chr(10).join(f'  🔥 {t}' for t in trending[:8])}""")

    return "\n\n".join(sections)


def _score_content(title: str, body: str, tags: list[str], account_id: Optional[str]) -> tuple[int, dict]:
    """Score generated content based on historical patterns (0-100)."""
    breakdown = {}
    score = 60  # base score

    # Title quality
    title_len = len(title)
    has_emoji = any(ord(c) > 0x1F300 for c in title)
    if 8 <= title_len <= 25:
        breakdown["标题长度"] = 10
        score += 10
    elif title_len > 25:
        breakdown["标题长度"] = 3
        score += 3
    else:
        breakdown["标题长度"] = 5
        score += 5

    if has_emoji:
        breakdown["Emoji使用"] = 5
        score += 5

    # Body quality
    body_len = len(body)
    if 200 <= body_len <= 600:
        breakdown["正文长度"] = 10
        score += 10
    elif body_len > 600:
        breakdown["正文长度"] = 5
        score += 5

    paragraphs = body.count("\n\n") + 1
    if paragraphs >= 3:
        breakdown["段落结构"] = 5
        score += 5

    # Tags
    if 3 <= len(tags) <= 8:
        breakdown["标签数量"] = 5
        score += 5

    # Pattern matching (if historical data available)
    if account_id:
        try:
            from core.analyzer import _load_history, _extract_pattern
            notes = _load_history(account_id)
            if notes:
                for n in notes:
                    n.calc_engagement()
                pattern = _extract_pattern(notes)
                tag_overlap = len(set(tags) & set(pattern.top_tags))
                if tag_overlap > 0:
                    tag_bonus = min(tag_overlap * 2, 5)
                    breakdown["标签匹配历史热门"] = tag_bonus
                    score += tag_bonus
        except Exception:
            pass

    return min(score, 100), breakdown


@ai_router.post("/generate", response_model=GenerateResponse)
async def generate_content(req: GenerateRequest):
    """Generate content with data-driven prompt enrichment."""
    try:
        api_key = req.api_key or os.getenv("OPENAI_API_KEY", "")
        if not api_key:
            return GenerateResponse(success=False, message="未配置 API Key")

        client = AsyncOpenAI(
            api_key=api_key,
            base_url=req.base_url if req.base_url else None,
        )

        data_context = _build_data_context(req.account_id, req.trending_titles)

        direction_context = ""
        if req.direction_name:
            direction_context = f"\n内容方向：{req.direction_name}"
            if req.direction_keywords:
                direction_context += f"\n方向关键词：{', '.join(req.direction_keywords)}"
            direction_context += "\n请确保生成的内容紧扣该内容方向，体现垂直领域的专业性。\n"

        prompt = f"""你是一个顶级小红书内容创作专家，擅长写出高互动率的爆款笔记。

请根据以下要求生成一篇小红书笔记：

主题：{req.topic}
风格：{req.style}
语气：{req.tone}
字数：约{req.word_count}字
{direction_context}"""

        if data_context:
            prompt += f"""
以下是基于数据分析得出的关键参考信息，请据此优化你的内容策略：

{data_context}

【创作策略要求】
1. 标题要参考爆款标题的句式和长度，吸引点击
2. 正文结构要清晰，多分段，适当使用emoji增加可读性
3. 标签要结合历史高频标签和当前热门趋势
4. 开头要有强烈的钩子（hook），让用户想继续读
5. 结尾要引导互动（提问/投票/留言）
"""

        prompt += """
请按以下 JSON 格式返回（不要包含 markdown 代码块标记）：
{
    "title": "标题（吸引眼球，8-22字，适当emoji）",
    "body": "正文内容（自然分段，开头有hook，结尾引导互动）",
    "tags": ["标签1", "标签2", "标签3", "标签4", "标签5"]
}"""

        response = await client.chat.completions.create(
            model=req.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.8,
        )

        text = response.choices[0].message.content.strip()
        text = text.replace("```json", "").replace("```", "").strip()
        data = json.loads(text)

        title = data.get("title", "")
        body = data.get("body", "")
        tags = data.get("tags", [])
        score, breakdown = _score_content(title, body, tags, req.account_id)

        return GenerateResponse(
            success=True,
            title=title,
            body=body,
            tags=tags,
            score=score,
            score_breakdown=breakdown,
        )
    except Exception as e:
        return GenerateResponse(success=False, message=str(e))


@ai_router.post("/suggest_topics", response_model=TopicResponse)
async def suggest_topics(req: GenerateRequest):
    """Data-driven topic suggestions based on performance + trends."""
    try:
        key = req.api_key or os.getenv("OPENAI_API_KEY", "")
        if not key:
            return TopicResponse(success=False, message="未配置 API Key")

        client = AsyncOpenAI(api_key=key, base_url=req.base_url if req.base_url else None)

        data_context = _build_data_context(req.account_id, req.trending_titles)
        data_driven = bool(data_context.strip())

        direction_hint = ""
        if req.direction_name:
            direction_hint = f"\n内容方向约束：{req.direction_name}"
            if req.direction_keywords:
                direction_hint += f"\n方向关键词：{', '.join(req.direction_keywords)}"
            direction_hint += "\n所有选题必须紧扣该内容方向，保持账号垂直度。\n"

        prompt = f"""你是小红书运营数据分析专家。请基于以下数据推荐 5 个高潜力选题：

目标领域/主题方向：{req.topic}
{direction_hint}"""
        if data_context:
            prompt += f"""
{data_context}

【选题策略】
1. 结合历史高互动内容的共性特征
2. 参考当前热门趋势，找到差异化切入角度
3. 避免与已发布内容过度重复
4. 优先推荐"高搜索量 + 低竞争"的蓝海选题
"""

        prompt += """
请按 JSON 数组格式返回（不要包含 markdown 代码块标记）：
[
    {"topic": "选题标题", "reason": "推荐理由（结合数据说明）", "estimated_engagement": "预估互动量级", "confidence": 0.85}
]

confidence 为 0-1 之间的置信度，基于数据支撑程度判断。"""

        response = await client.chat.completions.create(
            model=req.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.9,
        )

        text = response.choices[0].message.content.strip()
        text = text.replace("```json", "").replace("```", "").strip()
        data = json.loads(text)

        return TopicResponse(
            success=True,
            suggestions=[TopicSuggestion(**s) for s in data],
            data_driven=data_driven,
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
