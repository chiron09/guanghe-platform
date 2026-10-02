# -*- coding: utf-8 -*-
"""探针：摸清 login.taobao.com 密码/短信 tab 的验证码图 & 获取验证码按钮真实 DOM。"""
import json
import sys
from playwright.sync_api import sync_playwright

HOME = "https://creator.guanghe.taobao.com/page/"


def dump_inputs(scope, tag):
    print(f"\n===== {tag} input/button/a/img dump =====")
    for sel in ["input", "button", "a.send-btn-link", "a[class*=send]", "img", "canvas",
                "a[class*=tab]", "span[class*=tab]"]:
        try:
            els = scope.locator(sel)
            n = els.count()
            print(f"-- {sel} x{n}")
            for i in range(min(n, 12)):
                el = els.nth(i)
                try:
                    info = el.evaluate(
                        """e => ({
                            tag: e.tagName, id: e.id, cls: e.className,
                            type: e.type || '', ph: e.placeholder || '',
                            text: (e.innerText || '').slice(0, 30),
                            visible: !!(e.offsetWidth || e.offsetHeight),
                            disabled: e.disabled || false,
                            src: (e.src || '').slice(0, 80),
                            style_h: e.offsetHeight, style_w: e.offsetWidth
                        })""")
                    print(f"   [{i}] {json.dumps(info, ensure_ascii=False)}")
                except Exception as ex:
                    print(f"   [{i}] eval err: {str(ex)[:80]}")
        except Exception as ex:
            print(f"-- {sel} ERR {str(ex)[:80]}")


with sync_playwright() as pw:
    browser = pw.chromium.launch(
        headless=True,
        args=["--disable-blink-features=AutomationControlled", "--no-first-run",
              "--no-default-browser-check"])
    ctx = browser.new_context(viewport={"width": 1280, "height": 900})
    page = ctx.new_page()
    page.goto(HOME, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(6000)
    print("URL after home:", page.url)
    for f in page.frames:
        print("FRAME:", f.url[:120])

    # 等登录元素出现
    try:
        page.wait_for_selector("a.sms-login-tab-item", timeout=10000)
        print("login page ready (tabs found in main frame)")
    except Exception:
        print("!! tabs not found in main frame, dump frame urls again")
        for f in page.frames:
            print("FRAME:", f.url[:150])
        sys.exit(1)

    # ---- 短信 tab（重点：获取验证码按钮 + 图片验证码）----
    try:
        page.locator("a.sms-login-tab-item").click(timeout=8000)
        page.wait_for_timeout(1500)
        print("\n########## SMS TAB ##########")
        dump_inputs(page, "SMS")
        # 检查验证码图是否可见、是否有"换一张"
        try:
            cc = page.locator("img[class*=checkcode], img[id*=checkcode], .nc_iconfont, img[src*=checkcode]")
            print("checkcode img count:", cc.count())
        except Exception as e:
            print("checkcode probe err", e)
        page.screenshot(path="probe_sms_tab.png", timeout=5000)
        print("saved probe_sms_tab.png")
    except Exception as e:
        print("SMS tab err:", str(e)[:200])

    # ---- 密码 tab ----
    try:
        page.locator("a.password-login-tab-item").click(timeout=8000)
        page.wait_for_timeout(1500)
        print("\n########## PASSWORD TAB ##########")
        dump_inputs(page, "PASSWORD")
        page.screenshot(path="probe_pw_tab.png", timeout=5000)
        print("saved probe_pw_tab.png")
    except Exception as e:
        print("PW tab err:", str(e)[:200])

    browser.close()
