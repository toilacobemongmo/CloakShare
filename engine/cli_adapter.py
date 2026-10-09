import os
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from engine.ecies_envelope import ECIESEnvelope
from engine.wrappers.aes_wrapper import AESWrapper

_aes = AESWrapper()

class CLIAdapter:
    @staticmethod
    def encrypt_bytes(data: bytes, key: bytes | None = None) -> tuple[bytes, bytes, bytes]:
        """
        Mã hóa trực tiếp dữ liệu bytes trên RAM bằng AES-128-CBC + PKCS#7 (C Core).
        Trả về (key, iv, ciphertext).
        """
        session_key = key if key is not None else os.urandom(16)
        iv, ciphertext = _aes.encrypt(data, session_key)
        return session_key, iv, ciphertext

    @staticmethod
    def decrypt_bytes(ciphertext: bytes, key: bytes, iv: bytes) -> bytes:
        """
        Giải mã trực tiếp dữ liệu bytes trên RAM bằng AES-128-CBC + PKCS#7 (C Core).
        """
        return _aes.decrypt(ciphertext, key, iv)

    @staticmethod
    def encrypt_file(input_path: str, output_path: str) -> tuple[bytes, bytes]:
        """
        Đọc file, mã hóa trong RAM bằng AESWrapper, ghi kết quả ra output_path.
        """
        data = Path(input_path).read_bytes()
        session_key = os.urandom(16)
        iv, ciphertext = _aes.encrypt(data, session_key)
        Path(output_path).write_bytes(ciphertext)
        return session_key, iv

    @staticmethod
    def decrypt_file(input_path: str, output_path: str, key: bytes, iv: bytes) -> None:
        """
        Đọc ciphertext từ file, giải mã trong RAM bằng AESWrapper, ghi ra output_path.
        """
        ciphertext = Path(input_path).read_bytes()
        plaintext = _aes.decrypt(ciphertext, key, iv)
        Path(output_path).write_bytes(plaintext)

    @staticmethod
    def wrap_aes_key(aes_key: bytes, iv: bytes, receiver_pub_hex: str) -> bytes:
        return ECIESEnvelope.wrap_key(aes_key + iv, receiver_pub_hex)

    @staticmethod
    def unwrap_aes_key(wrapped: bytes, receiver_priv_hex: str) -> tuple[bytes, bytes]:
        combined = ECIESEnvelope.unwrap_key(wrapped, receiver_priv_hex)
        return combined[:32], combined[32:]