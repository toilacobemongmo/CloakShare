import os
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from engine.rsa_envelope import RSAEnvelope

@pytest.fixture
def generate_keypair():
    """Hàm fixture sinh cặp khóa RSA-2048 test tạm thời"""
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048
    )
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    ).decode('utf-8')

    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    ).decode('utf-8')

    return private_pem, public_pem

def test_wrap_unwrap_success(generate_keypair):
    """Kiểm tra bọc và mở khóa AES-128 thành công"""
    private_pem, public_pem = generate_keypair
    original_aes_key = os.urandom(16)  # Khóa AES 16 bytes

    # Người gửi bọc khóa bằng Public Key của người nhận
    wrapped_key = RSAEnvelope.wrap_key(original_aes_key, public_pem)
    assert len(wrapped_key) == 256  # RSA-2048 luôn xuất ra khối 256 bytes

    # Người nhận mở khóa bằng Private Key của mình
    recovered_aes_key = RSAEnvelope.unwrap_key(wrapped_key, private_pem)
    assert recovered_aes_key == original_aes_key

def test_unwrap_with_wrong_private_key(generate_keypair):
    """Kiểm tra báo lỗi khi dùng nhầm Private Key khác để giải mã (DoD)"""
    _, public_pem_1 = generate_keypair
    
    # Tạo cặp khóa thứ hai (của kẻ lạ)
    stranger_private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    stranger_private_pem = stranger_private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    ).decode('utf-8')

    aes_key = os.urandom(16)
    wrapped_key = RSAEnvelope.wrap_key(aes_key, public_pem_1)

    # Kẻ lạ cố giải mã bằng private key của họ -> phải ném ra ValueError
    with pytest.raises(ValueError, match="Decryption failed"):
        RSAEnvelope.unwrap_key(wrapped_key, stranger_private_pem)