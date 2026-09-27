"""
tests/test_broker_api.py

Test cho Zero-Log Broker (Issue #7, #8, #18, #20).
Chạy: pytest tests/test_broker_api.py -v
"""

import base64
import sys
import time
from pathlib import Path
from unittest.mock import patch

import pytest
from eth_account import Account
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from broker.main import app  # noqa: E402
from broker.memory_store import InMemoryStore, store  # noqa: E402
from engine.wallet_auth import Web3Auth  # noqa: E402

# Tài khoản ví mẫu cố định cho test
TEST_BUYER = Account.create()
TEST_BUYER_ADDR = TEST_BUYER.address
TEST_BUYER_KEY = TEST_BUYER.key.hex()

OTHER_USER = Account.create()
OTHER_USER_ADDR = OTHER_USER.address
OTHER_USER_KEY = OTHER_USER.key.hex()


@pytest.fixture()
def client():
    """TestClient, dọn sạch store trước và sau mỗi test."""
    store.purge_all()
    with TestClient(app) as c:
        yield c
    store.purge_all()


def _b64(raw: bytes) -> str:
    return base64.b64encode(raw).decode("ascii")


def make_payload(
    tx_id: str = "tx-demo-001",
    recipient: str = TEST_BUYER_ADDR,
    ttl_seconds: int = 300,
) -> dict:
    return {
        "tx_id": tx_id,
        "recipient": recipient,
        "iv": _b64(b"0123456789abcdef"),
        "wrapped_key": _b64(b"wrapped-session-key-rsa-oaep"),
        "ciphertext": _b64(b"encrypted-file-content-aes-128-cbc"),
        "signature": _b64(b"rsa-pss-sha256-signature"),
        "ttl_seconds": ttl_seconds,
    }


def make_auth_headers(
    tx_id: str,
    private_key: str = TEST_BUYER_KEY,
    address: str = TEST_BUYER_ADDR,
    timestamp: int | None = None,
) -> dict:
    ts, sig = Web3Auth.sign_retrieve_request(tx_id, private_key, timestamp)
    return {
        "X-Wallet-Address": address,
        "X-Timestamp": str(ts),
        "X-Signature": sig,
    }


# ------------------------------------------------------------------ #
# POST /api/v1/stage                                                  #
# ------------------------------------------------------------------ #

def test_stage_returns_201(client):
    resp = client.post("/api/v1/stage", json=make_payload())

    assert resp.status_code == 201
    body = resp.json()
    assert body["tx_id"] == "tx-demo-001"
    assert body["status"] == "staged"
    assert body["expires_at"] > time.time()


def test_stage_rejects_missing_field(client):
    bad = make_payload()
    del bad["ciphertext"]

    resp = client.post("/api/v1/stage", json=bad)
    assert resp.status_code == 422  # Pydantic validation error


def test_stage_rejects_invalid_ttl(client):
    bad = make_payload()
    bad["ttl_seconds"] = 0  # phải > 0

    resp = client.post("/api/v1/stage", json=bad)
    assert resp.status_code == 422


# ------------------------------------------------------------------ #
# GET /api/v1/retrieve/{tx_id} & Web3 SIWE Authentication            #
# ------------------------------------------------------------------ #

def test_retrieve_without_auth_headers_returns_422(client):
    """Không có header xác thực Web3 sẽ bị từ chối với 422."""
    payload = make_payload()
    client.post("/api/v1/stage", json=payload)

    resp = client.get(f"/api/v1/retrieve/{payload['tx_id']}")
    assert resp.status_code == 422


def test_retrieve_returns_full_payload(client):
    """Xác thực ví Web3 hợp lệ từ đúng Recipient sẽ lấy được payload."""
    payload = make_payload()
    client.post("/api/v1/stage", json=payload)

    headers = make_auth_headers(payload["tx_id"])
    resp = client.get(f"/api/v1/retrieve/{payload['tx_id']}", headers=headers)

    assert resp.status_code == 200
    body = resp.json()
    assert body["tx_id"] == payload["tx_id"]
    assert body["recipient"] == payload["recipient"]
    assert body["iv"] == payload["iv"]
    assert body["wrapped_key"] == payload["wrapped_key"]
    assert body["ciphertext"] == payload["ciphertext"]
    assert body["signature"] == payload["signature"]


