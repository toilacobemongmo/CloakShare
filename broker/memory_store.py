"""
broker/memory_store.py

Kho lưu trữ payload TRÊN RAM cho Zero-Log Broker (Issue #7).

Nguyên tắc bất di bất dịch:
  - Payload chỉ nằm trong dictionary Python (heap RAM của tiến trình).
  - KHÔNG open(), KHÔNG ghi file tạm, KHÔNG ghi log nội dung payload.
  - Sau khi Buyer lấy xong, hoặc khi hết TTL, payload bị ghi đè rồi xoá.

Module này cố tình KHÔNG import FastAPI/Pydantic để:
  - Có thể unit-test độc lập, không cần dựng server.
  - Tầng HTTP (main.py) thay đổi không ảnh hưởng tới lõi lưu trữ.

Ghi chú về "ghi đè bộ nhớ":
Trong CPython, đối tượng `str` là immutable nên không thể memset tại chỗ
như bên C. Vì vậy ta lưu các trường nhạy cảm dưới dạng `bytearray`
(mutable) để có thể ghi đè byte 0x00 thật sự trước khi giải phóng - đúng
tinh thần `memset` mô tả trong CONTRIBUTING.md. Đây là biện pháp
best-effort ở tầng Python: sau khi ghi đè, phần nhớ vẫn do garbage
collector quản lý, nhưng nội dung nhạy cảm đã bị xoá khỏi vùng nhớ đó.
"""

from __future__ import annotations

import threading
import time
from typing import Any


# Các trường nhạy cảm cần ghi đè bằng 0x00 khi purge.
_SENSITIVE_FIELDS = ("iv", "wrapped_key", "ciphertext", "signature")


def _wipe(value: Any) -> None:
    """Ghi đè nội dung một bytearray bằng byte 0x00 (mô phỏng memset)."""
    if isinstance(value, bytearray):
        for i in range(len(value)):
            value[i] = 0


