# Hướng Dẫn Đóng Góp Phát Triển CloakShare

Chào mừng bạn tham gia dự án **CloakShare**! Để các thành viên nắm rõ bức tranh toàn cảnh và không làm gãy kiến trúc bảo mật của hệ thống, vui lòng đọc kỹ tài liệu này trước khi nhận Issue.

---

## 1. Bản chất hệ thống CloakShare là gì?

CloakShare **không phải** là mạng P2P kết nối trực tiếp IP qua socket (không cần mở cổng, không cần NAT/STUN). 
Dự án là nền tảng trao đổi dữ liệu bảo mật kết hợp 3 trụ cột:
1. **Lõi Mật mã Lai (Hybrid Crypto):** Dữ liệu lớn mã hóa cực nhanh bằng AES-128 (viết bằng C). Khóa AES được bọc bằng Public Key RSA của người nhận. File được ký số bằng Private Key người gửi (SHA-256 + PSS).
2. **Hạ tầng khóa công khai dPKI (Blockchain):** Dùng Smart Contract trên Polygon Amoy để ánh xạ địa chỉ ví Web3 với Public Key. Không dùng máy chủ tập trung lưu khóa để chống tấn công Man-In-The-Middle (MITM).
3. **Máy chủ đệm Zero-Log (In-Memory RAM Broker):** Gói tin mã hóa chỉ lưu tạm trên RAM (`/dev/shm`), tuyệt đối không ghi file log hay file tạm xuống ổ cứng. Sau khi người nhận lấy file xong, bộ nhớ bị ghi đè byte `0x00` (`memset`) và giải phóng ngay lập tức.

---

## 2. Bản đồ phân công Issues (Issue Roadmap)

Các Issue được đánh số theo thứ tự phụ thuộc kỹ thuật từ thấp lên cao:

### Nhóm 1: Tầng Lõi C (Issue #1, #2, #3)
* **Ý nghĩa:** Xây dựng module mã hóa đối xứng hiệu năng cao.
* **Ai nhận?** Người thạo lập trình C, quản lý con trỏ, cấp phát bộ nhớ và Makefile.
* **Nhiệm vụ:** Hoàn thiện PKCS#7 padding, chế độ AES-128-CBC và build thành file thư viện động `.so` / `.dll`.

### Nhóm 2: Tầng Điều phối Python (Issue #4, #5, #6)
* **Ý nghĩa:** Cầu nối giữa file C và logic bảo mật tổng thể.
* **Ai nhận?** Người thạo Python, thư viện `ctypes` và module `cryptography`.
* **Nhiệm vụ:** Gọi hàm C từ Python, thực thi bọc khóa RSA-2048 OAEP và ký số tính toàn vẹn.

### Nhóm 3: Tầng Zero-Log Broker (Issue #7, #8)
* **Ý nghĩa:** Trạm trung chuyển dữ liệu tạm thời trên RAM.
* **Ai nhận?** Backend developer (FastAPI / Uvicorn / AsyncIO).
* **Nhiệm vụ:** Tạo API nhận payload vào biến `dict` trên RAM, chặn toàn bộ file access log và tự hủy bộ nhớ sau TTL/chuyển giao.

### Nhóm 4: Tầng Web3 & Smart Contract (Issue #10, #11, #13, #14)
* **Ý nghĩa:** Quản trị danh tính và cơ chế đăng nhập không mật khẩu.
* **Ai nhận?** Blockchain / Web3 developer (Solidity, Ethers.js, `web3.py`).
* **Nhiệm vụ:** Viết Smart Contract dPKI trên testnet và triển khai luồng ký số SIWE (Sign-In with Ethereum) không tốn gas.

### Nhóm 5: Tầng Giao diện Người dùng & Giám sát (Issue #9, #15, #16, #17, #18)
* **Ý nghĩa:** Mặt tiền ứng dụng cho người dùng và màn hình demo cho giảng viên.
* **Ai nhận?** Frontend / Fullstack developer (React/Vite hoặc Streamlit/HTML/Tailwind).
* **Nhiệm vụ:** Dựng UI kiểu Web3 chat (Sender gửi - Buyer nhận) và Dashboard Broker theo dõi RAM/Disk I/O theo thời gian thực.

---

## 3. Quy trình làm việc bắt buộc (Git Workflow)

Nhánh `main` đã được bật chế độ khóa bảo vệ. Contributor **không thể push trực tiếp vào `main`**.

### Bước 1: Nhận việc
* Vào tab **Issues** trên GitHub.
* Chọn Issue chưa có ai làm, để lại bình luận: *"Tôi xin phép nhận Issue này"* và tự gán tên mình vào mục **Assignees**.

### Bước 2: Tạo nhánh riêng từ `main` mới nhất
```bash
git checkout main
git pull origin main
# Đặt tên nhánh theo cấu trúc: feature/issue-[số issue]-[tên ngắn]
git checkout -b feature/issue-1-pkcs7-padding