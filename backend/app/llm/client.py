"""LLM 接入层：LangChain ChatOpenAI 封装（OpenAI 兼容协议）。

里程碑 2 起模型调用统一走 LangChain，供 LangGraph 调度图使用。
未配置密钥时由调用方前置拦截（chat.py 推 error 帧），此处直接抛错。
"""
from langchain_openai import ChatOpenAI

from ..config import get_settings
from ..services.runtime_settings import get_setting, user_scope


def get_chat_model(provider: str | None = None, temperature: float = 0.7, user_id: int = 0) -> ChatOpenAI:
    """构建指定供应商的 ChatOpenAI 实例；未配置密钥时抛错。

    Key 解析优先级：用户 BYOK（u{id}: 前缀，与 chat.py 预检同源）> 全局运行时键 > .env。
    user_id 缺省 0 时只查全局键——历史兼容，图内调用必须透传请求级 user_id。
    """
    settings = get_settings()
    p = (provider or settings.LLM_PROVIDER).lower()
    api_key, base_url, model = settings.provider_config(p)
    api_key = (
        get_setting(user_scope(user_id, f"{p}_api_key"))
        or get_setting(f"{p}_api_key")
        or api_key
    )
    if not api_key:
        raise RuntimeError(f"供应商 {p} 未配置 API 密钥")
    return ChatOpenAI(
        model=model,
        api_key=api_key,
        base_url=base_url,
        temperature=temperature,
        streaming=True,
        timeout=60,
        max_retries=1,
    )
