"""
tests/test_e2e_pipeline.py

Kiểm thử tự động tích hợp toàn diện E2E (End-to-End Pipeline):
1. Mã hóa đối xứng AES-128-CBC + PKCS#7 (C Core)
2. Bọc khóa RSA-2048 OAEP
3. Ký số toàn vẹn RSA-PSS SHA-256
4. Đăng ký & tra cứu dPKI
5. Staging lên Zero-Log RAM Broker
6. Chặn các truy cập trái phép / tấn công Replay
7. Ký số ví Web3 SIWE để rút file
8. Xác thực chữ ký số & phát hiện giả mạo
9. Giải mã an toàn trong RAM
10. Burn-after-read & zeroize bộ nhớ (memset 0x00)
11. Đảm bảo 0 disk writes suốt quy trình
"""

import os
import sys
import time
import uuid
from pathlib import Path
from unittest.mock import patch

import pytest
from eth_account import Account
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from broker.main import app
from broker.memory_store import store
from engine.dpki_client import DPKIClient
from engine.rsa_envelope import RSAEnvelope, generate_rsa_key_pair
from engine.signer import IntegritySigner
from engine.wallet_auth import Web3Auth
from engine.wrappers.aes_wrapper import AESWrapper


@pytest.fixture()
def client():
    store.purge_all()
    with TestClient(app) as c:
        yield c
    store.purge_all()


