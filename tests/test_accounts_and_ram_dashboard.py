"""
tests/test_accounts_and_ram_dashboard.py

Tests for:
1. engine.accounts (PBKDF2-HMAC-SHA256 & Fernet encrypted local storage, register, login, delete)
2. broker GET /api/v1/ram dashboard endpoint (RAM snapshot, STAGE/WIPE/EXPIRE events, zero disk writes)
"""

import base64
import sys
from pathlib import Path
import pytest
from eth_account import Account
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine import accounts
from broker.main import app
from broker.memory_store import store
from engine.wallet_auth import Web3Auth


@pytest.fixture()
def isolated_accounts_dir(tmp_path, monkeypatch):
    """Isolate accounts.json in a temp directory for safe testing."""
    test_acc_dir = tmp_path / ".cloakshare"
    test_acc_file = test_acc_dir / "accounts.json"
    monkeypatch.setattr(accounts, "ACCOUNTS_FILE", test_acc_file)
    return test_acc_file


@pytest.fixture()
def client():
    store.purge_all()
    with TestClient(app) as c:
        yield c
    store.purge_all()


def _b64(raw: bytes) -> str:
    return base64.b64encode(raw).decode("ascii")


def test_account_registration_and_authentication(isolated_accounts_dir):
    """Test register, authenticate, and password verification with PBKDF2 & Fernet."""
    test_wallet = Account.create()
    pk_hex = test_wallet.key.hex()
    addr = test_wallet.address

    # Register alice
    meta = accounts.register("alice", "MySecretPassword123!", pk_hex, addr)
    assert meta["address"].lower() == addr.lower()
    assert "salt" in meta
    assert "verifier" in meta
    assert "encrypted_key" in meta
    # Ensure plaintext private key is NOT in stored dict
    assert "private_key" not in meta

    # Authenticate with correct password
    dec_pk, dec_addr = accounts.authenticate("alice", "MySecretPassword123!")
    assert dec_pk == pk_hex
    assert dec_addr.lower() == addr.lower()

    # Authenticate with wrong password -> raises AuthError
    with pytest.raises(accounts.AuthError):
        accounts.authenticate("alice", "WrongPassword999!")

    # Authenticate nonexistent user -> raises AuthError
    with pytest.raises(accounts.AuthError):
        accounts.authenticate("ghost_user", "AnyPassword123!")


def test_account_duplicate_and_list_and_delete(isolated_accounts_dir):
    """Test duplicate check, listing public accounts, and deleting accounts."""
    w1 = Account.create()
    w2 = Account.create()
    accounts.register("user_one", "PasswordValid1!", w1.key.hex(), w1.address)
    accounts.register("user_two", "PasswordValid2!", w2.key.hex(), w2.address)

    # Duplicate registration should raise UsernameTaken
    with pytest.raises(accounts.UsernameTaken):
        accounts.register("user_one", "OtherPassword123!", w1.key.hex(), w1.address)

    # Weak password should raise WeakPassword
    with pytest.raises(accounts.WeakPassword):
        accounts.register("user_three", "short", w1.key.hex(), w1.address)

    # List accounts - must not expose private keys
    acc_list = accounts.list_accounts()
    assert len(acc_list) == 2
    for item in acc_list:
        assert "username" in item
        assert "address" in item
        assert "encrypted_key" not in item
        assert "verifier" not in item

    # Delete user_one with correct password
    accounts.delete_account("user_one", "PasswordValid1!")
    assert len(accounts.list_accounts()) == 1

    # Delete non-existent user raises AuthError
    with pytest.raises(accounts.AuthError):
        accounts.delete_account("nonexistent", "SomePassword123!")


def test_broker_ram_snapshot_endpoint(client):
    """Test GET /api/v1/ram returns active entries, event stream, and memory counters."""
    # 1. Initially empty
    res0 = client.get("/api/v1/ram")
    assert res0.status_code == 200
    data0 = res0.json()
    assert "entries" in data0
    assert "events" in data0
    assert "totals" in data0
    assert data0["totals"]["disk_writes"] == 0
    assert len(data0["entries"]) == 0

    # 2. Stage a payload
    test_receiver = Account.create()
    payload = {
        "tx_id": "tx-ram-test-001",
        "recipient": test_receiver.address,
        "iv": _b64(b"0123456789abcdef"),
        "wrapped_key": _b64(b"wrapped-key-rsa-oaep"),
        "ciphertext": _b64(b"confidential-data-here"),
        "signature": _b64(b"signature-bytes"),
        "ttl_seconds": 60,
    }
    stage_res = client.post("/api/v1/stage", json=payload)
    assert stage_res.status_code == 201

    # 3. Check RAM snapshot after staging
    res1 = client.get("/api/v1/ram")
    assert res1.status_code == 200
    data1 = res1.json()
    assert len(data1["entries"]) == 1
    assert data1["entries"][0]["tx_id"] == "tx-ram-test-001"
    assert data1["entries"][0]["recipient"] == test_receiver.address
    assert data1["entries"][0]["ttl_remaining"] <= 60
    assert data1["totals"]["bytes_staged"] > 0
    assert data1["totals"]["active_bytes"] > 0
    assert data1["totals"]["disk_writes"] == 0

    # Verify event log recorded STAGE
    assert len(data1["events"]) >= 1
    stage_event = data1["events"][-1]
    assert stage_event["action"] == "STAGE"
    assert stage_event["tx_id"] == "tx-ram-test-001"

    # 4. Retrieve payload with burn=true (Burn-After-Read with 0x00 wipe)
    ts, sig = Web3Auth.sign_retrieve_request("tx-ram-test-001", test_receiver.key.hex())
    ret_res = client.get(
        "/api/v1/retrieve/tx-ram-test-001",
        params={"burn": "true"},
        headers={
            "X-Wallet-Address": test_receiver.address,
            "X-Timestamp": str(ts),
            "X-Signature": sig,
        },
    )
    assert ret_res.status_code == 200

    # 5. Check RAM snapshot after retrieval
    res2 = client.get("/api/v1/ram")
    assert res2.status_code == 200
    data2 = res2.json()
    assert len(data2["entries"]) == 0
    assert data2["totals"]["active_bytes"] == 0
    assert data2["totals"]["bytes_wiped"] > 0

    # Verify event log recorded WIPE
    wipe_events = [e for e in data2["events"] if e["action"] == "WIPE"]
    assert len(wipe_events) >= 1
    assert wipe_events[-1]["tx_id"] == "tx-ram-test-001"
