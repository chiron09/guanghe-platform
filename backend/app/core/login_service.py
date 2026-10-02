# -*- coding: utf-8 -*-
"""光合账号登录服务：扫码 / 密码 / 短信 三种方式，Playwright 独立线程。

每个登录会话 = 独立线程 + 独立浏览器上下文，通过线程安全状态对外暴露进度。
登录页 = login.taobao.com（光合跳转过去，主 frame），登录成功后跳回 creator.guanghe.taobao.com。

登录页关键 DOM（2026-09 探针实测）：
- tab: a.password-login-tab-item / a.sms-login-tab-item
- 协议: input#fm-agreement-checkbox（必须勾选，否则提交报错）
- 密码 tab: #fm-login-id(账号) #fm-login-password #fm-login-checkcode(风控时出现)
- 短信 tab: #fm-sms-login-id(手机号) #fm-smscode a.send-btn-link(获取验证码)
- 图片验证码图: img.fm-login-checkcode-img（默认隐藏，风控时可见，点击可刷新）
- 错误提示: div#login-error / .login-error-msg
- 短信发送成功: .sms-send-success-tip（"验证码已发送"）
"""
import base64
import queue
import threading
import time
import uuid

HOME_URL = "https://creator.guanghe.taobao.com/page/"
T = 8000  # locator 默认超时


