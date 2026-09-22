"""LLM 接入层：LangChain ChatOpenAI 封装（OpenAI 兼容协议）。

里程碑 2 起模型调用统一走 LangChain，供 LangGraph 调度图使用。
未配置密钥时由调用方前置拦截（chat.py 推 error 帧），此处直接抛错。
"""
from langchain_openai import ChatOpenAI

from ..config import get_settings
from ..services.runtime_settings import get_setting


def get_chat_model(provider: str | None = None, temperature: float = 0.7) -> ChatOpenAI:
    """构建指定供应商的 ChatOpenAI 实例；未配置密钥时抛错。运行时 Key 优先。"""
    settings = get_settings()
    p = (provider or settings.LLM_PROVIDER).lower()
    api_key, base_url, model = settings.provider_config(p)
    api_key = get_setting(f"{p}_api_key") or api_key
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
