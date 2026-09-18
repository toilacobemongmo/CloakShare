from web3 import Web3
from typing import Optional

DPKI_ABI = [
    {
        "inputs": [{"internalType": "string", "name": "publicKeyPem", "type": "string"}],
        "name": "registerPublicKey",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [{"internalType": "address", "name": "user", "type": "address"}],
        "name": "getPublicKey",
        "outputs": [{"internalType": "string", "name": "", "type": "string"}],
        "stateMutability": "view",
        "type": "function"
    }
]

class DPKIClient:
    def __init__(
        self, 
        contract_address: str = "0x9fE46736679d2D9a65F0992F2272dE9f3c7fa6e0", 
        rpc_url: str = "http://127.0.0.1:8545"
    ):
        self.w3 = Web3(Web3.HTTPProvider(rpc_url))
        self.contract_address = Web3.to_checksum_address(contract_address)
        self.contract = self.w3.eth.contract(address=self.contract_address, abi=DPKI_ABI)

    def get_public_key(self, wallet_address: str) -> str:
        """Tra cứu Public Key RSA từ Contract bằng địa chỉ ví Ethereum"""
        checksum_addr = Web3.to_checksum_address(wallet_address)
        pub_key: str = self.contract.functions.getPublicKey(checksum_addr).call()
        if not pub_key or len(pub_key.strip()) == 0:
            raise ValueError(f"Ví {wallet_address} chưa đăng ký RSA Public Key trên dPKI Contract.")
        return pub_key

    def register_public_key(self, private_key_hex: str, public_key_pem: str) -> str:
        """Ký và gửi transaction lưu Public Key của ví lên Blockchain"""
        account = self.w3.eth.account.from_key(private_key_hex)
        nonce = self.w3.eth.get_transaction_count(account.address)

        tx = self.contract.functions.registerPublicKey(public_key_pem).build_transaction({
            "from": account.address,
            "nonce": nonce,
            "chainId": self.w3.eth.chain_id,
            "gas": 1_000_000,
            "gasPrice": self.w3.eth.gas_price,
        })

        signed_tx = self.w3.eth.account.sign_transaction(tx, private_key=private_key_hex)
        tx_hash = self.w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)

        if receipt.status != 1:
            raise RuntimeError(f"Giao dịch đăng ký bị REVERT (status={receipt.status})! Hash: {tx_hash.hex()}")

        return receipt.transactionHash.hex()