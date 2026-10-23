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
    # VÁ #5: đọc cả metadata tin cậy (hasPoP) — trước đây client chỉ đọc được
    # PEM nên KHÔNG THỂ phân biệt khoá đã chứng minh sở hữu với khoá rác.
    {
        "inputs": [{"internalType": "address", "name": "user", "type": "address"}],
        "name": "getKeyRecord",
        "outputs": [
            {"internalType": "string", "name": "publicKeyPem", "type": "string"},
            {"internalType": "bool", "name": "hasPoP", "type": "bool"},
            {"internalType": "uint256", "name": "registeredAt", "type": "uint256"},
        ],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "internalType": "address", "name": "user", "type": "address"},
            {"indexed": False, "internalType": "string", "name": "oldPem", "type": "string"},
            {"indexed": False, "internalType": "string", "name": "newPem", "type": "string"},
            {"indexed": False, "internalType": "uint256", "name": "at", "type": "uint256"},
        ],
        "name": "KeyRotated",
        "type": "event",
    },
]

# --------------------------------------------------------------------------- #
# VÁ #1 + #2: Đảo ngược mô hình tin cậy — ON-CHAIN là nguồn chân lý DUY NHẤT.  #
# RAM cục bộ và Broker chỉ là BỘ ĐỆM CÓ NGUỒN GỐC (cache with provenance),      #
# không bao giờ được là "tác giả" của khoá.                                     #
#                                                                              #
# Trước đây: local RAM (tự khai) -> Broker (không auth) -> chain (trustless)    #
#   => kẻ tấn công chỉ cần đầu độc 1 trong 2 nguồn yếu là che được khoá thật.   #
# Sau vá:  chain (trustless) -> cache chỉ khi CÓ nguồn gốc chain -> degraded     #
# --------------------------------------------------------------------------- #

# Địa chỉ -> (pem, source); source ∈ {"chain", "broker-unverified"}
_LOCAL_REGISTRY: dict[str, tuple[str, str]] = {}
_REGISTRY_LOCK = threading.Lock()

# Các nguồn dữ liệu được coi là "đã xác thực" (có nguồn gốc on-chain)
SOURCE_CHAIN = "chain"
SOURCE_CHAIN_CACHE = "chain-cache"
SOURCE_BROKER = "broker-unverified"


class KeyNotRegistered(Exception):
    """Chain đang sống nhưng không có khoá -> đây là câu trả lời CUỐI CÙNG.

    Không được fallback xuống broker/RAM, vì đó là chỗ kẻ tấn công ghi được.
    """


class ChainUnavailable(Exception):
    """Không thể hỏi chain (node chết / eth_call lỗi / cho phép offline)."""


class KeyUnverified(Exception):
    """Khoá lấy được từ nguồn degraded (broker) — CHƯA được chain xác nhận."""

    def __init__(self, pem: str, message: str = ""):
        super().__init__(message or "Khoá chưa được xác thực on-chain.")
        self.pem = pem


