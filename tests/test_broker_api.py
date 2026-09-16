"""
tests/test_broker_api.py

Test cho Zero-Log Broker (Issue #7).
Chạy: pytest tests/test_broker_api.py -v

Yêu cầu: pip install fastapi httpx pytest
(TestClient của FastAPI cần httpx)
"""

import base64
import sys
import time
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from broker.main import app  # noqa: E402
from broker.memory_store import InMemoryStore, store  # noqa: E402


@pytest.fixture()
def client():
    """TestClient, dọn sạch store trước và sau mỗi test."""
    store.purge_all()
    with TestClient(app) as c:
        yield c
    store.purge_all()


def _b64(raw: bytes) -> str:
    return base64.b64encode(raw).decode("ascii")


def make_payload(tx_id: str = "tx-demo-001", ttl_seconds: int = 300) -> dict:
    return {
        "tx_id": tx_id,
        "recipient": "0x1234567890abcdef1234567890abcdef12345678",
        "iv": _b64(b"0123456789abcdef"),
        "wrapped_key": _b64(b"wrapped-session-key-rsa-oaep"),
        "ciphertext": _b64(b"encrypted-file-content-aes-128-cbc"),
        "signature": _b64(b"rsa-pss-sha256-signature"),
        "ttl_seconds": ttl_seconds,
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
# GET /api/v1/retrieve/{tx_id}                                        #
# ------------------------------------------------------------------ #

def test_retrieve_returns_full_payload(client):
    payload = make_payload()
    client.post("/api/v1/stage", json=payload)

    resp = client.get(f"/api/v1/retrieve/{payload['tx_id']}")

    assert resp.status_code == 200
    body = resp.json()
    assert body["tx_id"] == payload["tx_id"]
    assert body["recipient"] == payload["recipient"]
    assert body["iv"] == payload["iv"]
    assert body["wrapped_key"] == payload["wrapped_key"]
    assert body["ciphertext"] == payload["ciphertext"]
    assert body["signature"] == payload["signature"]


def test_retrieve_unknown_tx_returns_404(client):
    resp = client.get("/api/v1/retrieve/khong-ton-tai")
    assert resp.status_code == 404


def test_retrieve_expired_payload_returns_404(client):
    payload = make_payload(tx_id="tx-short-ttl", ttl_seconds=1)
    client.post("/api/v1/stage", json=payload)

    time.sleep(1.2)

    resp = client.get("/api/v1/retrieve/tx-short-ttl")
    assert resp.status_code == 404


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

    real_open = open
    calls = []

    def spy_open(*args, **kwargs):
        calls.append(args[0] if args else None)
        return real_open(*args, **kwargs)

    with patch("builtins.open", side_effect=spy_open):
        client.post("/api/v1/stage", json=payload)
        client.get("/api/v1/retrieve/tx-no-disk")

    assert calls == [], f"Phat hien ghi/doc file: {calls}"


def test_stats_reports_zero_disk_writes(client):
    client.post("/api/v1/stage", json=make_payload())

    resp = client.get("/api/v1/stats")
    assert resp.status_code == 200
    assert resp.json()["disk_writes"] == 0


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
# Stats                                                               #
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


def test_health_endpoint(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
