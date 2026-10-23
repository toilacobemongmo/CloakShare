"""
broker/main.py

Zero-Log In-Memory Staging API (Issue #7).

VÁ #3: Endpoint /api/v1/dpki/register từng KHÔNG có xác thực. Nay bắt buộc
chữ ký EIP-191 của chính `address` được khai báo. Broker không còn là nơi
"ai cũng ghi được" — nó chỉ còn là RELAY, và mọi khoá ở đây bị đánh dấu
`unverified` cho tới khi có mặt on-chain.

Endpoints:
    POST /api/v1/stage            -> 201 Created
    GET  /api/v1/retrieve/{tx_id} -> 200 OK (toàn bộ payload)
    GET  /api/v1/stats            -> số liệu cho Dashboard (Issue #18)
    GET  /health                  -> healthcheck

Cam kết Zero-Log:
  - Payload chỉ nằm trong dictionary trên RAM (broker/memory_store.py).
  - Không có lệnh open() / ghi file nào trong toàn bộ luồng xử lý payload.
  - Access log của Uvicorn bị tắt để tx_id không rơi vào log server.
  - Background task quét và dọn payload quá hạn TTL theo chu kỳ.

Chạy dev:
    uvicorn broker.main:app --reload --port 8000
Chạy đúng chế độ Zero-Log (tắt access log):
    uvicorn broker.main:app --port 8000 --no-access-log
"""

from __future__ import annotations
from engine.wallet_auth import Web3Auth
import asyncio
import contextlib
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, status, Header, Query
from fastapi.middleware.cors import CORSMiddleware

from broker.memory_store import store
from broker.schemas import (
    RetrieveResponse,
    StagePayload,
    StageResponse,
    StatsResponse,
    DPKIRegisterRequest,
    DPKIRegisterResponse,
)

# Chu kỳ chạy background task dọn payload hết hạn (giây).
PURGE_INTERVAL_SECONDS = 5

# Logger dùng cho sự kiện bảo mật (xoay khoá dPKI, từ chối đăng ký...).
# LƯU Ý: logger này CHỈ ghi metadata (địa chỉ ví, thời điểm) — tuyệt đối
# không được log payload hay tx_id, nếu không sẽ phá cam kết Zero-Log.
logger = logging.getLogger(__name__)

# Tắt access log của Uvicorn: tx_id nằm trên URL của endpoint retrieve,
# nếu để mặc định thì tx_id sẽ bị ghi ra log -> vi phạm Zero-Log.
logging.getLogger("uvicorn.access").disabled = True


