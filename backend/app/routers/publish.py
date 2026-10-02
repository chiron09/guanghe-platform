# -*- coding: utf-8 -*-
"""视频发布路由（仿光合官方：上传 → 填写 → 发布/定时；含发布记录）。"""
import json
import os
import threading
import uuid
from datetime import datetime

import requests as httpx
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from .. import models, schemas, security
from ..config import DATA_DIR
from ..core import sdk
from ..database import get_db, SessionLocal
from .auth import get_current_user

router = APIRouter(prefix="/api", tags=["publish"])

VIDEO_EXTS = (".mp4", ".mov", ".m4v")
VIDEO_DIR = DATA_DIR / "videos"
VIDEO_DIR.mkdir(parents=True, exist_ok=True)

# 小红书无水印解析接口（json=1 返回标题/封面/视频直链/实况标记）
XHS_API = "https://1252026907-0z336n7lff.ap-guangzhou.tencentscf.com"


def _to_prepare_dict(draft: models.PublishDraft) -> dict:
    return json.loads(draft.prepare_json or "{}")


# ---------------- 视频选择 ----------------
@router.post("/videos/upload-file")
async def upload_video_file(file: UploadFile = File(...), title: str = Form(""),
                            user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    """浏览器直接上传视频文件到服务端。"""
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in VIDEO_EXTS:
        raise HTTPException(status_code=400, detail=f"仅支持 {','.join(VIDEO_EXTS)}")
    fname = f"{uuid.uuid4().hex[:8]}_{file.filename}"
    path = VIDEO_DIR / fname
    size = 0
    with open(path, "wb") as f:
        while chunk := await file.read(1 << 20):
            f.write(chunk)
            size += len(chunk)
    v = models.Video(path=str(path), filename=fname, title=title or os.path.splitext(fname)[0])
    db.add(v)
    db.commit()
    db.refresh(v)
    return {"id": v.id, "path": v.path, "filename": fname, "size": size}


@router.get("/videos/{vid}/file")
def get_video_file(vid: int, user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    """返回视频文件流（前端预览用）。"""
    v = db.get(models.Video, vid)
    if not v or not os.path.isfile(v.path):
        raise HTTPException(status_code=404, detail="视频不存在")
    return FileResponse(v.path, media_type="video/mp4")


@router.post("/videos/remote")
def add_remote_video(url: str, title: str = "", user: models.User = Depends(get_current_user),
                     db: Session = Depends(get_db)):
    """从远程 URL 拉取视频到本地。"""
    if not url.startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail="无效的 URL")
    try:
        r = httpx.get(url, stream=True, timeout=600, headers={"User-Agent": "Mozilla/5.0"})
        r.raise_for_status()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"下载失败: {str(e)[:200]}")
    ct = (r.headers.get("content-type") or "").lower()
    if "video" not in ct and not url.lower().split("?")[0].endswith(VIDEO_EXTS):
        raise HTTPException(status_code=400, detail=f"链接不是视频 (content-type={ct})")
    ext = ".mp4"
    for e in VIDEO_EXTS:
        if e in url.lower():
            ext = e
            break
    fname = f"remote_{uuid.uuid4().hex[:8]}{ext}"
    path = VIDEO_DIR / fname
    size = 0
    with open(path, "wb") as f:
        for chunk in r.iter_content(chunk_size=1 << 20):
            f.write(chunk)
            size += len(chunk)
    v = models.Video(path=str(path), filename=fname, title=title or os.path.splitext(fname)[0])
    db.add(v)
    db.commit()
    db.refresh(v)
    return {"id": v.id, "path": v.path, "filename": fname, "size": size}


