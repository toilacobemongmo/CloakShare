import os
import sys
import ctypes
from pathlib import Path
from typing import Tuple


def get_lib_path() -> str:
    """Tự động xác định đường dẫn file thư viện động theo hệ điều hành."""
    base_dir = Path(__file__).resolve().parent.parent.parent
    core_dir = base_dir / "core"

    if sys.platform.startswith("win"):
        lib_name = "aes128.dll"
    elif sys.platform.startswith("darwin"):
        lib_name = "libaes.dylib"
    else:
        lib_name = "libaes.so"

    full_path = core_dir / lib_name

    if not full_path.exists():
        raise FileNotFoundError(
            f"\n[!] Không tìm thấy thư viện C tại: {full_path}\n"
            f"[!] Hãy chạy 'make -C core' hoặc biên dịch file C trước!"
        )
    return str(full_path)


class AESWrapper:
    def __init__(self, lib_path: str = None) -> None:
        self.lib_path = lib_path or get_lib_path()
        self._c_lib = ctypes.CDLL(self.lib_path)
        self._bind_c_functions()

    def _bind_c_functions(self) -> None:
        """Khai báo chữ ký hàm C theo đúng core/padding.h và core/aes128.h"""
        # 1. int pkcs7_pad(const uint8_t *in, size_t in_len, uint8_t *out, size_t block_size)
        self._c_lib.pkcs7_pad.argtypes = [
            ctypes.POINTER(ctypes.c_uint8),
            ctypes.c_size_t,
            ctypes.POINTER(ctypes.c_uint8),
            ctypes.c_size_t
        ]
        self._c_lib.pkcs7_pad.restype = ctypes.c_int

        # 2. int pkcs7_unpad(const uint8_t *in, size_t in_len, uint8_t *out, size_t block_size)
        self._c_lib.pkcs7_unpad.argtypes = [
            ctypes.POINTER(ctypes.c_uint8),
            ctypes.c_size_t,
            ctypes.POINTER(ctypes.c_uint8),
            ctypes.c_size_t
        ]
        self._c_lib.pkcs7_unpad.restype = ctypes.c_int

        # 3. int aes128_cbc_encrypt(const uint8_t *plaintext, size_t len, const uint8_t key[16], const uint8_t iv[16], uint8_t *out)
        self._c_lib.aes128_cbc_encrypt.argtypes = [
            ctypes.POINTER(ctypes.c_uint8),
            ctypes.c_size_t,
            ctypes.POINTER(ctypes.c_uint8),
            ctypes.POINTER(ctypes.c_uint8),
            ctypes.POINTER(ctypes.c_uint8)
        ]
        self._c_lib.aes128_cbc_encrypt.restype = ctypes.c_int

        # 4. int aes128_cbc_decrypt(const uint8_t *ciphertext, size_t len, const uint8_t key[16], const uint8_t iv[16], uint8_t *out)
        self._c_lib.aes128_cbc_decrypt.argtypes = [
            ctypes.POINTER(ctypes.c_uint8),
            ctypes.c_size_t,
            ctypes.POINTER(ctypes.c_uint8),
            ctypes.POINTER(ctypes.c_uint8),
            ctypes.POINTER(ctypes.c_uint8)
        ]
        self._c_lib.aes128_cbc_decrypt.restype = ctypes.c_int

    def encrypt(self, plaintext: bytes, key: bytes) -> Tuple[bytes, bytes]:
        """Mã hóa plaintext bằng AES-128-CBC với padding PKCS#7."""
        if len(key) != 16:
            raise ValueError("Khóa AES-128 phải có độ dài chính xác 16 bytes")

        # 1. Sinh IV ngẫu nhiên 16 bytes
        iv = os.urandom(16)

        # 2. Đệm PKCS#7 qua core/padding.c
        block_size = 16
        pad_buffer_len = len(plaintext) + block_size
        padded_buffer = (ctypes.c_uint8 * pad_buffer_len)()
        in_buffer = (ctypes.c_uint8 * len(plaintext)).from_buffer_copy(plaintext)

        new_len = self._c_lib.pkcs7_pad(in_buffer, len(plaintext), padded_buffer, block_size)
        if new_len < 0:
            raise ValueError(f"Lỗi khi thực hiện padding, mã lỗi: {new_len}")

        # 3. Mã hóa CBC qua core/aes128.c
        key_buf = (ctypes.c_uint8 * 16).from_buffer_copy(key)
        iv_buf = (ctypes.c_uint8 * 16).from_buffer_copy(iv)
        ciphertext_buffer = (ctypes.c_uint8 * new_len)()

        ret = self._c_lib.aes128_cbc_encrypt(padded_buffer, new_len, key_buf, iv_buf, ciphertext_buffer)
        if ret != 0:
            raise ValueError(f"Lỗi khi thực hiện aes128_cbc_encrypt, mã lỗi: {ret}")

        return iv, bytes(ciphertext_buffer)

    def decrypt(self, ciphertext: bytes, key: bytes, iv: bytes) -> bytes:
        """Giải mã AES-128-CBC và loại bỏ PKCS#7 padding."""
        if len(key) != 16:
            raise ValueError("Khóa AES-128 phải có độ dài chính xác 16 bytes")
        if len(iv) != 16:
            raise ValueError("IV phải có độ dài chính xác 16 bytes")
        if len(ciphertext) == 0 or len(ciphertext) % 16 != 0:
            raise ValueError("Ciphertext phải là bội số của 16 bytes")

        # 1. Giải mã CBC qua core/aes128.c
        cipher_len = len(ciphertext)
        in_buf = (ctypes.c_uint8 * cipher_len).from_buffer_copy(ciphertext)
        key_buf = (ctypes.c_uint8 * 16).from_buffer_copy(key)
        iv_buf = (ctypes.c_uint8 * 16).from_buffer_copy(iv)
        decrypted_buffer = (ctypes.c_uint8 * cipher_len)()

        ret = self._c_lib.aes128_cbc_decrypt(in_buf, cipher_len, key_buf, iv_buf, decrypted_buffer)
        if ret != 0:
            raise ValueError(f"Lỗi khi thực hiện aes128_cbc_decrypt, mã lỗi: {ret}")

        # 2. Gỡ bỏ PKCS#7 Padding qua core/padding.c
        unpadded_buffer = (ctypes.c_uint8 * cipher_len)()
        actual_len = self._c_lib.pkcs7_unpad(decrypted_buffer, cipher_len, unpadded_buffer, 16)
        if actual_len < 0:
            raise ValueError("Dữ liệu padding PKCS#7 không hợp lệ hoặc sai khóa/IV!")

        return bytes(unpadded_buffer[:actual_len])