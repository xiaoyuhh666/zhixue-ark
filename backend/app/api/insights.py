"""学习足迹接口：近 14 天对话趋势 / 智能体使用分布 / 引用命中 / 活跃天数 / 薄弱点。"""
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Conversation, Memory, Message

router = APIRouter(prefix="/api/insights", tags=["insights"])

# 调度/汇总类标签不算领域智能体使用量
_META_AGENTS = {"智学方舟", "调度智能体", "多智能体协作", "调度智能体 · 汇总", ""}

# 薄弱关键词：长期记忆（画像提炼）中「××薄弱」「对××不熟」类条目即薄弱点
_WEAK_KEYWORDS = ["薄弱", "不熟", "不会", "困难", "吃力", "没掌握", "掌握不好", "恐惧", "焦虑"]


@router.get("")
def get_insights(db: Session = Depends(get_db)):
    # 近 14 天逐日用户消息量（含今天）
    since = datetime.now() - timedelta(days=13)
    rows = (
        db.query(Message.created_at, func.count(Message.id))
        .filter(Message.role == "user", Message.created_at >= since.replace(hour=0, minute=0))
        .group_by(func.date(Message.created_at))
        .all()
    )
    by_date = {r[0].strftime("%Y-%m-%d"): r[1] for r in rows}
    daily = []
    for i in range(14):
        d = (datetime.now() - timedelta(days=13 - i)).strftime("%Y-%m-%d")
        daily.append({"date": d[5:], "count": by_date.get(d, 0)})

    # 五智能体使用分布（assistant 消息，去掉「·」后缀归组，排除调度类）
    agent_rows = (
        db.query(Message.agent, func.count(Message.id))
        .filter(Message.role == "assistant")
        .group_by(Message.agent)
        .all()
    )
    merged: dict[str, int] = {}
    for agent, cnt in agent_rows:
        key = (agent or "").split("·")[0].strip()
        if key in _META_AGENTS:
            continue
        merged[key] = merged.get(key, 0) + cnt
    agents = [{"name": k, "count": v} for k, v in sorted(merged.items(), key=lambda x: -x[1])]

    # 引用命中：assistant 消息带 citations 的条数与片段总数
    cites = db.query(Message.citations).filter(
        Message.role == "assistant", Message.citations.isnot(None)
    ).all()
    cite_msgs = len(cites)
    cite_snippets = sum(len(c[0] or []) for c in cites)

    # 活跃天数：发过消息的不同日期数
    days = db.query(func.count(func.distinct(func.date(Message.created_at)))).filter(
        Message.role == "user"
    ).scalar() or 0

    # 薄弱点标签云：从长期记忆聚合学习薄弱点（呼应「0 次重复自我介绍」的记忆卖点）
    weak_rows = (
        db.query(Memory)
        .filter(
            Memory.user_id == 1,
            or_(*[Memory.content.contains(k) for k in _WEAK_KEYWORDS]),
        )
        .order_by(Memory.id.desc())
        .limit(30)
        .all()
    )
    weak_points = [
        {
            "id": w.id,
            "content": w.content,
            "tag": w.tag,
            "created_at": w.created_at.isoformat() if w.created_at else None,
        }
        for w in weak_rows
    ]

    return {
        "daily": daily,
        "agents": agents,
        "citations_msgs": cite_msgs,
        "citations_snippets": cite_snippets,
        "active_days": days,
        "total_conversations": db.query(Conversation).count(),
        "total_messages": db.query(Message).count(),
        "weak_points": weak_points,
    }
