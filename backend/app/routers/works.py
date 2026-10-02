# -*- coding: utf-8 -*-
"""作品管理路由：列表、同步、删除。"""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas, security
from ..core import sdk
from ..database import get_db
from .auth import get_current_user

router = APIRouter(prefix="/api/works", tags=["works"])


def _client_for(db, account_id):
    a = db.get(models.Account, account_id)
    if not a:
        raise HTTPException(status_code=404, detail="账号不存在")
    return a, sdk.build_client(db, a)


def _parse_work(item: dict) -> dict:
    """把光合作品原始结构解析为统一 dict（publish_time 为 datetime，写库用）。"""
    b = item.get("baseInfo", {})
    inter = item.get("interactiveInfo", {})
    v = (b.get("video") or {})
    return {
        "work_id": str(b.get("id", "")),
        "title": b.get("title", "") or (b.get("summary") or ""),
        "cover_url": (b.get("cover") or {}).get("url", ""),
        "status": (item.get("auditInfo") or {}).get("status", 0),
        "publish_time": (datetime.fromtimestamp(b.get("publishTime") / 1000)
                         if b.get("publishTime") else None),
        "play_count": inter.get("pvCount", 0) or 0,
        "like_count": inter.get("likeCount", 0) or 0,
        "collect_count": inter.get("collectCount", 0) or 0,
        "comment_count": inter.get("commentCount", 0) or 0,
        "duration": int(v.get("duration") or 0),
        "content_type": "video" if (v.get("duration") or b.get("video")) else "image",
        "high_quality": bool(b.get("highQuality")),
        "elite": bool(b.get("elite")),
        "homepage_top": bool(b.get("homepageTop")),
        "private_level": int(b.get("privateLevel") or 1),
    }


def _work_dict(p: dict) -> dict:
    """列表接口输出用：publish_time 转字符串。"""
    d = dict(p)
    d["publish_time"] = d["publish_time"].strftime("%Y-%m-%d %H:%M:%S") if d.get("publish_time") else ""
    return d


@router.get("")
def list_works(account_id: int, page: int = 1, size: int = 200, full: bool = True,
               user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    """作品列表。full=true 拉全量（自动翻页），否则按 page/size 分页。"""
    a, gh = _client_for(db, account_id)
    try:
        if full:
            data = gh.list_works_all()
            total = len(data)
        else:
            r = gh.list_works(page_size=size, page_no=page)
            data = r["items"]
            total = r["total"]
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"拉取失败: {str(e)[:200]}")
    return {"items": [_work_dict(_parse_work(item)) for item in data], "total": total}


@router.post("/{account_id}/sync")
def sync_works(account_id: int, user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    """把光合作品拉取到本地缓存（覆盖该账号的 works 表）。"""
    a, gh = _client_for(db, account_id)
    try:
        data = gh.list_works_all()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"同步失败: {str(e)[:200]}")
    # 清空旧缓存
    db.query(models.Work).filter_by(account_id=account_id).delete()
    for item in data:
        p = _parse_work(item)
        db.add(models.Work(account_id=account_id, raw_json=str(item)[:8000], **p))
    db.commit()
    return {"message": f"已同步 {len(data)} 条作品"}


@router.delete("/{account_id}/{work_id}", response_model=schemas.MsgOut)
def delete_work(account_id: int, work_id: str, user: models.User = Depends(get_current_user),
                db: Session = Depends(get_db)):
    a, gh = _client_for(db, account_id)
    try:
        ret = gh.delete_work(work_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"删除失败: {str(e)[:200]}")
    return {"message": f"删除结果: {ret}"}


@router.get("/{account_id}/{work_id}/edit-url")
def edit_url(account_id: int, work_id: str, user: models.User = Depends(get_current_user),
             db: Session = Depends(get_db)):
    """获取作品编辑页 URL。"""
    a, gh = _client_for(db, account_id)
    try:
        url = gh.get_edit_url(work_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"获取编辑入口失败: {str(e)[:200]}")
    return {"url": url}


_DECLARATION_REV = {0: "内容无需标注", 1: "含AI生成内容", 2: "含虚构演绎内容",
                    3: "内容为转载", 4: "个人观点，仅供参考", 5: "内容含营销信息"}


def _edit_item_out(it: dict) -> dict:
    out = dict(it)
    out["item_id"] = str(it.get("itemId", ""))
    pic = it.get("picUrl", "")
    out["pic_url"] = ("https:" + pic) if pic.startswith("//") else pic
    out["commission_rate"] = it.get("commissionRate", "")
    return out


@router.get("/{account_id}/{work_id}/edit-content")
def edit_content(account_id: int, work_id: str, user: models.User = Depends(get_current_user),
                 db: Session = Depends(get_db)):
    """获取作品可编辑内容（站内编辑回填，含智能封面候选/推荐标签/商品taskId/话题）。"""
    a, gh = _client_for(db, account_id)
    try:
        prep = gh.edit_prepare(work_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"获取编辑内容失败: {str(e)[:200]}")
    c = prep["content"]
    cover = (c.get("coverUser") or [{}])[0]
    from_type = (c.get("contentSource") or {}).get("fromType", 0)
    return {
        "title": c.get("shortTitle", ""),
        "desc": c.get("title", ""),
        "cover_url": cover.get("url", ""),
        "cover_width": cover.get("width"),
        "cover_height": cover.get("height"),
        "items": [_edit_item_out(it) for it in (c.get("items") or [])],
        "topics": [{"topic_id": t.get("topicId"), "title": t.get("topicTitle"),
                    "type": t.get("type", "hashtag_publicActivity")}
                   for t in (c.get("topics") or [])],
        "from_type": from_type,
        "declaration": _DECLARATION_REV.get(from_type, "内容无需标注"),
        "covers": prep.get("covers", []),
        "tags": prep.get("tags", []),
        "item_task_id": prep.get("item_task_id", ""),
        "publish_session": prep.get("publish_session", ""),
        "file_id": prep.get("file_id", ""),
    }


