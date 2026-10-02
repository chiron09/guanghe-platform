# -*- coding: utf-8 -*-
"""探针2：模拟提交，抓错误提示 DOM + 验证码行出现时机。"""
import json
from playwright.sync_api import sync_playwright

HOME = "https://creator.guanghe.taobao.com/page/"


def dump_visible(page, tag):
    print(f"\n===== {tag} 可见元素/错误提示 =====")
    for sel in ["div[class*=error]", "p[class*=error]", "span[class*=error]",
                "div[class*=tip]", "div[class*=msg]", "div[class*=notice]"]:
        try:
            els = page.locator(sel)
            n = els.count()
            for i in range(min(n, 8)):
                el = els.nth(i)
                try:
                    info = el.evaluate(
                        """e => ({
                            tag: e.tagName, id: e.id, cls: e.className,
                            text: (e.innerText || '').slice(0, 60),
                            visible: !!(e.offsetWidth || e.offsetHeight)})""")
                    if info["visible"] and info["text"]:
                        print(f"  {sel} [{i}] {json.dumps(info, ensure_ascii=False)}")
                except Exception:
                    pass
        except Exception:
            pass
    # 验证码行可见性
    try:
        cc_input = page.locator("input#fm-login-checkcode")
        cc_img = page.locator("img.fm-login-checkcode-img")
        print("  checkcode input visible:", cc_input.is_visible() if cc_input.count() else "N/A")
        print("  checkcode img visible:", cc_img.is_visible() if cc_img.count() else "N/A",
              "| count:", cc_img.count())
        if cc_img.count():
            print("  checkcode img src:", cc_img.first.evaluate("e => e.src")[:150])
    except Exception as e:
        print("  checkcode probe err:", str(e)[:100])


with sync_playwright() as pw:
    browser = pw.chromium.launch(
        headless=True,
        args=["--disable-blink-features=AutomationControlled", "--no-first-run",
              "--no-default-browser-check"])
    ctx = browser.new_context(viewport={"width": 1280, "height": 900})
    page = ctx.new_page()
    page.goto(HOME, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(6000)
    page.wait_for_selector("a.password-login-tab-item", timeout=10000)

    # ---------- 密码 tab：错误密码提交 ----------
    page.locator("a.password-login-tab-item").click(timeout=8000)
    page.wait_for_timeout(1200)
    # 先勾协议
    try:
        cb = page.locator("input#fm-agreement-checkbox")
        if cb.count() and not cb.is_checked():
            cb.check(timeout=3000)
            print("协议已勾选")
    except Exception as e:
        print("协议勾选失败:", str(e)[:100])
    page.locator("input#fm-login-id").fill("test_wrong_user_x", timeout=5000)
    page.locator("input#fm-login-password").fill("WrongPass123", timeout=5000)
    page.locator("button.fm-submit").click(timeout=5000)
    page.wait_for_timeout(5000)
    print("\n########## 密码提交（错误账号密码）后 ##########")
    print("URL:", page.url[:100])
    dump_visible(page, "错误密码提交后")
    page.screenshot(path="probe2_pw_submit.png", timeout=5000)
    print("saved probe2_pw_submit.png")

    # ---------- 再提交一次（可能触发验证码行）----------
    try:
        page.locator("button.fm-submit").click(timeout=5000)
        page.wait_for_timeout(5000)
        print("\n########## 第二次提交后 ##########")
        dump_visible(page, "第二次提交后")
        page.screenshot(path="probe2_pw_submit2.png", timeout=5000)
        # 若验证码图可见，截下来
        cc_img = page.locator("img.fm-login-checkcode-img")
        if cc_img.count() and cc_img.is_visible():
            cc_img.screenshot(path="probe2_checkcode.png", timeout=5000)
            print("saved probe2_checkcode.png (验证码图元素截图)")
            # 看验证码图有没有刷新机制（点击事件/换一张）
            parent_html = cc_img.evaluate("e => e.parentElement ? e.parentElement.outerHTML.slice(0,600) : ''")
            print("验证码父容器 HTML:", parent_html)
    except Exception as e:
        print("第二次提交 err:", str(e)[:200])

    # ---------- 短信 tab：只填手机号点获取验证码 ----------
    try:
        page.locator("a.sms-login-tab-item").click(timeout=8000)
        page.wait_for_timeout(1200)
        page.locator("input#fm-sms-login-id").fill("13800138000", timeout=5000)
        page.locator("a.send-btn-link").click(timeout=5000)
        page.wait_for_timeout(4000)
        print("\n########## 短信获取验证码（未填图片验证码）后 ##########")
        print("URL:", page.url[:100])
        dump_visible(page, "短信send后")
        page.screenshot(path="probe2_sms_send.png", timeout=5000)
        print("saved probe2_sms_send.png")
    except Exception as e:
        print("短信 send err:", str(e)[:200])

    browser.close()