class LoginSession:
    """一个登录会话（独立线程）。"""

    def __init__(self, sid: str, mode: str):
        self.sid = sid
        self.mode = mode          # scan / password / sms
        self.state = "starting"   # starting / ready / need_checkcode / submitted / success / error
        self.error = ""
        self.cookies = None       # 成功后：{name: value}
        self.screenshot = None    # base64：二维码 / 图片验证码 / 整页（滑块等）
        self.shot_type = ""       # qrcode / checkcode / page / ""
        self.taobao_id = ""
        self._lock = threading.Lock()
        self._cmd = queue.Queue()
        self._t0 = time.time()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    # ---------- 对外（线程安全） ----------
    def get_snapshot(self) -> dict:
        with self._lock:
            return {"sid": self.sid, "mode": self.mode, "state": self.state,
                    "error": self.error, "screenshot": self.screenshot,
                    "shot_type": self.shot_type,
                    "cookies": self.cookies, "taobao_id": self.taobao_id}

    def submit(self, **kw):
        """发送表单动作（异步执行，立即返回）；执行结果通过 status 轮询获取。"""
        self._cmd.put(("submit", kw, None))
        time.sleep(0.3)
        return self.get_snapshot()

    def refresh_code(self):
        """点击页面验证码图刷新，并重新截图（异步）。"""
        self._cmd.put(("refresh_code", {}, None))

    def close(self):
        self._cmd.put(("close", {}, None))

    # ---------- 内部 ----------
    def _set(self, **kw):
        with self._lock:
            for k, v in kw.items():
                setattr(self, k, v)

    @staticmethod
    def _shot(locator) -> str:
        try:
            return base64.b64encode(locator.screenshot(timeout=5000)).decode()
        except Exception:
            return ""

    def _run(self):
        try:
            from playwright.sync_api import sync_playwright
            with sync_playwright() as pw:
                browser = pw.chromium.launch(
                    headless=True,
                    args=["--disable-blink-features=AutomationControlled", "--no-first-run",
                          "--no-default-browser-check"])
                ctx = browser.new_context(viewport={"width": 1280, "height": 900})
                page = ctx.new_page()
                page.goto(HOME_URL, wait_until="domcontentloaded", timeout=60000)
                page.wait_for_timeout(6000)
                self._set(state="ready")
                # scan：截二维码；password/sms：切到对应 tab 并截整页（用户可见初始状态）
                if self.mode == "scan":
                    self._refresh_screenshot(page)
                elif self.mode in ("password", "sms"):
                    self._prepare_tab(page, self.mode)

                while True:
                    with self._lock:
                        if self.state == "error":
                            break
                    try:
                        action, kw, rq = self._cmd.get(timeout=3)
                    except queue.Empty:
                        action, kw, rq = None, {}, None

                    if action == "close":
                        break
                    if action is None:
                        # 先处理登录链路上的确认/弹窗，再判登录态
                        self._confirm_keep_login(page)
                        if self._check_logged_in(page):
                            self._on_success(page, ctx)
                            break
                        continue
                    print(f"[login:{self.mode}] 收到命令 {action}", flush=True)
                    if action == "submit":
                        self._do_submit(page, kw)
                        if rq:
                            rq.put(self.get_snapshot())
                            print(f"[login:{self.mode}] submit 完成 state={self.state}", flush=True)
                    elif action == "refresh_code":
                        self._do_refresh_code(page)
                        if rq:
                            rq.put(self.get_snapshot())
                    elif action == "refresh":
                        page.reload(wait_until="domcontentloaded")
                        page.wait_for_timeout(4000)
                        self._refresh_screenshot(page)
                        if rq:
                            rq.put(self.get_snapshot())
                browser.close()
        except Exception as e:
            self._set(state="error", error=str(e)[:300])

    def _check_logged_in(self, page) -> bool:
        try:
            if "creator.guanghe.taobao.com" in page.url and "login" not in page.url:
                return True
        except Exception:
            pass
        return False

    def _on_success(self, page, ctx):
        # 等 _m_h5_tk 生成
        for _ in range(6):
            page.wait_for_timeout(2000)
            cookies = ctx.cookies()
            if any(c["name"] == "_m_h5_tk" for c in cookies):
                break
        merged = {c["name"]: c["value"] for c in cookies if c.get("name") and c.get("value")}
        # 当前登录账号以 getUserSimple 接口为准（lgc/dnk 可能残留其他账号昵称）
        from .sdk import decode_taobao_nick
        from .guanghe import GuangheHTTP
        taobao_id = ""
        try:
            info = GuangheHTTP(merged).whoami()
            if isinstance(info, dict):
                taobao_id = decode_taobao_nick(info.get("nick") or info.get("displayNick") or "")
        except Exception:
            pass
        if not taobao_id:
            taobao_id = decode_taobao_nick(merged.get("lgc") or merged.get("dnk") or "")
        self._set(state="success", cookies=merged, taobao_id=taobao_id)

    def _prepare_tab(self, page, mode):
        """password/sms 会话就绪后切到对应 tab、勾协议、截整页图。"""
        try:
            page.wait_for_load_state("domcontentloaded", timeout=5000)
        except Exception:
            pass
        try:
            if mode == "password":
                page.locator("a.password-login-tab-item").click(timeout=T)
            else:
                page.locator("a.sms-login-tab-item").click(timeout=T)
            page.wait_for_timeout(800)
        except Exception:
            pass
        self._agree_protocol(page)
        try:
            shot = base64.b64encode(page.screenshot(timeout=5000)).decode()
        except Exception:
            shot = ""
        self._set(screenshot=shot, shot_type="page")

    def _agree_protocol(self, page):
        """勾选用户协议 checkbox（幂等）。"""
        try:
            cb = page.locator("input#fm-agreement-checkbox")
            if cb.count() and cb.is_visible() and not cb.is_checked():
                cb.check(timeout=3000)
        except Exception:
            pass

    def _dismiss_popups(self, page):
        """best-effort 关闭营销/引导弹窗（如"扫码登录更便捷"），全部静默不抛错。
        只点关闭类控件（X / 取消 / 暂不 / 跳过），绝不点确认/去扫码类主按钮。"""
        candidates = [
            "[class*=dialog] [class*=close], [class*=Dialog] [class*=close]",
            "[class*=modal] [class*=close], [class*=Modal] [class*=close]",
            "[class*=popup] [class*=close], [class*=pop] [class*=close]",
            "[class*=dialog-close], [class*=modal-close], [class*=pop-close], [class*=close-btn]",
            "button:has-text('取消')", "a:has-text('取消')",
            "button:has-text('暂不')", "a:has-text('暂不')",
            "button:has-text('跳过')", "a:has-text('跳过')",
            "button:has-text('下次再说')", "a:has-text('下次再说')",
            "button:has-text('关闭')", "a:has-text('关闭')",
        ]
        closed = 0
        for sel in candidates:
            try:
                els = page.locator(sel)
                for i in range(min(els.count(), 5)):
                    el = els.nth(i)
                    try:
                        if el.is_visible():
                            box = el.bounding_box()
                            # 关闭按钮通常是小尺寸控件，防止误点大区块
                            if box and box["width"] <= 120 and box["height"] <= 60:
                                el.click(timeout=2000)
                                page.wait_for_timeout(400)
                                closed += 1
                    except Exception:
                        pass
            except Exception:
                pass
        if closed:
            print(f"[login:{self.mode}] _dismiss_popups 关闭了 {closed} 个弹窗控件", flush=True)
        return closed

    def _confirm_keep_login(self, page):
        """登录成功前淘宝弹"保持登录状态"提示，必须点"知道了"才会继续跳转光合。"""
        btns = ["button:has-text('我知道了')", "a:has-text('我知道了')",
                "button:has-text('知道了')", "a:has-text('知道了')",
                "button:has-text('好的')", "a:has-text('好的')",
                "button:has-text('保持登录')", "a:has-text('保持登录')"]
        for sel in btns:
            try:
                els = page.locator(sel)
                for i in range(min(els.count(), 3)):
                    el = els.nth(i)
                    try:
                        if el.is_visible():
                            el.click(timeout=2000)
                            page.wait_for_timeout(600)
                            print(f"[login:{self.mode}] 已点击确认按钮({sel})", flush=True)
                            return True
                    except Exception:
                        pass
            except Exception:
                pass
        return False

    def _grab_error(self, page) -> str:
        """抓页面错误提示文本（如：账号名或密码不正确 / 请勾选同意…）。"""
        try:
            msg = page.locator("div#login-error .login-error-msg, div#login-error").first
            if msg.count() and msg.is_visible():
                return (msg.inner_text(timeout=2000) or "").strip()[:120]
        except Exception:
            pass
        return ""

    def _grab_sms_tip(self, page) -> str:
        """抓短信发送成功提示。"""
        try:
            tip = page.locator(".sms-send-success-tip").first
            if tip.count() and tip.is_visible():
                return (tip.inner_text(timeout=2000) or "").strip()[:60]
        except Exception:
            pass
        return ""

    def _checkcode_visible(self, page) -> bool:
        try:
            img = page.locator("img.fm-login-checkcode-img")
            return img.count() > 0 and img.is_visible()
        except Exception:
            return False

    def _shot_checkcode(self, page) -> str:
        try:
            img = page.locator("img.fm-login-checkcode-img").first
            if img.count() and img.is_visible():
                return self._shot(img)
        except Exception:
            pass
        return ""

    def _shot_page(self, page) -> str:
        try:
            return base64.b64encode(page.screenshot(timeout=5000)).decode()
        except Exception:
            return ""

    def _refresh_screenshot(self, page):
        """scan：截二维码；password/sms：优先验证码图（风控时出现），否则整页截图。"""
        try:
            page.wait_for_load_state("domcontentloaded", timeout=5000)
        except Exception:
            pass
        shot, stype = "", ""
        if self.mode == "scan":
            try:
                qr = page.locator("div.qrcode-img, canvas").first
                if qr.count():
                    shot = self._shot(qr)
                    stype = "qrcode"
            except Exception:
                pass
        else:
            shot = self._shot_checkcode(page)
            stype = "checkcode" if shot else ""
            if not shot:
                shot = self._shot_page(page)
                stype = "page" if shot else ""
        self._set(screenshot=shot, shot_type=stype)

    def _do_refresh_code(self, page):
        """点击验证码图刷新（淘宝点击图片即换一张），再重新截图。"""
        try:
            img = page.locator("img.fm-login-checkcode-img").first
            if img.count() and img.is_visible():
                img.click(timeout=3000)
                page.wait_for_timeout(1500)
        except Exception as e:
            print(f"[login:{self.mode}] refresh_code err: {str(e)[:100]}", flush=True)
        self._refresh_screenshot(page)

    def _after_submit(self, page, default_err: str):
        """提交后统一检查：登录态 / 错误提示 / 验证码行 / 整页截图。
        绝不在导航期间长时间阻塞：所有查询都带短超时并兜底。"""
        if self._check_logged_in(page):
            return  # 主循环空闲分支会走 _on_success
        err = self._grab_error(page)
        if self._checkcode_visible(page):
            self._set(screenshot=self._shot_checkcode(page), shot_type="checkcode",
                      state="need_checkcode",
                      error=err or "请输入图片验证码后重试")
            return
        self._set(screenshot=self._shot_page(page), shot_type="page", state="submitted",
                  error=err or default_err)

    def _do_submit(self, page, kw):
        """处理密码/短信表单动作。"""
        mode = self.mode
        try:
            print(f"[login:{mode}] _do_submit 开始 kw={list(kw.keys())}", flush=True)
            # 先关掉可能盖住表单的营销/引导弹窗
            self._dismiss_popups(page)
            if mode == "password":
                try:
                    page.locator("a.password-login-tab-item").click(timeout=T)
                    page.wait_for_timeout(800)
                except Exception:
                    pass
                account = kw.get("account", "")
                password = kw.get("password", "")
                checkcode = kw.get("checkcode", "")
                if account:
                    page.locator("#fm-login-id").fill(account, timeout=T)
                if password:
                    page.locator("#fm-login-password").fill(password, timeout=T)
                if checkcode and self._checkcode_visible(page):
                    page.locator("#fm-login-checkcode").fill(checkcode, timeout=T)
                self._agree_protocol(page)
                page.locator("button.fm-submit").click(timeout=T)
                print(f"[login:{mode}] click 登录 OK", flush=True)
                page.wait_for_timeout(4000)
                self._after_submit(page, "登录请求已提交，正在确认结果")

            elif mode == "sms":
                try:
                    page.locator("a.sms-login-tab-item").click(timeout=T)
                    page.wait_for_timeout(800)
                except Exception:
                    pass
                action = kw.get("action", "")
                phone = kw.get("phone", "")
                # 手机号回填：best-effort（send_code 时已填过；被弹窗挡住也不阻塞后续流程）
                if phone:
                    try:
                        page.locator("#fm-sms-login-id").fill(phone, timeout=4000)
                    except Exception:
                        self._dismiss_popups(page)
                        try:
                            page.locator("#fm-sms-login-id").fill(phone, timeout=4000)
                        except Exception:
                            print(f"[login:{mode}] 手机号回填失败（继续后续流程）", flush=True)
                if action == "send_code":
                    checkcode = kw.get("checkcode", "")
                    if checkcode and self._checkcode_visible(page):
                        page.locator("#fm-login-checkcode").fill(checkcode, timeout=T)
                    self._agree_protocol(page)
                    page.locator("a.send-btn-link").click(timeout=T)
                    print(f"[login:{mode}] click 获取验证码 OK", flush=True)
                    page.wait_for_timeout(4000)
                    tip = self._grab_sms_tip(page)
                    err = self._grab_error(page)
                    if self._checkcode_visible(page):
                        # 要求先输图片验证码
                        self._set(screenshot=self._shot_checkcode(page), shot_type="checkcode",
                                  state="need_checkcode",
                                  error=err or "请先输入图片验证码，再点「获取验证码」")
                    elif tip:
                        # 发送成功：立即关掉随后弹出的营销弹窗（如"扫码登录更便捷"），
                        # 否则它盖住表单导致后续填验证码/登录超时
                        self._dismiss_popups(page)
                        cc = self._shot_checkcode(page)
                        self._set(screenshot=cc or None, shot_type="checkcode" if cc else "",
                                  state="need_checkcode",
                                  error=f"{tip}，请输入收到的短信验证码")
                    else:
                        self._set(screenshot=self._shot_page(page), shot_type="page",
                                  state="submitted",
                                  error=err or "验证码请求已发出，如未收到请检查手机号或稍后重试")
                elif action == "login":
                    sms_code = kw.get("sms_code", "")
                    checkcode = kw.get("checkcode", "")
                    page.locator("#fm-smscode").fill(sms_code, timeout=T)
                    if checkcode and self._checkcode_visible(page):
                        page.locator("#fm-login-checkcode").fill(checkcode, timeout=T)
                    self._agree_protocol(page)
                    page.locator("button.fm-submit").click(timeout=T)
                    page.wait_for_timeout(4000)
                    self._after_submit(page, "登录请求已提交，正在确认结果")
        except Exception as e:
            msg = str(e)[:300]
            if "Timeout" in msg or "waiting for" in msg:
                # 页面被弹窗/风控层挡住导致控件不可交互：自动关弹窗 + 截图，允许重试
                closed = self._dismiss_popups(page)
                self._set(screenshot=self._shot_page(page), shot_type="page", state="submitted",
                          error=("页面出现弹窗已自动关闭，请重试；若仍失败建议改用扫码登录"
                                 if closed else
                                 "页面控件被遮挡（可能是风控/弹窗），请重试或改用扫码登录"))
            else:
                self._set(state="error", error=msg)


