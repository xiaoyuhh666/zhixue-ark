"""画像与长期记忆服务：上下文注入 + 对话后自动提炼。

- build_context：检索用户画像 + 相关记忆，拼成所有智能体共享的背景文本
- extract_and_store：对话结束后在后台线程调用 LLM 提炼画像更新与新记忆
"""
import json
import logging

from sqlalchemy.orm import Session

from ..db import SessionLocal
from ..llm.client import get_chat_model
from ..models import Memory, User

logger = logging.getLogger("zhixue.profile")

EXTRACT_PROMPT = """你是用户画像与记忆抽取模块。阅读最新一轮对话，输出严格 JSON：
{"profile": {"major": "专业，无新信息则空串", "grade": "年级，无新信息则空串",
"interests_new": ["新出现的兴趣方向"], "goals_new": ["新出现的目标"]},
"memories": [{"content": "第三人称记忆条目", "tag": "study|competition|research|career|life|general"}]}

规则：
- 只提取对话中明确体现的信息，宁缺毋滥；没有新信息就输出空值
- memories 记录值得长期记住的事实（身份、目标、偏好、进行中的事项），每条不超过 40 字
- 只输出 JSON，不要任何其他文字"""


def _bigrams(text: str) -> set[str]:
    """中文/字母二元组，用于简单的相关度打分。"""
    cleaned = "".join(ch for ch in text if ch.isalnum())
    return {cleaned[i : i + 2] for i in range(len(cleaned) - 1)}


def retrieve_memories(db: Session, user_id: int, query: str, limit: int = 6) -> list[Memory]:
    """检索记忆：按与当前问题的二元组重合度打分，无命中时回落最近记忆。"""
    mems = db.query(Memory).filter_by(user_id=user_id).order_by(Memory.id.desc()).limit(200).all()
    if not mems:
        return []
    q_grams = _bigrams(query)
    scored = [(len(q_grams & _bigrams(m.content)), m) for m in mems]
    hits = [m for score, m in sorted(scored, key=lambda x: -x[0])[:limit] if score > 0]
    return hits if hits else mems[:5]


def build_context(db: Session, user_id: int, query: str, limit: int = 6) -> str:
    """组装注入智能体提示词的共享背景（画像 + 相关记忆）。"""
    lines: list[str] = []
    user = db.get(User, user_id)
    if user:
        facts = []
        if user.nickname:
            facts.append(f"昵称：{user.nickname}")
        if user.school:
            facts.append(f"学校：{user.school}")
        if user.major:
            facts.append(f"专业：{user.major}")
        if user.grade:
            facts.append(f"年级：{user.grade}")
        if user.interests:
            facts.append("兴趣方向：" + "、".join(user.interests[:8]))
        if user.goals:
            facts.append("当前目标：" + "、".join(user.goals[:5]))
        # 画像扩展（2026-09-20）：偏好与时间预算，供智能体定制回答节奏与规划粒度
        if user.preferences:
            facts.append("学习偏好：" + "、".join(user.preferences[:6]))
        if user.weekly_hours:
            facts.append(f"每周可投入：约 {user.weekly_hours} 小时")
        if facts:
            lines.append("[用户画像] " + "；".join(facts))

    mems = retrieve_memories(db, user_id, query, limit)
    if mems:
        lines.append("[长期记忆] " + "；".join(f"({m.tag}) {m.content}" for m in mems))
    return "\n".join(lines)


def _parse_extract_json(text: str) -> dict:
    """容错解析抽取输出（截取首尾大括号）。"""
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        return {}
    try:
        return json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return {}


def _merge_profile(db: Session, user: User, profile: dict) -> None:
    """合并画像：只填空字段 / 追加不重复的列表项。"""
    changed = False
    if profile.get("major") and not user.major:
        user.major = profile["major"][:128]
        changed = True
    if profile.get("grade") and not user.grade:
        user.grade = profile["grade"][:32]
        changed = True
    for field, new_key in (("interests", "interests_new"), ("goals", "goals_new")):
        new_items = profile.get(new_key) or []
        current = list(getattr(user, field) or [])
        for item in new_items:
            item = str(item).strip()[:40]
            if item and item not in current:
                current.append(item)
                changed = True
        setattr(user, field, current[:20])
    if changed:
        db.commit()


def _store_memories(db: Session, user_id: int, conv_id: int, items: list[dict]) -> int:
    """写入新记忆，基于内容归一化去重（双向包含视为重复）。"""
    existing = [m.content.strip() for m in db.query(Memory).filter_by(user_id=user_id).all()]
    added = 0
    for item in items:
        content = str(item.get("content", "")).strip()
        if not content or len(content) > 120:
            continue
        if any(content in e or e in content for e in existing):
            continue
        db.add(Memory(
            user_id=user_id,
            content=content,
            tag=str(item.get("tag", "general"))[:32],
            source_conversation_id=conv_id,
        ))
        existing.append(content)
        added += 1
    if added:
        db.commit()
    return added


def extract_and_store(user_id: int, conversation_id: int, provider: str, turns: list[tuple[str, str]]) -> None:
    """对话结束后调用（后台线程）：提炼画像更新与新记忆。

    turns: [("user", "..."), ("assistant", "...")] 通常是最后一轮问答。
    """
    dialogue = "\n".join(f"{role}: {content}" for role, content in turns)
    try:
        resp = get_chat_model(provider, temperature=0.1).invoke(
            f"{EXTRACT_PROMPT}\n\n对话片段：\n{dialogue}"
        )
        data = _parse_extract_json(resp.content if isinstance(resp.content, str) else str(resp.content))
        if not data:
            return
        with SessionLocal() as db:
            user = db.get(User, user_id)
            if user:
                _merge_profile(db, user, data.get("profile") or {})
            added = _store_memories(db, user_id, conversation_id, data.get("memories") or [])
            if added:
                logger.info("extract_and_store: 新增 %d 条记忆", added)
    except Exception:
        logger.exception("画像/记忆抽取失败（不影响对话）")