def test_retrieve_with_invalid_signature_returns_401(client):
    """Chữ ký không khớp với message/ví sẽ bị 401 Unauthorized."""
    payload = make_payload()
    client.post("/api/v1/stage", json=payload)

    headers = make_auth_headers(payload["tx_id"])
    headers["X-Signature"] = "0x" + "00" * 65  # Signature giả

    resp = client.get(f"/api/v1/retrieve/{payload['tx_id']}", headers=headers)
    assert resp.status_code == 401


def test_retrieve_with_drifted_timestamp_returns_401(client):
    """Timestamp quá hạn (> 60 giây) chống Replay Attack bị 401."""
    payload = make_payload()
    client.post("/api/v1/stage", json=payload)

    old_timestamp = int(time.time()) - 120
    headers = make_auth_headers(payload["tx_id"], timestamp=old_timestamp)

    resp = client.get(f"/api/v1/retrieve/{payload['tx_id']}", headers=headers)
    assert resp.status_code == 401


def test_retrieve_with_wrong_recipient_returns_403(client):
    """Người khác (không phải recipient được chỉ định) cố rút file bị 403 Forbidden."""
    payload = make_payload(recipient=TEST_BUYER_ADDR)
    client.post("/api/v1/stage", json=payload)

    headers = make_auth_headers(
        payload["tx_id"],
        private_key=OTHER_USER_KEY,
        address=OTHER_USER_ADDR,
    )
    resp = client.get(f"/api/v1/retrieve/{payload['tx_id']}", headers=headers)
    assert resp.status_code == 403


def test_retrieve_unknown_tx_returns_404(client):
    headers = make_auth_headers("khong-ton-tai")
    resp = client.get("/api/v1/retrieve/khong-ton-tai", headers=headers)
    assert resp.status_code == 404


def test_retrieve_expired_payload_returns_404(client):
    payload = make_payload(tx_id="tx-short-ttl", ttl_seconds=1)
    client.post("/api/v1/stage", json=payload)

    time.sleep(1.2)

    headers = make_auth_headers("tx-short-ttl")
    resp = client.get("/api/v1/retrieve/tx-short-ttl", headers=headers)
    assert resp.status_code == 404


def test_retrieve_with_burn_after_read(client):
    """Khi burn=true, payload bị huỷ khỏi RAM ngay sau khi đọc."""
    payload = make_payload(tx_id="tx-burn-check")
    client.post("/api/v1/stage", json=payload)

    headers = make_auth_headers("tx-burn-check")
    resp = client.get("/api/v1/retrieve/tx-burn-check?burn=true", headers=headers)
    assert resp.status_code == 200

    # Lần gọi tiếp theo sẽ trả về 404 vì đã bị burn khỏi RAM
    resp_again = client.get("/api/v1/retrieve/tx-burn-check", headers=headers)
    assert resp_again.status_code == 404


def test_delete_payload_endpoint(client):
    """Xoá chủ động payload qua DELETE /api/v1/payload/{tx_id}."""
    payload = make_payload(tx_id="tx-del-test")
    client.post("/api/v1/stage", json=payload)

    headers = make_auth_headers("tx-del-test")
    resp_del = client.delete("/api/v1/payload/tx-del-test", headers=headers)
    assert resp_del.status_code == 200

    resp_get = client.get("/api/v1/retrieve/tx-del-test", headers=headers)
    assert resp_get.status_code == 404


# ------------------------------------------------------------------ #
# GET /api/v1/inbox                                                  #
# ------------------------------------------------------------------ #

def test_inbox_returns_pending_messages_for_recipient(client):
    p1 = make_payload(tx_id="tx-inbox-1", recipient=TEST_BUYER_ADDR)
    p2 = make_payload(tx_id="tx-inbox-2", recipient=TEST_BUYER_ADDR)
    p3 = make_payload(tx_id="tx-inbox-3", recipient=OTHER_USER_ADDR)

    client.post("/api/v1/stage", json=p1)
    client.post("/api/v1/stage", json=p2)
    client.post("/api/v1/stage", json=p3)

    now_ts = int(time.time())
    msg = f"CloakShare Inbox Access:{now_ts}"
    sig = Web3Auth.sign_challenge(TEST_BUYER_KEY, msg)
    headers = {
        "X-Wallet-Address": TEST_BUYER_ADDR,
        "X-Timestamp": str(now_ts),
        "X-Signature": sig,
    }

    resp = client.get("/api/v1/inbox", headers=headers)
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 2
    tx_ids = {it["tx_id"] for it in items}
    assert tx_ids == {"tx-inbox-1", "tx-inbox-2"}


