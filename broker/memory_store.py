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
from collections import deque
from typing import Any


# Các trường nhạy cảm cần ghi đè bằng 0x00 khi purge.
_SENSITIVE_FIELDS = ("iv", "wrapped_key", "ciphertext", "signature")

# Số dòng nhật ký sự kiện RAM giữ lại cho Dashboard (vòng tròn, chỉ trên RAM).
RAM_EVENT_LOG_SIZE = 100


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

        # Nhật ký sự kiện RAM cho Dashboard: mỗi lần ghi lên RAM và mỗi
        # lần ghi đè 0x00 đều được ghi lại để người dùng quan sát được vòng
        # đời của dữ liệu. Chỉ nằm trên RAM, không ghi xuống đĩa.
        self._events: deque[dict[str, Any]] = deque(maxlen=RAM_EVENT_LOG_SIZE)
        self._bytes_staged = 0
        self._bytes_wiped = 0
        self._seq = 0

    # ------------------------------------------------------------------ #
    # Nhật ký RAM (phục vụ Dashboard)                                     #
    # ------------------------------------------------------------------ #

    def _log_event(
        self,
        action: str,
        tx_id: str,
        *,
        size_bytes: int = 0,
        detail: str = "",
    ) -> None:
        """Ghi một dòng nhật ký RAM. Caller phải đang giữ self._lock."""
        self._seq += 1
        self._events.append(
            {
                "seq": self._seq,
                "ts": time.time(),
                "action": action,
                "tx_id": tx_id,
                "size_bytes": size_bytes,
                "detail": detail,
            }
        )

    def _entry_size(self, entry: dict[str, Any]) -> int:
        total = 0
        for field in _SENSITIVE_FIELDS:
            val = entry.get(field)
            if isinstance(val, (bytearray, bytes)):
                total += len(val)
        return total

    def ram_snapshot(self) -> dict[str, Any]:
        """
        Ảnh chụp trạng thái RAM cho Dashboard Broker.

        Trả về:
          - entries:  các vùng đang chiếm RAM, kèm thời điểm hết hạn
          - events:   nhật ký ghi/xoá gần đây (STAGE / WIPE / EXPIRE)
          - totals:   tổng byte đã lên RAM và tổng byte đã được ghi đè 0x00
        """
        now = time.time()
        with self._lock:
            entries = []
            for tx_id, entry in self._data.items():
                entries.append(
                    {
                        "tx_id": tx_id,
                        "recipient": entry["recipient"],
                        "size_bytes": self._entry_size(entry),
                        "ttl_remaining": max(0, int(entry["expires_at"] - now)),
                    }
                )
            entries.sort(key=lambda e: e["ttl_remaining"])

            return {
                "entries": entries,
                "events": list(self._events),
                "totals": {
                    "bytes_staged": self._bytes_staged,
                    "bytes_wiped": self._bytes_wiped,
                    "active_bytes": self.approx_ram_bytes(),
                    # VÁ #6: lấy từ backend, không phải hằng số.
                    "disk_writes": self.disk_write_count(),
                },
            }

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

            size = self._entry_size(self._data[tx_id])
            self._bytes_staged += size
            self._log_event(
                "STAGE",
                tx_id,
                size_bytes=size,
                detail=f"Ghi {size} byte lên RAM cho {recipient[:10]}...",
            )

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
                self._purge_one(tx_id, reason="EXPIRE")
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

    def _purge_one(self, tx_id: str, reason: str = "WIPE") -> bool:
        """
        Ghi đè 0x00 lên các trường nhạy cảm rồi xoá khỏi dict.
        Hàm nội bộ - caller phải đang giữ self._lock.

        `reason` chỉ dùng cho nhật ký Dashboard: "WIPE" (chủ động) hoặc
        "EXPIRE" (do hết TTL). Cả hai đều gọi cùng một cơ chế ghi đè 0x00.
        """
        entry = self._data.pop(tx_id, None)
        if entry is None:
            return False

        size = self._entry_size(entry)
        for field in _SENSITIVE_FIELDS:
            _wipe(entry.get(field))

        entry.clear()

        self._bytes_wiped += size
        self._log_event(
            reason,
            tx_id,
            size_bytes=size,
            detail=f"Ghi đè {size} byte bằng 0x00 rồi giải phóng",
        )
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
                self._purge_one(tx_id, reason="EXPIRE")

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

    def disk_write_count(self) -> int:
        """VÁ #6: số lần thực sự ghi payload xuống ổ cứng.

        Với InMemoryStore con số này LUÔN bằng 0 — và đó là sự thật kiểm chứng
        được: toàn bộ lớp này chỉ dùng dict/bytearray trên heap, không có một
        lời gọi open()/write() nào. Trước đây `disk_writes: 0` là hằng số viết
        cứng trong `stats()` nên nếu ai đổi backend sang Redis thì Dashboard
        VẪN báo 0 — tức là "nói dối bằng thiết kế". Nay mỗi store tự khai báo.
        """
        return 0

    def stats(self) -> dict[str, int]:
        """Số liệu cho Dashboard Broker."""
        with self._lock:
            return {
                "active_payloads": self.active_count(),
                "total_staged": self.total_staged,
                "total_retrieved": self.total_retrieved,
                "total_purged_expired": self.total_purged_expired,
                # VÁ #6: lấy từ backend thật, không phải hằng số.
                "disk_writes": self.disk_write_count(),
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
    """Backend lưu payload trên Redis — GHI XUỐNG Ổ CỨNG.

    VÁ #6: backend này TỒN TẠI để demo tính sẵn sàng đa máy, nhưng nó MẶC ĐỊNH
    BỊ CHẶN. Lý do: CloakShare cam kết Zero-Log (payload chỉ sống trên RAM).
    Redis persist data ra disk (RDB/AOF) nên nó vi phạm trực tiếp cam kết đó.
    Trước đây chỉ cần set `REDIS_URL` là app âm thầm chuyển sang Redis — không
    hỏi, không cảnh báo, và Dashboard vẫn báo `disk_writes: 0` trong khi
    toàn bộ payload đã nằm trên ổ cứng. Nay phải set THÊM
    `ALLOW_REDIS_STORE=1` và phải đọc được cảnh báo rõ ràng.
    """

    def __init__(self, url: str):
        self.client = redis.Redis.from_url(url, decode_responses=True)
        self.start_time = time.time()
        self.total_staged = 0
        self.total_retrieved = 0
        self.total_purged_expired = 0
        # VÁ #6: đếm thật số lần ghi xuống disk. KHÔNG phải hằng số 0.
        self._disk_writes = 0

    def disk_write_count(self) -> int:
        """Số payload đã thực sự được Redis persist xuống ổ cứng."""
        return self._disk_writes

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
        # VÁ #6: mỗi lần setex là một lần ghi xuống ổ cứng của Redis.
        self._disk_writes += 1
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
            "disk_writes": self.disk_write_count(),
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


# VÁ #6: Redis chỉ được bật khi TỰ NGUYỆN khai báo rõ ràng.
# Có REDIS_URL nhưng KHÔNG có ALLOW_REDIS_STORE=1 -> CRASH ngay lúc import
# (fail-fast) thay vì âm thầm hạ cấp Zero-Log. Một lỗi cấu hình chuyển backend
# từ RAM sang ổ cứng là vi phạm cam kết bảo mật cốt lõi, phải được phát hiện
# ngay, không thể im lặng.
ALLOW_REDIS_STORE = os.environ.get("ALLOW_REDIS_STORE", "").strip().lower() in (
    "1",
    "true",
    "yes",
    "on",
)

# Khởi tạo store: MẶC ĐỊNH InMemory (Zero-Log). Redis chỉ dùng khi được cho phép.
#
# Thứ tự kiểm tra là CÓ CHỦ Ý: kill switch được xét TRƯỚC khi kiểm tra thư viện
# `redis` có cài hay không. Nếu đảo lại, một máy thiếu thư viện `redis` sẽ khiến
# app "chạy được" bằng InMemoryStore trong khi người vận hành tưởng là đang chạy
# Redis -> cấu hình sai bị che giấu. Mọi cấu hình động tới ổ cứng phải FAIL-FAST.
redis_url = os.environ.get("REDIS_URL")
if redis_url and not ALLOW_REDIS_STORE:
    raise RuntimeError(
        "\n"
        "=" * 72 + "\n"
        "  TỪ CHỐI KHỞI ĐỘNG: REDIS_URL được set nhưng chưa bật ALLOW_REDIS_STORE.\n"
        "\n"
        "  Redis persist payload xuống Ổ CỨNG (RDB/AOF), điều này vi phạm\n"
        "  cam kết Zero-Log của CloakShare. Nếu bạn thực sự hiểu và chấp nhận\n"
        "  rủi ro đó, hãy khai báo tường minh:\n"
        "      set ALLOW_REDIS_STORE=1\n"
        "\n"
        "  Ngược lại, hãy bỏ REDIS_URL để Broker chạy chế độ Zero-Log thuần.\n"
        "=" * 72
    )
elif redis_url and not redis:
    raise RuntimeError(
        "\n"
        "=" * 72 + "\n"
        "  TỪ CHỐI KHỞI ĐỘNG: đã bật ALLOW_REDIS_STORE=1 nhưng thư viện 'redis'\n"
        "  chưa được cài (pip install redis).\n"
        "\n"
        "  KHÔNG tự động hạ cấp về InMemoryStore: làm vậy sẽ khiến bạn tưởng\n"
        "  payload đang nằm trên Redis trong khi thực tế chỉ nằm trên RAM.\n"
        "  Hãy cài 'redis' hoặc bỏ cả REDIS_URL và ALLOW_REDIS_STORE.\n"
        "=" * 72
    )
elif redis_url:
    print(f"[i] Đang kết nối tới Redis Store tại: {redis_url}")
    print(
        "[!] CẢNH BÁO: Redis GHI PAYLOAD XUỐNG Ổ CỨNG. Chế độ này KHÔNG còn là "
        "Zero-Log thuần túy. Số lần ghi disk được đếm và hiển thị tại /api/v1/stats."
    )
    store = RedisStore(redis_url)
else:
    store = InMemoryStore()

