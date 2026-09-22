"""智学方舟 后端入口：FastAPI 应用。

启动：uvicorn app.main:app --reload --port 8000（在 backend/ 目录下）
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func

from .api import agents, auth, chat, conversations, insights, kb, memories, plans, profile, settings
from .config import PROVIDER_LABELS
from .db import SessionLocal, init_db
from .models import Conversation, KnowledgeDoc, Memory, Message


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    yield


app = FastAPI(title="智学方舟 Campus Multi-Agent OS", version="0.1.0", lifespan=lifespan)

# 开发期放开跨域；生产环境再收紧
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat.router)
app.include_router(conversations.router)
app.include_router(profile.router)
app.include_router(memories.router)
app.include_router(kb.router)
app.include_router(agents.router)
app.include_router(plans.router)
app.include_router(insights.router)
app.include_router(settings.router)
app.include_router(auth.router)


@app.get("/api/health")
def health():
    return {"status": "ok", "app": "zhixue-ark", "version": "0.1.0"}


@app.get("/api/stats")
def stats():
    """平台统计面板：会话 / 消息 / 知识文档 / 长期记忆总量 + 各模型真实用量分布。"""
    db = SessionLocal()
    try:
        # assistant 消息落库时 model 字段记录了产出供应商，按其归组即得真实用量
        usage_rows = (
            db.query(Message.model, func.count(Message.id))
            .filter(Message.role == "assistant", Message.model != "")
            .group_by(Message.model)
            .all()
        )
        return {
            "conversations": db.query(Conversation).count(),
            "messages": db.query(Message).count(),
            "docs": db.query(KnowledgeDoc).filter_by(status="ready").count(),
            "memories": db.query(Memory).count(),
            "model_usage": [
                {"provider": p, "label": PROVIDER_LABELS.get(p, p), "count": n}
                for p, n in usage_rows
            ],
        }
    finally:
        db.close()
