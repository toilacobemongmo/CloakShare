import logging
import threading
from typing import Optional
import requests
from web3 import Web3
from eth_account import Account

logger = logging.getLogger("dpki_client")

DPKI_ABI = [
    {
        "inputs": [{"internalType": "string", "name": "publicKeyPem", "type": "string"}],
        "name": "registerPublicKey",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [
            {"internalType": "string", "name": "publicKeyPem", "type": "string"},
            {"internalType": "bytes", "name": "signature", "type": "bytes"}
        ],
        "name": "registerPublicKeyWithPoP",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [{"internalType": "address", "name": "user", "type": "address"}],
        "name": "getPublicKey",
        "outputs": [{"internalType": "string", "name": "", "type": "string"}],
        "stateMutability": "view",
        "type": "function",
    },
]

# Bộ nhớ đệm cục bộ (Fallback Safe Mode) khi Anvil/EVM RPC không chạy
_LOCAL_REGISTRY: dict[str, str] = {}
_REGISTRY_LOCK = threading.Lock()


class DPKIClient:
    def __init__(
        self,
        contract_address: str = "0xe7f1725E7734CE288F8367e1Bb143E90bb3F0512",
        rpc_url: str = "http://127.0.0.1:8545",
        broker_url: str = "http://127.0.0.1:8000",
        fallback_to_local: bool = True,
    ):
        self.rpc_url = rpc_url
        self.broker_url = broker_url.rstrip("/")
        self.fallback_to_local = fallback_to_local
        self.w3 = Web3(Web3.HTTPProvider(rpc_url, request_kwargs={"timeout": 2}))
        self.contract_address = Web3.to_checksum_address(contract_address)
        try:
            self.contract = self.w3.eth.contract(address=self.contract_address, abi=DPKI_ABI)
        except Exception:
            self.contract = None

    _last_check_ts: float = 0.0
    _cached_status: bool = False

    def is_connected(self) -> bool:
        """Kiểm tra cực nhanh xem node RPC 8545 có chạy không (timeout 50ms, cache 30s)."""
        import time, socket
        from urllib.parse import urlparse
        now = time.time()
        if now - DPKIClient._last_check_ts < 30.0:
            return DPKIClient._cached_status
        DPKIClient._last_check_ts = now
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            _u = urlparse(self.rpc_url)
            s.settimeout(0.5)
            s.connect((_u.hostname or "127.0.0.1", _u.port or 8545))
            s.close()
            DPKIClient._cached_status = True
        except Exception:
            DPKIClient._cached_status = False
        return DPKIClient._cached_status

    def is_live_chain(self) -> bool:
        """Kiểm tra kết nối và contract sẵn sàng."""
        return self.is_connected() and self.contract is not None

    def get_public_key(self, wallet_address: str) -> str:
        """
        Tra cứu Public Key RSA bằng địa chỉ ví Ethereum.
        Thứ tự ưu tiên:
        1. On-Chain qua Smart Contract (nếu có blockchain node)
        2. Bộ nhớ đệm RAM cục bộ (_LOCAL_REGISTRY)
        3. Broker dPKI Registry trung tâm qua mạng LAN/Internet (/api/v1/dpki/keys/{address})
        """
        checksum_addr = Web3.to_checksum_address(wallet_address)

        # 1. Kiểm tra bộ nhớ đệm RAM cục bộ trước (tức thì 0ms, không lag)
        with _REGISTRY_LOCK:
            val = _LOCAL_REGISTRY.get(checksum_addr.lower())
        if val and len(val.strip()) > 0:
            return val

        # 2. Tra cứu từ Broker dPKI Relay (chia sẻ giữa các máy qua mạng)
        try:
            resp = requests.get(f"{self.broker_url}/api/v1/dpki/keys/{checksum_addr}", timeout=1)
            if resp.status_code == 200:
                remote_pem = resp.json().get("public_key_pem", "")
                if remote_pem:
                    with _REGISTRY_LOCK:
                        _LOCAL_REGISTRY[checksum_addr.lower()] = remote_pem
                    return remote_pem
        except Exception:
            pass

        # 3. Thử gọi On-Chain nếu có blockchain node Anvil đang chạy
        if self.is_live_chain():
            try:
                pub_key: str = self.contract.functions.getPublicKey(checksum_addr).call()
                if pub_key and len(pub_key.strip()) > 0:
                    with _REGISTRY_LOCK:
                        _LOCAL_REGISTRY[checksum_addr.lower()] = pub_key
                    return pub_key
            except Exception as e:
                if not self.fallback_to_local:
                    raise e
        raise ValueError(f"Ví {wallet_address} chưa đăng ký RSA Public Key trên dPKI.")

    def register_public_key(self, private_key_hex: str, public_key_pem: str, rsa_private_key_path: Optional[str] = None) -> str:
        """
        Ký và gửi transaction lưu Public Key của ví lên Blockchain.
        Đồng thời đồng bộ lên Broker RAM dPKI để các máy khác trong mạng cùng thấy.
        
        Args:
            private_key_hex: Ethereum private key (hex)
            public_key_pem: RSA public key (PEM format)
            rsa_private_key_path: Optional path to RSA private key for PoP validation
        
        Returns:
            Transaction hash hoặc local registration ID
        """
        account = Account.from_key(private_key_hex)
        checksum_addr = Web3.to_checksum_address(account.address)

        # Đồng bộ vào bộ nhớ đệm cục bộ
        with _REGISTRY_LOCK:
            _LOCAL_REGISTRY[checksum_addr.lower()] = public_key_pem

        # Đồng bộ lên Broker dPKI Relay (cho các máy khác trong mạng truy vấn)
        try:
            requests.post(
                f"{self.broker_url}/api/v1/dpki/register",
                json={"address": checksum_addr, "public_key_pem": public_key_pem},
                timeout=2,
            )
        except Exception:
            pass

        # 1. Thử gửi on-chain transaction với PoP nếu có RSA private key
        if self.is_live_chain():
            try:
                try:
                    # Đã đăng ký đúng khóa này rồi thì không gửi giao dịch nữa (tránh tốn gas mỗi lần tải lại trang)
                    if self.contract.functions.getPublicKey(account.address).call() == public_key_pem:
                        return f"0xonchain_{checksum_addr.lower()[2:10]}"
                except Exception:
                    pass
                
                nonce = self.w3.eth.get_transaction_count(account.address)
                
                # Nếu có RSA private key, thử gửi với PoP validation
                if rsa_private_key_path:
                    try:
                        from . import pop_helper
                        with open(rsa_private_key_path, 'rb') as f:
                            rsa_private_key_pem = f.read()
                        
                        pop_signature = pop_helper.generate_pop_signature(
                            private_key_hex,
                            rsa_private_key_pem
                        )
                        
                        tx = self.contract.functions.registerPublicKeyWithPoP(
                            public_key_pem,
                            pop_signature
                        ).build_transaction({
                            "from": account.address,
                            "nonce": nonce,
                            "chainId": self.w3.eth.chain_id,
                            "gas": 2_000_000,  # Tăng gas limit vì PoP validation tốn nhiều gas hơn
                            "gasPrice": self.w3.eth.gas_price,
                        })
                        signed_tx = self.w3.eth.account.sign_transaction(tx, private_key=private_key_hex)
                        tx_hash = self.w3.eth.send_raw_transaction(signed_tx.raw_transaction)
                        receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=10)
                        if receipt.status != 1:
                            raise RuntimeError(f"PoP transaction REVERT (status={receipt.status})! Hash: {tx_hash.hex()}")
                        logger.info("✓ Registered with Proof-of-Possession validation")
                        return receipt.transactionHash.hex()
                    except Exception as pop_err:
                        logger.warning("PoP registration failed, falling back to legacy: %s", pop_err)
                
                # Fallback: Gửi legacy registerPublicKey (không có PoP)
                tx = self.contract.functions.registerPublicKey(public_key_pem).build_transaction({
                    "from": account.address,
                    "nonce": nonce,
                    "chainId": self.w3.eth.chain_id,
                    "gas": 1_000_000,
                    "gasPrice": self.w3.eth.gas_price,
                })
                signed_tx = self.w3.eth.account.sign_transaction(tx, private_key=private_key_hex)
                tx_hash = self.w3.eth.send_raw_transaction(signed_tx.raw_transaction)
                receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=10)
                if receipt.status != 1:
                    raise RuntimeError(f"Giao dịch đăng ký bị REVERT (status={receipt.status})! Hash: {tx_hash.hex()}")
                return receipt.transactionHash.hex()
            except Exception as e:
                if not self.fallback_to_local:
                    raise e
                logger.warning("On-chain registerPublicKey failed, registered locally & broker: %s", e)
                return f"0xlocal_{checksum_addr.lower()[2:10]}_{hex(abs(hash(public_key_pem)))[2:10]}"

        # 2. Local/Broker fallback registration
        return f"0xlocal_{checksum_addr.lower()[2:10]}_{hex(abs(hash(public_key_pem)))[2:10]}"

    def get_status(self) -> dict:
        """Thông tin trạng thái kết nối dPKI phục vụ UI và giám sát."""
        live = self.is_live_chain()
        with _REGISTRY_LOCK:
            local_count = len(_LOCAL_REGISTRY)
        return {
            "is_live_chain": live,
            "mode": "On-Chain (EVM)" if live else "Network/Broker Safe-Mode",
            "rpc_url": self.rpc_url,
            "broker_url": self.broker_url,
            "contract_address": self.contract_address,
            "cached_keys_count": local_count,
        }