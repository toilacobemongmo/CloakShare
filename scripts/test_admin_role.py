#!/usr/bin/env python3
"""
Kiểm thử hệ thống vai trò (role) của engine/accounts.py trong file tạm,
không đụng tới ~/.cloakshare/accounts.json thật.

Chạy:  python scripts/test_admin_role.py
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

# Chay tu thu muc scripts/ -> can dua root cua repo vao sys.path.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from engine import accounts


def check(label: str, condition: bool, detail: str = "") -> None:
    mark = "PASS" if condition else "FAIL"
    print(f"[{mark}] {label}" + (f" -> {detail}" if detail else ""))
    if not condition:
        raise AssertionError(label)


def main() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="cloakshare-role-"))
    accounts.ACCOUNTS_FILE = tmp / "accounts.json"

    print(f"File tai khoan tam: {accounts.ACCOUNTS_FILE}\n")

    # --- 1. ensure_roles() tren file rong ---------------------------------
    check(
        "ensure_roles() khong loi khi file chua ton tai",
        accounts.ensure_roles() == 0,
        "tra ve 0",
    )

    # --- 2. register voi role mac dinh = user ------------------------------
    accounts.register("alice", "alice123", "0x" + "11" * 32, "0xAAA")
    check("register mac dinh -> role=user", accounts.get_role("alice") == "user")
    check("is_admin(alice) = False", accounts.is_admin("alice") is False)

    # --- 3. register voi role=admin ---------------------------------------
    accounts.register("admin", "admin123", "0x" + "22" * 32, "0xBBB", role="admin")
    check("register(role=admin) -> role=admin", accounts.get_role("admin") == "admin")
    check("is_admin(admin) = True", accounts.is_admin("admin") is True)

    # --- 4. role khong hop le bi ep ve "user" ------------------------------
    accounts.register("carl", "carl12345", "0x" + "33" * 32, "0xCCC", role="root")
    check("role la 'root' -> bi ep ve user", accounts.get_role("carl") == "user")

    # --- 5. xac thuc van con hoat dong -------------------------------------
    pk, addr = accounts.authenticate("admin", "admin123")
    check("authenticate(admin) tra dung dia chi", addr == "0xBBB", addr)
    try:
        accounts.authenticate("admin", "sai-mat-khau")
        check("sai mat khau bi tu choi", False)
    except accounts.AuthError:
        check("sai mat khau bi tu choi", True)

    # --- 6. set_role cap/thu quyen ----------------------------------------
    accounts.set_role("alice", "admin")
    check("set_role(alice, admin)", accounts.is_admin("alice") is True)
    accounts.set_role("alice", "user")
    check("set_role(alice, user) thu quyen lai", accounts.is_admin("alice") is False)
    try:
        accounts.set_role("khong-ton-tai", "admin")
        check("set_role tai khoan khong ton tai -> loi", False)
    except accounts.AuthError:
        check("set_role tai khoan khong ton tai -> loi", True)

    # --- 7. get_role tai khoan chua ton tai -> "user" ----------------------
    check("get_role(ta-khong-ton-tai) = user", accounts.get_role("ta-khong-ton-tai") == "user")

    # --- 8. ensure_roles() backfill cho ban ghi cu (khong co truong role) ---
    raw = json.loads(accounts.ACCOUNTS_FILE.read_text(encoding="utf-8"))
    del raw["accounts"]["carl"]["role"]
    accounts.ACCOUNTS_FILE.write_text(
        json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    check("truoc backfill: get_role(carl) van la user (fallback)", accounts.get_role("carl") == "user")
    fixed = accounts.ensure_roles()
    check("ensure_roles() backfill 1 ban ghi", fixed == 1, f"fixed={fixed}")
    back = json.loads(accounts.ACCOUNTS_FILE.read_text(encoding="utf-8"))
    check("ban ghi cu da duoc ghi 'role' vao dia", back["accounts"]["carl"]["role"] == "user")
    check("ensure_roles() lan 2 khong doi gi", accounts.ensure_roles() == 0)
    check("role cua admin khong bi de do", accounts.get_role("admin") == "admin")

    # --- 9. list_accounts() co truong role ---------------------------------
    rows = {r["username"]: r["role"] for r in accounts.list_accounts()}
    check(
        "list_accounts() tra day du role",
        rows.get("admin") == "admin" and rows.get("alice") == "user",
        str(rows),
    )

    # --- 10. khong ro ri private key ra metadata ----------------------------
    blob = json.dumps(accounts.list_accounts())
    check("list_accounts() khong lo private key", "22" * 32 not in blob.replace('"', ""))

    print("\nTAT CA KIEM THU VAO ROLE PASS")
    print(f"(thu muc tam: {tmp})")


if __name__ == "__main__":
    main()