class LoginService:
    """登录会话管理器（单例）。"""

    def __init__(self):
        self._sessions = {}
        self._lock = threading.Lock()

    def start(self, mode: str) -> dict:
        sid = uuid.uuid4().hex[:16]
        s = LoginSession(sid, mode)
        with self._lock:
            self._sessions[sid] = s
            self._gc()
        return s.get_snapshot()

    def get(self, sid: str) -> dict:
        with self._lock:
            s = self._sessions.get(sid)
        if not s:
            return {"state": "error", "error": "会话不存在或已过期"}
        return s.get_snapshot()

    def submit(self, sid: str, **kw) -> dict:
        with self._lock:
            s = self._sessions.get(sid)
        if not s:
            return {"state": "error", "error": "会话不存在或已过期"}
        s.submit(**kw)
        return s.get_snapshot()

    def refresh_code(self, sid: str) -> dict:
        with self._lock:
            s = self._sessions.get(sid)
        if not s:
            return {"state": "error", "error": "会话不存在或已过期"}
        s.refresh_code()
        time.sleep(0.5)
        return s.get_snapshot()

    def refresh(self, sid: str) -> dict:
        """刷新登录页（重新加载并截图）。"""
        with self._lock:
            s = self._sessions.get(sid)
        if not s:
            return {"state": "error", "error": "会话不存在或已过期"}
        s._cmd.put(("refresh", {}, None))
        time.sleep(0.3)
        return s.get_snapshot()

    def close(self, sid: str):
        with self._lock:
            s = self._sessions.pop(sid, None)
        if s:
            s.close()

    def _gc(self):
        """清理超时（20 分钟）会话并关闭其浏览器。"""
        now = time.time()
        stale = [sid for sid, s in self._sessions.items()
                 if now - getattr(s, "_t0", now) > 1200 or s.get_snapshot()["state"] in ("success", "error")]
        for sid in stale:
            s = self._sessions.pop(sid, None)
            if s:
                s.close()


service = LoginService()
