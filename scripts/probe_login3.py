# -*- coding: utf-8 -*-
"""探针3：抓 send_code 后弹出的营销弹窗 DOM。"""
import json
from playwright.sync_api import sync_playwright

HOME = "https://creator.guanghe.taobao.com/page/"


def dump_popups(page, tag):
    print(f"\n===== {tag} 弹窗/浮层 dump =====")
    sels = ["[class*=dialog]", "[class*=Dialog]", "[class*=modal]", "[class*=Modal]",
            "[class*=pop]", "[class*=Pop]", "[class*=mask]", "[class*=Mask]",
            "[class*=overlay]", "[class*=layer]", "[class*=close]", "[class*=Cancel]",
            "button:has-text('取消')", "a:has-text('取消')", "[class*=guide]"]
    seen = set()
    for sel in sels:
        try:
            els = page.locator(sel)
            n = els.count()
            for i in range(min(n, 10)):
                el = els.nth(i)
                try:
                    info = el.evaluate(
                        """e => ({
                            tag: e.tagName, id: e.id, cls: (e.className || '').toString().slice(0, 100),
                            text: (e.innerText || '').replace(/\\n/g, ' | ').slice(0, 80),
                            visible: !!(e.offsetWidth || e.offsetHeight),
                            w: e.offsetWidth, h: e.offsetHeight})""")
                    key = (info["cls"], info["text"])
                    if info["visible"] and key not in seen:
                        seen.add(key)
                        print(f"  {sel} [{i}] {json.dumps(info, ensure_ascii=False)}")
                except Exception:
                    pass
        except Exception:
            pass


with sync_playwright() as pw:
    browser = pw.chromium.launch(
        headless=True,
        args=["--disable-blink-features=AutomationControlled", "--no-first-run",
              "--no-default-browser-check"])
    ctx = browser.new_context(viewport={"width": 1280, "height": 900})
    page = ctx.new_page()
    page.goto(HOME, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(6000)
    page.wait_for_selector("a.sms-login-tab-item", timeout=10000)
    page.locator("a.sms-login-tab-item").click(timeout=8000)
    page.wait_for_timeout(1200)
    try:
        cb = page.locator("input#fm-agreement-checkbox")
        if cb.count() and not cb.is_checked():
            cb.check(timeout=3000)
    except Exception:
        pass
    page.locator("#fm-sms-login-id").fill("18274717257", timeout=5000)
    page.locator("a.send-btn-link").click(timeout=5000)
    page.wait_for_timeout(6000)
    print("URL:", page.url[:100])
    dump_popups(page, "send_code 6s 后")
    page.screenshot(path="probe3_sms_popup.png", timeout=5000)
    print("saved probe3_sms_popup.png")
    # 再等 8s 看弹窗是否延迟出现
    page.wait_for_timeout(8000)
    dump_popups(page, "再等 8s 后")
    page.screenshot(path="probe3_sms_popup2.png", timeout=5000)
    browser.close()
