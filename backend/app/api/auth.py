"""账号认证：注册 / 登录 / 当前用户 / 鉴权依赖。

- 密码：PBKDF2-SHA256 哈希存储（salt$digest），无明文
- Token：HMAC 签名的自包含串（base64 payload + 签名，7 天有效），无需存表
- 数据隔离：所有业务接口通过 get_current_user 依赖解出真实用户，
  会话/文档/计划/记忆/画像全部按 user_id 隔离（2026-09-22 多用户改造）
"""
import base64
import hashlib
import hmac
import json
import secrets
import time

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import User

router = APIRouter(prefix="/api/auth", tags=["auth"])

_SECRET = b"zhixue-ark-secret-v1"
_TOKEN_TTL = 7 * 24 * 3600  # 7 天


def _hash_password(pwd: str) -> str:
    salt = secrets.token_hex(8)
    digest = hashlib.pbkdf2_hmac("sha256", pwd.encode(), salt.encode(), 60000).hex()
    return f"{salt}${digest}"


def _verify_password(pwd: str, stored: str) -> bool:
    try:
        salt, digest = stored.split("$", 1)
    except ValueError:
        return False
    calc = hashlib.pbkdf2_hmac("sha256", pwd.encode(), salt.encode(), 60000).hex()
    return hmac.compare_digest(calc, digest)


def _make_token(username: str) -> str:
    payload = base64.urlsafe_b64encode(
        json.dumps({"u": username, "e": time.time() + _TOKEN_TTL}).encode()
    ).decode()
    sig = hmac.new(_SECRET, payload.encode(), hashlib.sha256).hexdigest()[:32]
    return f"{payload}.{sig}"


def _parse_token(token: str) -> str | None:
    """校验签名与有效期，返回用户名；无效返回 None。"""
    try:
        payload, sig = token.split(".", 1)
        calc = hmac.new(_SECRET, payload.encode(), hashlib.sha256).hexdigest()[:32]
        if not hmac.compare_digest(calc, sig):
            return None
        data = json.loads(base64.urlsafe_b64decode(payload.encode()))
        if time.time() > data.get("e", 0):
            return None
        return data.get("u")
    except Exception:
        return None


def _user_dict(u: User) -> dict:
    return {
        "id": u.id,
        "username": u.username,
        "nickname": u.nickname or u.username,
        "major": u.major or "",
        "grade": u.grade or "",
    }


class AuthBody(BaseModel):
    username: str
    password: str
    nickname: str = ""


def _validate(body: AuthBody) -> None:
    name = body.username.strip()
    if not (3 <= len(name) <= 24):
        raise HTTPException(400, "用户名需 3~24 个字符")
    if len(body.password) < 6:
        raise HTTPException(400, "密码至少 6 位")


def get_current_user(
    authorization: str = Header(default=""), db: Session = Depends(get_db)
) -> User:
    """鉴权依赖：从 Authorization 头解出 token，校验签名与有效期，返回当前用户。

    所有需要按用户隔离的业务接口挂此依赖（FastAPI 自动透传 401）。
    """
    token = authorization.removeprefix("Bearer ").strip()
    name = _parse_token(token)
    if not name:
        raise HTTPException(401, "登录已过期，请重新登录")
    u = db.query(User).filter(User.username == name).first()
    if u is None:
        raise HTTPException(401, "登录不存在，请重新登录")
    return u


@router.post("/register")
def register(body: AuthBody, db: Session = Depends(get_db)):
    _validate(body)
    name = body.username.strip()
    if db.query(User).filter(User.username == name).first():
        raise HTTPException(400, "用户名已被占用")
    u = User(
        username=name,
        nickname=(body.nickname.strip() or name)[:64],
        password_hash=_hash_password(body.password),
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return {"token": _make_token(name), "user": _user_dict(u)}


@router.post("/login")
def login(body: AuthBody, db: Session = Depends(get_db)):
    u = db.query(User).filter(User.username == body.username.strip()).first()
    if not u or not _verify_password(body.password, u.password_hash):
        raise HTTPException(400, "用户名或密码错误")
    return {"token": _make_token(u.username), "user": _user_dict(u)}


@router.get("/me")
def me(user: User = Depends(get_current_user)):
    return {"user": _user_dict(user)}
