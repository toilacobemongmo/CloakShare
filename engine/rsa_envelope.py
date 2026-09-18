from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.backends import default_backend

def generate_rsa_key_pair():
    """Tạo cặp khóa RSA 2048-bit (Private Key và Public Key dưới dạng PEM bytes)."""
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
        backend=default_backend()
    )
    pem_private = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    )
    pem_public = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    )
    return pem_private, pem_public

def encrypt_aes_key_with_rsa(receiver_public_pem: bytes, aes_key: bytes) -> bytes:
    """Mã hóa khóa AES/IV bằng RSA Public Key chuẩn OAEP (SHA-256)."""
    public_key = serialization.load_pem_public_key(
        receiver_public_pem,
        backend=default_backend()
    )
    return public_key.encrypt(
        aes_key,
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None
        )
    )

def decrypt_aes_key_with_rsa(receiver_private_pem: bytes, wrapped_key: bytes) -> bytes:
    """Giải mã khóa AES/IV bằng RSA Private Key."""
    try:
        private_key = serialization.load_pem_private_key(
            receiver_private_pem,
            password=None,
            backend=default_backend()
        )
        return private_key.decrypt(
            wrapped_key,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        )
    except Exception:
        raise ValueError("Decryption failed: Private Key không khớp hoặc dữ liệu bọc bị hỏng!")

class RSAEnvelope:
    @staticmethod
    def wrap_key(aes_key: bytes, receiver_public_pem: str) -> bytes:
        return encrypt_aes_key_with_rsa(receiver_public_pem.encode('utf-8'), aes_key)

    @staticmethod
    def unwrap_key(wrapped_key: bytes, receiver_private_pem: str) -> bytes:
        return decrypt_aes_key_with_rsa(receiver_private_pem.encode('utf-8'), wrapped_key)