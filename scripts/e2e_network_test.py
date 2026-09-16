import sys
from pathlib import Path

# Đảm bảo Python tìm thấy thư mục gốc
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import os
import uuid
import httpx
from engine.wrappers.aes_wrapper import AESWrapper
from engine.rsa_envelope import RSAEnvelope
from engine.signer import IntegritySigner
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization

BROKER_URL = "http://127.0.0.1:8000"

# 1. Sinh cặp khóa RSA
def gen_keypair():
    k = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    priv = k.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption()
    ).decode()
    pub = k.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo
    ).decode()
    return priv, pub

seller_priv, seller_pub = gen_keypair()
buyer_priv, buyer_pub = gen_keypair()

# 2. Seller chuẩn bị và mã hóa dữ liệu
raw_data = b"CloakShare E2E Network Payload: Zero-Log Staging verified."
session_key = os.urandom(16)
aes = AESWrapper()

iv, ciphertext = aes.encrypt(raw_data, session_key)
wrapped_key = RSAEnvelope.wrap_key(session_key, buyer_pub)
signature = IntegritySigner.sign_file(ciphertext, seller_priv)

tx_id = f"0x{uuid.uuid4().hex}"
recipient_wallet = "0x70997970C51812dc3A010C7d01b50e0d17dc79C8"

# Chuẩn bị payload đúng schema của broker/schemas.py
payload = {
    "tx_id": tx_id,
    "recipient": recipient_wallet,
    "iv": iv.hex(),
    "wrapped_key": wrapped_key.hex(),
    "ciphertext": ciphertext.hex(),
    "signature": signature.hex(),
    "ttl_seconds": 60
}

# 3. Kết nối qua HTTP tới RAM Broker
with httpx.Client(base_url=BROKER_URL) as client:
    # POST lên /api/v1/stage
    res_stage = client.post("/api/v1/stage", json=payload)
    print("1. Stage status:", res_stage.status_code, res_stage.json())
    assert res_stage.status_code == 201

    # GET từ /api/v1/retrieve/{tx_id}
    res_retrieve = client.get(f"/api/v1/retrieve/{tx_id}")
    print("2. Retrieve status:", res_retrieve.status_code)
    assert res_retrieve.status_code == 200
    retrieved = res_retrieve.json()

# 4. Buyer xác thực và giải mã
recv_cipher = bytes.fromhex(retrieved["ciphertext"])
recv_sig = bytes.fromhex(retrieved["signature"])
recv_key_bytes = bytes.fromhex(retrieved["wrapped_key"])
recv_iv = bytes.fromhex(retrieved["iv"])

# Xác thực chữ ký số bằng Public Key của Seller
assert IntegritySigner.verify_file(recv_cipher, recv_sig, seller_pub), "Chữ ký không hợp lệ!"
print("3. Chữ ký số toàn vẹn: Hợp lệ.")

# Giải bọc Session Key và giải mã AES
recovered_key = RSAEnvelope.unwrap_key(recv_key_bytes, buyer_priv)
plaintext = aes.decrypt(recv_cipher, recovered_key, recv_iv)

print(f"4. Giải mã thành công: {plaintext.decode()}")