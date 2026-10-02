# -*- coding: utf-8 -*-
"""认证路由：注册、登录、当前用户。"""
from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session

from .. import models, schemas, security
from ..database import get_db

router = APIRouter(prefix="/api/auth", tags=["auth"])


def get_current_user(authorization: str = Header(None), db: Session = Depends(get_db)) -> models.User:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="未登录")
    try:
        uid = security.decode_token(authorization[7:])
    except Exception:
        raise HTTPException(status_code=401, detail="登录已过期")
    user = db.get(models.User, uid)
    if not user:
        raise HTTPException(status_code=401, detail="用户不存在")
    return user


@router.post("/register", response_model=schemas.TokenOut)
def register(body: schemas.RegisterIn, db: Session = Depends(get_db)):
    if db.query(models.User).filter_by(username=body.username).first():
        raise HTTPException(status_code=400, detail="用户名已存在")
    user = models.User(username=body.username, password_hash=security.hash_password(body.password))
    db.add(user)
    db.commit()
    return {"access_token": security.create_token(user.id)}


@router.post("/login", response_model=schemas.TokenOut)
def login(body: schemas.LoginIn, db: Session = Depends(get_db)):
    user = db.query(models.User).filter_by(username=body.username).first()
    if not user or not security.verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    return {"access_token": security.create_token(user.id)}


@router.get("/me")
def me(user: models.User = Depends(get_current_user)):
    return {"id": user.id, "username": user.username}
