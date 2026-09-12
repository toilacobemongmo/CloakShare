import os
import hashlib
import pytest
from engine.wrappers.aes_wrapper import AESWrapper

@pytest.fixture
def aes():
    return AESWrapper()

def test_invalid_key_length(aes):
    """Kiểm tra báo lỗi khi truyền key sai kích thước"""
    with pytest.raises(ValueError, match="Khóa AES-128 phải có độ dài chính xác 16 bytes"):
        aes.encrypt(b"hello", b"short_key")

def test_encrypt_decrypt_short_text(aes):
    """Kiểm tra mã hóa và giải mã chuỗi ngắn bất kỳ"""
    key = os.urandom(16)
    plaintext = b"CloakShare Secret Message - Zero Log Broker!"
    
    iv, ciphertext = aes.encrypt(plaintext, key)
    assert len(iv) == 16
    assert len(ciphertext) % 16 == 0
    assert ciphertext != plaintext

    decrypted = aes.decrypt(ciphertext, key, iv)
    assert decrypted == plaintext

def test_encrypt_decrypt_large_payload_1mb(aes):
    """Kiểm tra toàn vẹn dữ liệu cho payload lớn 1MB (DoD)"""
    key = os.urandom(16)
    payload_1mb = os.urandom(1024 * 1024)  # 1MB dữ liệu ngẫu nhiên
    original_hash = hashlib.sha256(payload_1mb).hexdigest()

    iv, ciphertext = aes.encrypt(payload_1mb, key)
    decrypted = aes.decrypt(ciphertext, key, iv)
    decrypted_hash = hashlib.sha256(decrypted).hexdigest()

    assert original_hash == decrypted_hash