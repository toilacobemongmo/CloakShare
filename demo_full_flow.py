import os
import uuid
from engine.wrappers.aes_wrapper import AESWrapper
from engine.rsa_envelope import RSAEnvelope
from engine.signer import IntegritySigner
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization

# --- 1. SETUP CẶP KHÓA RSA CHO SELLER VÀ BUYER ---
def gen_keypair():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    priv = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption()
    ).decode()
    pub = key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo
    ).decode()
    return priv, pub

seller_priv, seller_pub = gen_keypair()
buyer_priv, buyer_pub = gen_keypair()

print("1. [Identity] Cặp khóa Seller & Buyer đã sẵn sàng.")

# --- 2. SELLER CHUẨN BỊ VÀ MÃ HÓA GÓI TIN ---
raw_document = b"Noi dung hop dong mat chuyen giao tai san so: 50,000 USDT."
session_key = os.urandom(16)  # Khóa AES-128 phiên làm việc

# a. Khóa nội dung bằng AES (C Lõi)
aes = AESWrapper()
iv, ciphertext = aes.encrypt(raw_document, session_key)

# b. Bọc Session Key bằng Public Key của Buyer
wrapped_key = RSAEnvelope.wrap_key(session_key, buyer_pub)

# c. Ký xác thực toàn vẹn bằng Private Key của Seller
signature = IntegritySigner.sign_file(ciphertext, seller_priv)

print(f"2. [Seller] Đã mã hóa dữ liệu:")
print(f"   - Ciphertext : {len(ciphertext)} bytes")
print(f"   - Wrapped Key: {len(wrapped_key)} bytes")
print(f"   - Signature  : {len(signature)} bytes")

# --- 3. ĐẨY LÊN BROKER (GIẢ LẬP GÓI TIN MẠNG) ---
staged_payload = {
    "tx_id": str(uuid.uuid4()),
    "iv_hex": iv.hex(),
    "ciphertext_hex": ciphertext.hex(),
    "wrapped_key_hex": wrapped_key.hex(),
    "signature_hex": signature.hex()
}
print(f"3. [Broker] Lưu tạm payload với tx_id: {staged_payload['tx_id']}")

# --- 4. BUYER LẤY DỮ LIỆU VÀ GIẢI MÃ ---
# a. Chuyển đổi ngược từ hex sang bytes
recv_cipher = bytes.fromhex(staged_payload["ciphertext_hex"])
recv_sig = bytes.fromhex(staged_payload["signature_hex"])
recv_wrapped_key = bytes.fromhex(staged_payload["wrapped_key_hex"])
recv_iv = bytes.fromhex(staged_payload["iv_hex"])

# b. Xác thực chữ ký xem đúng Seller gửi và không bị sửa đổi
is_authentic = IntegritySigner.verify_file(recv_cipher, recv_sig, seller_pub)
assert is_authentic, "Chữ ký không hợp lệ! Dữ liệu có dấu hiệu bị giả mạo!"
print("4. [Buyer] Xác thực chữ ký Seller thành công (Dữ liệu nguyên vẹn 100%).")

# c. Mở khóa Session Key bằng Private Key của Buyer
recovered_key = RSAEnvelope.unwrap_key(recv_wrapped_key, buyer_priv)
assert recovered_key == session_key, "Mở bọc khóa thất bại!"

# d. Giải mã AES lấy lại file tài liệu ban đầu
recovered_document = aes.decrypt(recv_cipher, recovered_key, recv_iv)
print(f"5. [Buyer] Giải mã thành công! Nội dung nhận được:\n   -> '{recovered_document.decode()}'")