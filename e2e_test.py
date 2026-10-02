#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""端到端验证两阶段发布（封面/标签/商品增强），成功后删除测试作品。"""
import json
import sys
import time

import requests

BASE = "http://127.0.0.1:8000/api"
VIDEO = r"F:\Workbuddy\WorkBuddy\2026-09-27-21-18-54\guanghe-reverse\test_video.mp4"
COVER = r"F:\Workbuddy\WorkBuddy\2026-09-27-21-18-54\guanghe-reverse\test_cover.jpg"


def main():
    # 1. 登录
    r = requests.post(f"{BASE}/auth/login", json={"username": "admin", "password": "admin123"})
    H = {"Authorization": "Bearer " + r.json()["access_token"]}
    print("[1] 登录 OK")

    # 2. 上传视频素材
    with open(VIDEO, "rb") as f:
        r = requests.post(f"{BASE}/videos/upload-file", headers=H,
                          files={"file": ("e2e_test.mp4", f, "video/mp4")}, data={"title": ""})
    video_id = r.json()["id"]
    print(f"[2] 视频素材 id={video_id}")

    # 3. 拿账号
    accounts = requests.get(f"{BASE}/accounts", headers=H).json()
    aid = accounts[0]["id"]
    print(f"[3] 账号 id={aid} ({accounts[0]['name']})")

    # 4. prepare（预上传+解析）
    r = requests.post(f"{BASE}/publish/prepare", headers=H, json={
        "account_id": aid, "video_id": video_id,
        "title": "增强功能验证-稍后删除", "desc": "封面/标签/商品两阶段发布验证",
        "declaration": "内容无需标注"})
    draft_id = r.json()["id"]
    print(f"[4] prepare 启动, draft_id={draft_id}")

    # 5. 轮询 draft
    draft = None
    for i in range(60):
        time.sleep(3)
        d = requests.get(f"{BASE}/publish/draft/{draft_id}", headers=H).json()
        print(f"    draft 状态: {d['status']} ({i*3}s)")
        if d["status"] in ("prepared", "failed"):
            draft = d
            break
    if not draft or draft["status"] != "prepared":
        print("!! prepare 失败:", draft.get("error_msg") if draft else "超时")
        sys.exit(1)
    covers, tags = draft["covers"], draft["tags"]
    print(f"[5] 解析完成: 智能封面 {len(covers)} 张, 推荐标签 {len(tags)} 个")
    for t in tags[:5]:
        print(f"    推荐标签: {t.get('name')} (热度 {t.get('popularity', '?')})")

    # 6. 商品列表
    r = requests.get(f"{BASE}/publish/draft/{draft_id}/items", headers=H)
    items = r.json()["items"]
    print(f"[6] 关联商品: {len(items)} 个")
    picked = []
    for it in items[:2]:
        print(f"    {it['title'][:24]} | ¥{it['price']} | 佣金{it['commission_rate']}")
        picked.append({"itemId": it["item_id"], "title": it["title"]})

    # 7. 上传本地封面
    with open(COVER, "rb") as f:
        r = requests.post(f"{BASE}/publish/upload-cover", headers=H,
                          params={"account_id": aid},
                          files={"file": ("e2e_cover.jpg", f, "image/jpeg")})
    cover_url = r.json()["url"]
    print(f"[7] 自定义封面上传成功: {cover_url[:80]}")

    # 8. 选标签（取前2个推荐 + 1个自定义）
    topics = [{"id": t["id"], "name": t["name"]} for t in tags[:2] if t.get("id")]
    topics.append({"name": "好物分享"})
    print(f"[8] 选定标签: {[t['name'] for t in topics]}")

    # 9. 提交发布
    r = requests.post(f"{BASE}/publish/submit", headers=H, json={
        "draft_id": draft_id, "title": "增强功能验证-稍后删除",
        "desc": "封面/标签/商品两阶段发布验证", "declaration": "内容无需标注",
        "cover_url": cover_url, "topics": topics, "items": picked})
    print(f"[9] 提交结果: {r.json()}")

    # 10. 核验作品列表
    time.sleep(5)
    r = requests.get(f"{BASE}/works", params={"account_id": aid}, headers=H)
    works = r.json()
    hit = [w for w in works if "增强功能验证" in w["title"]]
    print(f"[10] 作品核验: {'找到 ' + hit[0]['work_id'] if hit else '未找到（可能仍在入库）'}")
    if hit:
        wid = hit[0]["work_id"]
        r = requests.delete(f"{BASE}/works/{aid}/{wid}", headers=H)
        print(f"[11] 删除测试作品 {wid}: {r.json()}")


if __name__ == "__main__":
    main()
