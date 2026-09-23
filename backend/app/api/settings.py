"""平台设置接口：API Key 运行时配置（按用户隔离）/ 连通测试 / 数据导出 / 清空本人数据。"""
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
from .auth import get_current_user

router = APIRouter(prefix="/api/settings", tags=["settings"])

_PROVIDER_KEYS = {"deepseek": "deepseek_api_key", "qwen": "qwen_api_key", "glm": "glm_api_key"}

# 连通测试延迟缓存（内存态）：模型广场展示最近一次实测延迟，重启后清空
_latency_cache: dict[str, int] = {}


class SettingsUpdate(BaseModel):
    deepseek_api_key: str | None = None
    qwen_api_key: str | None = None
    glm_api_key: str | None = None
    default_provider: str | None = None


def _uk(user, key: str) -> str:
    """用户级设置键：BYOK 与默认模型按账号隔离（u{id}: 前缀），互不可见/互不借用。"""
    return runtime_settings.user_scope(user.id, key)


@router.get("")
def get_settings_view(user=Depends(get_current_user)):
    """掩码回显：不回传明文 Key，只给「已配置 sk-***xxxx」与各供应商接入状态。"""
    s = get_settings()
    providers = []
    for p, key_name in _PROVIDER_KEYS.items():
        runtime_key = runtime_settings.get_setting(_uk(user, key_name))
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
        "default_provider": runtime_settings.get_setting(_uk(user, "default_provider")) or s.LLM_PROVIDER,
    }


@router.put("")
def update_settings(body: SettingsUpdate, user=Depends(get_current_user)):
    items = {}
    if body.deepseek_api_key is not None:
        items[_uk(user, "deepseek_api_key")] = body.deepseek_api_key
    if body.qwen_api_key is not None:
        items[_uk(user, "qwen_api_key")] = body.qwen_api_key
    if body.glm_api_key is not None:
        items[_uk(user, "glm_api_key")] = body.glm_api_key
    if body.default_provider is not None:
        items[_uk(user, "default_provider")] = body.default_provider
    runtime_settings.set_settings(items)
    return {"ok": True}


class TestRequest(BaseModel):
    provider: str
    api_key: str | None = None  # 可选：直接测试输入框里的草稿 Key（不落库，粘贴后无需先保存）


@router.get("/models")
def model_square(user=Depends(get_current_user)):
    """模型广场：MODEL_CATALOG 目录元数据 + 各家实时接入状态（本人运行时 Key 优先）。"""
    s = get_settings()
    items = []
    for p, meta in MODEL_CATALOG.items():
        runtime_key = runtime_settings.get_setting(_uk(user, _PROVIDER_KEYS[p]))
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
        "default_provider": runtime_settings.get_setting(_uk(user, "default_provider")) or s.LLM_PROVIDER,
        "configured_count": sum(1 for m in items if m["configured"]),
    }


@router.post("/test")
def test_provider(body: TestRequest, user=Depends(get_current_user)):
    """连通性测试：优先测 body 里传入的草稿 Key（不落库），否则用当前生效 Key 发最小请求。"""
    p = body.provider if body.provider in _PROVIDER_KEYS else "deepseek"
    s = get_settings()
    draft = (body.api_key or "").strip()
    api_key = draft or runtime_settings.get_setting(_uk(user, _PROVIDER_KEYS[p])) or s.provider_config(p)[0]
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
def export_data(user=Depends(get_current_user), db: Session = Depends(get_db)):
    """本人全量数据导出（JSON）：画像在 users 行，会话消息/记忆/计划按账号带走。"""
    convs = (
        db.query(Conversation)
        .filter(Conversation.user_id == user.id)
        .order_by(Conversation.id)
        .all()
    )
    data = {
        "exported_at": datetime.now().isoformat(),
        "profile": {
            "nickname": user.nickname or "",
            "school": user.school or "",
            "major": user.major or "",
            "grade": user.grade or "",
            "preferences": user.preferences or [],
            "weekly_hours": user.weekly_hours or 0,
            "interests": user.interests or [],
            "goals": user.goals or [],
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
            for m in db.query(Memory).filter_by(user_id=user.id).order_by(Memory.id).all()
        ],
        "plans": [
            {"title": p.title, "deadline": p.deadline, "items": p.items or []}
            for p in db.query(Plan).filter_by(user_id=user.id).order_by(Plan.id).all()
        ],
    }
    return data


@router.delete("/demo-data")
def clear_demo_data(user=Depends(get_current_user), db: Session = Depends(get_db)):
    """清空本人的对话/消息/记忆/计划（画像与知识库保留）；用于重置个人演示环境。"""
    own_conv_ids = [
        c.id for c in db.query(Conversation.id).filter_by(user_id=user.id).all()
    ]
    n_msgs = 0
    if own_conv_ids:
        n_msgs = db.query(Message).filter(Message.conversation_id.in_(own_conv_ids)).delete(synchronize_session=False)
    n_convs = db.query(Conversation).filter(Conversation.user_id == user.id).delete(synchronize_session=False)
    n_mems = db.query(Memory).filter(Memory.user_id == user.id).delete(synchronize_session=False)
    n_plans = db.query(Plan).filter(Plan.user_id == user.id).delete(synchronize_session=False)
    db.commit()
    return {"ok": True, "cleared": {"messages": n_msgs, "conversations": n_convs, "memories": n_mems, "plans": n_plans}}
