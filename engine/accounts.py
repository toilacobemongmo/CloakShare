"""
engine/accounts.py

Hệ thống tài khoản chính thống cho CloakShare (thay cho cơ chế "đổi acc qua lại").

Vấn đề giải quyết:
    Trước đây UI lưu private key dạng HEX plaintext trong
    ~/.cloakshare/accounts.json và cho phép chọn bất kỳ tài khoản nào
    bằng dropdown. Đó không phải là "đăng nhập" - bất kỳ ai mở app đều
    thấy toàn bộ khóa riêng của mọi tài khoản.

Cơ chế mới:
    - Mỗi tài khoản có username + mật khẩu.
    - Khóa phiên (khoá dẫn xuất) = PBKDF2-HMAC-SHA256(mật khẩu, salt, 390000 vòng).
    - Private key ví được mã hoá bằng Fernet (AES-128-CBC + HMAC-SHA256)
      với khóa dẫn xuất đó -> lưu xuống đĩa đã mã hoá.
    - Xác thực = giải mã thử verifier; sai mật khẩu thì giải mã hỏng
      (InvalidToken), KHÔNG lộ ra việc mật khẩu tồn tại hay không.
    - File lưu trữ ở ~/.cloakshare/accounts.json, chỉ chứa ciphertext.

Lưu ý bảo mật:
    - Salt ngẫu nhiên 16 byte cho từng tài khoản (lưu kèm trong record).
    - PBKDF2 390000 vòng bám sát khuyến nghị OWASP 2023 cho PBKDF2-HMAC-SHA256.
    - Hàm băm so sánh dùng hmac.compare_digest (constant-time).
    - Không bao giờ ghi log / in ra private key.
"""

from __future__ import annotations

import base64
import getpass
import hmac
import json
import os
import secrets
import time
from pathlib import Path
from typing import Any

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

# Số vòng lặp PBKDF2 (khuyến nghị OWASP: 600k cho SHA256; 390k là mức
# chấp nhận được để giao diện Streamlit không bị treo quá lâu).
PBKDF2_ITERATIONS = 390_000
SALT_BYTES = 16

# Chuỗi dùng làm "verifier": giải mã được thì mật khẩu đúng.
_VERIFIER_PLAINTEXT = b"cloakshare-account-v1"

ACCOUNTS_FILE = Path.home() / ".cloakshare" / "accounts.json"


class AuthError(Exception):
    """Sai tên đăng nhập hoặc sai mật khẩu (thông điệp trung tính)."""


class UsernameTaken(AuthError):
    """Tên tài khoản đã tồn tại."""


class WeakPassword(AuthError):
    """Mật khẩu không đạt yêu cầu tối thiểu."""


def _derive_fernet_key(password: str, salt: bytes) -> Fernet:
    """PBKDF2-HMAC-SHA256 -> khóa 32 byte -> Fernet."""
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=PBKDF2_ITERATIONS,
    )
    return Fernet(base64.urlsafe_b64encode(kdf.derive(password.encode("utf-8"))))


def _b64e(raw: bytes) -> str:
    return base64.b64encode(raw).decode("ascii")


def _b64d(text: str) -> bytes:
    return base64.b64decode(text.encode("ascii"))


def _validate_username(username: str) -> str:
    name = username.strip()
    if len(name) < 3 or len(name) > 32:
        raise AuthError("Tên tài khoản phải dài từ 3 đến 32 ký tự.")
    if not all(ch.isalnum() or ch in "._-" for ch in name):
        raise AuthError(
            "Tên tài khoản chỉ được chứa chữ, số và các ký tự . _ -"
        )
    return name


def _validate_password(password: str) -> str:
    pwd = password
    if len(pwd) < 8:
        raise WeakPassword("Mật khẩu phải có ít nhất 8 ký tự.")
    if len(pwd) > 256:
        raise WeakPassword("Mật khẩu quá dài (tối đa 256 ký tự).")
    return pwd


