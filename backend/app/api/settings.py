"""平台设置接口（设置模块）：API Key 运行时配置 / 连通测试 / 默认模型 / 数据导出 / 清空演示数据。"""
import time
from datetime import datetime

import httpx
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..config import MODEL_CATALOG, PROVIDER_LABELS, get_settings
from ..db import get_db
from ..models import Conversation, Memory, Message, Plan
from ..services import runtime_settings

router = APIRouter(prefix="/api/settings", tags=["settings"])

_PROVIDER_KEYS = {"deepseek": "deepseek_api_key", "qwen": "qwen_api_key", "glm": "glm_api_key"}

# 连通测试延迟缓存（内存态）：模型广场展示最近一次实测延迟，重启后清空
_latency_cache: dict[str, int] = {}


class SettingsUpdate(BaseModel):
    deepseek_api_key: str | None = None
    qwen_api_key: str | None = None
    glm_api_key: str | None = None
    default_provider: str | None = None


@router.get("")
def get_settings_view():
    """掩码回显：不回传明文 Key，只给「已配置 sk-***xxxx」与各供应商接入状态。"""
    s = get_settings()
    providers = []
    for p, key_name in _PROVIDER_KEYS.items():
        runtime_key = runtime_settings.get_setting(key_name)
        env_key, _, _ = s.provider_config(p)
        effective = runtime_key or env_key
        providers.append({
            "provider": p,
            "label": PROVIDER_LABELS.get(p, p),
            "model": s.provider_config(p)[2] or MODEL_CATALOG.get(p, {}).get("model", ""),
            "configured": bool(effective),
            "masked": runtime_settings.mask_key(effective),
            "source": "runtime" if runtime_key else ("env" if env_key else "none"),
        })
    return {
        "providers": providers,
        "default_provider": runtime_settings.get_setting("default_provider") or s.LLM_PROVIDER,
    }


@router.put("")
def update_settings(body: SettingsUpdate):
    items = {}
    if body.deepseek_api_key is not None:
        items["deepseek_api_key"] = body.deepseek_api_key
    if body.qwen_api_key is not None:
        items["qwen_api_key"] = body.qwen_api_key
    if body.glm_api_key is not None:
        items["glm_api_key"] = body.glm_api_key
    if body.default_provider is not None:
        items["default_provider"] = body.default_provider
    runtime_settings.set_settings(items)
    return {"ok": True}


class TestRequest(BaseModel):
    provider: str


@router.get("/models")
def model_square():
    """模型广场：MODEL_CATALOG 目录元数据 + 各家实时接入状态（运行时 Key 优先）。"""
    s = get_settings()
    items = []
    for p, meta in MODEL_CATALOG.items():
        runtime_key = runtime_settings.get_setting(_PROVIDER_KEYS[p])
        env_key = s.provider_config(p)[0]
        effective = runtime_key or env_key
        items.append({
            **meta,
            "provider": p,
            # 模型名以 .env 实际生效值为准（catalog 只是缺省展示）
            "model": s.provider_config(p)[2] or meta["model"],
            "configured": bool(effective),
            "masked": runtime_settings.mask_key(effective),
            "source": "runtime" if runtime_key else ("env" if env_key else "none"),
            "latency_ms": _latency_cache.get(p),
        })
    return {
        "models": items,
        "default_provider": runtime_settings.get_setting("default_provider") or s.LLM_PROVIDER,
        "configured_count": sum(1 for m in items if m["configured"]),
    }


@router.post("/test")
def test_provider(body: TestRequest):
    """连通性测试：用当前生效的 Key 发一个最小请求，验证 Key 真实可用（答辩防翻车）。"""
    p = body.provider if body.provider in _PROVIDER_KEYS else "deepseek"
    s = get_settings()
    api_key = runtime_settings.get_setting(_PROVIDER_KEYS[p]) or s.provider_config(p)[0]
    if not api_key:
        return {"ok": False, "error": "未配置 API Key"}
    _, base_url, model = s.provider_config(p)
    t0 = time.perf_counter()
    try:
        r = httpx.post(
            f"{base_url.rstrip('/')}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json={"model": model, "messages": [{"role": "user", "content": "hi"}], "max_tokens": 1},
            timeout=15,
        )
        ms = int((time.perf_counter() - t0) * 1000)
        if r.status_code == 200:
            _latency_cache[p] = ms  # 缓存延迟供模型广场展示
            return {"ok": True, "latency_ms": ms, "model": model}
        if r.status_code == 401:
            return {"ok": False, "error": "Key 无效（401 认证失败）"}
        if r.status_code == 402:
            return {"ok": False, "error": "余额不足（402），请充值后重试"}
        return {"ok": False, "error": f"HTTP {r.status_code}"}
    except httpx.TimeoutException:
        return {"ok": False, "error": "连接超时（15s），检查网络或代理"}
    except Exception as e:
        return {"ok": False, "error": str(e)[:120]}


@router.get("/export")
def export_data(db: Session = Depends(get_db)):
    """全量数据导出（JSON）：画像在 users，会话消息/记忆/计划一次带走。"""
    from ..models import User

    user = db.get(User, 1)
    convs = db.query(Conversation).order_by(Conversation.id).all()
    data = {
        "exported_at": datetime.now().isoformat(),
        "profile": {
            "nickname": user.nickname if user else "",
            "school": user.school if user else "",
            "major": user.major if user else "",
            "grade": user.grade if user else "",
            "preferences": user.preferences if user else [],
            "weekly_hours": user.weekly_hours if user else 0,
            "interests": user.interests if user else [],
            "goals": user.goals if user else [],
        },
        "conversations": [
            {
                "id": c.id,
                "title": c.title,
                "messages": [
                    {"role": m.role, "agent": m.agent, "content": m.content, "created_at": m.created_at.isoformat() if m.created_at else None}
                    for m in c.messages
                ],
            }
            for c in convs
        ],
        "memories": [
            {"content": m.content, "tag": m.tag, "created_at": m.created_at.isoformat() if m.created_at else None}
            for m in db.query(Memory).order_by(Memory.id).all()
        ],
        "plans": [
            {"title": p.title, "deadline": p.deadline, "items": p.items or []}
            for p in db.query(Plan).order_by(Plan.id).all()
        ],
    }
    return data


@router.delete("/demo-data")
def clear_demo_data(db: Session = Depends(get_db)):
    """清空对话/消息/记忆/计划（画像与知识库保留）；用于重置演示环境。"""
    n_msgs = db.query(Message).delete()
    n_convs = db.query(Conversation).delete()
    n_mems = db.query(Memory).delete()
    n_plans = db.query(Plan).delete()
    db.commit()
    return {"ok": True, "cleared": {"messages": n_msgs, "conversations": n_convs, "memories": n_mems, "plans": n_plans}}
