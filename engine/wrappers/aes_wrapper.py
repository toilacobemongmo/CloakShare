import os
import sys
import ctypes
from pathlib import Path
from typing import Tuple

def get_lib_path() -> str:
    """Tự động xác định đường dẫn file thư viện động theo hệ điều hành."""
    # Lùi 2 cấp thư mục từ engine/wrappers/ về thư mục gốc của project
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


# Định nghĩa Struct Context tương ứng với struct trong aes128.h
class AES128_Context(ctypes.Structure):
    _fields_ = [("round_keys", ctypes.c_uint8 * 176)]


class AESWrapper:
    def __init__(self, lib_path: str = None) -> None:
        self.lib_path = lib_path or get_lib_path()
        self._c_lib = ctypes.CDLL(self.lib_path)
        self._bind_c_functions()

    def _bind_c_functions(self) -> None:
        """Khai báo kiểu tham số (argtypes) và kiểu trả về (restype) cho các hàm C."""
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

        # 3. void aes128_init(AES128_Context *ctx, const uint8_t *key)
        self._c_lib.aes128_init.argtypes = [
            ctypes.POINTER(AES128_Context),
            ctypes.POINTER(ctypes.c_uint8)
        ]
        self._c_lib.aes128_init.restype = None

        # 4. void aes128_cbc_encrypt(const AES128_Context *ctx, const uint8_t *iv, const uint8_t *in, size_t len, uint8_t *out)
        self._c_lib.aes128_cbc_encrypt.argtypes = [
            ctypes.POINTER(AES128_Context),
            ctypes.POINTER(ctypes.c_uint8),
            ctypes.POINTER(ctypes.c_uint8),
            ctypes.c_size_t,
            ctypes.POINTER(ctypes.c_uint8)
        ]
        self._c_lib.aes128_cbc_encrypt.restype = None

        # 5. void aes128_cbc_decrypt(const AES128_Context *ctx, const uint8_t *iv, const uint8_t *in, size_t len, uint8_t *out)
        self._c_lib.aes128_cbc_decrypt.argtypes = [
            ctypes.POINTER(AES128_Context),
            ctypes.POINTER(ctypes.c_uint8),
            ctypes.POINTER(ctypes.c_uint8),
            ctypes.c_size_t,
            ctypes.POINTER(ctypes.c_uint8)
        ]
        self._c_lib.aes128_cbc_decrypt.restype = None

    def encrypt(self, plaintext: bytes, key: bytes) -> Tuple[bytes, bytes]:
        """Mã hóa plaintext bằng AES-128-CBC với padding PKCS#7."""
        if len(key) != 16:
            raise ValueError("Khóa AES-128 phải có độ dài chính xác 16 bytes")

        # 1. Sinh IV ngẫu nhiên 16 bytes
        iv = os.urandom(16)

        # 2. Thực hiện PKCS#7 Padding
        block_size = 16
        pad_buffer_len = len(plaintext) + block_size
        padded_buffer = (ctypes.c_uint8 * pad_buffer_len)()
        in_buffer = (ctypes.c_uint8 * len(plaintext)).from_buffer_copy(plaintext)

        new_len = self._c_lib.pkcs7_pad(in_buffer, len(plaintext), padded_buffer, block_size)
        if new_len < 0:
            raise ValueError(f"Lỗi khi thực hiện padding, mã lỗi: {new_len}")

        # 3. Khởi tạo Context và mã hóa CBC
        ctx = AES128_Context()
        key_buf = (ctypes.c_uint8 * 16).from_buffer_copy(key)
        iv_buf = (ctypes.c_uint8 * 16).from_buffer_copy(iv)
        ciphertext_buffer = (ctypes.c_uint8 * new_len)()

        self._c_lib.aes128_init(ctypes.byref(ctx), key_buf)
        self._c_lib.aes128_cbc_encrypt(ctypes.byref(ctx), iv_buf, padded_buffer, new_len, ciphertext_buffer)

        return iv, bytes(ciphertext_buffer)

    def decrypt(self, ciphertext: bytes, key: bytes, iv: bytes) -> bytes:
        """Giải mã AES-128-CBC và loại bỏ PKCS#7 padding."""
        if len(key) != 16:
            raise ValueError("Khóa AES-128 phải có độ dài chính xác 16 bytes")
        if len(iv) != 16:
            raise ValueError("IV phải có độ dài chính xác 16 bytes")
        if len(ciphertext) == 0 or len(ciphertext) % 16 != 0:
            raise ValueError("Ciphertext phải là bội số của 16 bytes")

        # 1. Khởi tạo Context và giải mã CBC
        ctx = AES128_Context()
        key_buf = (ctypes.c_uint8 * 16).from_buffer_copy(key)
        iv_buf = (ctypes.c_uint8 * 16).from_buffer_copy(iv)
        in_buf = (ctypes.c_uint8 * len(ciphertext)).from_buffer_copy(ciphertext)
        decrypted_buffer = (ctypes.c_uint8 * len(ciphertext))()

        self._c_lib.aes128_init(ctypes.byref(ctx), key_buf)
        self._c_lib.aes128_cbc_decrypt(ctypes.byref(ctx), iv_buf, in_buf, len(ciphertext), decrypted_buffer)

        # 2. Bỏ PKCS#7 Padding
        unpadded_buffer = (ctypes.c_uint8 * len(ciphertext))()
        actual_len = self._c_lib.pkcs7_unpad(decrypted_buffer, len(ciphertext), unpadded_buffer, 16)
        if actual_len < 0:
            raise ValueError("Dữ liệu padding PKCS#7 không hợp lệ hoặc sai khóa/IV!")

        return bytes(unpadded_buffer[:actual_len])