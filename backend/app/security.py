# -*- coding: utf-8 -*-
"""安全：JWT、密码哈希、Fernet cookie 加密。"""
import base64
import hashlib
import json
from datetime import datetime, timedelta

import jwt
from cryptography.fernet import Fernet

from .config import settings

# Fernet 密钥（持久化：优先环境变量，否则从 secret_key 派生）
_fernet = None


def get_fernet() -> Fernet:
    global _fernet
    if _fernet is None:
        if settings.fernet_key:
            key = settings.fernet_key.encode()
        else:
            key = base64.urlsafe_b64encode(hashlib.sha256(settings.secret_key.encode()).digest())
        _fernet = Fernet(key)
    return _fernet


# ---- 密码哈希 ----
def hash_password(pwd: str) -> str:
    return hashlib.sha256(pwd.encode()).hexdigest()


def verify_password(pwd: str, hashed: str) -> bool:
    return hash_password(pwd) == hashed


# ---- JWT ----
def create_token(user_id: int) -> str:
    payload = {"sub": str(user_id), "exp": datetime.utcnow() + timedelta(hours=settings.token_expire_hours)}
    return jwt.encode(payload, settings.secret_key, algorithm="HS256")


def decode_token(token: str) -> int:
    payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
    return int(payload["sub"])


# ---- Cookie 加密 ----
def encrypt_cookie(cookie_str: str) -> str:
    return get_fernet().encrypt(cookie_str.encode()).decode()


def decrypt_cookie(enc: str) -> str:
    return get_fernet().decrypt(enc.encode()).decode()


def cookie_str_to_dict(cookie_str: str) -> dict:
    """cookie 字符串 -> dict（同名取最后）。"""
    d = {}
    for part in cookie_str.split(";"):
        part = part.strip()
        if not part or "=" not in part:
            continue
        k, v = part.split("=", 1)
        d[k.strip()] = v.strip()
    return d


def cookie_dict_to_str(cookies: dict) -> str:
    return "; ".join(f"{k}={v}" for k, v in cookies.items())
