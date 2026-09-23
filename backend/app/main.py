"""智学方舟 后端入口：FastAPI 应用。

启动：uvicorn app.main:app --reload --port 8000（在 backend/ 目录下）
生产部署：frontend/ 存在 dist/ 时由本服务直接托管（单端口模式），
评委只访问 http://<服务器IP>:<端口> 一个地址，前后端同域无跨域。
"""
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
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

# 跨域白名单：Vercel 前端经 VITE_API_BASE 直连本后端 + 本地 Vite 开发服。
# 正则放行 *.vercel.app 预览部署域名；单端口部署（同域托管 frontend/dist）不经过 CORS。
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://zhixue-ark.vercel.app",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_origin_regex=r"https://.*\.vercel\.app",
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


# ---- 前端托管（生产部署）：frontend/dist 存在时单端口服务整个平台 ----
_DIST = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"

if (_DIST / "index.html").exists():
    app.mount("/assets", StaticFiles(directory=_DIST / "assets"), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa_fallback(full_path: str):
        """SPA 回落：静态文件存在则返回文件，否则回落 index.html（前端 hash 路由）。

        /api 前缀不托管——未匹配到 API 路由的 /api/* 请求应保持 404 语义。
        """
        if full_path.startswith("api/") or full_path == "api":
            raise HTTPException(status_code=404, detail="Not Found")
        candidate = _DIST / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(_DIST / "index.html")
