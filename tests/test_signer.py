"""
tests/test_signer.py

Test cho engine/signer.py (Issue #6).
Chạy: pytest tests/test_signer.py -v
"""

import sys
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

# Cho phép import engine/ dù chạy pytest từ thư mục gốc repo.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine.signer import IntegritySigner  # noqa: E402


# ---------------------------------------------------------------- #
# Fixtures: sinh cặp khoá RSA-2048 dùng chung cho cả file test      #
# ---------------------------------------------------------------- #

@pytest.fixture(scope="module")
def keypair_pem():
    """Sinh 1 cặp khoá RSA-2048, trả về (private_pem, public_pem) dạng str."""
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_key = private_key.public_key()

    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")

    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")

    return private_pem, public_pem


@pytest.fixture(scope="module")
def other_keypair_pem():
    """Cặp khoá RSA thứ 2 - dùng để test verify với public key SAI."""
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_key = private_key.public_key()

    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")

    return public_pem


@pytest.fixture()
def sample_data():
    return b"CloakShare - hybrid crypto file exchange demo payload."


# ---------------------------------------------------------------- #
# Test case chính                                                  #
# ---------------------------------------------------------------- #

def test_sign_returns_bytes(keypair_pem, sample_data):
    private_pem, _ = keypair_pem
    signature = IntegritySigner.sign_file(sample_data, private_pem)

    assert isinstance(signature, bytes)
    assert len(signature) == 256  # RSA-2048 -> signature dài 256 byte


def test_verify_valid_signature_returns_true(keypair_pem, sample_data):
    private_pem, public_pem = keypair_pem
    signature = IntegritySigner.sign_file(sample_data, private_pem)

    assert IntegritySigner.verify_file(sample_data, signature, public_pem) is True


def test_verify_fails_when_data_flipped_by_one_bit(keypair_pem, sample_data):
    """
    Tiêu chí DoD quan trọng nhất: thay đổi 1 bit bất kỳ trong data
    phải khiến verify_file() trả về False.
    """
    private_pem, public_pem = keypair_pem
    signature = IntegritySigner.sign_file(sample_data, private_pem)

    tampered = bytearray(sample_data)
    tampered[0] ^= 0x01  # lật đúng 1 bit ở byte đầu tiên
    tampered = bytes(tampered)

    assert tampered != sample_data
    assert IntegritySigner.verify_file(tampered, signature, public_pem) is False


def test_verify_fails_when_bit_flipped_at_end(keypair_pem, sample_data):
    """Lật 1 bit ở byte CUỐI cùng cũng phải fail (không chỉ byte đầu)."""
    private_pem, public_pem = keypair_pem
    signature = IntegritySigner.sign_file(sample_data, private_pem)

    tampered = bytearray(sample_data)
    tampered[-1] ^= 0x01
    tampered = bytes(tampered)

    assert IntegritySigner.verify_file(tampered, signature, public_pem) is False


def test_verify_fails_with_wrong_public_key(keypair_pem, other_keypair_pem, sample_data):
    """Ký bằng key A, verify bằng public key B (không liên quan) -> phải False."""
    private_pem, _ = keypair_pem
    wrong_public_pem = other_keypair_pem

    signature = IntegritySigner.sign_file(sample_data, private_pem)

    assert IntegritySigner.verify_file(sample_data, signature, wrong_public_pem) is False


def test_verify_fails_with_corrupted_signature(keypair_pem, sample_data):
    """Signature bị hỏng 1 byte (giả lập gói tin lỗi/giả mạo) -> phải False."""
    private_pem, public_pem = keypair_pem
    signature = bytearray(IntegritySigner.sign_file(sample_data, private_pem))

    signature[10] ^= 0xFF
    signature = bytes(signature)

    assert IntegritySigner.verify_file(sample_data, signature, public_pem) is False


def test_verify_fails_with_malformed_pem():
    """PEM rác/hỏng không được raise exception ra ngoài, phải trả về False."""
    result = IntegritySigner.verify_file(
        b"data",
        b"fake-signature",
        "-----BEGIN PUBLIC KEY-----\nkhong-hop-le\n-----END PUBLIC KEY-----",
    )
    assert result is False


def test_sign_is_non_deterministic_but_all_valid(keypair_pem, sample_data):
    """
    RSA-PSS có salt ngẫu nhiên -> ký 2 lần trên cùng data sẽ ra 2 signature
    KHÁC NHAU, nhưng cả 2 đều phải verify() ra True.
    """
    private_pem, public_pem = keypair_pem

    sig1 = IntegritySigner.sign_file(sample_data, private_pem)
    sig2 = IntegritySigner.sign_file(sample_data, private_pem)

    assert sig1 != sig2  # PSS salt ngẫu nhiên mỗi lần ký
    assert IntegritySigner.verify_file(sample_data, sig1, public_pem) is True
    assert IntegritySigner.verify_file(sample_data, sig2, public_pem) is True
