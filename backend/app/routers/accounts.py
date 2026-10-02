# -*- coding: utf-8 -*-
"""账号管理路由：CRUD、健康检查、从本机提取 cookie。"""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas, security
from ..core import sdk
from ..core.login_service import service as login_service
from ..database import get_db, SessionLocal
from .auth import get_current_user

router = APIRouter(prefix="/api/accounts", tags=["accounts"])


def _to_out(a: models.Account) -> schemas.AccountOut:
    return schemas.AccountOut(
        id=a.id, name=a.name, taobao_id=a.taobao_id, source=a.source, status=a.status,
        last_check=a.last_check, remark=a.remark, proxy=a.proxy, created_at=a.created_at)


@router.get("", response_model=list[schemas.AccountOut])
def list_accounts(user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    return [_to_out(a) for a in db.query(models.Account).order_by(models.Account.id).all()]


@router.post("", response_model=schemas.AccountOut)
def create_account(body: schemas.AccountIn, user: models.User = Depends(get_current_user),
                   db: Session = Depends(get_db)):
    cookies = security.cookie_str_to_dict(body.cookie)
    if "_m_h5_tk" not in cookies:
        raise HTTPException(status_code=400, detail="cookie 缺少 _m_h5_tk，请确认已登录光合后复制完整 cookie")
    # 健康检查
    hc = sdk.health_check(cookies)
    if not hc["ok"]:
        raise HTTPException(status_code=400, detail=f"cookie 无效: {hc.get('error')}")
    a = models.Account(
        name=body.name, cookies_enc=security.encrypt_cookie(body.cookie),
        taobao_id=hc.get("taobao_id", ""), source="manual", status="ok",
        last_check=datetime.utcnow(), remark=body.remark)
    db.add(a)
    db.commit()
    db.refresh(a)
    return _to_out(a)


# ---------------- 扫码 / 短信登录 ----------------
@router.post("/login/start")
def login_start(body: dict, user: models.User = Depends(get_current_user)):
    mode = body.get("mode", "scan")
    if mode not in ("scan", "sms"):
        raise HTTPException(status_code=400, detail="mode 需为 scan/sms")
    return login_service.start(mode)


@router.get("/login/{sid}")
def login_status(sid: str, user: models.User = Depends(get_current_user)):
    return login_service.get(sid)


@router.post("/login/{sid}/submit")
def login_submit(sid: str, body: dict, user: models.User = Depends(get_current_user)):
    return login_service.submit(sid, **body)


@router.post("/login/{sid}/refresh_code")
def login_refresh_code(sid: str, user: models.User = Depends(get_current_user)):
    """点击页面验证码图刷新（换一张），并重新截图。"""
    return login_service.refresh_code(sid)


@router.post("/login/{sid}/refresh")
def login_refresh(sid: str, user: models.User = Depends(get_current_user)):
    """刷新登录页（二维码过期时重载页面重新截图）。"""
    return login_service.refresh(sid)


@router.post("/login/{sid}/import")
def login_import(sid: str, body: dict, user: models.User = Depends(get_current_user),
                 db: Session = Depends(get_db)):
    """登录成功后把会话 cookie 导入为账号。"""
    snap = login_service.get(sid)
    if snap.get("state") != "success" or not snap.get("cookies"):
        raise HTTPException(status_code=400, detail="登录尚未成功")
    cookies = snap["cookies"]
    hc = sdk.health_check(cookies)
    if not hc["ok"]:
        raise HTTPException(status_code=400, detail=f"cookie 无效: {hc.get('error')}")
    a = models.Account(
        name=body.get("name") or snap.get("taobao_id") or "扫码账号",
        cookies_enc=security.encrypt_cookie(security.cookie_dict_to_str(cookies)),
        taobao_id=snap.get("taobao_id", ""), source="scan", status="ok",
        last_check=datetime.utcnow(), remark=body.get("remark", ""))
    db.add(a)
    db.commit()
    db.refresh(a)
    login_service.close(sid)
    return _to_out(a)


@router.get("/{aid}/check", response_model=schemas.MsgOut)
def check_account(aid: int, user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    a = db.get(models.Account, aid)
    if not a:
        raise HTTPException(status_code=404, detail="账号不存在")
    cookies = security.cookie_str_to_dict(security.decrypt_cookie(a.cookies_enc))
    hc = sdk.health_check(cookies, proxy=(a.proxy or "").strip() or None)
    a.status = "ok" if hc["ok"] else "expired"
    a.last_check = datetime.utcnow()
    db.commit()
    return {"message": "健康" if hc["ok"] else f"失效: {hc.get('error')}"}


@router.post("/{aid}/test-proxy")
def test_proxy(aid: int, user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    """测试账号代理连通性：出口 IP + 通过代理访问光合。"""
    import re
    import requests
    a = db.get(models.Account, aid)
    if not a:
        raise HTTPException(status_code=404, detail="账号不存在")
    proxy = (a.proxy or "").strip()
    if not proxy:
        return {"ok": False, "msg": "该账号未设置代理", "proxy": ""}
    proxies = sdk.parse_proxy(proxy)
    result = {"proxy": proxy, "ok": False}
    # 1. 出口 IP（用国内可达的 ipip.net；国外站 ipify 常被代理屏蔽）
    try:
        r = requests.get("https://myip.ipip.net", proxies=proxies, timeout=20,
                         headers={"User-Agent": "Mozilla/5.0"})
        if r.status_code == 200:
            m = re.search(r"(\d{1,3}(?:\.\d{1,3}){3})", r.text)
            if m:
                result["exit_ip"] = m.group(1)
                result["ip_text"] = r.text.strip()[:80]
        result["ip_test"] = f"HTTP {r.status_code}"
    except Exception as e:
        result["ip_test"] = f"失败: {str(e)[:120]}"
    # 2. 通过代理访问光合（用账号 cookie 调 whoami）—— 核心判定
    try:
        cookies = security.cookie_str_to_dict(security.decrypt_cookie(a.cookies_enc))
        hc = sdk.health_check(cookies, proxy=proxy)
        result["taobao_ok"] = hc["ok"]
        result["taobao_msg"] = "健康" if hc["ok"] else hc.get("error", "失效")
    except Exception as e:
        result["taobao_ok"] = False
        result["taobao_msg"] = str(e)[:120]
    # 判定：以光合访问为准（这才是账号操作真正关心的）；出口 IP 为附加信息
    tb_ok = bool(result.get("taobao_ok"))
    ip_ok = bool(result.get("exit_ip"))
    result["ok"] = tb_ok
    msg_parts = []
    if ip_ok:
        msg_parts.append(f"代理连通(出口IP {result['exit_ip']})")
    elif result.get("ip_test", "").startswith("失败"):
        msg_parts.append("出口IP获取失败")
    else:
        msg_parts.append("出口IP获取失败")
    msg_parts.append("光合访问正常" if tb_ok else f"光合访问失败: {result.get('taobao_msg', '')}")
    result["msg"] = "，".join(msg_parts)
    return result


@router.post("/{aid}/refresh", response_model=schemas.MsgOut)
def refresh_account(aid: int, user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    """刷新登录态 token，按账号来源区分：
    - profile（本机导入）：从 browser_profile 重新提取
    - manual（手动粘贴）：用账号自己的长期 cookie 换取新 token（不污染其他账号）
    """
    from ..config import settings
    a = db.get(models.Account, aid)
    if not a:
        raise HTTPException(status_code=404, detail="账号不存在")
    proxy = (a.proxy or "").strip() or None
    try:
        if a.source == "profile":
            cookies = sdk.extract_cookies_from_profile(str(settings.gh_home / "browser_profile"), proxy=proxy)
        else:
            own = security.cookie_str_to_dict(security.decrypt_cookie(a.cookies_enc))
            cookies = sdk.refresh_cookie_by_own(own, proxy=sdk.parse_proxy_for_playwright(proxy))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"刷新失败: {str(e)[:200]}")
    # 当前登录账号以 getUserSimple 接口为准（lgc/dnk 可能残留其他账号昵称）
    hc = sdk.health_check(cookies, proxy=proxy)
    new_taobao = hc.get("taobao_id") or sdk.decode_taobao_nick(
        cookies.get("lgc") or cookies.get("dnk") or "")
    if new_taobao and new_taobao != a.taobao_id:
        # 刷新后的淘宝账号与原来不一致，说明 cookie 指向了别的账号，拒绝覆盖
        raise HTTPException(status_code=400,
                            detail=f"刷新后淘宝ID({new_taobao})与原账号({a.taobao_id})不一致，已中止，请重新粘贴正确 cookie")
    a.cookies_enc = security.encrypt_cookie(security.cookie_dict_to_str(cookies))
    a.taobao_id = new_taobao or a.taobao_id
    a.status = "ok"
    a.last_check = datetime.utcnow()
    db.commit()
    return {"message": f"已刷新，淘宝ID: {a.taobao_id}"}


@router.put("/{aid}", response_model=schemas.AccountOut)
def update_account(aid: int, body: schemas.AccountUpdateIn,
                   user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    """编辑账号名称 / 备注 / 代理。"""
    a = db.get(models.Account, aid)
    if not a:
        raise HTTPException(status_code=404, detail="账号不存在")
    if body.name:
        a.name = body.name
    a.remark = body.remark
    a.proxy = (body.proxy or "").strip()
    db.commit()
    db.refresh(a)
    return _to_out(a)


@router.delete("/{aid}", response_model=schemas.MsgOut)
def delete_account(aid: int, user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    a = db.get(models.Account, aid)
    if not a:
        raise HTTPException(status_code=404, detail="账号不存在")
    db.delete(a)
    db.commit()
    return {"message": "已删除"}


# ---------------- 账号登录态自动刷新（后台定时任务） ----------------
def auto_refresh_account(aid: int) -> dict:
    """体检单个账号，失效则按来源自动刷新登录态。不依赖请求上下文，供后台任务调用。"""
    from ..config import settings
    db = SessionLocal()
    try:
        a = db.get(models.Account, aid)
        if not a:
            return {"aid": aid, "ok": False, "msg": "账号不存在"}
        proxy = (a.proxy or "").strip() or None
        # 1. 健康检查
        cookies = security.cookie_str_to_dict(security.decrypt_cookie(a.cookies_enc))
        hc = sdk.health_check(cookies, proxy=proxy)
        if hc["ok"]:
            a.status = "ok"
            a.last_check = datetime.utcnow()
            db.commit()
            return {"aid": aid, "ok": True, "msg": "健康", "refreshed": False}
        # 2. 失效：按来源刷新
        try:
            if a.source == "profile":
                cookies = sdk.extract_cookies_from_profile(str(settings.gh_home / "browser_profile"), proxy=proxy)
            else:
                own = security.cookie_str_to_dict(security.decrypt_cookie(a.cookies_enc))
                cookies = sdk.refresh_cookie_by_own(own, proxy=sdk.parse_proxy_for_playwright(proxy))
        except Exception as e:
            a.status = "expired"
            a.last_check = datetime.utcnow()
            db.commit()
            return {"aid": aid, "ok": False, "msg": f"刷新失败: {str(e)[:120]}", "refreshed": False}
        # 3. 刷新后校验
        hc2 = sdk.health_check(cookies, proxy=proxy)
        new_taobao = hc2.get("taobao_id") or sdk.decode_taobao_nick(
            cookies.get("lgc") or cookies.get("dnk") or "")
        if new_taobao and new_taobao != a.taobao_id:
            # 刷新后指向了别的账号，拒绝覆盖，标记失效
            a.status = "expired"
            a.last_check = datetime.utcnow()
            db.commit()
            return {"aid": aid, "ok": False, "msg": "刷新后淘宝ID与原账号不一致", "refreshed": False}
        a.cookies_enc = security.encrypt_cookie(security.cookie_dict_to_str(cookies))
        a.taobao_id = new_taobao or a.taobao_id
        a.status = "ok"
        a.last_check = datetime.utcnow()
        db.commit()
        return {"aid": aid, "ok": True, "msg": "已自动刷新", "refreshed": True}
    except Exception as e:
        return {"aid": aid, "ok": False, "msg": str(e)[:120], "refreshed": False}
    finally:
        db.close()


def auto_refresh_all():
    """定时任务入口：扫描所有账号，逐个体检并自动刷新。"""
    db = SessionLocal()
    try:
        ids = [r[0] for r in db.query(models.Account.id).all()]
    finally:
        db.close()
    for aid in ids:
        try:
            r = auto_refresh_account(aid)
            print(f"[账号自动刷新] aid={aid} ok={r.get('ok')} msg={r.get('msg')}", flush=True)
        except Exception as e:
            print(f"[账号自动刷新] aid={aid} 异常: {str(e)[:120]}", flush=True)


_auto_scheduler = None


def start_auto_refresh_scheduler():
    """启动账号登录态自动刷新调度器（默认每 60 分钟，可用 ACCOUNT_REFRESH_MINUTES 覆盖）。"""
    global _auto_scheduler
    if _auto_scheduler and _auto_scheduler.running:
        return
    from apscheduler.schedulers.background import BackgroundScheduler
    from ..config import settings
    _auto_scheduler = BackgroundScheduler(daemon=True)
    _auto_scheduler.add_job(auto_refresh_all, "interval",
                            minutes=settings.account_refresh_minutes,
                            id="account_auto_refresh", replace_existing=True,
                            max_instances=1)
    _auto_scheduler.start()
