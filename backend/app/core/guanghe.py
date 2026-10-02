# -*- coding: utf-8 -*-
"""光合平台 mtop 协议层（纯 HTTP，逆向产物）。

sign = md5(token & t & appKey & data)，token 取 cookie _m_h5_tk 下划线前半段。
本模块只做协议调用，不持有账号状态（cookie 由上层传入）。
"""
import hashlib
import json
import os
import re
import subprocess
import tempfile
import time
import urllib.parse
import uuid

import requests

APPKEY = "12574478"
GATEWAY = "https://h5api.m.taobao.com/h5/{api}/{v}/"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/153.0.0.0 Safari/537.36"
REFERER = "https://creator.guanghe.taobao.com/page/"
BIZ_CODE = "pc_video_daren_publish"
UGC_SCENE = "pc_newcreator_video"
SDK_VERSION = "0.6.2-beta.2"

DECLARATION_MAP = {
    "内容无需标注": 0, "含AI生成内容": 1, "含虚构演绎内容": 2,
    "内容为转载": 3, "个人观点，仅供参考": 4, "内容含营销信息": 5,
}


def extract_video_frames(video_path: str, count: int = 6):
    """用 ffmpeg 从视频均匀抽取 count 帧，返回 [jpg_bytes, ...]。

    光合的 comprehension/productpic 依赖视频抽帧图（前端上传视频后会自动抽帧并
    上传到 gg_tmp 图片空间），纯 HTTP 复现需本地补做这一步。
    """
    try:
        import imageio_ffmpeg
        ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return []
    try:
        r = subprocess.run([ffmpeg, "-i", video_path], stderr=subprocess.PIPE, stdout=subprocess.DEVNULL, timeout=30)
        m = re.search(rb"Duration:\s*(\d+):(\d+):(\d+\.?\d*)", r.stderr)
        if not m:
            return []
        duration = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
        if duration <= 0:
            return []
        fps = count / duration
        tmpdir = tempfile.mkdtemp(prefix="gh_frames_")
        out_pattern = os.path.join(tmpdir, "frame_%02d.jpg")
        subprocess.run([ffmpeg, "-y", "-i", video_path, "-vf", f"fps={fps:.4f}",
                        "-frames:v", str(count), "-q:v", "3", out_pattern],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=120)
        frames = []
        for i in range(1, count + 1):
            fp = os.path.join(tmpdir, f"frame_{i:02d}.jpg")
            if os.path.exists(fp):
                with open(fp, "rb") as f:
                    frames.append(f.read())
        return frames
    except Exception:
        return []


class MtopError(Exception):
    """mtop 调用失败（token 过期 / sign 错误 / 风控等）。"""


