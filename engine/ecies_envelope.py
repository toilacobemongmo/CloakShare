import ecies

class ECIESEnvelope:
    @staticmethod
    def wrap_key(aes_key: bytes, receiver_public_hex: str) -> bytes:
        """Mã hóa khóa AES/IV bằng ECIES (Sử dụng trực tiếp Public Key của ví EVM)."""
        return ecies.encrypt(receiver_public_hex, aes_key)

    @staticmethod
    def unwrap_key(wrapped_key: bytes, receiver_private_hex: str) -> bytes:
        """Giải mã khóa AES/IV bằng ECIES (Sử dụng trực tiếp Private Key của ví EVM)."""
        try:
            return ecies.decrypt(receiver_private_hex, wrapped_key)
        except Exception as e:
            raise ValueError(f"Decryption failed: Private Key ví không khớp hoặc dữ liệu bọc bị hỏng! Lỗi: {e}")