def _load_file() -> dict[str, Any]:
    if not ACCOUNTS_FILE.exists():
        return {"version": 1, "accounts": {}}
    try:
        with open(ACCOUNTS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict) and isinstance(data.get("accounts"), dict):
            return data
    except Exception:
        pass
    return {"version": 1, "accounts": {}}


def _save_file(data: dict[str, Any]) -> None:
    ACCOUNTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = ACCOUNTS_FILE.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, sort_keys=True)
    os.replace(tmp, ACCOUNTS_FILE)
    try:
        os.chmod(ACCOUNTS_FILE, 0o600)
    except Exception:
        pass  # Windows không hỗ trợ cờ POSIX


def register(
    username: str,
    password: str,
    private_key_hex: str,
    address: str,
    role: str = "user",
) -> dict[str, Any]:
    """
    Tạo bản ghi tài khoản mới. Private key được mã hoá trước khi ghi xuống đĩa.

    role: "user" (mặc định) hoặc "admin". Chỉ tài khoản admin mới xem được
    trang Dashboard giám sát Zero-Log (trang /admin).
    """
    name = _validate_username(username)
    pwd = _validate_password(password)
    if role not in ("user", "admin"):
        role = "user"

    data = _load_file()
    if name.lower() in {k.lower() for k in data["accounts"]}:
        raise UsernameTaken("Tên tài khoản đã tồn tại.")

    salt = secrets.token_bytes(SALT_BYTES)
    fernet = _derive_fernet_key(pwd, salt)

    record = {
        "salt": _b64e(salt),
        "verifier": fernet.encrypt(_VERIFIER_PLAINTEXT).decode("ascii"),
        "encrypted_key": fernet.encrypt(
            private_key_hex.encode("utf-8")
        ).decode("ascii"),
        "address": address,
        "role": role,
        "created_at": int(time.time()),
    }

    data["accounts"][name] = record
    _save_file(data)
    return record


def get_role(username: str) -> str:
    """Trả về vai trò ("admin" hoặc "user") của tài khoản. Mặc định 'user'."""
    name = (username or "").strip().lower()
    for key, record in _load_file()["accounts"].items():
        if key.lower() == name:
            return record.get("role", "user")
    return "user"


def is_admin(username: str) -> bool:
    """True nếu tài khoản có vai trò admin."""
    return get_role(username) == "admin"


def authenticate(username: str, password: str) -> tuple[str, str]:
    """
    Xác thực và trả về (private_key_hex, address).

    Sai tên hoặc sai mật khẩu đều ném AuthError với cùng thông điệp,
    không tiết lộ tên tài khoản có tồn tại hay không.
    """
    name = (username or "").strip()
    data = _load_file()

    record = None
    for key, value in data["accounts"].items():
        if key.lower() == name.lower():
            record = value
            break

    if record is None:
        # Vẫn chạy một lượt PBKDF2 để không lộ thông tin qua thời gian phản hồi.
        _derive_fernet_key(password or "", b"\x00" * SALT_BYTES)
        raise AuthError("Tên đăng nhập hoặc mật khẩu không đúng.")

    try:
        fernet = _derive_fernet_key(password, _b64d(record["salt"]))
        verifier = fernet.decrypt(record["verifier"].encode("ascii"))
        if not hmac.compare_digest(verifier, _VERIFIER_PLAINTEXT):
            raise AuthError("Tên đăng nhập hoặc mật khẩu không đúng.")
        private_key_hex = fernet.decrypt(
            record["encrypted_key"].encode("ascii")
        ).decode("utf-8")
    except InvalidToken as exc:
        raise AuthError("Tên đăng nhập hoặc mật khẩu không đúng.") from exc

    return private_key_hex, record["address"]


def list_accounts() -> list[dict[str, str]]:
    """Danh sách tài khoản (chỉ metadata công khai, KHÔNG có khóa)."""
    data = _load_file()
    out = []
    for name, record in sorted(data["accounts"].items()):
        out.append(
            {
                "username": name,
                "address": record.get("address", ""),
                "role": record.get("role", "user"),
                "created_at": str(record.get("created_at", "")),
            }
        )
    return out