class DPKIClient:
    def __init__(
        self,
        contract_address: str = "0xe7f1725E7734CE288F8367e1Bb143E90bb3F0512",
        rpc_url: str = "http://127.0.0.1:8545",
        broker_url: str = "http://127.0.0.1:8000",
        fallback_to_local: bool = True,
        allow_offline: bool = False,
    ):
        """
        VÁ #4: `allow_offline=False` (MẶC ĐỊNH MỚI).

        Trước đây `fallback_to_local=True` khiến hệ thống im lặng chuyển sang
        nguồn tin cậy thấp mà không báo ai. Giờ degraded mode phải được BẬT
        THỦ CÔNG và KHAI BÁO.
        """
        self.rpc_url = rpc_url
        self.broker_url = broker_url.rstrip("/")
        self.fallback_to_local = fallback_to_local
        # Chế độ suy giảm: chỉ bật khi người vận hành chấp nhận "tin nguồn chưa xác thực".
        self.allow_offline = allow_offline
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

    # ---- VÁ #2: bộ đệm CÓ NGUỒN GỐC (provenance-aware cache) ----

    @staticmethod
    def _cache_put(key: str, pem: str, *, source: str) -> None:
        with _REGISTRY_LOCK:
            _LOCAL_REGISTRY[key] = (pem, source)

    @staticmethod
    def _cache_get(key: str) -> tuple[str, str] | None:
        with _REGISTRY_LOCK:
            return _LOCAL_REGISTRY.get(key)

    @staticmethod
    def _cache_del(key: str) -> None:
        with _REGISTRY_LOCK:
            _LOCAL_REGISTRY.pop(key, None)

    def get_public_key_with_provenance(self, wallet_address: str) -> tuple[str, str]:
        """
        Tra cứu Public Key RSA bằng địa chỉ ví Ethereum.

        THỨ TỰ ƯU TIÊN (đã đảo ngược so với bản cũ — xem ghi chú VÁ #1/#2 ở đầu file):

        1. ON-CHAIN qua Smart Contract — NGUỒN CHÂN LÝ DUY NHẤT.
           - Có khoá  -> trả về, cache với source="chain".
           - Trả rỗng (và chain đang sống) -> raise KeyNotRegistered.
             TUYỆT ĐỐI KHÔNG fallback xuống broker: broker không có auth,
             kẻ tấn công POST 1 lần là che được khoá thật.
           - eth_call lỗi -> raise ChainUnavailable (không đoán bừa).

        2. Chain chết:
           - allow_offline=False -> raise ChainUnavailable.
           - allow_offline=True  -> dùng degraded mode:
             · Cache cũ có source="chain" -> trả về (source="chain-cache").
             · Broker -> trả về nhưng ném KeyUnverified(pem) để caller BẮT BUỘC
               biết khoá này chưa được xác thực. Không được im lặng.

        Returns:
            (pem, source) với source ∈ {"chain", "chain-cache", "broker-unverified"}

        Raises:
            KeyNotRegistered — chain sống và chưa có khoá (câu trả lời cuối cùng)
            ChainUnavailable — không thể hỏi chain và không được phép offline
        """
        checksum_addr = Web3.to_checksum_address(wallet_address)
        key = checksum_addr.lower()

        # ---- 1. ON-CHAIN LÀ NGUỒN CHÂN LÝ ----
        if self.is_live_chain():
            has_pop = True  # contract cũ chưa có getKeyRecord -> không chặn
            try:
                # VÁ #5: đọc kèm hasPoP để không bao giờ tin khoá chưa PoP.
                pub_key, has_pop, _reg_at = self.contract.functions.getKeyRecord(
                    checksum_addr
                ).call()
            except Exception:
                # Fallback cho contract chưa nâng cấp (chưa có getKeyRecord).
                try:
                    pub_key = self.contract.functions.getPublicKey(checksum_addr).call()
                except Exception as e:
                    # Chain sống nhưng eth_call lỗi -> KHÔNG được đoán bừa.
                    raise ChainUnavailable(f"Chain sống nhưng eth_call lỗi: {e}") from e

            if pub_key and pub_key.strip():
                if not has_pop:
                    # Có khoá nhưng chưa chứng minh sở hữu -> coi như CHƯA đăng ký.
                    self._cache_del(key)
                    raise KeyNotRegistered(
                        f"Ví {wallet_address} có khoá on-chain nhưng KHÔNG có "
                        "Proof-of-Possession (hasPoP=false) — từ chối sử dụng khoá này."
                    )
                self._cache_put(key, pub_key, source=SOURCE_CHAIN)
                return pub_key, SOURCE_CHAIN

            # Chain trả rỗng + chain đang sống = CHƯA ĐĂNG KÝ. Đây là kết luận cuối.
            self._cache_del(key)
            raise KeyNotRegistered(
                f"Ví {wallet_address} chưa đăng ký RSA Public Key trên dPKI on-chain."
            )

        # ---- 2. Chain chết: chỉ khi được phép mới dùng degraded mode ----
        if not self.allow_offline:
            raise ChainUnavailable(
                "Không kết nối được EVM node và allow_offline=False. "
                "Từ chối tra khoá vì không thể xác thực nguồn."
            )

        cached = self._cache_get(key)
        if cached and cached[1] in (SOURCE_CHAIN, SOURCE_CHAIN_CACHE):
            return cached[0], SOURCE_CHAIN_CACHE

        try:
            resp = requests.get(
                f"{self.broker_url}/api/v1/dpki/keys/{checksum_addr}", timeout=1
            )
            if resp.status_code == 200:
                pem = resp.json().get("public_key_pem", "")
                if pem:
                    self._cache_put(key, pem, source=SOURCE_BROKER)
                    # KHÔNG trả ngầm — ném để caller phải xử lý tình trạng "chưa xác thc".
                    raise KeyUnverified(
                        pem,
                        "Khoá lấy từ Broker dPKI, CHƯA được xác thực on-chain.",
                    )
        except KeyUnverified:
            raise
        except Exception:
            pass

        raise ChainUnavailable("Chain chết và broker không có khoá. Không thể tra cứu.")

    def get_public_key(self, wallet_address: str) -> str:
        """
        Wrapper tương thích ngược: chỉ trả PEM.

        LƯU Ý: hàm này NUỐT thông tin nguồn gốc (provenance). Code mới NÊN gọi
        `get_public_key_with_provenance()` để phân biệt được khoá đã xác thực
        on-chain với khoá degraded.
        """
        try:
            pem, _source = self.get_public_key_with_provenance(wallet_address)
            return pem
        except KeyUnverified as e:
            # Degraded mode: trả khoá nhưng cảnh báo rõ ràng trong log.
            logger.warning(
                "Trả khoá CHƯA xác thực on-chain cho %s (nguồn: broker)", wallet_address
            )
            return e.pem

    # ------------------------------------------------------------------ #
    # VÁ #3 (phía client): đăng ký lên Broker phải kèm chữ ký EIP-191    #
    # ------------------------------------------------------------------ #
    @staticmethod
    def _broker_register_message(address: str, pem: str, ts: int) -> str:
        """Thông điệp chuẩn để broker xác thực chủ sở hữu địa chỉ ví."""
        import hashlib

        pem_digest = hashlib.sha256(pem.encode("utf-8")).hexdigest()
        return (
            "CloakShare dPKI Register\n"
            f"address: {address.lower()}\n"
            f"ts: {ts}\n"
            f"pem_sha256: {pem_digest}"
        )

    def _post_broker_registration(self, checksum_addr: str, public_key_pem: str, private_key_hex: str) -> bool:
        """Gửi đăng ký khoá lên Broker, CÓ chữ ký EIP-191 của chủ ví.

        Broker không còn là nơi ai cũng ghi được. Broker chỉ là RELAY —
        khoá ở đây luôn bị đánh dấu "unverified" cho tới khi có trên chain.
        """
        import time as _time

        from eth_account import Account as _Account
        from eth_account.messages import encode_defunct

        ts = int(_time.time())
        msg = self._broker_register_message(checksum_addr, public_key_pem, ts)
        try:
            signed = _Account.sign_message(encode_defunct(text=msg), private_key=private_key_hex)
            sig_hex = signed.signature.hex()
        except Exception as e:
            logger.warning("Không ký được yêu cầu đăng ký broker: %s", e)
            return False

        try:
            resp = requests.post(
                f"{self.broker_url}/api/v1/dpki/register",
                json={
                    "address": checksum_addr,
                    "public_key_pem": public_key_pem,
                    "timestamp": ts,
                    "signature": sig_hex,
                },
                timeout=2,
            )
            if resp.status_code != 200:
                logger.warning(
                    "Broker từ chối đăng ký khoá (HTTP %s): %s", resp.status_code, resp.text[:200]
                )
                return False
            return True
        except Exception as e:
            logger.warning("Không gửi được đăng ký broker: %s", e)
            return False

    def register_public_key(self, private_key_hex: str, public_key_pem: str, rsa_private_key_path: Optional[str] = None) -> str:
        """
        Đăng ký Public Key RSA của ví.

        THỨ TỰ ĐÃ SỬA (VÁ #1/#2):
          1. Ghi ON-CHAIN trước (nguồn chân lý).
          2. Đọc lại từ chain để XÁC NHẬN rồi mới ghi cache.
          3. Chỉ sau đó mới báo Broker (relay, không phải tác giả).

        Bản cũ ghi RAM + Broker TRƯỚC khi kiểm tra chain, khiến giá trị
        CHƯA được chain xác nhận trở thành nguồn ưu tiên số 1 — đó chính là
        lỗ hổng "cache poisoning by design".

        Args:
            private_key_hex: Ethereum private key (hex)
            public_key_pem: RSA public key (PEM format)
            rsa_private_key_path: Optional path to RSA private key for PoP validation

        Returns:
            Transaction hash (on-chain) hoặc local registration ID (degraded)
        """
        account = Account.from_key(private_key_hex)
        checksum_addr = Web3.to_checksum_address(account.address)
        key = checksum_addr.lower()

        # ---- 0. Chain chết? ----
        if not self.is_live_chain():
            if not self.allow_offline:
                raise ChainUnavailable(
                    "Không thể đăng ký khoá: cần EVM node để ghi vĩnh viễn. "
                    "Đặt allow_offline=True nếu chấp nhận chế độ suy giảm (KHÔNG khuyến nghị)."
                )
            logger.warning(
                "DEGRADED: đăng ký khoá cho %s KHÔNG có on-chain. Chỉ broker/local.",
                checksum_addr,
            )
            self._post_broker_registration(checksum_addr, public_key_pem, private_key_hex)
            # KHÔNG cache như "chain" — chỉ đánh dấu unverified.
            self._cache_put(key, public_key_pem, source=SOURCE_BROKER)
            return f"0xlocal_{key[2:10]}_{hex(abs(hash(public_key_pem)))[2:10]}"

        # ---- 1. Ghi ON-CHAIN (nguồn chân lý) ----
        try:
            # Đã đúng khoá này VÀ đã có PoP rồi thì không tốn gas lại.
            # VÁ #5: phải kiểm `hasPoP` — trước đây chỉ so PEM, nên một bản ghi
            # legacy (không PoP) trùng PEM sẽ khiến ta bỏ qua bước chứng minh
            # sở hữu và coi như "đã đăng ký đàng hoàng".
            try:
                pem_onchain, has_pop, _ts = self.contract.functions.getKeyRecord(
                    account.address
                ).call()
                if pem_onchain == public_key_pem and has_pop:
                    self._cache_put(key, public_key_pem, source=SOURCE_CHAIN)
                    self._post_broker_registration(checksum_addr, public_key_pem, private_key_hex)
                    return f"0xonchain_{key[2:10]}"
            except Exception:
                # Contract cũ chưa có getKeyRecord -> bỏ qua shortcut, đi PoP.
                pass

            nonce = self.w3.eth.get_transaction_count(account.address)
            tx_hash = None

            # 1a. PoP là ĐƯỜNG DUY NHẤT (VÁ #5) — không còn fallback legacy.
            # Trước đây nếu PoP lỗi (vd: thiếu file khoá RSA, sai mật khẩu PEM),
            # code âm thầm rơi xuống `registerPublicKey()` — hàm không yêu cầu
            # chứng minh sở hữu khoá riêng. Kết quả: kẻ tấn công chỉ cần làm PoP
            # thất bại là đăng ký được khoá rác, và vì chain không phân biệt
            # `hasPoP`, mọi client vẫn tin khoá đó là thật. Nay PoP thất bại
            # nghĩa là ĐĂNG KÝ THẤT BẠI, không có đường vòng.
            if not rsa_private_key_path:
                raise RuntimeError(
                    "Từ chối đăng ký khoá lên chain: thiếu RSA private key để tạo "
                    "Proof-of-Possession. Hãy tạo lại cặp khoá RSA "
                    "(chạy: python scripts/gen_rsa_keys.py) rồi thử lại."
                )

            from . import pop_helper

            with open(rsa_private_key_path, "rb") as f:
                rsa_private_key_pem = f.read()

            pop_signature = pop_helper.generate_pop_signature(
                private_key_hex, rsa_private_key_pem
            )

            tx = self.contract.functions.registerPublicKeyWithPoP(
                public_key_pem, pop_signature
            ).build_transaction({
                "from": account.address,
                "nonce": nonce,
                "chainId": self.w3.eth.chain_id,
                "gas": 2_000_000,  # PoP validation tốn nhiều gas hơn
                "gasPrice": self.w3.eth.gas_price,
            })
            signed_tx = self.w3.eth.account.sign_transaction(tx, private_key=private_key_hex)
            raw = self.w3.eth.send_raw_transaction(signed_tx.raw_transaction)
            receipt = self.w3.eth.wait_for_transaction_receipt(raw, timeout=10)
            if receipt.status != 1:
                raise RuntimeError(
                    f"PoP transaction REVERT (status={receipt.status})! Hash: {raw.hex()}"
                )
            logger.info("✓ Đã đăng ký với Proof-of-Possession")
            # BUG ĐÃ SỬA: `receipt.transactionHash` là `HexBytes`, và `HexBytes.hex()`
            # KHÔNG thêm tiền tố "0x" (nó trả về đúng 64 ký tự hex). Hệ quả: hàm
            # `register_public_key()` trả về chuỗi KHÔNG có "0x" — tức là không còn
            # là transaction hash hợp lệ nữa. Mọi caller làm `tx.startswith("0x")`
            # hoặc nộp chuỗi này cho Etherscan/block explorer đều hỏng.
            # Phải dùng `to_0x_hex()` để giữ nguyên định dạng 0x + 64 hex.
            tx_hash = Web3.to_hex(raw)

            # ---- 2. ĐỌC LẠI TỪ CHAIN để xác nhận TRƯỚC khi cache ----
            # VÁ #5: xác nhận cả PEM LẪN hasPoP. Chỉ cache khi chain thực sự
            # ghi nhận khoá này ĐÃ qua Proof-of-Possession.
            confirmed, confirmed_pop, _reg_at = self.contract.functions.getKeyRecord(
                account.address
            ).call()
            if confirmed != public_key_pem:
                raise RuntimeError(
                    "Chain KHÔNG xác nhận khoá vừa ghi — từ chối cache để tránh "
                    "dùng khoá chưa được chứng thực."
                )
            if not confirmed_pop:
                raise RuntimeError(
                    "Chain ghi nhận khoá nhưng KHÔNG có Proof-of-Possession "
                    "(hasPoP=false) — từ chối cache: khoá này chưa chứng minh "
                    "được quyền sở hữu khoá riêng tương ứng."
                )
            self._cache_put(key, confirmed, source=SOURCE_CHAIN)

            # ---- 3. Broker chỉ là RELAY sau khi chain đã xác nhận ----
            self._post_broker_registration(checksum_addr, public_key_pem, private_key_hex)
            return tx_hash

        except Exception as e:
            # VÁ #5: chain ĐANG SỐNG mà ghi thất bại (PoP sai, thiếu khoá RSA,
            # tx revert, hết gas...) thì TUYỆT ĐỐI KHÔNG được âm thầm rơi xuống
            # broker. Trước đây `allow_offline=True` biến mọi lỗi on-chain thành
            # một lần "đăng ký thành công" ở broker — nghĩa là kẻ tấn công chỉ
            # cần làm PoP thất bại là có ngay bản ghi khoá, và UI vẫn báo xanh.
            # `allow_offline` chỉ được dùng khi chain CHẾT (nhánh 0 ở trên),
            # không bao giờ dùng để che lỗi của một chain đang sống.
            logger.error("Đăng ký on-chain THẤT BẠI (chain đang sống): %s", e)
            raise

    def get_status(self) -> dict:
        """Thông tin trạng thái kết nối dPKI phục vụ UI và giám sát (VÁ #4)."""
        live = self.is_live_chain()
        with _REGISTRY_LOCK:
            local_count = len(_LOCAL_REGISTRY)
            unverified_count = sum(
                1 for _pem, src in _LOCAL_REGISTRY.values() if src == SOURCE_BROKER
            )
        if live:
            mode, trust = "on-chain", "trustless"
        elif self.allow_offline:
            mode, trust = "offline-degraded", "degraded"
        else:
            mode, trust = "unavailable", "unavailable"
        return {
            "is_live_chain": live,
            "mode": mode,
            "trust_level": trust,
            "allow_offline": self.allow_offline,
            "rpc_url": self.rpc_url,
            "broker_url": self.broker_url,
            "contract_address": self.contract_address,
            "cached_keys_count": local_count,
            "unverified_keys_count": unverified_count,
        }