from web3 import Web3
from typing import Optional

# ABI tối giản của Smart Contract dPKI (Identity Registry)
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
    def __init__(self, rpc_url: str, contract_address: str):
        self.w3 = Web3(Web3.HTTPProvider(rpc_url))
        self.contract_address = Web3.to_checksum_address(contract_address)
        self.contract = self.w3.eth.contract(address=self.contract_address, abi=DPKI_ABI)

    def get_public_key(self, wallet_address: str) -> Optional[str]:
        """Tra cứu Public Key RSA của một địa chỉ ví từ Smart Contract"""
        checksum_addr = Web3.to_checksum_address(wallet_address)
        pub_key = self.contract.functions.getPublicKey(checksum_addr).call()
        if not pub_key:
            raise ValueError(f"Ví {wallet_address} chưa đăng ký Public Key trên dPKI Contract!")
        return pub_key

    def register_public_key(self, private_key_hex: str, public_key_pem: str) -> str:
        """Ký và gửi transaction đăng ký Public Key RSA của bản thân lên Contract"""
        account = self.w3.eth.account.from_key(private_key_hex)
        nonce = self.w3.eth.get_transaction_count(account.address)
        
        tx = self.contract.functions.registerPublicKey(public_key_pem).build_transaction({
            'from': account.address,
            'nonce': nonce,
            'gas': 200000,
            'maxFeePerGas': self.w3.to_wei('35', 'gwei'),
            'maxPriorityFeePerGas': self.w3.to_wei('30', 'gwei'),
            'chainId': self.w3.eth.chain_id
        })
        
        signed_tx = self.w3.eth.account.sign_transaction(tx, private_key=private_key_hex)
        tx_hash = self.w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        return tx_hash.hex()