@router.post("/videos/import-xhs")
def import_xhs(url: str, user: models.User = Depends(get_current_user),
               db: Session = Depends(get_db)):
    """小红书一键导入：解析元数据（标题/封面/视频直链），下载无水印视频到本地。

    返回 {id, filename, size, title, cover_url, tags}；
    tags 为从描述(desc)提取的前 4 个 #话题（供前端填入描述框）。
    """
    import re
    # 兼容粘贴整段分享文案：从中提取第一个 URL（保留 ? & = % 等查询字符，仅去掉末尾粘连的中文标点）
    m = re.search(r"https?://[^\s]+", url)
    if m:
        url = m.group(0).rstrip("，。；、!！?？\"'（）()【】[]")
    if not url.startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail="无效的小红书链接")
    # 1. 解析元数据
    try:
        r = httpx.get(XHS_API, params={"url": url, "json": "1"}, timeout=60,
                      headers={"User-Agent": "Mozilla/5.0"})
        if r.status_code in (400, 404):
            raise HTTPException(status_code=400, detail="小红书链接无效或笔记不存在")
        r.raise_for_status()
        meta = r.json()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"小红书解析失败: {str(e)[:200]}")
    if not isinstance(meta, dict):
        raise HTTPException(status_code=400, detail="小红书解析失败: 响应不是 JSON")
    if meta.get("error"):
        raise HTTPException(status_code=400,
                            detail=f"小红书解析失败: {meta.get('message') or meta['error']}")
    if str(meta.get("type") or "").lower() != "video":
        raise HTTPException(status_code=400, detail="这是图文笔记（无视频），无法导入视频")
    title = (meta.get("title") or "").strip()
    desc = (meta.get("desc") or "").strip()
    cover_url = (meta.get("cover") or "").replace("http://", "https://")
    video_url = ((meta.get("video") or {}).get("url") or "").replace("http://", "https://")
    if not video_url:
        raise HTTPException(status_code=400, detail="未解析到视频直链")
    # 2. 下载无水印原片（CDN 可能有 Referer 白名单：先带小红书 Referer，被拒则无 Referer 重试）
    ua = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
          "(KHTML, like Gecko) Chrome/153.0.0.0 Safari/537.36")
    try:
        vr = httpx.get(video_url, stream=True, timeout=600,
                       headers={"User-Agent": ua, "Referer": "https://www.xiaohongshu.com/"})
        if vr.status_code in (403, 451):
            vr.close()
            vr = httpx.get(video_url, stream=True, timeout=600, headers={"User-Agent": ua})
        vr.raise_for_status()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"视频下载失败: {str(e)[:200]}")
    fname = f"xhs_{uuid.uuid4().hex[:8]}.mp4"
    path = VIDEO_DIR / fname
    size = 0
    with open(path, "wb") as f:
        for chunk in vr.iter_content(chunk_size=1 << 20):
            f.write(chunk)
            size += len(chunk)
    v = models.Video(path=str(path), filename=fname, title=title[:64])
    db.add(v)
    db.commit()
    db.refresh(v)
    # 3. 从描述提取 # 话题（格式 "#标签[话题]"，取前 4 个）
    tags = re.findall(r"#([^#\s\[\]]+)", desc)[:4]
    return {"id": v.id, "filename": fname, "size": size,
            "title": title, "cover_url": cover_url, "tags": tags}


# ---------------- 发布：阶段一 prepare ----------------
def _run_prepare(draft_id: int, skip_covers: bool = False):
    db = SessionLocal()
    try:
        draft = db.get(models.PublishDraft, draft_id)
        if not draft:
            return
        account = db.get(models.Account, draft.account_id)
        video = db.get(models.Video, draft.video_id)
        if not account or not video:
            draft.status = "failed"
            draft.error_msg = "账号或视频不存在"
            db.commit()
            return
        gh = sdk.build_client(db, account)
        prepare = gh.publish_prepare(video.path, skip_covers=skip_covers)
        draft.file_id = prepare["file_id"]
        draft.publish_session = prepare["publish_session"]
        draft.item_task_id = prepare["item_task_id"]
        draft.covers_json = json.dumps(prepare["covers"], ensure_ascii=False)
        draft.tags_json = json.dumps(prepare["tags"], ensure_ascii=False)
        draft.prepare_json = json.dumps(prepare, ensure_ascii=False)
        draft.status = "prepared"
        db.commit()
    except Exception as e:
        draft.status = "failed"
        draft.error_msg = str(e)[:300]
        db.commit()
    finally:
        db.close()


@router.post("/publish/prepare")
def prepare(body: dict, background: BackgroundTasks, user: models.User = Depends(get_current_user),
            db: Session = Depends(get_db)):
    """阶段一：预上传视频并解析（后台执行），返回 draft id 供轮询。"""
    account_id = body.get("account_id")
    video_id = body.get("video_id")
    if not db.get(models.Account, account_id):
        raise HTTPException(status_code=404, detail="账号不存在")
    video = db.get(models.Video, video_id)
    if not video:
        raise HTTPException(status_code=404, detail="视频不存在")
    draft = models.PublishDraft(
        account_id=account_id, video_id=video_id, title=body.get("title") or video.title or "",
        desc=body.get("desc") or video.desc or "",
        declaration=body.get("declaration") or "内容无需标注", status="preparing")
    db.add(draft)
    db.commit()
    db.refresh(draft)
    skip_covers = bool(body.get("skip_covers"))
    background.add_task(_run_prepare, draft.id, skip_covers)
    return {"id": draft.id, "status": draft.status}


