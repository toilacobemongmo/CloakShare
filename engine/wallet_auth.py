import time
from eth_account import Account
from eth_account.messages import encode_defunct
from web3 import Web3


class Web3Auth:
    AUTH_MESSAGE_PREFIX = "CloakShare Retrieve Auth"
    MAX_CLOCK_DRIFT = 60  # Cho phép chênh lệch tối đa 60 giây

    def __init__(self, rpc_url: str = "https://rpc-amoy.polygon.technology"):
        self.w3 = Web3(Web3.HTTPProvider(rpc_url))

    @classmethod
    def create_retrieve_message(cls, tx_id: str, timestamp: int) -> str:
        """Tạo chuỗi thông điệp chuẩn mực cho việc xác thực rút file."""
        return f"{cls.AUTH_MESSAGE_PREFIX}: {tx_id} @ {timestamp}"

    @classmethod
    def sign_challenge(cls, private_key_hex: str, message: str) -> str:
        """Ký số một thông điệp tùy ý bằng ví Web3 (EIP-191)."""
        signable_msg = encode_defunct(text=message)
        signed = Account.sign_message(signable_msg, private_key=private_key_hex)
        return signed.signature.hex()

    @classmethod
    def verify_signature(cls, address: str, message: str, signature_hex: str) -> bool:
        """Broker kiểm tra chữ ký của thông điệp bất kỳ."""
        try:
            signable_msg = encode_defunct(text=message)
            recovered_addr = Account.recover_message(signable_msg, signature=signature_hex)
            return recovered_addr.lower() == address.lower()
        except Exception:
            return False

    @classmethod
    def sign_retrieve_request(
        cls, tx_id: str, private_key_hex: str, timestamp: int | None = None
    ) -> tuple[int, str]:
        """Buyer tạo timestamp và ký challenge rút file."""
        ts = timestamp if timestamp is not None else int(time.time())
        msg = cls.create_retrieve_message(tx_id, ts)
        sig = cls.sign_challenge(private_key_hex, msg)
        return ts, sig

    @classmethod
    def verify_retrieve_request(
        cls, tx_id: str, address: str, timestamp: int, signature_hex: str
    ) -> bool:
        """Broker xác thực chữ ký và kiểm tra giới hạn thời gian (chống Replay Attack)."""
        current_time = int(time.time())
        if abs(current_time - timestamp) > cls.MAX_CLOCK_DRIFT:
            return False

        msg = cls.create_retrieve_message(tx_id, timestamp)
        return cls.verify_signature(address, msg, signature_hex)