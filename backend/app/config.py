"""全局配置：读取 backend/.env，管理各家用 LLM 供应商的接入参数。"""
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings

# backend/ 目录（.env 与数据文件都相对它定位）
BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    # ---- 应用 ----
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    DATABASE_URL: str = f"sqlite:///{(BASE_DIR / 'data' / 'app.db').as_posix()}"

    # ---- Turso 云数据库（可选）：配置后业务数据与知识库向量走远端 libSQL，重启不丢 ----
    TURSO_DATABASE_URL: str = ""  # 形如 libsql://xxx.turso.io；留空回落本地 SQLite
    TURSO_AUTH_TOKEN: str = ""

    # ---- LLM（OpenAI 兼容协议）----
    LLM_PROVIDER: str = "deepseek"  # deepseek | qwen | glm
    DEEPSEEK_API_KEY: str = ""
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com/v1"
    DEEPSEEK_MODEL: str = "deepseek-chat"
    QWEN_API_KEY: str = ""
    QWEN_BASE_URL: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    QWEN_MODEL: str = "qwen-plus"
    GLM_API_KEY: str = ""
    GLM_BASE_URL: str = "https://open.bigmodel.cn/api/paas/v4"
    GLM_MODEL: str = "glm-4-flash"
    FALLBACK_PROVIDER: str = "glm"  # 免费兜底供应商：所选模型未接入时自动切换

    # ---- 知识库 RAG（里程碑 4；嵌入走智谱 API，复用 GLM_API_KEY/GLM_BASE_URL）----
    KB_EMBED_MODEL: str = "embedding-3"  # 智谱嵌入模型（OpenAI 兼容 /embeddings）
    KB_EMBED_DIMENSIONS: int = 1024  # 输出向量维度；0 = 用模型默认（embedding-3 默认 2048）
    KB_EMBED_BATCH: int = 16  # 单次嵌入请求的最大文本条数（智谱上限 64，留余量）
    KB_CHUNK_SIZE: int = 500  # 每块目标字符数
    KB_CHUNK_OVERLAP: int = 80  # 相邻块重叠字符数
    KB_TOP_K: int = 3  # 检索返回条数
    KB_MIN_SCORE: float = 0.35  # 相似度阈值，低于此值不作为引用（归一化余弦）

    model_config = {"env_file": str(BASE_DIR / ".env"), "extra": "ignore"}

    def provider_config(self, provider: str | None = None) -> tuple[str, str, str]:
        """返回指定供应商的 (api_key, base_url, model)，缺省回落到 LLM_PROVIDER。"""
        p = (provider or self.LLM_PROVIDER).lower()
        prefix = f"{p.upper()}_"
        return (
            getattr(self, f"{prefix}API_KEY", ""),
            getattr(self, f"{prefix}BASE_URL", ""),
            getattr(self, f"{prefix}MODEL", ""),
        )


# 供应商中文名，用于消息记录与前端展示
PROVIDER_LABELS = {"deepseek": "DeepSeek", "qwen": "Qwen", "glm": "GLM"}

# 模型广场目录：每家供应商的展示元数据（上下文窗口、能力标签、计费档位等）
# 接新模型只改这一个字典；运行时 Key 配置与切换由 settings.py / runtime_settings.py 负责
MODEL_CATALOG: dict[str, dict] = {
    "deepseek": {
        "name": "DeepSeek",
        "logo": "D",
        "model": "deepseek-chat",
        "endpoint": "https://api.deepseek.com/v1",
        "context": "128K",
        "streaming": True,
        "function_calling": True,
        "pricing": "付费 · 低成本",
        "tags": ["主力推荐", "低成本"],
        "console": "https://platform.deepseek.com",
    },
    "qwen": {
        "name": "通义千问 Qwen",
        "logo": "Q",
        "model": "qwen-plus",
        "endpoint": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "context": "128K",
        "streaming": True,
        "function_calling": True,
        "pricing": "赠金额度",
        "tags": ["100 万赠金", "BYOK"],
        "console": "https://bailian.console.aliyun.com",
    },
    "glm": {
        "name": "智谱 GLM",
        "logo": "G",
        "model": "glm-4-flash",
        "endpoint": "https://open.bigmodel.cn/api/paas/v4",
        "context": "128K",
        "streaming": True,
        "function_calling": True,
        "pricing": "永久免费",
        "tags": ["永久免费", "免费兜底"],
        "console": "https://open.bigmodel.cn",
    },
}


@lru_cache
def get_settings() -> Settings:
    return Settings()