class InMemoryStore:
    """
    Dictionary-based store có TTL, thread-safe.

    Cấu trúc nội bộ:
        self._data[tx_id] = {
            "recipient":   str,
            "iv":          bytearray,
            "wrapped_key": bytearray,
            "ciphertext":  bytearray,
            "signature":   bytearray,
            "expires_at":  float,   # Unix timestamp
        }
    """

    def __init__(self) -> None:
        self._data: dict[str, dict[str, Any]] = {}
        self._lock = threading.RLock()

        # Bộ đếm phục vụ Dashboard giám sát (Issue #18).
        self.start_time = time.time()
        self.total_staged = 0
        self.total_retrieved = 0
        self.total_purged_expired = 0

    # ------------------------------------------------------------------ #
    # Ghi / đọc payload                                                   #
    # ------------------------------------------------------------------ #

    def stage(
        self,
        tx_id: str,
        recipient: str,
        iv: str,
        wrapped_key: str,
        ciphertext: str,
        signature: str,
        ttl_seconds: int,
    ) -> float:
        """
        Lưu payload vào RAM. Trả về `expires_at` (Unix timestamp).
        Nếu tx_id đã tồn tại, bản cũ bị wipe rồi ghi đè bằng bản mới.
        """
        expires_at = time.time() + ttl_seconds

        with self._lock:
            if tx_id in self._data:
                self._purge_one(tx_id)

            self._data[tx_id] = {
                "recipient": recipient,
                "iv": bytearray(iv.encode("utf-8")),
                "wrapped_key": bytearray(wrapped_key.encode("utf-8")),
                "ciphertext": bytearray(ciphertext.encode("utf-8")),
                "signature": bytearray(signature.encode("utf-8")),
                "expires_at": expires_at,
            }
            self.total_staged += 1

        return expires_at

    def retrieve(self, tx_id: str) -> dict[str, str] | None:
        """
        Lấy payload theo tx_id.

        Trả về dict các trường dạng str, hoặc None nếu không tồn tại
        / đã hết hạn (hết hạn thì purge luôn tại chỗ).

        LƯU Ý: hàm này KHÔNG tự xoá payload sau khi đọc. Việc "đọc xong
        thì huỷ" (burn-after-read) thuộc phạm vi Issue #8 - Zero-Log &
        Memory Purge, nên để tầng trên gọi purge() tường minh, tránh làm
        Buyer mất dữ liệu nếu request bị lỗi mạng giữa chừng.
        """
        with self._lock:
            entry = self._data.get(tx_id)
            if entry is None:
                return None

            if time.time() >= entry["expires_at"]:
                self._purge_one(tx_id)
                self.total_purged_expired += 1
                return None

            result = {
                "tx_id": tx_id,
                "recipient": entry["recipient"],
                "iv": entry["iv"].decode("utf-8"),
                "wrapped_key": entry["wrapped_key"].decode("utf-8"),
                "ciphertext": entry["ciphertext"].decode("utf-8"),
                "signature": entry["signature"].decode("utf-8"),
            }
            self.total_retrieved += 1
            return result

    def exists(self, tx_id: str) -> bool:
        """Kiểm tra tx_id còn tồn tại và chưa hết hạn."""
        with self._lock:
            entry = self._data.get(tx_id)
            if entry is None:
                return False
            return time.time() < entry["expires_at"]

    # ------------------------------------------------------------------ #
    # Dọn dẹp                                                             #
    # ------------------------------------------------------------------ #

    def _purge_one(self, tx_id: str) -> bool:
        """
        Ghi đè 0x00 lên các trường nhạy cảm rồi xoá khỏi dict.
        Hàm nội bộ - caller phải đang giữ self._lock.
        """
        entry = self._data.pop(tx_id, None)
        if entry is None:
            return False

        for field in _SENSITIVE_FIELDS:
            _wipe(entry.get(field))

        entry.clear()
        return True

    def purge(self, tx_id: str) -> bool:
        """Xoá một payload tường minh. Trả về True nếu có xoá được."""
        with self._lock:
            return self._purge_one(tx_id)

    def purge_expired(self) -> int:
        """
        Quét toàn bộ store, xoá mọi payload đã quá hạn TTL.
        Trả về số payload đã dọn. Đây là hàm mà background task gọi định kỳ.
        """
        now = time.time()
        with self._lock:
            expired = [
                tx_id
                for tx_id, entry in self._data.items()
                if now >= entry["expires_at"]
            ]
            for tx_id in expired:
                self._purge_one(tx_id)

            self.total_purged_expired += len(expired)
            return len(expired)

    def purge_all(self) -> int:
        """Dọn sạch toàn bộ store (dùng khi shutdown hoặc trong test)."""
        with self._lock:
            count = len(self._data)
            for tx_id in list(self._data.keys()):
                self._purge_one(tx_id)
            return count

    # ------------------------------------------------------------------ #
    # Giám sát                                                            #
    # ------------------------------------------------------------------ #

    def active_count(self) -> int:
        """Số payload đang còn sống (chưa hết hạn)."""
        now = time.time()
        with self._lock:
            return sum(
                1 for entry in self._data.values() if now < entry["expires_at"]
            )

    def approx_ram_bytes(self) -> int:
        """Ước tính tổng dung lượng RAM đang cấp phát cho payloads (bytes)."""
        total = 0
        with self._lock:
            for entry in self._data.values():
                for field in _SENSITIVE_FIELDS:
                    val = entry.get(field)
                    if isinstance(val, (bytearray, bytes)):
                        total += len(val)
        return total

    def stats(self) -> dict[str, int]:
        """Số liệu cho Dashboard Broker."""
        with self._lock:
            return {
                "active_payloads": self.active_count(),
                "total_staged": self.total_staged,
                "total_retrieved": self.total_retrieved,
                "total_purged_expired": self.total_purged_expired,
                "disk_writes": 0,
                "approx_ram_bytes": self.approx_ram_bytes(),
                "uptime_seconds": int(time.time() - self.start_time),
            }
    def get_inbox(self, recipient: str) -> list[dict[str, str]]:
        """
        Lấy danh sách toàn bộ payload còn hạn trên RAM dành riêng cho địa chỉ ví recipient.
        """
        now = time.time()
        inbox_items = []
        with self._lock:
            for tx_id, entry in self._data.items():
                if now < entry["expires_at"] and entry["recipient"].lower() == recipient.lower():
                    inbox_items.append({
                        "tx_id": tx_id,
                        "recipient": entry["recipient"],
                        "iv": entry["iv"].decode("utf-8"),
                        "wrapped_key": entry["wrapped_key"].decode("utf-8"),
                        "ciphertext": entry["ciphertext"].decode("utf-8"),
                        "signature": entry["signature"].decode("utf-8"),
                    })
        return inbox_items


