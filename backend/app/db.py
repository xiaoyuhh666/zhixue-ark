"""数据库连接与初始化（SQLite / Turso libSQL + SQLAlchemy 2.x）。

2026-09-23 接入 Turso 云数据库：配置 TURSO_DATABASE_URL 时，业务数据与知识库向量
持久化到远端 libSQL（Render 等临时盘平台重启不再丢）；未配置则回落本地 SQLite 文件，
本地开发体验完全不变。
"""
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import get_settings

settings = get_settings()


def _resolve_db_url() -> tuple[str, bool]:
    """解析最终连接串。返回 (url, is_local_sqlite)。

    Turso 官方 SQLAlchemy 方言（sqlalchemy-libsql）走 sqlite+libsql:// 方案，
    连接串形如 sqlite+libsql://<host>?authToken=<token>&secure=true。
    """
    if settings.TURSO_DATABASE_URL:
        host = settings.TURSO_DATABASE_URL.split("://", 1)[-1].rstrip("/")
        return (
            f"sqlite+libsql://{host}?authToken={settings.TURSO_AUTH_TOKEN}&secure=true",
            False,
        )
    return settings.DATABASE_URL, settings.DATABASE_URL.startswith("sqlite")


DB_URL, IS_LOCAL_SQLITE = _resolve_db_url()

# 禁用同线程限制：FastAPI 线程池跨线程使用连接池（本地 SQLite 与远端 libSQL 均支持该参数）
connect_args = {"check_same_thread": False}
engine = create_engine(DB_URL, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def init_db() -> None:
    """建表 + 轻量迁移 + 预置演示用户。"""
    if IS_LOCAL_SQLITE:
        # sqlite:///C:/xx/app.db -> 取出文件路径并确保目录存在
        db_path = settings.DATABASE_URL.split("///")[-1]
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    from . import models  # noqa: F401  # 注册模型

    Base.metadata.create_all(engine)
    _migrate_sqlite()
    _seed_demo_user()


def _migrate_sqlite() -> None:
    """幂等加列迁移：create_all 不会给已有表补列，这里按需 ALTER（不删库、保数据）。

    列清单用 SELECT ... LIMIT 0 的结果集元数据获取，PRAGMA 在部分远端方言上不可用，
    这种写法本地 SQLite 与 Turso 均通用。
    """
    from sqlalchemy import text

    stmts = [
        "ALTER TABLE users ADD COLUMN school VARCHAR(128) DEFAULT ''",
        "ALTER TABLE users ADD COLUMN preferences JSON",
        "ALTER TABLE users ADD COLUMN weekly_hours INTEGER DEFAULT 0",
        "ALTER TABLE users ADD COLUMN password_hash VARCHAR(128) DEFAULT ''",
        "ALTER TABLE users ADD COLUMN avatar TEXT DEFAULT ''",
    ]
    with engine.begin() as conn:
        cols = set(conn.execute(text("SELECT * FROM users LIMIT 0")).keys())
        for stmt in stmts:
            name = stmt.split("ADD COLUMN ")[1].split(" ")[0]
            if name not in cols:
                conn.execute(text(stmt))


def _seed_demo_user() -> None:
    from .models import User

    with SessionLocal() as db:
        if db.query(User).count() == 0:
            db.add(User(username="demo", nickname="同学"))
            db.commit()


def get_db():
    """FastAPI 依赖：请求级会话。"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
