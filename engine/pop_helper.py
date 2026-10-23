"""
engine/pop_helper.py
Helper để tạo Proof-of-Possession (PoP) signature dùng RSA-PKCS1-v1.5 (RFC 8017).
"""

from typing import Union
from eth_account import Account
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.serialization import load_pem_private_key

try:  # cryptography >= 2.5
    from cryptography.hazmat.primitives.asymmetric.utils import Prehashed
except ImportError:  # pragma: no cover
    from cryptography.hazmat.primitives.asymmetric.utils import (  # type: ignore
        Prehashed,
    )


def generate_pop_signature(
    eth_private_key_hex: str,
    rsa_private_key_pem: Union[str, bytes],
) -> bytes:
    """
    Tạo Proof-of-Possession signature bằng RSA-PKCS1-v1.5 theo RFC 8017.

    Flow:
      1. Derive Ethereum wallet address (20 bytes) từ eth_private_key_hex.
      2. Hash message: sha256(wallet_address).
      3. Sign message hash bằng RSA private key với RSASSA-PKCS1-v1_5.
      4. Trả về raw signature bytes để nạp thẳng vào smart contract (bytes memory).

    :param eth_private_key_hex: Khóa riêng Ethereum (dạng hex, có hoặc không có prefix 0x).
    :param rsa_private_key_pem: Khóa riêng RSA dạng PEM (str hoặc bytes).
    :return: Raw signature bytes (ví dụ: 256 bytes với RSA-2048, 512 bytes với RSA-4096).
    """
    # 1. Chuẩn hóa Ethereum Private Key & Derive canonical 20-byte address
    if not eth_private_key_hex.startswith("0x"):
        eth_private_key_hex = "0x" + eth_private_key_hex

    account = Account.from_key(eth_private_key_hex)
    wallet_address_bytes = bytes.fromhex(account.address[2:])  # 20 raw bytes

    # 2. Tính sha256(wallet_address) — ĐÂY LÀ HASH DUY NHẤT ĐƯỢC KÝ.
    import hashlib
    message_digest = hashlib.sha256(wallet_address_bytes).digest()

    # 3. Load RSA Private Key từ PEM
    pem_bytes = (
        rsa_private_key_pem.encode("utf-8")
        if isinstance(rsa_private_key_pem, str)
        else rsa_private_key_pem
    )
    rsa_key = load_pem_private_key(pem_bytes, password=None)

    # 4. Ký theo RFC 8017 (RSASSA-PKCS1-v1_5 + SHA-256).
    #    VÁ #5: Dùng Prehashed để báo cho OpenSSL rằng `message_digest` ĐÃ là
    #    SHA-256 digest rồi — nó chỉ cần bọc DigestInfo + padding, KHÔNG hash
    #    thêm lần nữa. Trước đây truyền thẳng hashes.SHA256() khiến OpenSSL
    #    hash lần 2 -> chữ ký thực chất trên sha256(sha256(address)), buộc
    #    smart contract phải "bù" bằng sha256(digest) và làm chữ ký không thể
    #    verify được bằng bất kỳ thư viện RSA chuẩn nào bên ngoài.
    signature: bytes = rsa_key.sign(
        message_digest,
        padding.PKCS1v15(),
        Prehashed(hashes.SHA256()),
    )

    return signature
