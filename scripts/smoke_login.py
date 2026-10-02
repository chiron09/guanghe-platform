# -*- coding: utf-8 -*-
"""冒烟测试：密码/短信登录会话（错误凭据验证错误透出 + 短信发送流程）。"""
import base64
import time

import requests

BASE = "http://127.0.0.1:8000/api"


def wait_state(sid, H, want, timeout=40, prefix=""):
    t0 = time.time()
    last = {}
    while time.time() - t0 < timeout:
        last = requests.get(f"{BASE}/accounts/login/{sid}", headers=H).json()
        if last.get("state") in want:
            return last
        time.sleep(2)
    return last


def save_b64(b64, name):
    if b64:
        with open(name, "wb") as f:
            f.write(base64.b64decode(b64))


def main():
    r = requests.post(f"{BASE}/auth/login", json={"username": "admin", "password": "admin123"})
    H = {"Authorization": "Bearer " + r.json()["access_token"]}

    # ---------- 密码登录：错误凭据，应透出页面错误 ----------
    print("== 密码登录会话 ==")
    r = requests.post(f"{BASE}/accounts/login/start", headers=H, json={"mode": "password"}).json()
    sid = r["sid"]
    print(f"[start] sid={sid} state={r['state']}")
    s = wait_state(sid, H, ("ready",), 40)
    print(f"[ready] state={s['state']} shot_type={s.get('shot_type')} has_shot={bool(s.get('screenshot'))}")
    save_b64(s.get("screenshot"), "smoke_pw_ready.png")

    r = requests.post(f"{BASE}/accounts/login/{sid}/submit", headers=H,
                      json={"action": "login", "account": "test_wrong_user_x",
                            "password": "WrongPass123"}).json()
    print(f"[submit] state={r['state']}")
    s = wait_state(sid, H, ("need_checkcode", "submitted", "error"), 40)
    print(f"[after] state={s['state']} error={s.get('error')!r} shot_type={s.get('shot_type')}")
    save_b64(s.get("screenshot"), "smoke_pw_after.png")
    requests.post(f"{BASE}/accounts/login/{sid}/refresh_code", headers=H)
    time.sleep(4)
    s = requests.get(f"{BASE}/accounts/login/{sid}", headers=H).json()
    print(f"[refresh_code] state={s['state']} shot_type={s.get('shot_type')}")

    # ---------- 短信登录：发送验证码 ----------
    print("\n== 短信登录会话 ==")
    r = requests.post(f"{BASE}/accounts/login/start", headers=H, json={"mode": "sms"}).json()
    sid2 = r["sid"]
    print(f"[start] sid={sid2} state={r['state']}")
    s2 = wait_state(sid2, H, ("ready",), 40)
    print(f"[ready] state={s2['state']} shot_type={s2.get('shot_type')}")
    save_b64(s2.get("screenshot"), "smoke_sms_ready.png")

    r = requests.post(f"{BASE}/accounts/login/{sid2}/submit", headers=H,
                      json={"action": "send_code", "phone": "13800138000"}).json()
    print(f"[submit] state={r['state']}")
    s2 = wait_state(sid2, H, ("need_checkcode", "submitted", "error"), 40)
    print(f"[after] state={s2['state']} error={s2.get('error')!r} shot_type={s2.get('shot_type')}")
    save_b64(s2.get("screenshot"), "smoke_sms_after.png")


if __name__ == "__main__":
    main()
