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
    # VÁ #6: TRƯỚC ĐÂY trường này là `default=0` viết cứng kèm mô tả "Luôn bằng 0".
    # Đó là một lời khẳng định về bảo mật được in ra cho người dùng đọc, nhưng
    # KHÔNG hề kiểm tra backend thật. Khi REDIS_URL được set, payload thực sự
    # nằm trên ổ cứng mà Dashboard vẫn hiển thị 0 -> "nói dối bằng thiết kế".
    # Nay giá trị này do chính store cung cấp qua `disk_write_count()`, nên
    # nó luôn phản ánh đúng backend đang chạy.
    disk_writes: int = Field(
        ...,
        description=(
            "Số lần payload thực sự được ghi xuống ổ cứng, do backend tự báo cáo. "
            "InMemoryStore luôn trả 0 (Zero-Log thuần); RedisStore trả số lần "
            "setex thật -> nếu khác 0 nghĩa là cam kết Zero-Log ĐANG BỊ VI PHẠM."
        ),
    )
    approx_ram_bytes: int = Field(
        default=0,
        description="Ước tính dung lượng RAM đang chứa payload (bytes).",
    )
    uptime_seconds: int = Field(
        default=0,
        description="Thời gian hoạt động của Broker (giây).",
    )


class DPKIRegisterRequest(BaseModel):
    """VÁ #3: đăng ký khoá lên Broker BẮT BUỘC phải có chữ ký EIP-191.

    Trước đây endpoint này không có bất kỳ xác thực nào: bất kỳ ai cũng POST
    được khoá công khai cho BẤT KỲ địa chỉ nào. Khi chain offline, kẻ tấn công
    đầu độc được cả danh bạ khoá -> che mất khoá thật trên chain.
    """

    address: str = Field(..., min_length=42, max_length=42, description="Địa chỉ ví Ethereum (0x...)")
    public_key_pem: str = Field(..., min_length=10, description="RSA Public Key dạng PEM")
    timestamp: int = Field(
        ...,
        description="Unix seconds tại thời điểm ký. Chống replay (cửa sổ ±300s).",
    )
    signature: str = Field(
        ...,
        min_length=132,
        max_length=132,
        description="Chữ ký EIP-191 (65 byte hex, 0x...) của CHÍNH `address` trên thông điệp chuẩn.",
    )


class DPKIRegisterResponse(BaseModel):
    address: str
    # VÁ #3: đổi mặc định để client KHÔNG THỂ nhầm broker với chain.
    status: str = "registered_unverified"
