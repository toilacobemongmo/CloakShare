"""
engine/signer.py

Module ký số và kiểm tra toàn vẹn file cho CloakShare (Issue #6).

Sử dụng RSA-PSS (Probabilistic Signature Scheme) + SHA-256 theo đúng
Interface Contract:
    - sign_file(data, sender_private_pem)   -> chữ ký (bytes)
    - verify_file(data, signature, sender_public_pem) -> True/False

Chỉ dùng để KÝ SỐ TOÀN VẸN (integrity/authenticity), không phải mã hoá.
Việc mã hoá dữ liệu do module core/engine AES-128-CBC (Issue #1-5) đảm nhiệm.
Người nhận (Buyer) phải verify_file() TRƯỚC khi tin tưởng giải mã file.
"""

from __future__ import annotations

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding


class IntegritySigner:
    """
    Đóng gói logic ký số / kiểm tra chữ ký RSA-PSS + SHA-256.
    Mọi phương thức đều là @staticmethod theo đúng Interface Contract
    của Issue #6 - không cần khởi tạo instance.
    """

    # PSS salt length dùng chuẩn khuyến nghị: bằng độ dài digest (SHA-256 = 32 byte).
    # (PSS.MAX_LENGTH cũng hợp lệ nhưng DIGEST_LENGTH cho salt cố định,
    # dễ dự đoán kích thước chữ ký hơn khi ghép vào giao thức truyền tin.)
    _PADDING = padding.PSS(
        mgf=padding.MGF1(hashes.SHA256()),
        salt_length=padding.PSS.DIGEST_LENGTH,
    )
    _HASH_ALGO = hashes.SHA256()

    @staticmethod
    def sign_file(data: bytes, sender_private_pem: str) -> bytes:
        """
        Ký số `data` bằng Private Key RSA của người gửi (PEM string).

        Tham số:
            data                : nội dung file (hoặc digest) cần ký, dạng bytes.
            sender_private_pem  : Private Key RSA ở dạng chuỗi PEM
                                   (ví dụ đọc từ file .pem bằng open().read()).

        Trả về:
            Chữ ký số dạng bytes (độ dài = key size, ví dụ 256 byte với RSA-2048).

        Raises:
            ValueError / TypeError - nếu PEM không hợp lệ hoặc không phải khoá RSA.
        """
        if not isinstance(data, bytes):
            raise TypeError("data phải là bytes")

        pem_bytes = (
            sender_private_pem.encode("utf-8")
            if isinstance(sender_private_pem, str)
            else sender_private_pem
        )

        private_key = serialization.load_pem_private_key(
            pem_bytes,
            password=None,
        )

        signature = private_key.sign(
            data,
            IntegritySigner._PADDING,
            IntegritySigner._HASH_ALGO,
        )
        return signature

    @staticmethod
    def verify_file(data: bytes, signature: bytes, sender_public_pem: str) -> bool:
        """
        Kiểm tra `signature` có khớp với `data` dưới Public Key RSA của
        người gửi (PEM string) hay không.

        Tham số:
            data               : nội dung file (hoặc digest) cần kiểm tra.
            signature          : chữ ký số nhận được (bytes).
            sender_public_pem  : Public Key RSA ở dạng chuỗi PEM, thường
                                  lấy từ dPKI (Smart Contract Registry -
                                  Issue #11) tương ứng với địa chỉ ví người gửi.

        Trả về:
            True  - chữ ký hợp lệ, data còn nguyên vẹn, đúng là của người gửi.
            False - chữ ký sai, hoặc data đã bị thay đổi/giả mạo (kể cả khi
                    chỉ lệch 1 bit), hoặc PEM không hợp lệ / lỗi định dạng.

        Hàm này KHÔNG raise exception ra ngoài - mọi lỗi (khoá sai, PEM hỏng,
        chữ ký không khớp) đều được quy về False, để lớp gọi (Broker/UI) chỉ
        cần kiểm tra boolean, không cần bọc try/except riêng.
        """
        try:
            pem_bytes = (
                sender_public_pem.encode("utf-8")
                if isinstance(sender_public_pem, str)
                else sender_public_pem
            )

            public_key = serialization.load_pem_public_key(pem_bytes)

            public_key.verify(
                signature,
                data,
                IntegritySigner._PADDING,
                IntegritySigner._HASH_ALGO,
            )
            return True

        except InvalidSignature:
            # Chữ ký không khớp - data bị đổi hoặc signature giả mạo.
            return False
        except (ValueError, TypeError):
            # PEM sai định dạng, khoá không phải RSA, signature rỗng, v.v.
            return False
