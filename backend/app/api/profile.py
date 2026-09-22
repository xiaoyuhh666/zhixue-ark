"""用户画像接口：查看 + 手动编辑 + 对话提炼候选（画像改版 2026-09-20）。"""
import re

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Conversation, KnowledgeDoc, Memory, Message
from .auth import get_current_user

router = APIRouter(prefix="/api/profile", tags=["profile"])

# 汇总/调度类标签不算「最常用智能体」
_META_AGENTS = {"智学方舟", "调度智能体", "多智能体协作", "调度智能体 · 汇总", ""}

# 提炼规则（演示可用、答辩可控）：关键词 -> 候选标签；真实模式可在此替换/叠加 LLM 抽取
_INTEREST_RULES = [
    (r"算法|ACM|蓝桥|PAT", "算法竞赛"),
    (r"后端|Java|Spring|接口开发", "后端开发"),
    (r"前端|Vue|React|页面", "前端开发"),
    (r"机器学习|深度学习|论文|训练模型", "机器学习"),
    (r"数据结构|二叉树|链表|排序", "数据结构"),
    (r"数学建模|国赛|美赛", "数学建模"),
    (r"实习|简历|秋招|面试", "求职准备"),
    (r"科研|项目|实验室|开源", "科研探索"),
    (r"考研|保研|复试", "考研升学"),
]
_GOAL_RULES = [
    (r"期末|复习|考试|绩点", "期末考试高分通过"),
    (r"数学建模|国赛|竞赛|蓝桥", "拿下学科竞赛奖项"),
    (r"实习|简历|秋招|面试", "拿到心仪实习 offer"),
    (r"科研|项目|论文", "完成第一个科研项目"),
    (r"考研|保研", "考研上岸目标院校"),
    (r"数据结构|复习计划", "吃透数据结构核心考点"),
]


class ProfileUpdate(BaseModel):
    nickname: str | None = None
    major: str | None = None
    grade: str | None = None
    school: str | None = None
    preferences: list[str] | None = None
    weekly_hours: int | None = None
    interests: list[str] | None = None
    goals: list[str] | None = None


def _top_agent(db: Session, user_id: int) -> tuple[str, int]:
    """最常用智能体：当前用户的 assistant 消息按 agent 计数（去「·」后缀，排除调度类）。"""
    rows = (
        db.query(Message.agent, func.count(Message.id))
        .join(Conversation, Message.conversation_id == Conversation.id)
        .filter(Message.role == "assistant", Conversation.user_id == user_id)
        .group_by(Message.agent)
        .all()
    )
    merged: dict[str, int] = {}
    for agent, cnt in rows:
        key = (agent or "").split("·")[0].strip()
        if key in _META_AGENTS:
            continue
        merged[key] = merged.get(key, 0) + cnt
    if not merged:
        return "—", 0
    name, cnt = max(merged.items(), key=lambda x: x[1])
    return name, cnt


@router.get("")
def get_profile(user=Depends(get_current_user), db: Session = Depends(get_db)):
    top_agent, top_count = _top_agent(db, user.id)
    return {
        "nickname": user.nickname,
        "major": user.major,
        "grade": user.grade,
        "school": user.school,
        "preferences": user.preferences or [],
        "weekly_hours": user.weekly_hours or 0,
        "interests": user.interests or [],
        "goals": user.goals or [],
        "memory_count": db.query(Memory).filter_by(user_id=user.id).count(),
        "conversation_count": db.query(Conversation).filter_by(user_id=user.id).count(),
        "doc_count": db.query(KnowledgeDoc).filter_by(user_id=user.id).count(),
        "top_agent": top_agent,
        "top_agent_count": top_count,
    }


@router.put("")
def update_profile(body: ProfileUpdate, user=Depends(get_current_user), db: Session = Depends(get_db)):
    if body.nickname is not None:
        user.nickname = body.nickname.strip()[:64]
    if body.major is not None:
        user.major = body.major.strip()[:128]
    if body.grade is not None:
        user.grade = body.grade.strip()[:32]
    if body.school is not None:
        user.school = body.school.strip()[:128]
    if body.preferences is not None:
        user.preferences = [i.strip()[:40] for i in body.preferences if i.strip()][:20]
    if body.weekly_hours is not None:
        user.weekly_hours = max(0, min(int(body.weekly_hours), 168))
    if body.interests is not None:
        user.interests = [i.strip()[:40] for i in body.interests if i.strip()][:20]
    if body.goals is not None:
        user.goals = [g.strip()[:40] for g in body.goals if g.strip()][:20]
    db.commit()
    return {"ok": True}


@router.post("/extract")
def extract_candidates(user=Depends(get_current_user), db: Session = Depends(get_db)):
    """从最近对话 + 长期记忆提炼画像候选（只返回候选，由用户勾选后合入，不直接写入）。"""
    msgs = (
        db.query(Message)
        .join(Conversation, Message.conversation_id == Conversation.id)
        .filter(Message.role == "user", Conversation.user_id == user.id)
        .order_by(Message.id.desc())
        .limit(20)
        .all()
    )
    mems = (
        db.query(Memory)
        .filter_by(user_id=user.id)
        .order_by(Memory.id.desc())
        .limit(10)
        .all()
    )
    corpus = " ".join(m.content for m in msgs) + " " + " ".join(m.content for m in mems)

    def _pick(rules, existing):
        found = []
        for pattern, label in rules:
            if re.search(pattern, corpus) and label not in existing:
                found.append(label)
        return found[:4]

    return {
        "interests": _pick(_INTEREST_RULES, set(user.interests or [])),
        "goals": _pick(_GOAL_RULES, set(user.goals or [])),
        "scanned": len(msgs),
        "memory_used": len(mems),
    }
