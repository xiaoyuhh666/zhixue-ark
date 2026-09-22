"""任务计划接口（任务计划中心）：对话规划转入 / 手动创建 / 勾选推进。"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Plan

router = APIRouter(prefix="/api/plans", tags=["plans"])

# 计划所属智能体域白名单（与知识库分类一致）
PLAN_CATEGORIES = {"study", "competition", "research", "career", "life", "general"}


class PlanItemIn(BaseModel):
    content: str
    done: bool = False


class PlanCreate(BaseModel):
    title: str = "新计划"
    deadline: str = ""
    category: str = "general"
    items: list[PlanItemIn] = []
    source_message_id: int | None = None


class PlanUpdate(BaseModel):
    title: str | None = None
    deadline: str | None = None
    items: list[PlanItemIn] | None = None


def _serialize(p: Plan) -> dict:
    items = p.items or []
    return {
        "id": p.id,
        "title": p.title,
        "deadline": p.deadline or "",
        "category": p.category or "general",
        "items": items,
        "done_count": sum(1 for i in items if i.get("done")),
        "total": len(items),
        "finished": bool(items) and all(i.get("done") for i in items),
        "source_message_id": p.source_message_id,
        "created_at": p.created_at.isoformat() if p.created_at else None,
        "updated_at": p.updated_at.isoformat() if p.updated_at else None,
    }


@router.get("")
def list_plans(db: Session = Depends(get_db)):
    plans = db.query(Plan).filter_by(user_id=1).order_by(Plan.updated_at.desc()).limit(200).all()
    return [_serialize(p) for p in plans]


@router.post("")
def create_plan(body: PlanCreate, db: Session = Depends(get_db)):
    plan = Plan(
        user_id=1,
        title=body.title.strip()[:128] or "新计划",
        deadline=body.deadline.strip()[:32],
        category=body.category if body.category in PLAN_CATEGORIES else "general",
        items=[{"content": i.content.strip()[:200], "done": i.done} for i in body.items if i.content.strip()],
        source_message_id=body.source_message_id,
    )
    db.add(plan)
    db.commit()
    db.refresh(plan)
    return _serialize(plan)


@router.put("/{plan_id}")
def update_plan(plan_id: int, body: PlanUpdate, db: Session = Depends(get_db)):
    plan = db.get(Plan, plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="计划不存在")
    if body.title is not None:
        plan.title = body.title.strip()[:128] or plan.title
    if body.deadline is not None:
        plan.deadline = body.deadline.strip()[:32]
    if body.items is not None:
        plan.items = [{"content": i.content.strip()[:200], "done": i.done} for i in body.items if i.content.strip()]
    db.commit()
    db.refresh(plan)
    return _serialize(plan)


@router.delete("/{plan_id}")
def delete_plan(plan_id: int, db: Session = Depends(get_db)):
    plan = db.get(Plan, plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="计划不存在")
    db.delete(plan)
    db.commit()
    return {"ok": True}
