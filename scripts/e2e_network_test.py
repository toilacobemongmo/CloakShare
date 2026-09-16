import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import os
import uuid
import httpx
from eth_account import Account
from engine.wrappers.aes_wrapper import AESWrapper
from engine.rsa_envelope import RSAEnvelope
from engine.signer import IntegritySigner
from engine.wallet_auth import Web3Auth
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization

BROKER_URL = "http://127.0.0.1:8000"

# 1. Sinh cặp khóa RSA và ví Web3 cho Buyer
buyer_eth = Account.create()
buyer_wallet_address = buyer_eth.address
buyer_wallet_private_key = buyer_eth.key.hex()

def gen_rsa_pair():
    k = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    priv = k.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()).decode()
    pub = k.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo).decode()
    return priv, pub

seller_priv, seller_pub = gen_rsa_pair()
buyer_priv, buyer_pub = gen_rsa_pair()

# 2. Seller mã hóa & Stage payload
raw_data = b"CloakShare Protected by Web3 Sign-in Auth."
session_key = os.urandom(16)
aes = AESWrapper()

iv, ciphertext = aes.encrypt(raw_data, session_key)
wrapped_key = RSAEnvelope.wrap_key(session_key, buyer_pub)
signature = IntegritySigner.sign_file(ciphertext, seller_priv)
tx_id = f"0x{uuid.uuid4().hex}"

payload = {
    "tx_id": tx_id,
    "recipient": buyer_wallet_address,
    "iv": iv.hex(),
    "wrapped_key": wrapped_key.hex(),
    "ciphertext": ciphertext.hex(),
    "signature": signature.hex(),
    "ttl_seconds": 60
}

with httpx.Client(base_url=BROKER_URL) as client:
    res_stage = client.post("/api/v1/stage", json=payload)
    print("1. Stage:", res_stage.status_code)
    assert res_stage.status_code == 201

    # 3. Thử lấy khi KHÔNG có chữ ký ví (Kỳ vọng lỗi 422 hoặc 401)
    res_unauth = client.get(f"/api/v1/retrieve/{tx_id}")
    print("2. Unauthenticated retrieve status:", res_unauth.status_code)
    assert res_unauth.status_code in (401, 422)

    # 4. Buyer ký thông điệp xác thực bằng Private Key ví Web3
    ts, sig_hex = Web3Auth.sign_retrieve_request(tx_id, buyer_wallet_private_key)
    auth_headers = {
        "X-Wallet-Address": buyer_wallet_address,
        "X-Timestamp": str(ts),
        "X-Signature": sig_hex
    }

    # 5. Buyer rút payload hợp lệ
    res_auth = client.get(f"/api/v1/retrieve/{tx_id}", headers=auth_headers)
    print("3. Authenticated retrieve status:", res_auth.status_code)
    assert res_auth.status_code == 200
    retrieved = res_auth.json()

# 6. Giải mã
recv_cipher = bytes.fromhex(retrieved["ciphertext"])
recv_sig = bytes.fromhex(retrieved["signature"])
assert IntegritySigner.verify_file(recv_cipher, recv_sig, seller_pub)

recovered_key = RSAEnvelope.unwrap_key(bytes.fromhex(retrieved["wrapped_key"]), buyer_priv)
plaintext = aes.decrypt(recv_cipher, recovered_key, bytes.fromhex(retrieved["iv"]))
print(f"4. Giai ma thanh cong sau xac thuc vi Web3: '{plaintext.decode()}'")