async def _purge_loop() -> None:
    """Task nền: định kỳ dọn sạch payload đã quá hạn TTL."""
    while True:
        await asyncio.sleep(PURGE_INTERVAL_SECONDS)
        store.purge_expired()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Khởi động task nền khi app start, dọn sạch RAM khi app shutdown."""
    task = asyncio.create_task(_purge_loop())
    try:
        yield
    finally:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
        # Shutdown: wipe toàn bộ payload còn sót lại trên RAM.
        store.purge_all()


app = FastAPI(
    title="CloakShare Zero-Log Broker",
    description="Trạm trung chuyển payload mã hoá, chỉ lưu trên RAM.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post(
    "/api/v1/stage",
    response_model=StageResponse,
    status_code=status.HTTP_201_CREATED,
)
async def stage_payload(payload: StagePayload) -> StageResponse:
    """
    Sender đẩy gói tin đã mã hoá lên Broker.

    Broker KHÔNG giải mã, KHÔNG verify chữ ký, KHÔNG đọc nội dung -
    chỉ giữ nguyên trên RAM tới khi Buyer lấy hoặc hết TTL.
    """
    expires_at = store.stage(
        tx_id=payload.tx_id,
        recipient=payload.recipient,
        iv=payload.iv,
        wrapped_key=payload.wrapped_key,
        ciphertext=payload.ciphertext,
        signature=payload.signature,
        ttl_seconds=payload.ttl_seconds,
    )

    return StageResponse(
        tx_id=payload.tx_id,
        status="staged",
        expires_at=expires_at,
    )




@app.get("/api/v1/stats", response_model=StatsResponse)
async def get_stats() -> StatsResponse:
    """Số liệu giám sát cho Dashboard Broker."""
    return StatsResponse(**store.stats())


@app.get("/api/v1/ram")
async def get_ram_snapshot() -> dict:
    """
    Ảnh chụp trạng thái RAM cho Dashboard Broker.

    Danh sách các payload đang nằm trên RAM (kích thước + thời hạn còn
    lại) và nhật ký sự kiện ghi/xoá gần đây. Toàn bộ dữ liệu chỉ nằm
    trên RAM của tiến trình Broker - endpoint này không ghi gì xuống đĩa.
    """
    return store.ram_snapshot()


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}

@app.get("/api/v1/retrieve/{tx_id}", response_model=RetrieveResponse)
async def retrieve_payload(
    tx_id: str,
    burn: bool = Query(default=False, description="Tự huỷ payload sau khi đọc (burn-after-read)"),
    x_wallet_address: str = Header(..., alias="X-Wallet-Address"),
    x_timestamp: int = Header(..., alias="X-Timestamp"),
    x_signature: str = Header(..., alias="X-Signature"),
) -> RetrieveResponse:
    """
    Buyer lấy toàn bộ payload theo tx_id.
    Bắt buộc phải có chữ ký ví Web3 hợp lệ từ đúng địa chỉ recipient.
    """
    # 1. Kiểm tra tồn tại trong RAM
    data = store.retrieve(tx_id)
    if data is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payload khong ton tai hoac da het han TTL.",
        )

    # 2. Kiểm tra chữ ký ví và time drift (chống Replay Attack)
    is_valid_sig = Web3Auth.verify_retrieve_request(
        tx_id=tx_id,
        address=x_wallet_address,
        timestamp=x_timestamp,
        signature_hex=x_signature,
    )
    if not is_valid_sig:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Chu ky xac thuc vi Web3 khong hop le hoac da qua han.",
        )

    # 3. Kiểm tra địa chỉ ví có đúng là người nhận (recipient) không
    if data["recipient"].lower() != x_wallet_address.lower():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Vi nay khong phai la nguoi nhan duoc chi dinh cho payload.",
        )

    if burn:
        store.purge(tx_id)

    return RetrieveResponse(**data)


@app.delete("/api/v1/payload/{tx_id}")
async def delete_payload(
    tx_id: str,
    x_wallet_address: str = Header(..., alias="X-Wallet-Address"),
    x_timestamp: int = Header(..., alias="X-Timestamp"),
    x_signature: str = Header(..., alias="X-Signature"),
) -> dict[str, str]:
    """
    Buyer yêu cầu huỷ payload trên RAM ngay lập tức (burn-after-read thủ công).
    """
    data = store.retrieve(tx_id)
    if data is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payload khong ton tai hoac da het han TTL.",
        )

    is_valid_sig = Web3Auth.verify_retrieve_request(
        tx_id=tx_id,
        address=x_wallet_address,
        timestamp=x_timestamp,
        signature_hex=x_signature,
    )
    if not is_valid_sig:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Chu ky xac thuc vi Web3 khong hop le hoac da qua han.",
        )

    if data["recipient"].lower() != x_wallet_address.lower():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Vi nay khong phai la nguoi nhan duoc chi dinh cho payload.",
        )

    store.purge(tx_id)
    return {"tx_id": tx_id, "status": "purged_from_ram"}
@app.get("/api/v1/inbox", response_model=list[RetrieveResponse])
async def get_inbox(
    x_wallet_address: str = Header(..., alias="X-Wallet-Address"),
    x_timestamp: int = Header(..., alias="X-Timestamp"),
    x_signature: str = Header(..., alias="X-Signature"),
) -> list[RetrieveResponse]:
    """
    Lấy danh sách các payload đang chờ trong hòm thư của địa chỉ ví.
    Bắt buộc phải có chữ ký ví Web3 hợp lệ từ chính chủ ví đó.
    """
    # 1. Kiểm tra chữ ký ví và time drift (chống Replay Attack dựa trên timestamp chung)
    # Ta có thể dùng hàm verify hoặc tạo một message chuẩn cho inbox request.
    # Để đơn giản và an toàn, ta tái sử dụng cơ chế tạo message với một định danh cố định hoặc timestamp.
    msg = f"CloakShare Inbox Access:{x_timestamp}"
    is_valid_sig = Web3Auth.verify_signature(
        address=x_wallet_address,
        message=msg,
        signature_hex=x_signature,
    )
    
    # Kiểm tra time drift chống replay
    import time
    if not is_valid_sig or abs(int(time.time()) - x_timestamp) > Web3Auth.MAX_CLOCK_DRIFT:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Chu ky xac thuc hòm thư khong hop le hoac da qua han.",
        )

    # 2. Lấy danh sách từ RAM store theo recipient address
    items = store.get_inbox(x_wallet_address)
    return [RetrieveResponse(**item) for item in items]


# ------------------------------------------------------------------ #
# Mạng dPKI Cục Bộ Qua Broker (Hỗ Trợ Đa Máy Không Cần EVM Node)    #
# ------------------------------------------------------------------ #

_BROKER_DPKI_REGISTRY: dict[str, str] = {}

# VÁ #3: cửa sổ thời gian chống replay cho yêu cầu đăng ký khoá.
DPKI_REGISTER_MAX_SKEW_SECONDS = 300


def _dpki_register_message(address: str, pem: str, ts: int) -> str:
    """Thông điệp chuẩn mà chủ ví phải ký (EIP-191) để được đăng ký khoá.

    Ràng buộc cả PEM (qua sha256) lẫn timestamp -> không thể tái dùng chữ ký
    cho một khoá khác, và không thể replay sau cửa sổ thời gian.
    """
    import hashlib

    pem_digest = hashlib.sha256(pem.encode("utf-8")).hexdigest()
    return (
        "CloakShare dPKI Register\n"
        f"address: {address.lower()}\n"
        f"ts: {ts}\n"
        f"pem_sha256: {pem_digest}"
    )


@app.post("/api/v1/dpki/register", response_model=DPKIRegisterResponse)
async def register_broker_dpki(payload: DPKIRegisterRequest) -> DPKIRegisterResponse:
    """Đăng ký Public Key lên bảng danh bạ RAM của Broker.

    VÁ #3: BẮT BUỘC chữ ký EIP-191 của chính `payload.address`.
    Trước đây endpoint này không xác thực gì: ai cũng ghi đè được khoá của
    bất kỳ địa chỉ nào -> đầu độc danh bạ khi chain offline.
    """
    import time as _time

    # 1. Chống replay theo thời gian
    now = int(_time.time())
    if abs(now - payload.timestamp) > DPKI_REGISTER_MAX_SKEW_SECONDS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Timestamp qua cu (ngoai cua so +-300s) - tu choi dang ky khoa.",
        )

    # 2. Xác thực chữ ký ví trên thông điệp ràng buộc address + PEM + ts
    msg = _dpki_register_message(payload.address, payload.public_key_pem, payload.timestamp)
    if not Web3Auth.verify_signature(payload.address, msg, payload.signature):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Chu ky vi khong hop le - tu choi dang ky khoa cho dia chi nay.",
        )

    # 3. Ghi nhận (có audit khi xoay khoá)
    addr = payload.address.lower()
    previous = _BROKER_DPKI_REGISTRY.get(addr)
    if previous and previous != payload.public_key_pem:
        logger.warning(
            "dPKI KEY ROTATION cho %s (khoa cu -> khoa moi). Nguon: broker (unverified).",
            addr,
        )
    _BROKER_DPKI_REGISTRY[addr] = payload.public_key_pem

    # status="registered_unverified": client KHÔNG được nhầm broker là chain.
    return DPKIRegisterResponse(address=payload.address, status="registered_unverified")


@app.get("/api/v1/dpki/keys/{address}")
async def get_broker_dpki_key(address: str) -> dict[str, object]:
    """Tra cứu Public Key của địa chỉ ví qua bảng danh bạ RAM của Broker.

    VÁ #3/#4: response LUÔN kèm `"verified": false` + `"source": "broker"`
    để client buộc phải biết khoá này CHƯA được chain xác thực. Trước đây
    response chỉ có `public_key_pem`, khiến caller dễ hiểu nhầm là đã xác thực.
    """
    pem = _BROKER_DPKI_REGISTRY.get(address.lower())
    if not pem:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dia chi {address} chua dang ky khoa tren Broker dPKI.",
        )
    return {
        "address": address,
        "public_key_pem": pem,
        "verified": False,
        "source": "broker",
    }


@app.get("/api/v1/dpki/list")
async def list_broker_dpki() -> dict[str, list[str]]:
    """Liệt kê danh sách tất cả các địa chỉ ví đã đăng ký trên Broker."""
    return {"addresses": list(_BROKER_DPKI_REGISTRY.keys())}