# ------------------------------------------------------------------ #
# DoD: payload chỉ nằm trên RAM, không ghi ổ cứng                     #
# ------------------------------------------------------------------ #

def test_payload_stored_in_ram_dictionary(client):
    """Payload phải nằm trong dictionary in-memory của store."""
    payload = make_payload(tx_id="tx-ram-check")
    client.post("/api/v1/stage", json=payload)

    assert "tx-ram-check" in store._data
    assert store.exists("tx-ram-check") is True


def test_no_open_call_during_stage_and_retrieve(client):
    """
    DoD: không gọi open() ghi ổ cứng trong toàn bộ luồng xử lý payload.
    Patch builtins.open để phát hiện mọi truy cập file.
    """
    payload = make_payload(tx_id="tx-no-disk")
    headers = make_auth_headers("tx-no-disk")

    real_open = open
    calls = []

    def spy_open(*args, **kwargs):
        calls.append(args[0] if args else None)
        return real_open(*args, **kwargs)

    with patch("builtins.open", side_effect=spy_open):
        client.post("/api/v1/stage", json=payload)
        client.get("/api/v1/retrieve/tx-no-disk", headers=headers)

    assert calls == [], f"Phat hien ghi/doc file: {calls}"


def test_stats_reports_zero_disk_writes_and_ram_bytes(client):
    client.post("/api/v1/stage", json=make_payload())

    resp = client.get("/api/v1/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert data["disk_writes"] == 0
    assert data["active_payloads"] >= 1
    assert data["approx_ram_bytes"] > 0
    assert "uptime_seconds" in data


# ------------------------------------------------------------------ #
# DoD: task nền tự dọn payload quá hạn TTL                            #
# ------------------------------------------------------------------ #

def test_purge_expired_removes_only_expired():
    s = InMemoryStore()
    s.stage("expired", "0x1", "I", "W", "C", "S", ttl_seconds=1)
    s.stage("alive", "0x2", "I", "W", "C", "S", ttl_seconds=300)

    time.sleep(1.2)
    purged = s.purge_expired()

    assert purged == 1
    assert s.exists("expired") is False
    assert s.exists("alive") is True


def test_purge_wipes_sensitive_bytes_with_zeros():
    """
    Sau khi purge, vùng nhớ chứa ciphertext phải bị ghi đè 0x00
    (tương đương memset bên C) chứ không chỉ xoá key khỏi dict.
    """
    s = InMemoryStore()
    s.stage("tx-wipe", "0x1", "IV", "WK", "SECRET-CIPHERTEXT", "SIG", 300)

    ref = s._data["tx-wipe"]["ciphertext"]  # giữ tham chiếu tới bytearray
    assert bytes(ref) == b"SECRET-CIPHERTEXT"

    s.purge("tx-wipe")

    assert bytes(ref) == b"\x00" * len(b"SECRET-CIPHERTEXT")


def test_restage_same_tx_id_wipes_old_payload():
    s = InMemoryStore()
    s.stage("dup", "0x1", "I", "W", "OLD", "S", 300)
    old_ref = s._data["dup"]["ciphertext"]

    s.stage("dup", "0x1", "I", "W", "NEW", "S", 300)

    assert bytes(old_ref) == b"\x00" * 3
    assert s.retrieve("dup")["ciphertext"] == "NEW"


# ------------------------------------------------------------------ #
# Stats & Health                                                      #
# ------------------------------------------------------------------ #

def test_stats_counters():
    s = InMemoryStore()
    s.stage("a", "0x", "I", "W", "C", "S", 300)
    s.stage("b", "0x", "I", "W", "C", "S", 300)
    s.retrieve("a")

    stats = s.stats()
    assert stats["active_payloads"] == 2
    assert stats["total_staged"] == 2
    assert stats["total_retrieved"] == 1
    assert stats["approx_ram_bytes"] > 0


def test_health_endpoint(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
