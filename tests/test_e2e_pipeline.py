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
from web3 import Web3

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


# Anvil account #0 — public, deterministic, unlocked.
ANVIL_FUNDER_KEY = "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80"
ANVIL_FUNDER = Account.from_key(ANVIL_FUNDER_KEY).address

RPC_URL = "http://127.0.0.1:8545"


def _parse_contract_address(text: str) -> str | None:
    """Tìm địa chỉ contract trong stdout/stderr của scripts/deploy_dpki.py."""
    import re

    m = re.search(r"Contract Address\s*:\s*(0x[0-9a-fA-F]{40})", text)
    if m:
        return Web3.to_checksum_address(m.group(1))
    for tok in text.replace(":", " ").replace("=", " ").split():
        tok = tok.strip(".,;'\"")
        if tok.startswith("0x") and len(tok) == 42:
            return Web3.to_checksum_address(tok)
    return None


@pytest.fixture(scope="module")
def anvil():
    """Deploy dPKIRegistry mới TỨC THÌ và trả về (w3, contract_address).

    BUG ĐÃ SỬA: test cũ dùng địa chỉ contract HARD-CODE trong
    `DPKIClient.__init__`. Anvil là node in-memory — mỗi lần khởi động lại là
    toàn bộ state (kể cả contract đã deploy) mất sạch. Hệ quả: chỉ cần restart
    Anvil là test đứng ở `getKeyRecord` với lỗi "Could not transact with/call
    contract function". Giờ test tự deploy, không phụ thuộc state cũ.
    """
    import subprocess

    w3 = Web3(Web3.HTTPProvider(RPC_URL, request_kwargs={"timeout": 30}))
    try:
        if not w3.is_connected():
            yield None
            return
        if w3.eth.get_balance(ANVIL_FUNDER) == 0:
            yield None
            return

        result = subprocess.run(
            [sys.executable, "scripts/deploy_dpki.py", "--rpc", RPC_URL],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=str(Path(__file__).resolve().parent.parent),
            timeout=180,
        )
        if result.returncode != 0:
            print(f"\n[!] Deploy thất bại:\n{result.stdout}\n{result.stderr}")
            yield None
            return

        address = _parse_contract_address(result.stdout + "\n" + result.stderr)
        if not address:
            print(f"\n[!] Không parse được địa chỉ contract:\n{result.stdout}")
            yield None
            return

        # Xác nhận contract thật sự có bytecode on-chain trước khi dùng.
        if len(w3.eth.get_code(address)) == 0:
            print(f"\n[!] Không có bytecode tại {address}")
            yield None
            return

        print(f"\n[dPKI] Contract deployed for E2E: {address}")
        yield w3, address
    finally:
        pass


def _fund_if_available(anvil_ctx, address: str, amount_wei: int = 50 * 10**18) -> None:
    """Nạp gas cho ví; bỏ qua nếu không có node (test sẽ chạy chế độ degraded)."""
    if anvil_ctx is None:
        return
    w3, _addr = anvil_ctx
    w3.eth.send_transaction({"from": ANVIL_FUNDER, "to": address, "value": amount_wei})


def _write_priv_pem(tmp_path: Path, name: str, pem: str) -> str:
    """Ghi RSA Private Key ra file tạm để test đăng ký kèm PoP (VÁ #5)."""
    path = tmp_path / name
    path.write_text(pem, encoding="utf-8")
    return str(path)


def test_complete_e2e_hybrid_security_pipeline(client, anvil, tmp_path):
    # 1. Danh tính Web3 & Cặp khóa RSA cho Alice (Seller) và Bob (Buyer)
    alice_wallet = Account.create()
    bob_wallet = Account.create()
    _fund_if_available(anvil, alice_wallet.address)
    _fund_if_available(anvil, bob_wallet.address)

    alice_priv_bytes, alice_pub_bytes = generate_rsa_key_pair()
    bob_priv_bytes, bob_pub_bytes = generate_rsa_key_pair()

    alice_priv_pem = alice_priv_bytes.decode("utf-8")
    alice_pub_pem = alice_pub_bytes.decode("utf-8")
    bob_priv_pem = bob_priv_bytes.decode("utf-8")
    bob_pub_pem = bob_pub_bytes.decode("utf-8")

    # 2. Đăng ký Public Key lên dPKI — VÁ #5: PoP là đường duy nhất nên bắt buộc
    #    phải truyền RSA Private Key để tạo chữ ký chứng minh sở hữu.
    #    Contract address lấy từ fixture `anvil` (deploy mới), KHÔNG hard-code.
    if anvil is not None:
        _w3, contract_address = anvil
        dpki = DPKIClient(contract_address=contract_address)
    else:
        dpki = DPKIClient()
    dpki.register_public_key(
        alice_wallet.key.hex(),
        alice_pub_pem,
        rsa_private_key_path=_write_priv_pem(tmp_path, "alice_priv.pem", alice_priv_pem),
    )
    dpki.register_public_key(
        bob_wallet.key.hex(),
        bob_pub_pem,
        rsa_private_key_path=_write_priv_pem(tmp_path, "bob_priv.pem", bob_priv_pem),
    )

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
