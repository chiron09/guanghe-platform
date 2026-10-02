# -*- coding: utf-8 -*-
"""应用配置。"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent  # backend/
DATA_DIR = Path(os.environ.get("GH_DATA_DIR", BASE_DIR / "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)


class Settings:
    app_name = "淘宝光合运营平台"
    # 安全
    secret_key = os.environ.get("SECRET_KEY", "guanghe-platform-secret-change-me")
    # Fernet 密钥（加密账号 cookie）
    fernet_key = os.environ.get("FERNET_KEY", "")
    # 数据库
    database_url = os.environ.get("DATABASE_URL", f"sqlite:///{DATA_DIR / 'guanghe.db'}")
    # 本机光合运行目录（browser_profile 登录态）
    gh_home = Path(os.environ.get("GH_HOME", Path.home() / "taobao-guanghe-auto"))
    # token 有效期（小时）
    token_expire_hours = int(os.environ.get("TOKEN_EXPIRE_HOURS", "72"))
    # 账号登录态自动刷新间隔（分钟）
    account_refresh_minutes = int(os.environ.get("ACCOUNT_REFRESH_MINUTES", "60"))


settings = Settings()