# ---------------- 编辑场景：话题 / 商品（session 由 edit-content 返回后回传） ----------------
def _edit_topic_out(t: dict) -> dict:
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


@router.get("/{account_id}/{work_id}/topics")
def edit_topics(account_id: int, work_id: str, session: str = "", tab_id: str = "1", cursor: str = "1",
                user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    """编辑场景官方征稿话题列表。"""
    if not session:
        return {"tabs": [], "topics": [], "cursor": "", "has_next": False}
    a, gh = _client_for(db, account_id)
    try:
        r = gh.topic_list(session, tab_id=tab_id, cursor=cursor)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"话题查询失败: {str(e)[:200]}")
    return {"tabs": r.get("tabs", []), "topics": [_edit_topic_out(t) for t in r.get("topics", [])],
            "cursor": r.get("cursor", ""), "has_next": r.get("has_next", False)}


@router.get("/{account_id}/{work_id}/topics/search")
def edit_topics_search(account_id: int, work_id: str, session: str = "", keyword: str = "", cursor: str = "1",
                       user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    """编辑场景官方话题搜索。"""
    if not session:
        return {"topics": [], "cursor": "", "has_next": False}
    a, gh = _client_for(db, account_id)
    try:
        r = gh.topic_search(session, keyword=keyword, cursor=cursor)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"话题搜索失败: {str(e)[:200]}")
    return {"topics": [_edit_topic_out(t) for t in r.get("topics", [])],
            "cursor": r.get("cursor", ""), "has_next": r.get("has_next", False)}


@router.get("/{account_id}/{work_id}/items")
def edit_items(account_id: int, work_id: str, session: str = "", task_id: str = "", cursor: str = "", size: int = 20,
               user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    """编辑场景推荐商品列表（基于 task_id）。"""
    if not session or not task_id:
        return {"items": [], "cursor": ""}
    a, gh = _client_for(db, account_id)
    try:
        r = gh.list_items(task_id, session, cursor=cursor, page_size=size)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"商品查询失败: {str(e)[:200]}")
    return {"items": [_edit_item_out(it) for it in r.get("items", [])], "cursor": r.get("cursor", "")}


@router.get("/{account_id}/{work_id}/search-items")
def edit_search_items(account_id: int, work_id: str, session: str = "", keyword: str = "",
                      cursor: str = "", size: int = 15,
                      user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    """编辑场景「平台优选」商品搜索。"""
    if not session:
        return {"items": [], "cursor": ""}
    a, gh = _client_for(db, account_id)
    try:
        r = gh.search_items(session, keyword=keyword, cursor=cursor, page_size=size)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"搜索失败: {str(e)[:200]}")
    return {"items": [_edit_item_out(it) for it in r.get("items", [])], "cursor": r.get("cursor", "")}


@router.post("/{account_id}/{work_id}/edit")
def edit_work(account_id: int, work_id: str, body: dict,
              user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    """站内编辑提交（改标题/描述/封面/商品/话题/声明）。"""
    a, gh = _client_for(db, account_id)
    try:
        prep = gh.edit_prepare(work_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"获取编辑内容失败: {str(e)[:200]}")
    from app.core.guanghe import DECLARATION_MAP
    from_type = DECLARATION_MAP.get(body.get("declaration") or "内容无需标注", 0)
    items = body.get("items")
    topics = body.get("topics")
    try:
        result = gh.edit_submit(
            prep, title=body.get("title"), desc=body.get("desc"),
            cover_url=body.get("cover_url") or None,
            cover_width=body.get("cover_width"), cover_height=body.get("cover_height"),
            items=items, from_type=from_type, topics=topics)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"编辑失败: {str(e)[:200]}")
    ret = result.get("ret", [])
    ok = bool(ret) and "SUCCESS" in ret[0]
    msg = ret[0] if ret else ""
    if "editNotSupport" in msg:
        return {"status": "failed", "result_msg": "该作品已编辑过一次，光合限制每条内容最多编辑 1 次"}
    return {"status": "success" if ok else "failed", "result_msg": str(ret)[:300]}


@router.post("/{account_id}/{work_id}/top", response_model=schemas.MsgOut)
def top_work(account_id: int, work_id: str, top: bool = True,
             user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    """置顶 / 取消置顶。"""
    a, gh = _client_for(db, account_id)
    try:
        ret = gh.top_work(work_id, top=top)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"置顶失败: {str(e)[:200]}")
    return {"message": f"已{'置顶' if top else '取消置顶'}"}


@router.post("/{account_id}/{work_id}/privacy", response_model=schemas.MsgOut)
def set_privacy(account_id: int, work_id: str, private: bool = True,
                user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    """设为私密 / 设为公开。"""
    a, gh = _client_for(db, account_id)
    try:
        ret = gh.set_privacy(work_id, private=private)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"设置失败: {str(e)[:200]}")
    return {"message": f"已{'设为私密' if private else '设为公开'}"}
