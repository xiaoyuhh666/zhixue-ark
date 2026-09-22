"""账号认证（毕设演示级）：注册 / 登录 / 当前用户。

- 密码：PBKDF2-SHA256 哈希存储（salt$digest），无明文
- Token：HMAC 签名的自包含串（base64 payload + 签名，7 天有效），无需存表
- 演示阶段数据层仍为单用户（user_id=1），auth 负责登录门禁与身份展示；
  多用户数据隔离作为后续里程碑
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


def _sync_profile_nickname(db: Session, nickname: str) -> None:
    """把账号昵称同步到画像行（user_id=1）：全站展示名与注册信息保持一致。

    数据层演示阶段为单用户（画像/记忆/计划均挂 id=1），画像昵称默认是 seed 值；
    登录/注册成功后同步为账号昵称，保证右上角、画像卡与智能体称呼统一。
    """
    profile = db.get(User, 1)
    if profile and nickname and profile.nickname != nickname:
        profile.nickname = nickname[:64]
        db.commit()


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
    _sync_profile_nickname(db, u.nickname or name)
    return {"token": _make_token(name), "user": _user_dict(u)}


@router.post("/login")
def login(body: AuthBody, db: Session = Depends(get_db)):
    u = db.query(User).filter(User.username == body.username.strip()).first()
    if not u or not _verify_password(body.password, u.password_hash):
        raise HTTPException(400, "用户名或密码错误")
    _sync_profile_nickname(db, u.nickname or u.username)
    return {"token": _make_token(u.username), "user": _user_dict(u)}


@router.get("/me")
def me(authorization: str = Header(default=""), db: Session = Depends(get_db)):
    token = authorization.removeprefix("Bearer ").strip()
    name = _parse_token(token)
    if not name:
        raise HTTPException(401, "登录已过期，请重新登录")
    u = db.query(User).filter(User.username == name).first()
    if not u:
        raise HTTPException(401, "用户不存在")
    return {"user": _user_dict(u)}
