"""
broker/schemas.py

Định nghĩa schema (Pydantic) cho các endpoint của Zero-Log Broker.
Chỉ mô tả hình dạng dữ liệu - không chứa logic lưu trữ.

Các trường nhị phân (iv, wrapped_key, ciphertext, signature) được truyền
dưới dạng chuỗi Base64 trong JSON, vì JSON không mang được raw bytes.
Broker KHÔNG giải mã, KHÔNG kiểm tra chữ ký - nó chỉ là trạm trung
chuyển mù (blind relay), giữ nguyên payload trên RAM rồi trả lại.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class StagePayload(BaseModel):
    """Body của POST /api/v1/stage - gói tin mã hoá do Sender đẩy lên."""

    tx_id: str = Field(
        ...,
        min_length=1,
        max_length=128,
        description="Mã giao dịch duy nhất, dùng làm ticket cho Buyer tra cứu.",
    )
    recipient: str = Field(
        ...,
        min_length=1,
        max_length=128,
        description="Địa chỉ ví Web3 của người nhận (0x...).",
    )
    iv: str = Field(
        ...,
        description="Initialization Vector của AES-128-CBC, Base64 (16 byte gốc).",
    )
    wrapped_key: str = Field(
        ...,
        description="Session key AES đã bọc bằng RSA-2048 OAEP, Base64.",
    )
    ciphertext: str = Field(
        ...,
        description="Dữ liệu file đã mã hoá AES-128-CBC, Base64.",
    )
    signature: str = Field(
        ...,
        description="Chữ ký RSA-PSS + SHA-256 của người gửi, Base64.",
    )
    ttl_seconds: int = Field(
        default=300,
        gt=0,
        le=86_400,
        description="Thời gian sống của payload trên RAM (giây). Quá hạn sẽ bị purge.",
    )


class StageResponse(BaseModel):
    """Trả về khi stage thành công (HTTP 201)."""

    tx_id: str
    status: str = "staged"
    expires_at: float = Field(
        ...,
        description="Thời điểm hết hạn (Unix timestamp, giây).",
    )


class RetrieveResponse(BaseModel):
    """Trả về toàn bộ payload cho Buyer (GET /api/v1/retrieve/{tx_id})."""

    tx_id: str
    recipient: str
    iv: str
    wrapped_key: str
    ciphertext: str
    signature: str


class StatsResponse(BaseModel):
    """Thông tin giám sát cho Dashboard Broker (Issue #18)."""

    active_payloads: int
    total_staged: int
    total_retrieved: int
    total_purged_expired: int
    disk_writes: int = Field(
        default=0,
        description="Luôn bằng 0 - Broker không bao giờ ghi payload xuống ổ cứng.",
    )