class GuangheHTTP:
    def __init__(self, cookies: dict, token_refresher=None, proxy=None):
        self.cookies = dict(cookies)
        self.token = self.cookies.get("_m_h5_tk", "").split("_")[0]
        if not self.token:
            raise MtopError("cookie 缺少 _m_h5_tk")
        self.session = requests.Session()
        # 关键：禁用环境变量代理（HTTPS_PROXY 等）强制直连。
        # 光合是淘宝国内域名，走代理反而不稳（实测代理转发 h5api 时好时坏导致拉取失败）。
        self.session.trust_env = False
        # 显式代理：账号配置了代理时所有请求只走该代理（trust_env=False 不影响手动 proxies）
        # socks5 -> socks5h：强制远程 DNS 解析（部分代理对 IP 直连返回 TTL expired）
        if proxy:
            p = proxy.strip()
            if p.startswith("socks5://"):
                p = "socks5h://" + p[len("socks5://"):]
            self.proxy = p
            self.session.proxies = {"http": p, "https": p}
        else:
            self.proxy = None
        # token 失效时的刷新回调（返回新 cookies dict）；None 则不自动刷新
        self.token_refresher = token_refresher

    def _sign(self, t, data_str):
        return hashlib.md5(f"{self.token}&{t}&{APPKEY}&{data_str}".encode()).hexdigest()

    def call(self, api, data, v="1.0", method="GET", _retry=True):
        try:
            return self._call(api, data, v, method, _retry)
        except (requests.exceptions.SSLError, requests.exceptions.ConnectionError):
            if _retry:
                # 连接池坏连接（服务端断开空闲连接后复用报 SSL EOF）：重建 session 重试一次
                try:
                    self.session.close()
                except Exception:
                    pass
                self.session = requests.Session()
                self.session.trust_env = False
                if self.proxy:
                    self.session.proxies = {"http": self.proxy, "https": self.proxy}
                return self.call(api, data, v, method, _retry=False)
            raise

    def _call(self, api, data, v="1.0", method="GET", _retry=True):
        t = str(int(time.time() * 1000))
        data_str = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
        sg = self._sign(t, data_str)
        url = GATEWAY.format(api=api, v=v)
        params = {"jsv": "2.6.1", "appKey": APPKEY, "t": t, "sign": sg, "v": v,
                  "api": api, "dataType": "jsonp", "type": "originaljson"}
        headers = {"User-Agent": UA, "Referer": REFERER, "Accept": "*/*",
                   "Cookie": "; ".join(f"{k}={v}" for k, v in self.cookies.items())}
        if method == "GET":
            params["data"] = data_str
            params["dataType"] = "originaljsonp"
            params["type"] = "originaljsonp"
            resp = self.session.get(url, params=params, headers=headers, timeout=60)
        else:
            params["data"] = data_str
            resp = self.session.post(url, data=params,
                                     headers={**headers, "Content-Type": "application/x-www-form-urlencoded"},
                                     timeout=60)
        text = resp.text.strip()
        m = re.match(r"^[A-Za-z_$][\w$]*\((.*)\)\s*$", text, re.DOTALL)
        if m:
            text = m.group(1)
        try:
            j = json.loads(text)
        except json.JSONDecodeError as e:
            raise MtopError(f"响应非 JSON: {text[:200]}") from e
        ret = j.get("ret", [])
        if ret and isinstance(ret, list):
            s = ret[0]
            if s.startswith("FAIL_SYS_TOKEN"):
                # token 过期：尝试自动刷新后重试一次
                if _retry and self.token_refresher:
                    try:
                        new_cookies = self.token_refresher()
                        if new_cookies and new_cookies.get("_m_h5_tk"):
                            self.cookies = dict(new_cookies)
                            self.token = self.cookies.get("_m_h5_tk", "").split("_")[0]
                            return self.call(api, data, v, method, _retry=False)
                    except Exception:
                        pass
                raise MtopError(f"token 失效: {s}")
            if s.startswith("FAIL_SYS_ILLEGAL_ACCESS"):
                raise MtopError(f"sign 非法: {s}")
        return j

    # ---------------- 账号 ----------------
    def whoami(self):
        """探测账号登录态与基本信息。"""
        j = self.call("mtop.user.getUserSimple", {})
        return j.get("data", {})

    # ---------------- 作品 ----------------
    def list_works(self, page_size=200, page_no=1):
        """作品列表（分页）。返回 {items, total, has_next, page_count}。单页上限约 200。"""
        j = self.call("mtop.taobao.gcm.content.admin.list", {
            "condition": json.dumps({"showContentDiagnosis": True}, separators=(",", ":")),
            "source": "guanghe", "mode": 0, "scene": "workList", "agentType": "",
            "pageSize": page_size, "pageNo": page_no,
            "channelLocation": "creator_contentmanagement",
            "promoteSourceUrl": "https://creator.guanghe.taobao.com/page/workspace/tb",
            "version": 2})
        model = j.get("data", {}).get("model", {})
        return {"items": model.get("data", []) or [],
                "total": model.get("totalCount", 0),
                "has_next": bool(model.get("hasNext", False)),
                "page_count": model.get("pageCount", 0)}

    def list_works_all(self, max_pages=50):
        """拉取全部作品（自动翻页，单页 200）。"""
        all_items = []
        page = 1
        while page <= max_pages:
            r = self.list_works(page_size=200, page_no=page)
            all_items.extend(r["items"])
            if not r["has_next"]:
                break
            page += 1
        return all_items

    def delete_work(self, work_id):
        j = self.call("mtop.taobao.gcm.content.admin.delete",
                      {"id": int(work_id), "source": "guanghe", "mode": 0, "agentType": ""})
        return j.get("ret")

    def top_work(self, work_id, top=True):
        """置顶/取消置顶作品。"""
        j = self.call("mtop.taobao.gcm.content.admin.top",
                      {"id": int(work_id), "top": top, "source": "guanghe", "mode": 0, "agentType": ""})
        return j.get("ret")

    def get_edit_url(self, work_id):
        """获取作品编辑页 URL（发布页 + contentId）。"""
        j = self.call("mtop.taobao.media.guang.pcPublish.publishUrl",
                      {"request": json.dumps({"ugc_scene": "pc_newcreator_video", "content_type": "video"},
                                             separators=(",", ":"))})
        pub_url = j.get("data", {}).get("publishUrl", "")
        if not pub_url:
            raise MtopError("获取编辑入口失败")
        edit_pub = pub_url + ("&" if "?" in pub_url else "?") + "contentId=" + str(work_id)
        return ("https://creator.guanghe.taobao.com/page/pubNew/video?pub_url="
                + urllib.parse.quote(edit_pub, safe="") + "&mode=0&pub_scene=")

    def set_privacy(self, work_id, private=True):
        """设置作品私密/公开。privacyLevel: 4=私密, 1=公开。"""
        level = 4 if private else 1
        j = self.call("mtop.taobao.gcm.content.admin.privacy",
                      {"id": int(work_id), "privacyLevel": level, "source": "guanghe", "mode": 0, "agentType": ""})
        return j.get("ret")

    # ---------------- 佣金 ----------------
    def commission(self, page_size=20, cursor="1"):
        j = self.call("mtop.taobao.guangguangsellermanager.highcommission.item.list",
                      {"cursor": cursor, "pageSize": page_size})
        return j.get("data", {})

    # ---------------- 数据看板 ----------------
    def dashboard_indicators(self, days=7):
        """账号核心指标（数据看板）。"""
        j = self.call("mtop.taobao.guangguang.creator.gateway.oneservice.kind.list", {
            "source": "guanghe", "scene": "darenDashboardKeyIndicators2",
            "conditions": json.dumps({"content_type": "all", "biz_line": "all",
                                      "start_date": "${statDate_%d}" % days,
                                      "end_date": "${statDate_1}",
                                      "retainLatestDs": True, "retainChosenDs": True},
                                     separators=(",", ":")),
            "timeRangeTypeStr": str(days)})
        return j.get("data", {})

    # ---------------- 图片上传（封面） ----------------
    def upload_image(self, file_bytes: bytes, filename: str, appkey: str = "daren") -> str:
        """上传图片到光合图片空间（stream-upload），返回 img.alicdn.com URL。"""
        url = (f"https://stream-upload.taobao.com/api/upload.api?appkey={appkey}"
               f"&folderId=&_input_charset=utf-8&useGtrSessionFilter=false")
        headers = {"User-Agent": UA, "Referer": "https://huodong.taobao.com/",
                   "Origin": "https://huodong.taobao.com",
                   "Cookie": "; ".join(f"{k}={v}" for k, v in self.cookies.items())}
        name = os.path.splitext(filename)[0]
        r = self.session.post(url, data={"name": name},
                              files={"file": (filename, file_bytes, "image/jpeg")},
                              headers=headers, timeout=60)
        j = r.json()
        if not j.get("success"):
            raise MtopError(f"图片上传失败: {str(j)[:200]}")
        return j["object"]["url"]

    # ---------------- 推荐标签 / 关联商品 ----------------
    def comprehension(self, file_id, title="", images=None, publish_session="", keys=("hashtag",),
                      method="POST", select_items=None, ugc_scene=None):
        """内容理解：recommendKeys=hashtag 返回 recommendHashtags（推荐话题标签）；
        item 返回 taskId（关联商品，需 GET 方法）。编辑场景 ugc_scene 用 'GG'。"""
        params = {"fileId": file_id, "ugcScene": ugc_scene or UGC_SCENE, "recommendKeys": list(keys),
                  "title": title, "images": images or []}
        if select_items is not None:
            params["selectItems"] = select_items
        if publish_session:
            params["publishSession"] = publish_session
        j = self.call("mtop.taobao.media.guang.publish.comprehension",
                      {"params": json.dumps(params, ensure_ascii=False, separators=(",", ":"))}, method=method)
        return j.get("data", {})

    def list_items(self, task_id, publish_session, keyword="", cursor="", page_size=20, retries=3):
        """关联商品列表（需 comprehension(keys=['item']) 的 taskId）。商品推荐是异步任务，空结果会重试。"""
        d = {}
        for attempt in range(retries):
            j = self.call("mtop.taobao.media.guang.item.listItems", {
                "taskId": task_id, "cursor": cursor, "keyword": keyword, "pageSize": page_size,
                "expoContents": "", "sortType": "", "source": "recommend",
                "ugc_scene": UGC_SCENE, "publishVersion": "1", "site": "guangguang",
                "publishSession": publish_session})
            d = j.get("data", {})
            items = d.get("data", []) or []
            if items or attempt == retries - 1:
                break
            time.sleep(3)
        return {"items": d.get("data", []) or [], "cursor": d.get("cursor", "")}

    def search_items(self, publish_session, keyword="", cursor="", page_size=15):
        """「平台优选」商品库搜索（官方搜索即走此接口）：
        listItems + source=coreitem + POST + 双 ugcScene 字段 + pageType/filterValue。
        支持 itemId 精确搜与标题关键词搜。"""
        j = self.call("mtop.taobao.media.guang.item.listItems", {
            "source": "coreitem", "cursor": cursor, "keyword": keyword, "pageSize": page_size,
            "expoContents": "", "sortType": "", "sortValue": "",
            "ugc_scene": UGC_SCENE, "ugcScene": UGC_SCENE, "pageType": "video",
            "site": "guangguang", "publishVersion": "1", "publishSession": publish_session,
            "filterValue": "-1", "secondLevelFilterValue": "-1"}, method="POST")
        d = j.get("data", {})
        return {"items": d.get("data", []) or [], "cursor": d.get("cursor", "")}

    # ---------------- 参与话题活动（官方征稿话题） ----------------
    def topic_list(self, publish_session, tab_id="1", cursor="1"):
        """官方征稿话题列表（话题选择器）。返回 {tabs, topics, cursor, has_next}。"""
        params = {"ugcScene": UGC_SCENE, "publishVersion": "1", "site": "guangguang",
                  "publishSession": publish_session, "tabId": tab_id, "cursor": cursor,
                  "dailyTrending": True}
        j = self.call("mtop.taobao.media.guang.topic.topicSelector",
                      {"params": json.dumps(params, ensure_ascii=False, separators=(",", ":"))})
        d = j.get("data", {})
        return {"tabs": d.get("tabs", []) or [], "topics": d.get("topics", []) or [],
                "cursor": d.get("cursor", ""), "has_next": bool(d.get("hasNext", False))}

    def topic_search(self, publish_session, keyword="", cursor="1"):
        """官方话题搜索。返回 {topics, cursor, has_next}。"""
        params = {"ugcScene": UGC_SCENE, "publishVersion": "1", "site": "guangguang",
                  "publishSession": publish_session, "keyword": keyword, "cursor": cursor}
        j = self.call("mtop.taobao.media.guang.topic.topicSearch",
                      {"params": json.dumps(params, ensure_ascii=False, separators=(",", ":"))})
        d = j.get("data", {})
        return {"topics": d.get("topics", []) or [], "cursor": d.get("cursor", ""),
                "has_next": bool(d.get("hasNext", False))}

    # ---------------- 发布（两阶段） ----------------
    def publish_prepare(self, video_path, skip_covers=False):
        """阶段一：上传视频并解析，返回 fileId/会话/配置/封面候选/推荐标签/商品taskId。不提交。

        skip_covers=True 时跳过智能封面生成（例如小红书导入已有封面），节省时间。
        """
        j = self.call("mtop.taobao.media.guang.session.generate",
                      {"request": json.dumps({"ugcScene": UGC_SCENE}, separators=(",", ":"))}, method="POST")
        pub_session = j["data"]["publishSession"]
        j = self.call("mtop.taobao.media.guang.pc.config",
                      {"contentType": "video", "ugcScene": UGC_SCENE, "contentId": None,
                       "publishSession": pub_session, "dataSession": str(uuid.uuid1())})
        cfg = j["data"]
        biz_code = cfg.get("bizCode", BIZ_CODE)
        publish_params = cfg.get("publishParams", {})
        ab_dict = cfg.get("abParams", {})
        ab_params = ([{k: v for k, v in it.items() if k != "dataTracks"} for it in ab_dict.values()]
                     if isinstance(ab_dict, dict) else ab_dict)
        fsize = os.path.getsize(video_path)
        j = self.call("mtop.video.upload.init.taobao",
                      {"bizCode": biz_code, "fileSize": fsize, "mimeType": "video/mp4",
                       "localFileName": os.path.basename(video_path), "netSpeed": 1739.0, "sdkVersion": SDK_VERSION})
        up = j["data"]["model"]
        file_id, upload_id, put_url = up["fileId"], up["uploadId"], up["uploadUrlList"][0]["url"]
        with open(video_path, "rb") as f:
            body = f.read()
        r = self.session.put(put_url, data=body, timeout=600)
        if r.status_code not in (200, 201):
            raise MtopError(f"OSS 上传失败: HTTP {r.status_code}")
        file_md5 = hashlib.md5(body).hexdigest().upper()
        part_list = json.dumps([json.dumps({"partNumber": 1, "md5": file_md5})])
        self.call("mtop.video.upload.complete.taobao",
                  {"bizCode": biz_code, "uploadId": upload_id, "partList": part_list,
                   "netSpeed": 729.0, "sdkVersion": SDK_VERSION}, method="POST")
        self.call("mtop.taobao.media.guang.videoFile.getFileMeta",
                  {"ugcScene": UGC_SCENE, "bizCode": biz_code, "fileId": file_id, "publishSession": pub_session})
        # 等视频转码完成（内容理解依赖转码后的抽帧）
        time.sleep(3)
        # 抽帧 + 上传抽帧图（前端上传视频后会自动做这一步，供内容识别）
        images = []
        frame_urls = []
        frame_size = [720, 1280]
        try:
            frames = extract_video_frames(video_path, count=3)
            if frames:
                try:
                    import io as _io
                    from PIL import Image as _Image
                    frame_size = list(_Image.open(_io.BytesIO(frames[0])).size)
                except Exception:
                    pass
            for i, fb in enumerate(frames):
                url = self.upload_image(fb, f"frame_{i}", appkey="gg_tmp")
                frame_urls.append(url)
            images = [{"imageUrl": u} for u in frame_urls]
        except Exception:
            pass
        covers = []
        if not skip_covers:
            for _ in range(3):
                j = self.call("mtop.taobao.media.guang.publish.intelligent.productpic",
                              {"itemId": "", "picUrls": "", "templateSize": "", "fileId": file_id,
                               "title": "", "summary": ""}, method="POST")
                req_id = j.get("data", {}).get("reqId", "")
                if req_id:
                    # 轮询 result（智能封面异步生成）：先立即查一次，再短间隔重试
                    for _ in range(5):
                        j = self.call("mtop.taobao.media.guang.publish.intelligent.productpic.result",
                                      {"reqId": req_id})
                        covers = [{"url": c["url"], "width": int(c["width"]), "height": int(c["height"])}
                                  for c in (j.get("data", {}).get("data", []) or [])]
                        if covers:
                            break
                        time.sleep(1.5)
                    if covers:
                        break
                time.sleep(1)
        tags = []
        try:
            d = self.comprehension(file_id, keys=("hashtag",), images=images,
                                   publish_session=pub_session)
            tags = d.get("recommendHashtags", []) or []
        except MtopError:
            pass
        item_task_id = ""
        try:
            d = self.comprehension(file_id, keys=("item",), images=images,
                                   publish_session=pub_session, method="GET")
            item_task_id = d.get("taskId", "")
            # 商品推荐是异步任务，list_items 内部已有空结果重试，这里无需额外等待
        except MtopError:
            pass
        return {"file_id": file_id, "publish_session": pub_session, "biz_code": biz_code,
                "publish_params": publish_params, "ab_params": ab_params,
                "covers": covers, "tags": tags, "item_task_id": item_task_id,
                "frame_urls": frame_urls, "frame_size": frame_size}

    def publish_submit(self, title, desc, declaration, prepare, cover_url=None,
                       cover_width=720, cover_height=1280, topics=None, items=None):
        """阶段二：基于 prepare 结果 + 用户选择（封面/标签/商品）组装提交。"""
        from_type = DECLARATION_MAP.get(declaration, 0)

        def _s(v):
            if isinstance(v, bool):
                return "true" if v else "false"
            if isinstance(v, (int, float)):
                return str(v)
            return v
        req_id = str(uuid.uuid1())
        publish_extra = {k: _s(v) for k, v in prepare["publish_params"].items()}
        publish_extra["umi_pub_session"] = req_id
        publish_extra["dataSession"] = req_id + "39"
        cover_user = []
        if cover_url:
            cover_user = [{"url": cover_url, "width": cover_width, "height": cover_height,
                           "statInfo": {"source": None, "cover_text": None, "cover_text_content": None}}]
        elif prepare.get("covers"):
            c = prepare["covers"][0]
            cover_user = [{"url": c["url"], "width": c["width"], "height": c["height"],
                           "statInfo": {"source": None, "cover_text": None, "cover_text_content": None}}]
        elif prepare.get("frame_urls"):
            # 无智能封面且未选封面：用视频抽帧第一帧作为默认封面
            fw, fh = prepare.get("frame_size") or [720, 1280]
            cover_user = [{"url": prepare["frame_urls"][0], "width": int(fw), "height": int(fh),
                           "statInfo": {"source": None, "cover_text": None, "cover_text_content": None}}]
        req_body = {
            "id": "", "bizCode": prepare["biz_code"], "shortTitle": title, "title": desc,
            "titleRaw": desc, "requestId": req_id, "contentType": "video",
            "ugcScene": UGC_SCENE, "shareResult": "", "topics": (topics or [])[:5], "items": items or [],
            "video": {"fileId": prepare["file_id"], "interactiveId": "", "statInfo": {"audio": []}},
            "coverUser": cover_user, "customModuleFrontData": {}, "abParams": prepare["ab_params"],
            "pois": [], "collections": [], "titleElements": None, "publishExtra": publish_extra,
            "contentSource": {"fromType": from_type}, "publishSession": prepare["publish_session"],
            "publishToken": uuid.uuid4().hex,
        }
        j = self.call("mtop.taobao.media.guang.pcPublish.publish",
                      {"request": json.dumps(req_body, ensure_ascii=False, separators=(",", ":"))}, method="POST")
        used_cover = cover_user[0]["url"] if cover_user else ""
        return {"ret": j.get("ret"), "data": j.get("data", {}), "cover_url": used_cover}

    def publish(self, video_path, title, desc="", declaration="内容无需标注", dry_run=False):
        """一步式发布（兼容旧接口）：prepare + submit。"""
        prepare = self.publish_prepare(video_path)
        if dry_run:
            return {"dry_run": True,
                    "prepare": {k: v for k, v in prepare.items()
                                if k in ("file_id", "publish_session", "covers", "tags")}}
        return self.publish_submit(title, desc, declaration, prepare)

    # ---------------- 编辑（站内改稿） ----------------
    def edit_prepare(self, work_id):
        """编辑模式：session + pc.config + getContent，返回原作品完整数据用于回填。

        编辑场景与新建不同：ugcScene/bizCode 都是 'GG' / 'wireless_video_ugc_publish'，
        视频已存在（getContent 返回 fileId），无需重新上传。
        """
        wid = str(work_id)
        j = self.call("mtop.taobao.media.guang.session.generate",
                      {"request": json.dumps({"ugcScene": "GG"}, separators=(",", ":"))}, method="POST")
        pub_session = j["data"]["publishSession"]
        j = self.call("mtop.taobao.media.guang.pc.config",
                      {"contentType": "video", "ugcScene": "GG", "contentId": wid,
                       "publishSession": pub_session, "dataSession": str(uuid.uuid1())})
        cfg = j["data"]
        ab_dict = cfg.get("abParams", {})
        ab_params = ([{k: v for k, v in it.items() if k != "dataTracks"} for it in ab_dict.values()]
                     if isinstance(ab_dict, dict) else ab_dict)
        j = self.call("mtop.taobao.media.guang.pcPublish.getContent",
                      {"contentId": wid, "publishSession": pub_session})
        content = j.get("data", {})
        file_id = (content.get("video") or {}).get("fileId", "")
        # 智能封面候选（基于原视频 fileId，编辑场景也能重新生成）
        covers = []
        if file_id:
            for _ in range(3):
                j = self.call("mtop.taobao.media.guang.publish.intelligent.productpic",
                              {"itemId": "", "picUrls": "", "templateSize": "", "fileId": file_id,
                               "title": "", "summary": ""}, method="POST")
                req_id = j.get("data", {}).get("reqId", "")
                if req_id:
                    time.sleep(2)
                    j = self.call("mtop.taobao.media.guang.publish.intelligent.productpic.result",
                                  {"reqId": req_id})
                    covers = [{"url": c["url"], "width": int(c["width"]), "height": int(c["height"])}
                              for c in (j.get("data", {}).get("data", []) or [])]
                    break
                time.sleep(1)
        # 推荐内容标签（GG 场景）
        tags = []
        try:
            d = self.comprehension(file_id, keys=("hashtag",), publish_session=pub_session, ugc_scene="GG")
            tags = d.get("recommendHashtags", []) or []
        except MtopError:
            pass
        # 关联商品 taskId（GG 场景，需 GET）
        item_task_id = ""
        try:
            d = self.comprehension(file_id, keys=("item",), publish_session=pub_session,
                                   method="GET", ugc_scene="GG")
            item_task_id = d.get("taskId", "")
            if item_task_id:
                time.sleep(3)
        except MtopError:
            pass
        return {"publish_session": pub_session,
                "biz_code": content.get("bizCode", "wireless_video_ugc_publish"),
                "ab_params": ab_params, "content": content,
                "file_id": file_id, "covers": covers, "tags": tags, "item_task_id": item_task_id}

    def edit_submit(self, prep, title=None, desc=None, cover_url=None, cover_width=None,
                    cover_height=None, items=None, from_type=None, topics=None):
        """编辑提交（pcPublish.edit）。未传字段原样沿用原作品值。"""
        c = prep["content"]

        def _as_int(x, default=0):
            try:
                return int(x)
            except (TypeError, ValueError):
                return default
        cover_user = c.get("coverUser", [])
        if cover_url:
            cover_user = [{
                "url": cover_url,
                "width": str(cover_width or c.get("coverUser", [{}])[0].get("width") or 720),
                "height": str(cover_height or c.get("coverUser", [{}])[0].get("height") or 1280),
                "id": "1",
                "statInfo": {"is_hq_record": "false", "camera_rotation": "0",
                             "pub_session": prep["publish_session"], "cover_text": "-1",
                             "source": "user_frame"},
            }]
        req_id = str(uuid.uuid1())
        req_body = {
            "id": c.get("id"),
            "bizCode": prep["biz_code"],
            "shortTitle": title if title is not None else c.get("shortTitle", ""),
            "title": desc if desc is not None else c.get("title", ""),
            "titleRaw": c.get("titleRaw", ""),
            "requestId": req_id,
            "contentType": "video",
            "ugcScene": "GG",
            "shareResult": c.get("shareResult", []),
            "topics": (topics if topics is not None else c.get("topics", []))[:5],
            "items": items if items is not None else c.get("items", []),
            "video": c.get("video", {}),
            "coverUser": cover_user,
            "customModuleFrontData": {},
            "abParams": prep["ab_params"],
            "pois": c.get("pois", []),
            "collections": c.get("collections", []),
            "titleElements": c.get("titleElements"),
            "publishExtra": c.get("publishExtra", {}),
            "contentSource": {"fromType": from_type if from_type is not None
                              else c.get("contentSource", {}).get("fromType", 0)},
            "publishSession": prep["publish_session"],
            "publishToken": uuid.uuid4().hex,
        }
        j = self.call("mtop.taobao.media.guang.pcPublish.edit",
                      {"request": json.dumps(req_body, ensure_ascii=False, separators=(",", ":"))}, method="POST")
        return {"ret": j.get("ret"), "data": j.get("data", {})}
