"""运行时平台设置：API Key 等存 PlatformSetting 表，优先级高于 .env。

设计：进程内缓存 + 落库持久化；设置接口写入后立即生效（无需重启），
答辩换电脑时现场填 Key 即可从演示模式切到真实模型。
"""
import threading
from datetime import date

_lock = threading.Lock()
_cache: dict[str, str] = {}
_loaded = False

# 允许通过设置接口写入的键（白名单）
ALLOWED_KEYS = {
    "deepseek_api_key",
    "qwen_api_key",
    "glm_api_key",
    "default_provider",
}


def _load_all() -> None:
    global _loaded
    with _lock:
        if _loaded:
            return
        from ..db import SessionLocal
        from ..models import PlatformSetting

        try:
            with SessionLocal() as db:
                for row in db.query(PlatformSetting).all():
                    if row.key in ALLOWED_KEYS:
                        _cache[row.key] = row.value
        except Exception:
            pass  # 表尚未建好时静默，回落 .env
        _loaded = True


def get_setting(key: str, default: str = "") -> str:
    """读运行时设置（带缓存）；无则返回 default（调用方再回落 .env）。"""
    if key not in ALLOWED_KEYS:
        return default
    _load_all()
    return _cache.get(key, default)


def set_settings(items: dict[str, str]) -> None:
    """批量写入；value 为空串表示清除该键（回落 .env）。"""
    global _loaded
    _load_all()
    with _lock:
        from ..db import SessionLocal
        from ..models import PlatformSetting

        with SessionLocal() as db:
            for k, v in items.items():
                if k not in ALLOWED_KEYS:
                    continue
                v = str(v or "").strip()
                row = db.query(PlatformSetting).filter_by(key=k).first()
                if v == "":
                    if row:
                        db.delete(row)
                    _cache.pop(k, None)
                    continue
                if row:
                    row.value = v
                else:
                    db.add(PlatformSetting(key=k, value=v))
                _cache[k] = v
            db.commit()


def mask_key(key: str) -> str:
    """密钥掩码回显：sk-abcdefgh12 -> sk-***gh12（不足 8 位全掩）。"""
    if not key:
        return ""
    if len(key) <= 8:
        return "*" * len(key)
    return key[:3] + "***" + key[-4:]


# ---- 平台 Key 每日配额（内存态计数，重启清零；多用户隔离待数据层里程碑）----
# 规则：用户在「个人中心 → 模型管理」自配的 Key（运行时）不限量；
#       平台 .env Key 中，付费供应商日限 PLATFORM_DAILY_LIMIT 次，免费供应商不限。
PLATFORM_DAILY_LIMIT = 20
FREE_PROVIDERS = {"glm"}  # 平台免费 Key 不限（零成本）
_platform_usage: dict[str, tuple[str, int]] = {}  # provider -> (日期, 已用次数)


def platform_left(provider: str) -> int | None:
    """今日平台配额剩余次数；None 表示不限（免费模型）。"""
    if provider in FREE_PROVIDERS:
        return None
    today = date.today().isoformat()
    d, n = _platform_usage.get(provider, ("", 0))
    if d != today:
        return PLATFORM_DAILY_LIMIT
    return max(0, PLATFORM_DAILY_LIMIT - n)


def consume_platform(provider: str) -> bool:
    """扣减一次平台配额；不限量供应商恒通过，用尽返回 False。"""
    if provider in FREE_PROVIDERS:
        return True
    today = date.today().isoformat()
    d, n = _platform_usage.get(provider, ("", 0))
    if d != today:
        d, n = today, 0
    if n >= PLATFORM_DAILY_LIMIT:
        return False
    _platform_usage[provider] = (d, n + 1)
    return True
