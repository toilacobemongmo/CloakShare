from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.backends import default_backend

class RSAEnvelope:
    @staticmethod
    def wrap_key(aes_key: bytes, receiver_public_pem: str) -> bytes:
        """
        Bọc (mã hóa) khóa AES 16 bytes bằng Public Key RSA-2048 của người nhận.
        Sử dụng chuẩn OAEP với MGF1(SHA-256).
        """
        if len(aes_key) != 16:
            raise ValueError("Khóa AES cần bọc phải có độ dài chính xác 16 bytes")

        # Nạp Public Key từ chuỗi định dạng PEM
        public_key = serialization.load_pem_public_key(
            receiver_public_pem.encode('utf-8'),
            backend=default_backend()
        )

        # Mã hóa khóa AES bằng thuật toán RSA-OAEP
        wrapped_key = public_key.encrypt(
            aes_key,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        )
        return wrapped_key

    @staticmethod
    def unwrap_key(wrapped_key: bytes, receiver_private_pem: str) -> bytes:
        """
        Mở phong bì (giải mã) lấy lại khóa AES bằng Private Key RSA của người nhận.
        """
        try:
            private_key = serialization.load_pem_private_key(
                receiver_private_pem.encode('utf-8'),
                password=None,
                backend=default_backend()
            )

            aes_key = private_key.decrypt(
                wrapped_key,
                padding.OAEP(
                    mgf=padding.MGF1(algorithm=hashes.SHA256()),
                    algorithm=hashes.SHA256(),
                    label=None
                )
            )
            return aes_key
        except Exception:
            # Bắt toàn bộ lỗi Padding/Decryption Error và quy về lỗi chuẩn
            raise ValueError("Decryption failed: Khóa Private Key không khớp hoặc dữ liệu bọc bị hỏng!")