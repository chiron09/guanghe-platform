# -*- coding: utf-8 -*-
"""选品佣金 + 数据看板路由。"""
import concurrent.futures
import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas, security
from ..core import sdk
from ..database import get_db
from .auth import get_current_user

router = APIRouter(prefix="/api", tags=["commission", "dashboard"])

# 高佣接口不返回店铺名，用 listItems 按 itemId 补查的结果缓存（进程级）
_shop_cache = {}


def _full_pic(url: str) -> str:
    """补全图片 URL（淘宝部分返回 //xxx 协议相对路径）。"""
    if not url:
        return ""
    if url.startswith("//"):
        return "https:" + url
    return url


def _client_for(db, account_id):
    a = db.get(models.Account, account_id)
    if not a:
        raise HTTPException(status_code=404, detail="账号不存在")
    return sdk.build_client(db, a)


def _fetch_shop_name(cookies: dict, ps: str, item_id: str, proxy=None):
    """按 itemId 精确搜 listItems 补全店铺名；查不到不缓存（下次再试）。"""
    if item_id in _shop_cache:
        return item_id, _shop_cache[item_id]
    try:
        from ..core.guanghe import GuangheHTTP
        gh = GuangheHTTP(dict(cookies), proxy=proxy)   # 每线程独立实例，避免共享 Session 竞争
        r = gh.search_items(ps, keyword=str(item_id), page_size=3)
        for it in r.get("items", []):
            if str(it.get("itemId")) == str(item_id):
                name = it.get("shopTitle", "") or ""
                _shop_cache[item_id] = name
                return item_id, name
    except Exception:
        pass
    return item_id, ""


@router.get("/commission")
def commission(account_id: int, cursor: str = "1", size: int = 20,
               user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    gh = _client_for(db, account_id)
    try:
        d = gh.commission(page_size=size, cursor=cursor)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"查询失败: {str(e)[:200]}")
    items = d.get("page", {}).get("data", []) or []
    out = [schemas.CommissionItem(
        item_id=str(it.get("itemId", "")), title=it.get("title", ""),
        price=it.get("price", ""), commission_rate=it.get("commissionRate", ""),
        predict_income=it.get("predictIncome", ""),
        item_url=it.get("itemUrl", ""),
        shop_name=it.get("shopTitle", ""),
        pic_url=_full_pic(it.get("picUrl", "")),
        sell_count=it.get("recentSellFuzzyCount", "")) for it in items]
    # 高佣接口不返回店铺名：并发按 itemId 精确搜 listItems 补全（带进程缓存）
    try:
        missing = [o for o in out if not o.shop_name]
        if missing:
            j = gh.call("mtop.taobao.media.guang.session.generate",
                        {"request": json.dumps({"ugcScene": "pc_newcreator_video"}, separators=(",", ":"))},
                        method="POST")
            ps = j["data"]["publishSession"]
            with concurrent.futures.ThreadPoolExecutor(max_workers=6) as ex:
                pairs = list(ex.map(lambda o: _fetch_shop_name(gh.cookies, ps, o.item_id, gh.proxy), missing))
            id2shop = dict(pairs)
            for o in out:
                o.shop_name = o.shop_name or id2shop.get(o.item_id, "")
    except Exception:
        pass
    return {"items": out, "cursor": d.get("page", {}).get("cursor", "")}


@router.get("/commission/search")
def commission_search(account_id: int, keyword: str, size: int = 20,
                      user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    """带货商品搜索（关键字 / 商品ID，走平台优选 source=coreitem 接口）。"""
    import json
    import uuid
    gh = _client_for(db, account_id)
    try:
        j = gh.call("mtop.taobao.media.guang.session.generate",
                    {"request": json.dumps({"ugcScene": "pc_newcreator_video"}, separators=(",", ":"))},
                    method="POST")
        ps = j["data"]["publishSession"]
        r = gh.search_items(ps, keyword=keyword, page_size=size)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"搜索失败: {str(e)[:200]}")
    items = r.get("items", [])
    out = [schemas.CommissionItem(
        item_id=str(it.get("itemId", "")), title=it.get("title", ""),
        price=it.get("price", ""), commission_rate=it.get("commissionRate", ""),
        predict_income=it.get("predictIncome", ""),
        item_url=it.get("itemUrl", ""),
        shop_name=it.get("shopTitle", ""),
        pic_url=_full_pic(it.get("picUrl", "")),
        sell_count=it.get("recentSellFuzzyCount", "")) for it in items]
    return {"items": out, "cursor": r.get("cursor", "")}


@router.get("/dashboard")
def dashboard(account_id: int, days: int = 7,
              user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    gh = _client_for(db, account_id)
    try:
        d = gh.dashboard_indicators(days=days)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"查询失败: {str(e)[:200]}")
    return d
