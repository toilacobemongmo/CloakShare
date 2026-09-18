import sys
from pathlib import Path
import ctypes
import os

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from engine.rsa_envelope import RSAEnvelope

# Load trực tiếp file DLL từ thư mục core bằng ctypes
DLL_PATH = ROOT_DIR / "core" / "aes128.dll"
_aes_lib = ctypes.CDLL(str(DLL_PATH))

class CLIAdapter:
    @staticmethod
    def encrypt_file(input_path: str, output_path: str) -> tuple[bytes, bytes]:
        key = os.urandom(16)
        iv = os.urandom(16)
        with open(input_path, "rb") as f:
            plaintext = f.read()
        
        # Đệm PKCS7 chuẩn (bội số của 16 bytes)
        padding_len = 16 - (len(plaintext) % 16)
        padded = plaintext + bytes([padding_len] * padding_len)
        
        # Dùng create_string_buffer thay vì bytearray để ctypes nhận diện đúng buffer
        ciphertext_buf = ctypes.create_string_buffer(len(padded))
        
        _aes_lib.aes128_cbc_encrypt(
            ctypes.c_char_p(padded),
            ctypes.c_int(len(padded)),
            ctypes.c_char_p(key),
            ctypes.c_char_p(iv),
            ciphertext_buf
        )
        
        ciphertext = ciphertext_buf.raw
        with open(output_path, "wb") as f:
            f.write(ciphertext)
        return key, iv

    @staticmethod
    def decrypt_file(input_path: str, output_path: str, key: bytes, iv: bytes):
        with open(input_path, "rb") as f:
            ciphertext = f.read()
            
        plaintext_buf = ctypes.create_string_buffer(len(ciphertext))
        
        _aes_lib.aes128_cbc_decrypt(
            ctypes.c_char_p(ciphertext),
            ctypes.c_int(len(ciphertext)),
            ctypes.c_char_p(key),
            ctypes.c_char_p(iv),
            plaintext_buf
        )
        
        plaintext = plaintext_buf.raw
        # Bỏ đệm PKCS7
        padding_len = plaintext[-1]
        final_plaintext = bytes(plaintext[:-padding_len])
        
        with open(output_path, "wb") as f:
            f.write(final_plaintext)

    @staticmethod
    def wrap_aes_key(aes_key: bytes, iv: bytes, receiver_pub_pem: str) -> bytes:
        return RSAEnvelope.wrap_key(aes_key + iv, receiver_pub_pem)

    @staticmethod
    def unwrap_aes_key(wrapped: bytes, receiver_priv_pem: str) -> tuple[bytes, bytes]:
        combined = RSAEnvelope.unwrap_key(wrapped, receiver_priv_pem)
        return combined[:16], combined[16:]