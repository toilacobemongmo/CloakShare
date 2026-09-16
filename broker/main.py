"""
broker/main.py

Zero-Log In-Memory Staging API (Issue #7).

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

from fastapi import FastAPI, HTTPException, status,Header

from broker.memory_store import store
from broker.schemas import (
    RetrieveResponse,
    StagePayload,
    StageResponse,
    StatsResponse,
)

# Chu kỳ chạy background task dọn payload hết hạn (giây).
PURGE_INTERVAL_SECONDS = 5

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


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}

@app.get("/api/v1/retrieve/{tx_id}", response_model=RetrieveResponse)
async def retrieve_payload(
    tx_id: str,
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

    return RetrieveResponse(**data)