# Instance dùng chung toàn ứng dụng (singleton đơn giản).

import os
import json
try:
    import redis
except ImportError:
    redis = None

class RedisStore:
    def __init__(self, url: str):
        self.client = redis.Redis.from_url(url, decode_responses=True)
        self.start_time = time.time()
        self.total_staged = 0
        self.total_retrieved = 0
        self.total_purged_expired = 0

    def stage(self, tx_id: str, recipient: str, iv: str, wrapped_key: str, ciphertext: str, signature: str, ttl_seconds: int) -> float:
        expires_at = time.time() + ttl_seconds
        payload = {
            "recipient": recipient,
            "iv": iv,
            "wrapped_key": wrapped_key,
            "ciphertext": ciphertext,
            "signature": signature,
            "expires_at": expires_at,
        }
        self.client.setex(f"cloakshare:tx:{tx_id}", ttl_seconds, json.dumps(payload))
        self.total_staged += 1
        return expires_at

    def retrieve(self, tx_id: str) -> dict | None:
        key = f"cloakshare:tx:{tx_id}"
        data = self.client.get(key)
        if not data:
            return None
        payload = json.loads(data)
        if time.time() >= payload["expires_at"]:
            self.purge(tx_id)
            return None
        self.total_retrieved += 1
        return {
            "tx_id": tx_id,
            "recipient": payload["recipient"],
            "iv": payload["iv"],
            "wrapped_key": payload["wrapped_key"],
            "ciphertext": payload["ciphertext"],
            "signature": payload["signature"],
        }

    def exists(self, tx_id: str) -> bool:
        return self.client.exists(f"cloakshare:tx:{tx_id}") > 0

    def purge(self, tx_id: str) -> bool:
        return self.client.delete(f"cloakshare:tx:{tx_id}") > 0

    def purge_expired(self) -> int:
        return 0  # Redis handles TTL automatically

    def purge_all(self) -> int:
        keys = self.client.keys("cloakshare:tx:*")
        if keys:
            self.client.delete(*keys)
            return len(keys)
        return 0

    def active_count(self) -> int:
        return len(self.client.keys("cloakshare:tx:*"))

    def approx_ram_bytes(self) -> int:
        info = self.client.info("memory")
        return int(info.get("used_memory", 0))

    def stats(self) -> dict:
        return {
            "active_payloads": self.active_count(),
            "total_staged": self.total_staged,
            "total_retrieved": self.total_retrieved,
            "total_purged_expired": self.total_purged_expired,
            "disk_writes": 0,
            "approx_ram_bytes": self.approx_ram_bytes(),
            "uptime_seconds": int(time.time() - self.start_time),
        }

    def get_inbox(self, recipient: str) -> list:
        inbox_items = []
        for key in self.client.keys("cloakshare:tx:*"):
            data = self.client.get(key)
            if data:
                payload = json.loads(data)
                if time.time() < payload["expires_at"] and payload["recipient"].lower() == recipient.lower():
                    tx_id = key.split(":")[-1]
                    inbox_items.append({
                        "tx_id": tx_id,
                        "recipient": payload["recipient"],
                        "iv": payload["iv"],
                        "wrapped_key": payload["wrapped_key"],
                        "ciphertext": payload["ciphertext"],
                        "signature": payload["signature"],
                    })
        return inbox_items


# Khởi tạo store: Ưu tiên Redis nếu có REDIS_URL (Giải quyết Nút thắt cổ chai và tính sẵn sàng)
redis_url = os.environ.get("REDIS_URL")
if redis_url and redis:
    print(f"[i] Đang kết nối tới Redis Store tại: {redis_url}")
    store = RedisStore(redis_url)
else:
    store = InMemoryStore()

