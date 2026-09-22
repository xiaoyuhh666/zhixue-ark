"""会话管理接口：列表 / 新建 / 详情 / 删除。"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from ..db import get_db
from ..models import Conversation, Message
from .auth import get_current_user

router = APIRouter(prefix="/api/conversations", tags=["conversations"])


class ConversationCreate(BaseModel):
    title: str = "新对话"


def _summary(conv: Conversation) -> dict:
    return {
        "id": conv.id,
        "title": conv.title,
        "created_at": conv.created_at.isoformat() if conv.created_at else None,
        "updated_at": conv.updated_at.isoformat() if conv.updated_at else None,
    }


@router.get("")
def list_conversations(user=Depends(get_current_user), db: Session = Depends(get_db)):
    convs = (
        db.query(Conversation)
        .filter(Conversation.user_id == user.id)
        .order_by(Conversation.updated_at.desc())
        .all()
    )
    # 批量取每个会话最后一条消息做列表摘要（两条查询搞定，避免逐会话 N+1）
    last_map: dict[int, Message] = {}
    if convs:
        max_rows = (
            db.query(Message.conversation_id, func.max(Message.id))
            .filter(Message.conversation_id.in_([c.id for c in convs]))
            .group_by(Message.conversation_id)
            .all()
        )
        ids = [mid for _, mid in max_rows]
        if ids:
            for m in db.query(Message).filter(Message.id.in_(ids)).all():
                last_map[m.conversation_id] = m
    result = []
    for c in convs:
        d = _summary(c)
        last = last_map.get(c.id)
        d["last_message"] = last.content[:60] if last else None  # 左栏会话卡摘要
        d["last_role"] = last.role if last else None
        result.append(d)
    return result


@router.post("")
def create_conversation(body: ConversationCreate, user=Depends(get_current_user), db: Session = Depends(get_db)):
    conv = Conversation(user_id=user.id, title=body.title[:128])
    db.add(conv)
    db.commit()
    db.refresh(conv)
    return _summary(conv)


@router.get("/{conv_id}")
def get_conversation(conv_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)):
    conv = (
        db.query(Conversation)
        .options(joinedload(Conversation.messages))
        .filter(Conversation.id == conv_id, Conversation.user_id == user.id)
        .first()
    )
    if conv is None:
        raise HTTPException(status_code=404, detail="会话不存在")
    data = _summary(conv)
    data["messages"] = [
        {
            "id": m.id,
            "role": m.role,
            "agent": m.agent,
            "content": m.content,
            "model": m.model,
            "citations": m.citations,
            "plan": m.plan,  # 里程碑 6：任务规划与分段，用于历史回放
            "created_at": m.created_at.isoformat() if m.created_at else None,
        }
        for m in sorted(conv.messages, key=lambda x: x.id)
    ]
    return data


@router.delete("/{conv_id}")
def delete_conversation(conv_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)):
    conv = (
        db.query(Conversation)
        .filter(Conversation.id == conv_id, Conversation.user_id == user.id)
        .first()
    )
    if conv is None:
        raise HTTPException(status_code=404, detail="会话不存在")
    db.delete(conv)  # messages 通过 cascade 一起删除
    db.commit()
    return {"ok": True}
