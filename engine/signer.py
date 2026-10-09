"""
engine/signer.py

Module ký số và kiểm tra toàn vẹn file cho CloakShare.
Hỗ trợ cả:
  - Chuẩn Web3 ECDSA (SECP256K1 qua eth_keys) với khóa ví EVM (hex).
  - Chuẩn RSA-PSS (SHA-256 qua cryptography) với khóa PEM (để tương thích ngược test suite).
"""

from __future__ import annotations
import eth_keys
from hashlib import sha256
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding


class IntegritySigner:
    _PADDING = padding.PSS(
        mgf=padding.MGF1(hashes.SHA256()),
        salt_length=padding.PSS.DIGEST_LENGTH,
    )
    _HASH_ALGO = hashes.SHA256()

    @staticmethod
    def sign_file(data: bytes, sender_private: str) -> bytes:
        if not isinstance(data, bytes):
            raise TypeError("data phải là bytes")

        key_str = sender_private.strip()
        if key_str.startswith("-----BEGIN"):
            # Chế độ RSA-PSS (PEM)
            pem_bytes = key_str.encode("utf-8")
            private_key = serialization.load_pem_private_key(pem_bytes, password=None)
            return private_key.sign(
                data,
                IntegritySigner._PADDING,
                IntegritySigner._HASH_ALGO,
            )

        # Chế độ Web3 ECDSA (SECP256K1)
        clean_hex = key_str.replace("0x", "")
        priv_key = eth_keys.keys.PrivateKey(bytes.fromhex(clean_hex))
        msg_hash = sha256(data).digest()
        signature = priv_key.sign_msg_hash(msg_hash)
        return signature.to_bytes()

    @staticmethod
    def verify_file(data: bytes, signature: bytes, sender_public: str) -> bool:
        if not isinstance(data, bytes) or not isinstance(signature, (bytes, bytearray)):
            return False

        try:
            pub_str = sender_public.strip()
            if pub_str.startswith("-----BEGIN"):
                # Chế độ RSA-PSS (PEM)
                pem_bytes = pub_str.encode("utf-8")
                public_key = serialization.load_pem_public_key(pem_bytes)
                public_key.verify(
                    bytes(signature),
                    data,
                    IntegritySigner._PADDING,
                    IntegritySigner._HASH_ALGO,
                )
                return True

            # Chế độ Web3 ECDSA (SECP256K1)
            clean_hex = pub_str.replace("0x", "")
            if len(clean_hex) == 130 and clean_hex.startswith("04"):
                clean_hex = clean_hex[2:]

            if len(clean_hex) == 66 and clean_hex[:2] in ("02", "03"):
                pub_key = eth_keys.keys.PublicKey.from_compressed_bytes(bytes.fromhex(clean_hex))
            else:
                pub_key = eth_keys.keys.PublicKey(bytes.fromhex(clean_hex))

            msg_hash = sha256(data).digest()
            sig = eth_keys.keys.Signature(bytes(signature))
            recovered_pub = sig.recover_public_key_from_msg_hash(msg_hash)
            return recovered_pub == pub_key

        except (InvalidSignature, Exception):
            return False

