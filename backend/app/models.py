# -*- coding: utf-8 -*-
"""SQLAlchemy 数据模型。"""
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, Boolean
from sqlalchemy.orm import relationship

from .database import Base


class User(Base):
    """平台登录用户。"""
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(64), unique=True, index=True, nullable=False)
    password_hash = Column(String(128), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class Account(Base):
    """光合账号（登录态 cookie 加密存储）。"""
    __tablename__ = "accounts"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(128), nullable=False)
    # Fernet 加密后的 cookie JSON 字符串
    cookies_enc = Column(Text, nullable=False)
    # 淘宝账号标识（lgc/nick 等，用于展示）
    taobao_id = Column(String(64), default="")
    # 来源：profile=本机 browser_profile 导入；manual=手动粘贴 cookie
    source = Column(String(16), default="manual")
    status = Column(String(16), default="unknown")  # ok / expired / unknown
    last_check = Column(DateTime, nullable=True)
    remark = Column(String(256), default="")
    # 代理地址（http://host:port 或 socks5://host:port，可带认证 user:pass@host:port）；空=直连
    proxy = Column(String(256), default="")
    created_at = Column(DateTime, default=datetime.utcnow)

    works = relationship("Work", back_populates="account", cascade="all, delete-orphan")


class Work(Base):
    """作品缓存（从光合拉取的作品列表快照）。"""
    __tablename__ = "works"
    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(Integer, ForeignKey("accounts.id"), index=True)
    work_id = Column(String(32), index=True)          # 光合作品 ID
    title = Column(String(256), default="")
    cover_url = Column(String(512), default="")
    status = Column(Integer, default=0)                # 光合审核状态
    publish_time = Column(DateTime, nullable=True)
    play_count = Column(Integer, default=0)
    like_count = Column(Integer, default=0)
    collect_count = Column(Integer, default=0)         # 收藏
    comment_count = Column(Integer, default=0)         # 评论
    duration = Column(Integer, default=0)              # 视频时长（秒）
    content_type = Column(String(16), default="video") # video / image（图文）
    high_quality = Column(Boolean, default=False)      # 优质
    elite = Column(Boolean, default=False)             # 精选
    homepage_top = Column(Boolean, default=False)      # 置顶
    private_level = Column(Integer, default=1)         # 1=公开 4=私密
    raw_json = Column(Text, default="")                # 原始 JSON 快照
    synced_at = Column(DateTime, default=datetime.utcnow)

    account = relationship("Account", back_populates="works")


class Video(Base):
    """本地视频素材。"""
    __tablename__ = "videos"
    id = Column(Integer, primary_key=True, index=True)
    path = Column(String(512), nullable=False, unique=True)
    filename = Column(String(256), default="")
    title = Column(String(64), default="")
    desc = Column(Text, default="")
    declaration = Column(String(32), default="内容无需标注")
    status = Column(String(16), default="pending")     # pending / published / failed
    created_at = Column(DateTime, default=datetime.utcnow)

    publishes = relationship("PublishTask", back_populates="video")


class PublishTask(Base):
    """发布任务（定时发布用；立即发布不走此表）。"""
    __tablename__ = "publish_tasks"
    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(Integer, ForeignKey("accounts.id"), index=True)
    video_id = Column(Integer, ForeignKey("videos.id"), index=True)
    title = Column(String(64), default="")
    desc = Column(Text, default="")
    declaration = Column(String(32), default="内容无需标注")
    status = Column(String(16), default="pending")     # scheduled / running / success / failed
    schedule_at = Column(DateTime, nullable=True)      # 定时发布时间
    cover_url = Column(String(512), default="")        # 用户选定的封面（空则用智能封面/平台默认）
    topics_json = Column(Text, default="[]")
    items_json = Column(Text, default="[]")
    result_msg = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)
    finished_at = Column(DateTime, nullable=True)

    video = relationship("Video", back_populates="publishes")
    account = relationship("Account")


class PublishDraft(Base):
    """发布草稿（两阶段发布：预上传后的中间状态）。"""
    __tablename__ = "publish_drafts"
    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(Integer, ForeignKey("accounts.id"), index=True)
    video_id = Column(Integer, ForeignKey("videos.id"), index=True)
    title = Column(String(64), default="")
    desc = Column(Text, default="")
    declaration = Column(String(32), default="内容无需标注")
    # prepare 结果
    file_id = Column(String(64), default="")
    publish_session = Column(String(64), default="")
    item_task_id = Column(String(64), default="")
    covers_json = Column(Text, default="[]")     # 智能封面候选 [{url,width,height}]
    tags_json = Column(Text, default="[]")       # 推荐标签 [{id,name,...}]
    prepare_json = Column(Text, default="{}")    # 完整 prepare 结果（提交时用）
    status = Column(String(16), default="preparing")  # preparing / prepared / failed
    error_msg = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)

    video = relationship("Video")
    account = relationship("Account")


class PublishRecord(Base):
    """发布记录（每次提交发布的留痕）。"""
    __tablename__ = "publish_records"
    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(Integer, index=True)
    account_name = Column(String(128), default="")
    taobao_id = Column(String(64), default="")
    title = Column(String(256), default="")
    desc = Column(Text, default="")
    declaration = Column(String(32), default="")
    cover_url = Column(String(512), default="")
    topics_json = Column(Text, default="[]")
    items_json = Column(Text, default="[]")
    status = Column(String(16), default="success")   # success / failed
    result_msg = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)
