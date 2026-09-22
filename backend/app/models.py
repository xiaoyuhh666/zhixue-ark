"""数据模型：用户、会话、消息（里程碑 1 范围）。"""
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True)
    nickname: Mapped[str] = mapped_column(String(64), default="")
    # 账号密码（PBKDF2 哈希，salt$digest 格式；空=未设密码的演示用户）
    password_hash: Mapped[str] = mapped_column(String(128), default="")
    # 用户画像字段（里程碑 3：画像系统自动提炼 + 手动编辑）
    major: Mapped[str] = mapped_column(String(128), default="")
    grade: Mapped[str] = mapped_column(String(32), default="")
    # 画像扩展字段（2026-09-20 画像改版）：学校 / 学习偏好 / 每周可投入时长
    school: Mapped[str] = mapped_column(String(128), default="")
    preferences: Mapped[list | None] = mapped_column(JSON, default=None)
    weekly_hours: Mapped[int] = mapped_column(default=0)
    interests: Mapped[list | None] = mapped_column(JSON, default=None)
    goals: Mapped[list | None] = mapped_column(JSON, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    conversations: Mapped[list["Conversation"]] = relationship(back_populates="user")


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), default=1)
    title: Mapped[str] = mapped_column(String(128), default="新对话")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    user: Mapped["User"] = relationship(back_populates="conversations")
    messages: Mapped[list["Message"]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan"
    )


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    conversation_id: Mapped[int] = mapped_column(
        ForeignKey("conversations.id"), index=True
    )
    role: Mapped[str] = mapped_column(String(16))  # user | assistant
    agent: Mapped[str] = mapped_column(String(32), default="")  # 里程碑 2 起记录来源智能体
    content: Mapped[str] = mapped_column(Text)
    model: Mapped[str] = mapped_column(String(32), default="")  # deepseek | qwen | glm
    # 里程碑 4：RAG 引用溯源 [{doc, snippet, score}]
    citations: Mapped[list | None] = mapped_column(JSON, default=None)
    # 里程碑 6：任务规划与分段回放 {"tasks": [{agent, objective}], "segments": [{agent, label, content}]}
    plan: Mapped[dict | None] = mapped_column(JSON, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    conversation: Mapped["Conversation"] = relationship(back_populates="messages")


class Memory(Base):
    """跨会话长期记忆条目，所有智能体共享。"""

    __tablename__ = "memories"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), default=1, index=True)
    content: Mapped[str] = mapped_column(Text)  # 第三人称事实描述
    tag: Mapped[str] = mapped_column(String(32), default="general")  # study/competition/research/career/life/general
    source_conversation_id: Mapped[int | None] = mapped_column(
        ForeignKey("conversations.id"), default=None
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Plan(Base):
    """任务计划（2026-09-20 任务计划中心）：对话规划一键转入或手动创建。"""

    __tablename__ = "plans"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), default=1, index=True)
    title: Mapped[str] = mapped_column(String(128), default="新计划")
    deadline: Mapped[str] = mapped_column(String(32), default="")  # YYYY-MM-DD，可空
    # 所属智能体域（五域分类）：study/competition/research/career/life/general
    category: Mapped[str] = mapped_column(
        String(20), default="general", server_default="general", nullable=False, index=True
    )
    # 步骤清单 [{content: str, done: bool}]
    items: Mapped[list | None] = mapped_column(JSON, default=None)
    source_message_id: Mapped[int | None] = mapped_column(default=None)  # 来源对话消息（可追溯）
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class PlatformSetting(Base):
    """平台设置（设置模块）：键值对存储，API Key 等运行时配置，优先于 .env。"""

    __tablename__ = "platform_settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class KnowledgeDoc(Base):
    """知识库文档（里程碑 4）：原文入库，向量存 ChromaDB。"""

    __tablename__ = "knowledge_docs"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), default=1, index=True)
    filename: Mapped[str] = mapped_column(String(256))  # 原始文件名
    ext: Mapped[str] = mapped_column(String(16), default="")  # md/txt/pdf/docx/pptx
    # 里程碑 6：文档分类（study/competition/research/career/life/general），
    # 智能体可按分类定向检索（ChromaDB where 过滤）
    category: Mapped[str] = mapped_column(String(32), default="general")
    status: Mapped[str] = mapped_column(String(16), default="ready")  # ready | failed
    chunk_count: Mapped[int] = mapped_column(default=0)  # 切块数量
    note: Mapped[str] = mapped_column(String(256), default="")  # 失败原因等备注
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