@router.get("/publish/draft/{did}")
def get_draft(did: int, user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    d = db.get(models.PublishDraft, did)
    if not d:
        raise HTTPException(status_code=404, detail="草稿不存在")
    return {"id": d.id, "status": d.status, "error_msg": d.error_msg, "title": d.title,
            "desc": d.desc, "declaration": d.declaration,
            "covers": json.loads(d.covers_json or "[]"), "tags": json.loads(d.tags_json or "[]")}


def _item_out(it: dict) -> dict:
    """返回完整商品对象 + 前端展示用兼容字段（提交时需带 source 等原始字段）。"""
    out = dict(it)
    out["item_id"] = str(it.get("itemId", ""))
    out["pic_url"] = ("https:" + it["picUrl"]) if it.get("picUrl", "").startswith("//") else it.get("picUrl", "")
    out["commission_rate"] = it.get("commissionRate", "")
    return out


def _dedup(items: list) -> list:
    """按 itemId 去重（平台优选接口对同一商品可能返回重复记录）。"""
    seen, out = set(), []
    for it in items:
        if it["item_id"] and it["item_id"] in seen:
            continue
        if it["item_id"]:
            seen.add(it["item_id"])
        out.append(it)
    return out


@router.get("/publish/draft/{did}/items")
def draft_items(did: int, keyword: str = "", cursor: str = "", size: int = 20,
                user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    """关联商品列表（基于 prepare 拿到的 taskId；光合服务端不支持 keyword 搜索，搜索由前端本地过滤）。"""
    d = db.get(models.PublishDraft, did)
    if not d:
        raise HTTPException(status_code=404, detail="草稿不存在")
    if not d.item_task_id:
        return {"items": [], "cursor": ""}
    account = db.get(models.Account, d.account_id)
    gh = sdk.build_client(db, account)
    try:
        r = gh.list_items(d.item_task_id, d.publish_session, cursor=cursor, page_size=size)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"商品查询失败: {str(e)[:200]}")
    return {"items": _dedup([_item_out(it) for it in r.get("items", [])]), "cursor": r.get("cursor", "")}


@router.get("/publish/draft/{did}/search-items")
def draft_search_items(did: int, keyword: str, cursor: str = "", size: int = 15,
                       user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    """「平台优选」商品库搜索（官方同款接口 source=coreitem，支持 itemId 精确搜与标题关键词搜）。"""
    d = db.get(models.PublishDraft, did)
    if not d:
        raise HTTPException(status_code=404, detail="草稿不存在")
    if not d.publish_session:
        return {"items": [], "cursor": ""}
    account = db.get(models.Account, d.account_id)
    gh = sdk.build_client(db, account)
    try:
        r = gh.search_items(d.publish_session, keyword=keyword, cursor=cursor, page_size=size)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"搜索失败: {str(e)[:200]}")
    return {"items": _dedup([_item_out(it) for it in r.get("items", [])]), "cursor": r.get("cursor", "")}


# ---------------- 参与话题活动 ----------------
def _topic_out(t: dict) -> dict:
    """话题元素精简（前端展示 + 提交用）。提交需 {topicId: sceneId, topicTitle: title, type}。"""
    acts = [{"id": a.get("id"), "title": a.get("title"), "level": a.get("level"),
             "delivery": f"{(a.get('deliveryBegin') or '')[:10]}~{(a.get('deliveryEnd') or '')[:10]}",
             "rewards": a.get("rewardTypeDesc", [])} for a in (t.get("activities") or [])]
    return {"topic_id": t.get("sceneId", ""), "title": t.get("title", ""),
            "type": t.get("type", "hashtag_publicActivity"),
            "content_count": t.get("formatValidContentCount", ""),
            "user_count": t.get("formatUserCount", ""),
            "browse_count": t.get("formatBrowseCount", ""),
            "cover": t.get("cover", ""), "desc": (t.get("desc") or "").strip()[:60],
            "category": ",".join(t.get("firstCategoryNames", []) or []),
            "topic_rank": t.get("topicRank", ""), "icon_type": t.get("iconType", ""),
            "prize": t.get("prize", "false"), "activities": acts}


def _draft_session(db, did: int):
    d = db.get(models.PublishDraft, did)
    if not d:
        raise HTTPException(status_code=404, detail="草稿不存在")
    if not d.publish_session:
        return None, None
    account = db.get(models.Account, d.account_id)
    return db.get(models.Account, d.account_id) and account, d


@router.get("/publish/draft/{did}/topics")
def draft_topics(did: int, tab_id: str = "1", cursor: str = "1",
                 user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    """参与话题活动：官方征稿话题列表（分类 tabs + cursor 翻页）。"""
    d = db.get(models.PublishDraft, did)
    if not d:
        raise HTTPException(status_code=404, detail="草稿不存在")
    if not d.publish_session:
        return {"tabs": [], "topics": [], "cursor": "", "has_next": False}
    account = db.get(models.Account, d.account_id)
    gh = sdk.build_client(db, account)
    try:
        r = gh.topic_list(d.publish_session, tab_id=tab_id, cursor=cursor)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"话题查询失败: {str(e)[:200]}")
    return {"tabs": r.get("tabs", []), "topics": [_topic_out(t) for t in r.get("topics", [])],
            "cursor": r.get("cursor", ""), "has_next": r.get("has_next", False)}


@router.get("/publish/draft/{did}/topics/search")
def draft_topics_search(did: int, keyword: str, cursor: str = "1",
                        user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    """官方话题搜索。"""
    d = db.get(models.PublishDraft, did)
    if not d:
        raise HTTPException(status_code=404, detail="草稿不存在")
    if not d.publish_session:
        return {"topics": [], "cursor": "", "has_next": False}
    account = db.get(models.Account, d.account_id)
    gh = sdk.build_client(db, account)
    try:
        r = gh.topic_search(d.publish_session, keyword=keyword, cursor=cursor)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"话题搜索失败: {str(e)[:200]}")
    return {"topics": [_topic_out(t) for t in r.get("topics", [])],
            "cursor": r.get("cursor", ""), "has_next": r.get("has_next", False)}


# ---------------- 封面上传 ----------------
async def _upload_cover_bytes(db, account_id: int, data: bytes, fname: str):
    a = db.get(models.Account, account_id)
    if not a:
        raise HTTPException(status_code=404, detail="账号不存在")
    if len(data) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="图片超过 10MB")
    gh = sdk.build_client(db, a)
    try:
        pic_url = gh.upload_image(data, fname)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"封面上传失败: {str(e)[:200]}")
    return {"url": pic_url, "size": len(data)}


