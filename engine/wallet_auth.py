from web3 import Web3
from eth_account.messages import encode_defunct
from eth_account import Account

class Web3Auth:
    def __init__(self, rpc_url: str = "https://rpc-amoy.polygon.technology"):
        self.w3 = Web3(Web3.HTTPProvider(rpc_url))

    @staticmethod
    def sign_challenge(private_key_hex: str, message: str) -> str:
        """
        Ký số một thông điệp challenge bằng ví Web3 để xác thực danh tính với Broker.
        """
        signable_msg = encode_defunct(text=message)
        signed = Account.sign_message(signable_msg, private_key=private_key_hex)
        return signed.signature.hex()

    @staticmethod
    def verify_signature(address: str, message: str, signature_hex: str) -> bool:
        """
        Broker dùng hàm này để kiểm tra chữ ký có đúng do chủ ví ký ra hay không.
        """
        try:
            signable_msg = encode_defunct(text=message)
            recovered_addr = Account.recover_message(signable_msg, signature=signature_hex)
            return recovered_addr.lower() == address.lower()
        except Exception:
            return False