def account_exists(username: str) -> bool:
    name = (username or "").strip().lower()
    return any(k.lower() == name for k in _load_file()["accounts"])


def change_password(username: str, old_password: str, new_password: str) -> None:
    """Đổi mật khẩu: xác thực mật khẩu cũ rồi mã hoá lại khóa bằng mật khẩu mới."""
    name = (username or "").strip()
    private_key_hex, _ = authenticate(name, old_password)
    new_pwd = _validate_password(new_password)

    data = _load_file()
    record = next(
        v for k, v in data["accounts"].items() if k.lower() == name.lower()
    )
    salt = secrets.token_bytes(SALT_BYTES)
    fernet = _derive_fernet_key(new_pwd, salt)
    record["salt"] = _b64e(salt)
    record["verifier"] = fernet.encrypt(_VERIFIER_PLAINTEXT).decode("ascii")
    record["encrypted_key"] = fernet.encrypt(
        private_key_hex.encode("utf-8")
    ).decode("ascii")
    _save_file(data)


def delete_account(username: str, password: str) -> None:
    """Xóa tài khoản (khóa riêng bị mất vĩnh viễn)."""
    name = (username or "").strip()
    authenticate(name, password)
    data = _load_file()
    for key in [k for k in data["accounts"] if k.lower() == name.lower()]:
        del data["accounts"][key]
    _save_file(data)


# --------------------------------------------------------------------------- #
# CLI hỗ trợ vận hành (không dùng trong UI)
# --------------------------------------------------------------------------- #

def set_role(username: str, role: str) -> None:
    """Cấp/thu quyền admin cho một tài khoản đã tồn tại."""
    if role not in ("user", "admin"):
        raise AuthError("Vai trò chỉ được là 'user' hoặc 'admin'.")
    name = (username or "").strip()
    data = _load_file()
    matched = [k for k in data["accounts"] if k.lower() == name.lower()]
    if not matched:
        raise AuthError(f"Không tìm thấy tài khoản '{name}'.")
    for key in matched:
        data["accounts"][key]["role"] = role
    _save_file(data)


def ensure_roles() -> int:
    """
    Bổ sung trường "role" = "user" cho các tài khoản cũ chưa có trường này.

    Trả về số bản ghi đã được cập nhật. Gọi một lần khi khởi động UI để
    đảm bảo mọi tài khoản đều có vai trò rõ ràng (mặc định "user").
    """
    data = _load_file()
    changed = 0
    for record in data["accounts"].values():
        if "role" not in record or record.get("role") not in ("user", "admin"):
            record["role"] = "user"
            changed += 1
    if changed:
        _save_file(data)
    return changed


def _cli() -> None:
    import sys

    if len(sys.argv) < 2:
        print("Dùng: python -m engine.accounts list|register|delete <tên>")
        print("     python -m engine.accounts setrole <tên> admin|user")
        return
    cmd = sys.argv[1]
    if cmd == "list":
        for item in list_accounts():
            print(f"- {item['username']}  {item['address']}")
    elif cmd == "register":
        name = input("Tên tài khoản: ").strip()
        pwd = getpass.getpass("Mật khẩu: ")
        role_in = input("Vai trò [user/admin] (mặc định user): ").strip().lower()
        role = "admin" if role_in == "admin" else "user"
        from eth_account import Account

        wallet = Account.create()
        register(name, pwd, wallet.key.hex(), wallet.address, role=role)
        print(f"Đã tạo tài khoản '{name}' ({role}) tại {wallet.address}")
    elif cmd == "delete" and len(sys.argv) > 2:
        name = sys.argv[2]
        pwd = getpass.getpass("Mật khẩu: ")
        delete_account(name, pwd)
        print(f"Đã xóa tài khoản '{name}'")
    elif cmd == "setrole" and len(sys.argv) > 3:
        set_role(sys.argv[2], sys.argv[3])
        print(f"Đã đặt vai trò '{sys.argv[2]}' = {sys.argv[3]}")
    else:
        print("Lệnh không hợp lệ.")


if __name__ == "__main__":
    _cli()