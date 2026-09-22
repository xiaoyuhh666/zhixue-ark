"""数据库连接与初始化（SQLite + SQLAlchemy 2.x）。"""
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import get_settings

settings = get_settings()

# SQLite 需要关闭同线程检查，配合 FastAPI 的线程池使用
connect_args = {"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(settings.DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def init_db() -> None:
    """建表 + 轻量迁移 + 预置演示用户。"""
    if settings.DATABASE_URL.startswith("sqlite"):
        # sqlite:///C:/xx/app.db -> 取出文件路径并确保目录存在
        db_path = settings.DATABASE_URL.split("///")[-1]
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    from . import models  # noqa: F401  # 注册模型

    Base.metadata.create_all(engine)
    _migrate_sqlite()
    _seed_demo_user()


def _migrate_sqlite() -> None:
    """SQLite 幂等加列迁移：create_all 不会给已有表补列，这里按需 ALTER（不删库、保数据）。"""
    from sqlalchemy import text

    stmts = [
        "ALTER TABLE users ADD COLUMN school VARCHAR(128) DEFAULT ''",
        "ALTER TABLE users ADD COLUMN preferences JSON",
        "ALTER TABLE users ADD COLUMN weekly_hours INTEGER DEFAULT 0",
        "ALTER TABLE users ADD COLUMN password_hash VARCHAR(128) DEFAULT ''",
    ]
    with engine.begin() as conn:
        cols = {row[1] for row in conn.execute(text("PRAGMA table_info(users)"))}
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
