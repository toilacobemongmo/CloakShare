# 🛡️ Chính Sách & Kiến Trúc Bảo Mật CloakShare (Security Architecture & Threat Model)

Tài liệu này mô tả chi tiết mô hình đe dọa (Threat Model), các giả định tin cậy (Trust Assumptions) và các biện pháp giảm thiểu rủi ro bảo mật trong dự án **CloakShare**.

---

## 1. Mô Hình Đe Dọa (Threat Model)

### Đối Tượng Tấn Công (Adversary Capabilities):
- **Kẻ Nghe Lén Trên Mạng (Passive Eavesdropper / ISP):** Có thể bắt trọn vẹn các gói tin HTTP/JSON lưu thông giữa Client và RAM Broker.
- **Kẻ Tấn Công Chủ Động (Active MITM):** Có thể sửa đổi, giả mạo, hoặc phát lại (replay) các gói tin truyền qua mạng.
- **Máy Chủ Đệm Bị Xâm Nhập (Compromised Broker Server):** Kẻ tấn công chiếm quyền đọc bộ nhớ hoặc ổ đĩa của máy chủ trung chuyển.
- **Kẻ Mạo Danh Danh Tính (Identity Impersonator):** Kẻ cố gắng tạo public key giả hoặc rút dữ liệu không thuộc về mình.

---

## 2. Các Biện Pháp Phòng Vệ & Giảm Thiểu Rủi Ro (Security Controls)

### A. Tầng Mã Hóa Lai (Hybrid Cryptography Layer)
1. **Mã Hóa Dữ Liệu Lớn bằng AES-128-CBC (C Core):**
   - Thực thi theo chuẩn FIPS-197 trong file C độc lập.
   - IV (Initialization Vector) được sinh ngẫu nhiên 16 bytes bằng hàm entropy bảo mật cao của hệ điều hành (`os.urandom(16)` / `getrandom`).
   - Padding PKCS#7 kiểm tra chặt chẽ độ dài và giá trị byte đệm, chống tấn công Padding Oracle.
2. **Bọc Khóa Phiên (Key Encapsulation):**
   - Khóa phiên AES được bọc bằng **RSA-2048 OAEP (SHA-256)** với Mask Generation Function (MGF1).
   - Chỉ người sở hữu Private Key RSA tương ứng mới có thể mở bọc khóa (Unwrap).
3. **Ký Số Toàn Vẹn Chống Giả Mạo (Digital Signature):**
   - Ciphertext được ký số bằng **RSA-PSS SHA-256** với độ dài Salt bằng độ dài digest (32 bytes).
   - Người nhận bắt buộc phải xác thực chữ ký số bằng Public Key của người gửi trước khi giải mã.
   - **Cam kết:** Bất kỳ sự thay đổi nào đối với ciphertext (kể cả chỉ lệch 1 bit) sẽ khiến quá trình xác thực thất bại ngay lập tức (`assert IntegritySigner.verify_file == False`).

### B. Tầng Danh Tính Phi Tập Trung (dPKI Blockchain Layer)
1. **Chống Tấn Công Man-in-the-Middle (MITM):**
   - Không sử dụng máy chủ chứng thực khóa tập trung (Certificate Authority dễ bị hack).
   - Public Key được liên kết trực tiếp với địa chỉ ví Ethereum trên Smart Contract [`contracts/dPKIRegistry.sol`](file:///C:/Users/ghaob/CloakShare/contracts/dPKIRegistry.sol).
   - Chỉ chủ sở hữu Private Key của ví mới có quyền gọi hàm `registerPublicKey()`.
2. **Cơ Chế Local Safe-Mode Fallback:**
   - Khi node blockchain tạm thời không khả dụng, hệ thống tự động kích hoạt bộ đệm an toàn cục bộ có khóa luồng (`threading.Lock`), ngăn chặn gián đoạn dịch vụ.

### C. Tầng Trạm Trung Chuyển Không Lưu Vết (Zero-Log RAM Broker)
1. **Cam Kết 0 Lần Ghi Ổ Cứng (`0 Disk Writes`):**
   - Payload chỉ tồn tại trong heap memory của tiến trình Python dưới dạng `bytearray`.
   - Toàn bộ Access Log của Uvicorn bị vô hiệu hóa (`logging.getLogger("uvicorn.access").disabled = True`) để ngăn `tx_id` bị ghi vào log server.
2. **Ghi Đè Bộ Nhớ (Memset Zeroize):**
   - Khi hết hạn TTL hoặc khi gọi lệnh tự hủy (Burn-After-Read), toàn bộ các mảng byte nhạy cảm (`iv`, `wrapped_key`, `ciphertext`, `signature`) được ghi đè byte `0x00` trước khi xóa khỏi dictionary và thu hồi bộ nhớ.
3. **Xác Thực Truy Cập Rút File Bằng Ví Web3 (SIWE Challenge):**
   - Khi yêu cầu lấy file, Buyer phải tạo chữ ký số EIP-191 trên thông điệp:
     `"CloakShare Retrieve Auth: <tx_id> @ <timestamp>"`
   - Broker kiểm tra địa chỉ ví phục hồi từ chữ ký:
     1. Chữ ký phải hợp lệ từ đúng ví `recipient`.
     2. Thời gian `timestamp` không được lệch quá 60 giây so với đồng hồ Broker (chống **Replay Attack**).
4. **Tự Hủy Tức Thì (Burn-After-Read):**
   - Hỗ trợ tham số `?burn=true` và endpoint `DELETE /api/v1/payload/{tx_id}` để tiêu hủy dữ liệu ngay sau khi đối tác nhận thành công.

---

## 3. Báo Cáo Lỗ Hổng Bảo Mật (Vulnerability Disclosure)

Nếu phát hiện bất kỳ vấn đề hoặc lỗ hổng bảo mật nào trong CloakShare:
- **Không tạo Issue công khai trên GitHub.**
- Vui lòng gửi email trực tiếp tới nhóm phát triển dự án với tiêu đề `[SECURITY VULNERABILITY] CloakShare`.
- Cung cấp kịch bản tái hiện mã khai thác (PoC) để nhóm tiến hành đánh giá và phát hành bản vá.