@router.post("/publish/upload-cover")
async def upload_cover(account_id: int, file: UploadFile = File(...),
                       user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    """上传本地图片作为封面。"""
    data = await file.read()
    fname = file.filename or "cover.jpg"
    return await _upload_cover_bytes(db, account_id, data, fname)


@router.post("/publish/upload-cover-url")
async def upload_cover_url(account_id: int, url: str,
                           user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    """拉取远程图片并上传为封面。"""
    if not url.startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail="无效的图片 URL")
    try:
        r = httpx.get(url, timeout=60, headers={"User-Agent": "Mozilla/5.0"})
        r.raise_for_status()
        data = r.content
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"下载图片失败: {str(e)[:200]}")
    ct = (r.headers.get("content-type") or "")
    if "image" not in ct and not url.lower().split("?")[0].endswith((".jpg", ".jpeg", ".png", ".webp")):
        raise HTTPException(status_code=400, detail=f"链接不是图片 (content-type={ct})")
    fname = os.path.basename(url.split("?")[0]) or "cover.jpg"
    return await _upload_cover_bytes(db, account_id, data, fname)


# ---------------- 发布：阶段二 submit ----------------
@router.post("/publish/submit")
def submit(body: dict, user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    """阶段二：提交发布。带 schedule_at 则创建定时任务（到点自动执行完整发布），否则立即发布。"""
    d = db.get(models.PublishDraft, body.get("draft_id"))
    if not d:
        raise HTTPException(status_code=404, detail="草稿不存在")
    if d.status != "prepared":
        if d.status == "preparing":
            raise HTTPException(status_code=400, detail="视频正在解析中，请稍候再发布")
        if d.status == "submitted":
            raise HTTPException(status_code=400, detail="该视频已提交过发布，请重新上传视频后再试")
        raise HTTPException(status_code=400, detail=f"当前状态({d.status})不可发布，请重新上传视频后再试")
    account = db.get(models.Account, d.account_id)
    title = body.get("title") or d.title
    desc = body.get("desc") or d.desc
    declaration = body.get("declaration") or d.declaration
    cover_url = body.get("cover_url") or None
    topics = body.get("topics") or []
    items = body.get("items") or []

    # 定时发布：创建任务，到点由调度器执行完整发布（视频文件已在本地）
    schedule_at = (body.get("schedule_at") or "").strip()
    if schedule_at:
        try:
            run_at = datetime.strptime(schedule_at, "%Y-%m-%d %H:%M")
        except ValueError:
            raise HTTPException(status_code=400, detail="定时时间格式应为 YYYY-MM-DD HH:MM")
        if run_at <= datetime.now():
            raise HTTPException(status_code=400, detail="定时时间必须晚于当前时间")
        task = models.PublishTask(
            account_id=account.id, video_id=d.video_id, title=title, desc=desc,
            declaration=declaration, status="scheduled", schedule_at=run_at,
            cover_url=cover_url or "",
            topics_json=json.dumps(topics, ensure_ascii=False),
            items_json=json.dumps(items, ensure_ascii=False))
        db.add(task)
        db.commit()
        db.refresh(task)
        return {"status": "scheduled", "task_id": task.id,
                "result_msg": f"定时任务已创建：{schedule_at} 自动发布"}

    # 立即发布
    gh = sdk.build_client(db, account)
    prepare = _to_prepare_dict(d)
    try:
        result = gh.publish_submit(title, desc, declaration, prepare,
                                   cover_url=cover_url,
                                   topics=topics, items=items)
        ret = result.get("ret", [])
        ok = bool(ret) and "SUCCESS" in ret[0]
        d.status = "submitted"
        db.commit()
        return {"status": "success" if ok else "failed", "result_msg": str(ret)[:300]}
    except Exception as e:
        db.commit()
        return {"status": "failed", "result_msg": str(e)[:300]}


# ---------------- 定时发布调度器 ----------------
def _run_scheduled(task_id: int):
    """到点执行定时任务：完整 prepare + submit。"""
    db = SessionLocal()
    task = None
    try:
        task = db.get(models.PublishTask, task_id)
        if not task or task.status != "scheduled":
            return
        task.status = "running"
        db.commit()
        account = db.get(models.Account, task.account_id)
        video = db.get(models.Video, task.video_id)
        if not account or not video:
            raise RuntimeError("账号或视频不存在")
        gh = sdk.build_client(db, account)
        prepare = gh.publish_prepare(video.path)
        cover_url = (task.cover_url
                     or (prepare["covers"][0]["url"] if prepare.get("covers") else None)
                     or (prepare["frame_urls"][0] if prepare.get("frame_urls") else None))
        result = gh.publish_submit(task.title, task.desc, task.declaration, prepare,
                                   cover_url=cover_url,
                                   topics=json.loads(task.topics_json or "[]"),
                                   items=json.loads(task.items_json or "[]"))
        ret = result.get("ret", [])
        ok = bool(ret) and "SUCCESS" in ret[0]
        task.status = "success" if ok else "failed"
        task.result_msg = str(ret)[:300]
        task.finished_at = datetime.now()
        db.commit()
    except Exception as e:
        if task:
            task.status = "failed"
            task.result_msg = str(e)[:300]
            task.finished_at = datetime.now()
            db.commit()
    finally:
        db.close()


def _check_scheduled():
    """扫描到期定时任务并异步执行。"""
    db = SessionLocal()
    try:
        due = (db.query(models.PublishTask)
               .filter(models.PublishTask.status == "scheduled",
                       models.PublishTask.schedule_at <= datetime.now())
               .all())
        for t in due:
            t.status = "running"
            db.commit()
            threading.Thread(target=_run_scheduled, args=(t.id,), daemon=True).start()
    finally:
        db.close()


scheduler = None


def start_scheduler():
    global scheduler
    if scheduler and scheduler.running:
        return
    from apscheduler.schedulers.background import BackgroundScheduler
    scheduler = BackgroundScheduler(daemon=True)
    scheduler.add_job(_check_scheduled, "interval", seconds=20, id="check_scheduled",
                      replace_existing=True, max_instances=1)
    scheduler.start()