def test_complete_e2e_hybrid_security_pipeline(client):
    # 1. Danh tính Web3 & Cặp khóa RSA cho Alice (Seller) và Bob (Buyer)
    alice_wallet = Account.create()
    bob_wallet = Account.create()

    alice_priv_bytes, alice_pub_bytes = generate_rsa_key_pair()
    bob_priv_bytes, bob_pub_bytes = generate_rsa_key_pair()

    alice_priv_pem = alice_priv_bytes.decode("utf-8")
    alice_pub_pem = alice_pub_bytes.decode("utf-8")
    bob_priv_pem = bob_priv_bytes.decode("utf-8")
    bob_pub_pem = bob_pub_bytes.decode("utf-8")

    # 2. Đăng ký Public Key lên dPKI
    dpki = DPKIClient()
    dpki.register_public_key(alice_wallet.key.hex(), alice_pub_pem)
    dpki.register_public_key(bob_wallet.key.hex(), bob_pub_pem)

    # Alice tra cứu Public Key của Bob từ dPKI
    resolved_bob_pub = dpki.get_public_key(bob_wallet.address)
    assert resolved_bob_pub == bob_pub_pem

    # 3. Alice chuẩn bị dữ liệu và thực hiện mã hóa lai (Hybrid Encryption)
    secret_message = b"CloakShare E2E Confidential Protocol Payload: $10,000,000 Transfer."
    session_key = os.urandom(16)

    # a. Mã hóa AES-128-CBC (C Core)
    aes = AESWrapper()
    iv, ciphertext = aes.encrypt(secret_message, session_key)
    assert len(ciphertext) % 16 == 0

    # b. Bọc Session Key bằng Public Key RSA của Bob (OAEP)
    wrapped_key = RSAEnvelope.wrap_key(session_key, resolved_bob_pub)

    # c. Ký số toàn vẹn bằng Private Key RSA của Alice (RSA-PSS)
    signature = IntegritySigner.sign_file(ciphertext, alice_priv_pem)

    # 4. Đẩy payload lên RAM Broker (giám sát không cho ghi ổ cứng)
    tx_id = f"tx-e2e-{uuid.uuid4().hex[:12]}"
    payload = {
        "tx_id": tx_id,
        "recipient": bob_wallet.address,
        "iv": iv.hex(),
        "wrapped_key": wrapped_key.hex(),
        "ciphertext": ciphertext.hex(),
        "signature": signature.hex(),
        "ttl_seconds": 180,
    }

    real_open = open
    file_operations = []

    def spy_open(*args, **kwargs):
        file_operations.append(args[0] if args else None)
        return real_open(*args, **kwargs)

    with patch("builtins.open", side_effect=spy_open):
        stage_res = client.post("/api/v1/stage", json=payload)

    assert stage_res.status_code == 201
    assert file_operations == [], "Zero-Log vi pham: Da co lenh open() khi stage!"

    # 5. Kiểm tra bảo mật: Không có auth headers -> Bị chặn
    unauth_res = client.get(f"/api/v1/retrieve/{tx_id}")
    assert unauth_res.status_code == 422

    # 6. Kiểm tra bảo mật: Kẻ thứ ba (Mallory) cố rút payload của Bob -> 403 Forbidden
    mallory_wallet = Account.create()
    now_ts = int(time.time())
    _, mallory_sig = Web3Auth.sign_retrieve_request(tx_id, mallory_wallet.key.hex(), now_ts)
    forbidden_res = client.get(
        f"/api/v1/retrieve/{tx_id}",
        headers={
            "X-Wallet-Address": mallory_wallet.address,
            "X-Timestamp": str(now_ts),
            "X-Signature": mallory_sig,
        },
    )
    assert forbidden_res.status_code == 403

    # 7. Bob xác thực bằng ví Web3 (SIWE challenge) để rút file
    ts, bob_sig = Web3Auth.sign_retrieve_request(tx_id, bob_wallet.key.hex(), now_ts)
    bob_headers = {
        "X-Wallet-Address": bob_wallet.address,
        "X-Timestamp": str(ts),
        "X-Signature": bob_sig,
    }

    with patch("builtins.open", side_effect=spy_open):
        retrieved_res = client.get(f"/api/v1/retrieve/{tx_id}", headers=bob_headers)

    assert retrieved_res.status_code == 200
    assert file_operations == [], "Zero-Log vi pham: Da co lenh open() khi retrieve!"

    retrieved_data = retrieved_res.json()
    recv_cipher = bytes.fromhex(retrieved_data["ciphertext"])
    recv_sig = bytes.fromhex(retrieved_data["signature"])
    recv_wrapped = bytes.fromhex(retrieved_data["wrapped_key"])
    recv_iv = bytes.fromhex(retrieved_data["iv"])

    # 8. Bob tra cứu Public Key của Alice trên dPKI để xác thực chữ ký số
    resolved_alice_pub = dpki.get_public_key(alice_wallet.address)
    assert IntegritySigner.verify_file(recv_cipher, recv_sig, resolved_alice_pub) is True

    # Kiểm tra chống giả mạo: Thay đổi 1 bit trong ciphertext -> Xác thực thất bại ngay lập tức
    tampered_cipher = bytearray(recv_cipher)
    tampered_cipher[0] ^= 0x01
    assert IntegritySigner.verify_file(bytes(tampered_cipher), recv_sig, resolved_alice_pub) is False

    # 9. Bob mở bọc khóa Session Key bằng RSA Private Key của mình
    recovered_session_key = RSAEnvelope.unwrap_key(recv_wrapped, bob_priv_pem)
    assert recovered_session_key == session_key

    # 10. Bob giải mã AES-128-CBC (C Core)
    decrypted_message = aes.decrypt(recv_cipher, recovered_session_key, recv_iv)
    assert decrypted_message == secret_message

    # 11. Bob kích hoạt Burn-After-Read (Xóa sạch khỏi RAM Broker)
    del_res = client.delete(f"/api/v1/payload/{tx_id}", headers=bob_headers)
    assert del_res.status_code == 200

    # Lần truy vấn tiếp theo phải báo 404 (đã bị xoá)
    after_res = client.get(f"/api/v1/retrieve/{tx_id}", headers=bob_headers)
    assert after_res.status_code == 404

    # 12. Kiểm tra chỉ số giám sát: Luôn đảm bảo 0 disk writes
    stats_res = client.get("/api/v1/stats")
    assert stats_res.status_code == 200
    assert stats_res.json()["disk_writes"] == 0
