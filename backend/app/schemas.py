# -*- coding: utf-8 -*-
"""Pydantic 请求/响应模型。"""
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


# ---- 认证 ----
class RegisterIn(BaseModel):
    username: str
    password: str


class LoginIn(BaseModel):
    username: str
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ---- 账号 ----
class AccountIn(BaseModel):
    name: str
    cookie: str          # 完整 cookie 字符串
    remark: str = ""


class AccountUpdateIn(BaseModel):
    name: str = ""
    remark: str = ""
    proxy: str = ""


class AccountOut(BaseModel):
    id: int
    name: str
    taobao_id: str
    source: str
    status: str
    last_check: Optional[datetime]
    remark: str
    proxy: str
    created_at: datetime

    class Config:
        from_attributes = True


# ---- 作品 ----
class WorkOut(BaseModel):
    work_id: str
    title: str
    cover_url: str
    status: int
    play_count: int
    like_count: int


# ---- 视频 ----
class VideoIn(BaseModel):
    path: str
    title: str = ""
    desc: str = ""
    declaration: str = "内容无需标注"


# ---- 发布 ----
class PublishIn(BaseModel):
    account_id: int
    video_id: int
    title: str
    desc: str = ""
    declaration: str = "内容无需标注"
    schedule_at: Optional[datetime] = None


class PublishOut(BaseModel):
    id: int
    account_id: int
    video_id: int
    title: str
    status: str
    schedule_at: Optional[datetime]
    result_msg: str
    created_at: datetime

    class Config:
        from_attributes = True


# ---- 佣金 ----
class CommissionItem(BaseModel):
    item_id: str
    title: str
    price: str
    commission_rate: str
    predict_income: str
    item_url: str = ""
    shop_name: str = ""
    pic_url: str = ""
    sell_count: str = ""


# ---- 通用 ----
class MsgOut(BaseModel):
    message: str
