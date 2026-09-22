"""长期记忆接口：列表 / 手动新增 / 删除。"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Memory

router = APIRouter(prefix="/api/memories", tags=["memories"])


class MemoryCreate(BaseModel):
    content: str
    tag: str = "general"


@router.get("")
def list_memories(q: str = "", db: Session = Depends(get_db)):
    """记忆列表；q 为可选关键词过滤。"""
    query = db.query(Memory).filter_by(user_id=1)
    if q.strip():
        query = query.filter(Memory.content.contains(q.strip()))
    mems = query.order_by(Memory.id.desc()).limit(200).all()
    return [
        {
            "id": m.id,
            "content": m.content,
            "tag": m.tag,
            "source_conversation_id": m.source_conversation_id,
            "created_at": m.created_at.isoformat() if m.created_at else None,
        }
        for m in mems
    ]


@router.post("")
def create_memory(body: MemoryCreate, db: Session = Depends(get_db)):
    content = body.content.strip()
    if not content:
        raise HTTPException(status_code=400, detail="记忆内容不能为空")
    # 去重：内容完全一致的记忆只保留一条
    exists = (
        db.query(Memory)
        .filter_by(user_id=1, content=content)
        .first()
    )
    if exists:
        return {"ok": True, "created": False, "id": exists.id}
    mem = Memory(user_id=1, content=content[:120], tag=body.tag[:32])
    db.add(mem)
    db.commit()
    db.refresh(mem)
    return {"ok": True, "created": True, "id": mem.id}


@router.delete("/{memory_id}")
def delete_memory(memory_id: int, db: Session = Depends(get_db)):
    mem = db.get(Memory, memory_id)
    if mem is None:
        raise HTTPException(status_code=404, detail="记忆不存在")
    db.delete(mem)
    db.commit()
    return {"ok": True}
