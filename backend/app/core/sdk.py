# -*- coding: utf-8 -*-
"""光合 SDK 适配层：账号 cookie 提取与健康检查。

本机场景下可用 Playwright 从 browser_profile 提取登录态 cookie；
也支持直接解析用户粘贴的 cookie 字符串。
"""
import json
import re
import urllib.parse

from .guanghe import GuangheHTTP, MtopError

# 淘宝 cookie 昵称的 \uXXXX 转义（URL 编码后形如 %5Cu732A...）
_NICK_UESCAPE_RE = re.compile(r"\\u([0-9a-fA-F]{4})")


def decode_taobao_nick(v: str) -> str:
    """解码淘宝 cookie 里的中文昵称（lgc/dnk/tracknick）。

    原始值形如 %5Cu732A%5Cu9E4F...（URL 编码的 \\uXXXX JSON 转义），
    解码两步还原为中文；已是明文则原样返回（幂等）。
    """
    if not v:
        return v
    s = v
    if "%" in s:
        try:
            s = urllib.parse.unquote(s)
        except Exception:
            pass
    if "\\u" in s:
        try:
            s = _NICK_UESCAPE_RE.sub(lambda m: chr(int(m.group(1), 16)), s)
        except Exception:
            pass
    return s


def parse_proxy(proxy_str: str):
    """解析代理字符串为 requests 的 proxies dict。空返回 None。

    支持：http://host:port、https://host:port、socks5://host:port，
    可带认证 http://user:pass@host:port；无 scheme 时默认 http://。
    socks5 会自动转成 socks5h（远程 DNS 解析），避免代理端对 IP 直连返回 TTL expired。
    """
    if not proxy_str:
        return None
    s = proxy_str.strip()
    if not s:
        return None
    if "://" not in s:
        s = "http://" + s
    # socks5 -> socks5h：强制远程 DNS 解析（部分代理要求域名 CONNECT）
    if s.startswith("socks5://"):
        s = "socks5h://" + s[len("socks5://"):]
    return {"http": s, "https": s}


def parse_proxy_for_playwright(proxy_str: str):
    """解析代理字符串为 Playwright 的 proxy 配置。空返回 None。"""
    if not proxy_str:
        return None
    s = proxy_str.strip()
    if not s:
        return None
    if "://" not in s:
        s = "http://" + s
    try:
        u = urllib.parse.urlparse(s)
        if not u.hostname:
            return None
        conf = {"server": f"{u.scheme}://{u.hostname}:{u.port or 80}"}
        if u.username:
            conf["username"] = urllib.parse.unquote(u.username)
            conf["password"] = urllib.parse.unquote(u.password or "")
        return conf
    except Exception:
        return None


def extract_cookies_from_profile(profile_dir: str, headless: bool = False, proxy=None) -> dict:
    """用 Playwright 从本机 Chrome 的 browser_profile 提取光合登录态 cookie。"""
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            user_data_dir=profile_dir, headless=headless, viewport=None,
            proxy=parse_proxy_for_playwright(proxy),
            args=["--disable-blink-features=AutomationControlled", "--no-first-run",
                  "--no-default-browser-check"],
            ignore_default_args=["--enable-automation"])
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto("https://creator.guanghe.taobao.com/page/", wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(6000)
        if any(k in page.url for k in ("login", "punish", "captcha")):
            ctx.close()
            raise MtopError("browser_profile 登录态失效，需先扫码登录")
        cookies = ctx.cookies()
        merged = {c["name"]: c["value"] for c in cookies if c.get("name") and c.get("value")}
        ctx.close()
        return merged


def refresh_cookie_by_own(cookies: dict, proxy=None) -> dict:
    """用账号自己的 cookie 构建临时浏览器上下文，访问光合刷新 token。

    适用于手动粘贴 cookie 导入的账号：不依赖全局 browser_profile，
    用该账号自带的长期登录态（cookie2/lgc 等）换取新 _m_h5_tk。
    proxy 为 Playwright 代理配置（账号设置了代理时传入，让刷新也走代理）。
    """
    # Chromium 不支持带认证的 SOCKS5 代理（只有 Firefox 支持），提前给出友好提示
    if proxy and isinstance(proxy, dict):
        server = str(proxy.get("server", ""))
        if "socks" in server and proxy.get("username"):
            raise MtopError(
                "带认证的 SOCKS5 代理无法用于浏览器刷新登录态（Chromium 限制）。"
                "请改用 HTTP 代理，或使用不带认证的 SOCKS5，或临时取消代理后手动刷新")
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(
            user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                        "(KHTML, like Gecko) Chrome/153.0.0.0 Safari/537.36"),
            viewport={"width": 1440, "height": 900},
            proxy=proxy)
        try:
            cookie_list = [{"name": k, "value": v, "domain": ".taobao.com", "path": "/"}
                           for k, v in cookies.items() if k and v]
            ctx.add_cookies(cookie_list)
            page = ctx.new_page()
            page.goto("https://creator.guanghe.taobao.com/page/", wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(6000)
            if any(k in page.url for k in ("login", "punish", "captcha")):
                raise MtopError("该账号登录态已失效，请重新登录/粘贴 cookie")
            new_cookies = {c["name"]: c["value"] for c in ctx.cookies() if c.get("name") and c.get("value")}
            return new_cookies
        finally:
            ctx.close()
            browser.close()


def health_check(cookies: dict, proxy=None) -> dict:
    """健康检查：验证 cookie 是否有效并返回淘宝账号标识。"""
    try:
        gh = GuangheHTTP(cookies, proxy=proxy)
        info = gh.whoami()
        # 当前登录账号以 getUserSimple 接口为准（cookie 的 lgc/dnk 可能残留其他账号昵称）
        nick = ""
        if isinstance(info, dict):
            nick = info.get("nick") or info.get("displayNick") or ""
        if not nick:
            nick = cookies.get("lgc") or cookies.get("dnk") or cookies.get("tracknick") or ""
        return {"ok": True, "taobao_id": decode_taobao_nick(nick), "info": info}
    except MtopError as e:
        return {"ok": False, "error": str(e)}
    except Exception as e:
        return {"ok": False, "error": str(e)[:200]}


def build_client_from_enc(cookies_enc: str) -> GuangheHTTP:
    """从加密 cookie 构建 GuangheHTTP 客户端。"""
    from ..security import decrypt_cookie, cookie_str_to_dict
    cookie_str = decrypt_cookie(cookies_enc)
    return GuangheHTTP(cookie_str_to_dict(cookie_str))


def build_client(db, account) -> GuangheHTTP:
    """构建客户端，并附带 token 失效自动刷新（按账号来源区分刷新方式）。

    账号设置了 proxy 时，所有请求（含 token 刷新）都只走该代理。
    """
    from ..config import settings
    from ..security import decrypt_cookie, cookie_str_to_dict, cookie_dict_to_str, encrypt_cookie

    proxy = (account.proxy or "").strip() or None
    pw_proxy = parse_proxy_for_playwright(proxy)

    def refresh():
        if account.source == "profile":
            cookies = extract_cookies_from_profile(str(settings.gh_home / "browser_profile"), proxy=proxy)
        else:
            own = cookie_str_to_dict(decrypt_cookie(account.cookies_enc))
            cookies = refresh_cookie_by_own(own, proxy=pw_proxy)
        account.cookies_enc = encrypt_cookie(cookie_dict_to_str(cookies))
        db.commit()
        return cookies

    cookie_str = decrypt_cookie(account.cookies_enc)
    return GuangheHTTP(cookie_str_to_dict(cookie_str), token_refresher=refresh, proxy=proxy)
