"""
engine/pop_helper.py
Helper để tạo Proof-of-Possession (PoP) signature dùng RSA-PKCS1-v1.5 (RFC 8017).
"""

from typing import Union
from eth_account import Account
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.serialization import load_pem_private_key


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

    # 2. Tính sha256(wallet_address)
    import hashlib
    message_to_sign = hashlib.sha256(wallet_address_bytes).digest()

    # 3. Load RSA Private Key từ PEM
    pem_bytes = (
        rsa_private_key_pem.encode("utf-8")
        if isinstance(rsa_private_key_pem, str)
        else rsa_private_key_pem
    )
    rsa_key = load_pem_private_key(pem_bytes, password=None)

    # 4. Ký message theo chuẩn RFC 8017 (RSASSA-PKCS1-v1_5 với SHA-256)
    signature: bytes = rsa_key.sign(
        message_to_sign,
        padding.PKCS1v15(),
        hashes.SHA256(),
    )

    return signature
