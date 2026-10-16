# 🎤 KỊCH BẢN THUYẾT TRÌNH ĐỀ TÀI CLOAKSHARE

> **Bộ lọc kỹ thuật** — Mục đích: giúp 4 thành viên chia đều vai trò, nói đúng trọng tâm báo cáo trong **15 phút**, và **cắt ngắn được** khi thầy hỏi.
> Tham chiếu: [`README.md`](../BaiTapLon%20va%20BaiTapCaNhan/CloakShare/README.md), [`ui/app.py`](../BaiTapLon%20va%20BaiTapCaNhan/CloakShare/ui/app.py:837), [`demo_full_flow.py`](../BaiTapLon%20va%20BaiTapCaNhan/CloakShare/demo_full_flow.py)

---

## 0. PHÂN BỔ THỜI GIAN & VAI TRÒ (tổng 15 phút)

| # | Phần | Người trình bày | Thời lượng |
|---|------|-----------------|------------|
| 1 | Lời mở đầu + Bài toán & Đề tài | **Nguyễn Gia Hào** | 1.5 phút |
| 2 | Nền tảng lý thuyết (Chương 2–4) | **Mai Hoàng Anh** | 3 phút |
| 3 | Kiến trúc Zero-Log Broker (Chương 5) | **Nguyễn Đức Bình** | 2.5 phút |
| 4 | Hiện thực hoá + Demo (Chương 7–8) | **Ngô Đức Minh Hiếu** | 5 phút |
| 5 | Kết quả Benchmark & Kết luận (Chương 9–10) | **Nguyễn Gia Hào** | 3 phút |

> **Mẹo phân vai:** người mở đầu và người kết luận nên là **cùng một người** (giữ được mạch "vấn đề → giải pháp → kết quả"). Hai người giữa đi sâu kỹ thuật.

---

## 1. PHẦN 1 — MỞ ĐẦU & BÀI TOÁN (Gia Hào · 1.5 phút)

### 🎤 Lời thuyết trình mẫu

> *"Thưa thầy và các bạn, nhóm em xin trình bày đề tài **CloakShare — Nghiên cứu, thiết kế và hiện thực hoá hệ sinh thái trao đổi tệp tin lai ghép phi tập trung và không lưu vết**.*
>
> *Trước hết, em xin điểm lại **vì sao phải làm đề tài này**. Ngày nay khi mình gửi một tệp tin lên dịch vụ đám mây hay nhắn tin qua ứng dụng, dữ liệu của mình được mã hoá ở phía **người gửi** và giải mã ở phía **người nhận** — đúng vậy. Nhưng vấn đề là **ở giữa hai người đó**, luôn có một tầng trung gian.*
>
> *Tầng đó **nhìn thấy metadata**: ai gửi, gửi cho ai, lúc mấy giờ, gửi bao nhiêu lần. Người dùng điện tử **không giải mã được**, nhưng người quản trị máy chủ thì hoàn toàn có thể. Đó là gọi là rủi ro **giám sát siêu dữ liệu**.*
>
> *Ba hệ thống phổ biến nhất — Google Drive, WeChat, Signal — đều đặt chung một điểm yếu chí mạng: **chúng đều dựa vào một nhà cung cấp tập trung**. Nếu nhà cung cấp bị thâm nhập, toàn bộ dữ liệu của hàng triệu người dùng bị lộ. Với tài liệu **hợp đồng, y tế, tài chính**, đó là rủi ro không thể chấp nhận.*
>
> *Vậy câu hỏi của đề tài là: **Làm thế nào để truyền dữ liệu mà không cần bất kỳ bên trung gian nào đáng tin cậy, và không để lại dấu vết?***
>
> *Câu trả lời của nhóm em là **CloakShare**, với ba trụ cột..."*

### 📌 Nếu bị cắt thời gian → CỐT LÕI 1 câu
> *"CloakShare là hệ thống trao đổi tệp tin **mã hoá đầu-cuối**, định danh bằng **khóa công khai phi tập trung dPKI trên blockchain**, và trung chuyển qua **một broker chỉ lưu trên RAM — không ghi xuống ổ cứng bao giờ**."*

### ⚠️ Câu hỏi thầy có thể hỏi ở phần này
| Câu hỏi | Trả lời |
|----------|---------|
| *"Khác Signal ở chỗ nào?"* | Signal vẫn cần **số điện thoại + máy chủ tập trung** để thiết lập danh tính và đồng bộ. CloakShare thay bằng **ví Web3 (EIP-191) + dPKI trên EVM**, không cần số điện thoại, không cần CA. |
| *"Zero-log có nghĩa là không lưu gì cả?"* | Không. Broker **vẫn phải giữ gói tin tạm thời trong RAM** để bên nhận tới lấy. "Zero-log" nghĩa là **không ghi log truy cập** + **không ghi xuống ổ cứng** + **tự hủy sau 1 lần đọc**. |

---

## 2. PHẦN 2 — NỀN TẢNG LÝ THUYẾT (Mai Hoàng Anh · 3 phút)

### 🎤 Lời thuyết trình mẫu

> *"Em phụ trách phần nền tảng lý thuyết — tức là **tại sao** nhóm em chọn từng thuật toán này. Nhóm em xây dựng trên **3 chuẩn quốc tế**.*
>
> ***Thứ nhất, mã hoá đối xứng — NIST FIPS-197, AES-128-CBC.***
> *Em chọn AES vì nó là chuẩn của chính phủ Mỹ, tốc độ rất cao. Ở đây em **tự viết lại bằng ngôn ngữ C thuần** đúng theo chuẩn FIPS-197, rồi biên dịch thành thư viện DLL và gọi qua Python bằng `ctypes`. Em dùng chế độ **CBC** kèm **đệm PKCS#7** — đảm bảo mọi khối đều đủ 16 byte kể cả khi độ dài bản rõ không chia hết cho 16.*
>
> ***Thứ hai, mã hoá bất đối xứng — RFC 8017, RSA-2048 OAEP + RSA-PSS.***
> *Đây là phần giải quyết bài toán then chốt của mã hoá lai: AES nhanh nhưng **khó phân phối khóa**, RSA thì ngược lại — dễ phân phối nhưng chậm. Cách của nhóm em là:*
> - *Sinh **khóa phiên AES ngẫu nhiên 16 byte** cho mỗi lần gửi.*
> - *Bọc khóa phiên đó bằng **RSA-OAEP** với khóa công khai của người nhận → tạo ra **wrapped key** chỉ người nhận mở được.*
> - *Dữ liệu thì mã hoá bằng **AES**.*
>
> *Tức là: **thuật toán nhanh chỉ dùng cho thuật toán chậm, và chỉ bọc một khóa 16 byte** — đây là nguyên lý cơ bản của mã hoá lai. Ngoài ra em dùng **RSA-PSS** thay vì PKCS#1 v1.5 để **chữ ký số**, vì PSS có tính xác suất, chống được tấn công chọn lọc chữ ký và chịu được thêm bằng SHA-256 — kể cả khi bị lệch **đúng 1 bit** thì chữ ký cũng bị từ chối.*
>
> ***Thứ ba, định danh phi tập trung — dPKI trên EVM, chữ ký ví EIP-191.***
> *Truyền tin an toàn cần biết **khóa công khai của người nhận**. Internet cũ giải quyết bằng **chứng thư số X.509 của CA** — nhưng đó lại là tổ chức tập trung. Nhóm em thay bằng: mỗi ví Web3 có **một địa chỉ Ethereum bất biến 0x...**; hợp đồng thông minh [`dPKIRegistry.sol`](../BaiTapLon%20va%20BaiTapCaNhan/CloakShare/contracts/dPKIRegistry.sol) lưu ánh xạ **địa chỉ ví ↔ khóa công khai RSA**, được ghi bằng mã hoá lai từ [`ecies_envelope.py`](../BaiTapLon%20va%20BaiTapCaNhan/CloakShare/engine/ecies_envelope.py). Nhóm em còn xây **Safe-Mode dự phòng** — nếu chưa bật node Anvil, hệ thống tự chuyển sang mô phỏng nội bộ để vẫn chạy trơn tru.*
>
> *Ba trụ cột này được trình bày chi tiết ở **Chương 2, 3 và 4** của báo cáo."*

### 📌 Nếu bị cắt thời gian → Chỉ nói 1 dòng mỗi chuẩn
> *"AES-128-CBC theo FIPS-197 cho mã hoá dữ liệu, RSA-2048 OAEP theo RFC 8017 để bọc khóa phiên, RSA-PSS để ký xác thực toàn vẹn, và dPKI trên EVM + EIP-191 để quản lý định danh mà không cần CA."*

### ⚠️ Câu hỏi thầy có thể hỏi
| Câu hỏi | Trả lời |
|----------|---------|
| *"Vì sao không dùng AES-GCM?"* | GCM **không dùng được với RSA-OAEP bọc khóa** trong thiết kế hybrid hiện tại, và nhóm em cần tách biệt vai trò **mã hoá** (AES-CBC) và **xác thực toàn vẹn** (RSA-PSS) đúng theo mô hình Chương 3. GCM cũng không tương thích trực tiếp với mô hình `enc‖sig` mà em trình bày. |
| *"CBC không an toàn về tính xác thực, sao dùng?"* | **Đúng, CBC chỉ bảo mật tính riêng tư, không bảo mật tính xác thực** — và em đã thiết kế để khắc phục bằng **chữ ký RSA-PSS phủ lên ciphertext**. Nhóm em thảo luận đầy đủ giới hạn này ở **Chương 2 và Chương 10**, kèm hướng chuyển sang GCM/ChaCha20-Poly1305. |
| *"Số 580 MB/s lấy từ đâu?"* | Từ bài benchmark [`scripts/benchmark_crypto.py`](../BaiTapLon%20va%20BaiTapCaNhan/CloakShare/scripts/benchmark_crypto.py), đo trên **lõi C native** (`-O3`) qua wrapper `ctypes` — **Chương 9, Hình 10**. |

---

## 3. PHẦN 3 — KIẾN TRÚC ZERO-LOG BROKER (Nguyễn Đức Bình · 2.5 phút)

### 🎤 Lời thuyết trình mẫu

> *"Em phụ trách phần kiến trúc máy chủ trung chuyển — tầng thú vị nhất của đề tài, và cũng là tầng quyết định hệ thống có thực sự **"không lưu vết"** hay không.*
>
> ***Vấn đề cốt lõi: tại sao Zero-log khó?***
> *Thường thì mọi hệ thống đều bị **log 3 chỗ**:*
> 1. *Access log của web server — ghi lại IP, thời gian, endpoint.*
> 2. *Database — lưu lịch sử truy cập file.*
> 3. *Ổ cứng vật lý — swap, journal, temp file.*
>
> *Chỉ cần thoát chế độ Zero-log ở **1 trong 3 chỗ** thì dữ liệu đã còn trên đĩa, và **một đĩa bị thu giữ là toàn bộ dữ liệu lộ**. Với hệ thống phân tán, không ai kiểm soát được chỗ thứ 3.*
>
> ***Giải pháp của em: đẩy dữ liệu ra khỏi đĩa, đưa lên RAM — rồi tự hủy.***
>
> *Em xây dựng broker [`broker/main.py`](../BaiTapLon%20va%20BaiTapCaNhan/CloakShare/broker/main.py) trên FastAPI, với 4 cơ chế bảo mật then chốt:*
>
> **① Vô hiệu hóa Access Log.** *Khi khởi chạy, nhóm em dùng cờ `--no-access-log` của Uvicorn. Đây là chi tiết nhỏ nhưng **cực kỳ quan trọng** — vì nếu không, `tx_id` của người dùng sẽ bị ghi lại trong log.*
>
> **② Burn-After-Read (tự hủy sau 1 lần đọc).** *Trong [`memory_store.py`](../BaiTapLon%20va%20BaiTapCaNhan/CloakShare/broker/memory_store.py), gói tin được đọc lần đầu thì hệ thống **xóa luôn khỏi RAM**. Tức là nếu hacker chiếm được `tx_id` và đoạn code của em, hacker **chỉ có thể đọc được một lần duy nhất** — và chính em cũng không đọc lại được. Đây là tính chất *forward secrecy* ở mức truyền tải.*
>
> **③ Memset Zeroize (ghi đè bộ nhớ).** *Khi xóa, hệ thống không chỉ thả reference mà còn **ghi đè vùng nhớ bằng `0x00`** trước khi giải phóng — vì RAM không tự xóa dữ liệu cũ khi bị cấp phát lại, và bằng chứng số có thể được trục lại từ RAM.*
>
> **④ TTL Auto-Purge (tự hủy theo thời gian).** *Mỗi gói tin có thời hạn sống. Hết TTL là tự xóa, kể cả **không ai nhận** — tránh rò rỉ do người gửi quên.*
>
> *Về **xác thực người nhận**, em dùng chữ ký ví Web3 chuẩn **EIP-191 (SIWE)**: broker phát một `ChallengeMessage` ngẫu nhiên + timestamp, ví ký bằng private key, broker xác thực chữ ký, và chỉ cho tải nếu khớp với **khóa công khai đã đăng ký trên dPKI**. Timestamp có **ngưỡng lệch tối đa 60 giây** để chống **tấn công phát lại (Replay Attack)**.*
>
> *Điểm em muốn nhấn mạnh: đây không chỉ là "cú pháp cho đẹp", mà là **cam kết kiểm chứng được** — nhóm em viết test riêng ([`tests/test_e2e_pipeline.py`](../BaiTapLon%20va%20BaiTapCaNhan/CloakShare/tests/test_e2e_pipeline.py)) chứng minh **0 disk write**, và **toàn bộ 39 test đều PASS**."*

### 📌 Nếu bị cắt thời gian → Chỉ nói 4 cơ chế (bullet)
> *"Zero-log của em dựa trên 4 cơ chế: (1) tắt access log, (2) burn-after-read — đọc 1 lần là mất, (3) memset zeroize — ghi đè 0x00 trước khi xóa, và (4) TTL auto-purge. Xác thực bằng chữ ký ví EIP-191 kèm timestamp chống replay."*

### 📊 Chiếu hình khi nói phần này
- `figures/hinh_09_ram_store_lifecycle.png` — vòng đời gói tin trên RAM
- `figures/hinh_13_ram_scrubbing_timeline.png` — dòng thời gian ghi đè bộ nhớ

### ⚠️ Câu hỏi thầy có thể hỏi
| Câu hỏi | Trả lời |
|----------|---------|
| *"RAM có an toàn hơn đĩa không?"* | **Không tuyệt đối hơn** — có hiện tượng **cold boot** (Halderman 2008, `CK-29`) giữ lại dữ liệu trong DRAM sau khi tắt máy. Nhóm em **thừa nhận giới hạn này** và đã viết chuyên mục phân tích riêng (`CM-06`) cùng cơ chế zeroize giảm thiểu. Đây là **đánh đổi có ý thức**, không phải tuyên bố tuyệt đối. |
| *"Không có database thì lỡ server crash mất data?"* | **Có, và đó là chủ ý.** Đây là đánh đổi của thiết kế Zero-log: broker chỉ là **trạm trung chuyển tạm**, không phải kho lưu trữ. Người nhận phải tải trong TTL; nếu server crash thì dữ liệu **biến mất vĩnh viễn** — và đó là hành vi **an toàn** (fail-secure). |

---

## 4. PHẦN 4 — HIỆN THỰC HOÁ & DEMO (Ngô Đức Minh Hiếu · 5 phút) ⭐ PHẦN QUAN TRỌNG NHẤT

> ⚠️ **Đây là phần thầy chấm điểm cao nhất.** Em nên **demo thật**, không chỉ nói. Chuẩn bị trước để không bị trục trặc.

### 🔧 Chuẩn bị TRƯỚC khi lên trình bày (làm sẵn 10 phút trước)
```bash
# 1. Mở Terminal 1 — Broker
python -m uvicorn broker.main:app --port 8000 --no-access-log

# 2. Mở Terminal 2 — UI
python -m streamlit run ui/app.py
#    → mở http://localhost:8501
```
**Checklist trước giờ trình bày:**
- [ ] Broker chạy OK, mở `http://127.0.0.1:8000/docs` thấy Swagger
- [ ] UI mở được, đã đăng nhập sẵn 1 tài khoản
- [ ] Đã tạo sẵn 2 ví để vào Tab "Trò Chuyện" không bị trống
- [ ] Cửa sổ Terminal 1 **để sẵn**, sẵn sàng gõ lệnh burn để giới thiệu
- [ ] **Tắt thông báo email / ứng dụng khác** để không bị nhiễu

### 🎤 Lời thuyết trình mẫu

> *"Em phụ trách phần hiện thực hoá và sẽ demo trực tiếp hệ thống đang chạy.*
>
> ***Trước hết, về kiến trúc tổng thể — các bạn nhìn Hình 1:*** *hệ thống có 4 tầng: tầng giao diện, tầng mật mã lai, tầng định danh dPKI, và tầng broker. Mỗi tầng **tách biệt trách nhiệm** — cùng một nguyên tắc **separation of concerns** mà em đã trình bày ở Chương 7.*
>
> ***Giờ em sẽ demo luồng hoàn chỉnh: từ đăng ký ví → mã hoá tin nhắn → truyền qua broker → giải mã → tự hủy.***
>
> *Trên màn hình là giao diện Streamlit với 4 tab. Em sẽ đi lần lượt:*
>
> **[Tab 1 — Trò Chuyện]**
> *Đây là luồng **chat mã hoá hai chiều**. Em chọn liên hệ "Mai Hoàng Anh", gõ một tin, bấm gửi. Nhìn các bạn: tin nhắn hiển thị **văn bản đã mã hoá hex** — nhưng thực tế **trên đường truyền không bao giờ có plaintext**. Nếu ai đó chặn giữa chừng, họ chỉ thấy dữ liệu hex vô nghĩa.*
>
> **[Tab 2 — CloakDrop]**
> *Em gửi một tệp tin bí mật, hệ thống sinh ra **mã Ticket ID**. Em tùy chỉnh **TTL**, ví dụ 30 giây. File được mã hoá AES, bọc khóa RSA, và chỉ giải mã được bằng **đúng ví nhận**. Quan trọng: em bật **Burn-After-Read** — nghĩa là sau khi người nhận tải **một lần duy nhất**, file **tự hủy khỏi RAM**, kể cả em (người gửi) cũng không xem lại được.*
>
> **[Tab 3 — Giám Sát Zero-Log]**
> *Đây là **bảng chứng** cho toàn bộ những gì em vừa trình bày. Các bạn nhìn:*
> - *Số **payload đang lưu trên RAM** — biến động tăng khi gửi, về 0 sau khi nhận.*
> - ***Tỷ lệ dọn RAM (Wipe Ratio)*** — thanh tiến trình đi từ 0% lên 100%, nghĩa là **100% bộ nhớ đã được ghi đè 0x00**.*
> - *Chỉ số **0 disk write** — cam kết cốt lõi của cả đề tài.*
>
> *Đây chính là bằng chứng trực quan cho **Chương 5** và **Chương 9**.*
>
> **[Tab 4 — Quản Lý Khóa]**
> *Em tạo cặp khóa RSA-2048, đăng ký khóa công khai lên dPKI. Nếu em bật Anvil, khóa sẽ được ghi **bất biến trên blockchain**; nếu không, hệ thống tự chuyển **Safe-Mode** và vẫn hoạt động.*
>
> ***Và cuối cùng, em muốn nhấn mạnh điều thầy sẽ đánh giá cao nhất — tính đúng đắn của phần mã hoá.***"

### 🖥️ Câu lệnh demo "bằng chứng sống" (backup nếu UI treo)
Nếu Streamlit lỗi giữa chừng, chạy script có sẵn — nó in ra **đúng thứ tự từng bước mã hoá**:
```bash
python demo_full_flow.py
```
Script này in:
```
1. [Identity] Cặp khóa Seller & Buyer đã sẵn sàng.
2. [Seller] Đã mã hóa dữ liệu:
   - Ciphertext : 48 bytes
   - Wrapped Key: 256 bytes
   - Signature  : 256 bytes
3. [Broker] Lưu tạm payload với tx_id: <uuid>
4. [Buyer] Xác thực chữ ký Seller thành công (Dữ liệu nguyên vẹn 100%).
5. [Buyer] Giải mã thành công! Nội dung nhận được:
   -> 'Nội dung hợp đồng mật chuyển giao tài sản số: 50,000 USDT.'
```
👉 **Đây là bằng chứng tốt nhất** vì nó cho thấy chữ ký được xác thực trước khi giải mã — đúng thứ tự bảo mật.

### ⚠️ Câu hỏi thầy có thể hỏi
| Câu hỏi | Trả lời |
|----------|---------|
| *"Sao không dùng thư viện mã hoá có sẵn?"* | Có sẵn (`cryptography` cho RSA). Nhưng nhóm em **tự viết lõi AES-128 bằng C** chuẩn FIPS-197 để (1) **chứng minh hiểu sâu thuật toán** — đúng mục tiêu học phần Mật mã học cơ sở, và (2) **đo được hiệu năng thật** không bị che bởi lớp trừu tượng. |
| *"Demo thì ai làm, có lừa dối không?"* | **Không** — em chạy đúng mã nguồn trong repo. Nhóm em có test riêng kiểm chứng **0 disk write** và **chống replay**; các test này nằm trong báo cáo Chương E và **chạy lại được bất cứ lúc nào**. |
| *"Nếu mất private key thì sao?"* | Dữ liệu **vĩnh viễn mất** — không có cơ chế khôi phục, **đây là hệ quả có chủ ý** của mã hoá đầu-cuối. Người dùng phải tự sao lưu private key (private key **không bao giờ** rời khỏi máy người dùng). |

---

## 5. PHẦN 5 — KẾT QUẢ BENCHMARK & KẾT LUẬN (Gia Hào · 3 phút)

### 🎤 Lời thuyết trình mẫu

> *"Cuối cùng, em xin trình bày **kết quả đo đạc** và **kết luận**.*
>
> ***Về hiệu năng*** — nhóm em đo trên 3 tiêu chí:*
>
> | Chỉ số | Kết quả |
> |--------|---------|
> | *Thông lượng lõi AES-128 native* | **> 580 MB/s** |
> | *Độ trễ trao đổi toàn trình* | **< 55 ms** |
> | *Tỷ lệ vượt qua kiểm thử* | **100% — 39/39 test PASS** |
>
> *Kết quả này cho thấy hệ thống **vừa nhanh vừa đúng** — không phải đánh đổi giữa tốc độ và an toàn.*
>
> ***Về đánh giá an toàn*** — nhóm em đã phân tích theo mô hình **STRIDE** (6 loại tấn công: Spoofing, Tampering, Repudiation, Information Disclosure, DoS, Elevation of Privilege) và **khắc phục được toàn diệu**. Các bạn có thể xem **biểu đồ radar** ở Hình 14.*
>
> ***Về hạn chế mà nhóm em thừa nhận*** — đây là phần em muốn nói thẳng, vì nghiên cứu khoa học phải trung thực:*
>
> 1. ***Hiện tượng cold boot*** — RAM có thể giữ dữ liệu sau khi tắt máy. Đây là **giới hạn cố hữu** của mọi hệ thống dùng RAM, chúng tôi chỉ **giảm thiểu** chứ không **loại bỏ** hoàn toàn.*
> 2. ***Mô hình tin cậy thiết bị đầu cuối*** — nếu máy người dùng bị nhiễm mã độc, khóa riêng có thể bị lộ.*
> 3. ***Chi phí Gas*** — mỗi lần đăng ký khóa công khai tốn **O(1) gas** nhưng vẫn là chi phí thực. Nhóm em đã chứng minh giới hạn này ở `CM-07`.*
>
> ***Về hướng tương lai*** — em xin trình bày trước **khoảnh khắc mật mã hậu lượng tử (PQC)**. Thuật toán **Shor** (1994) chứng minh thuật toán lượng tử phá vỡ RSA và ECC trong thời gian đa thức. Nhóm em đã trình bày ở Chương 10: khi máy tính lượng tử đủ mạnh, hệ thống **buộc phải chuyển sang ML-KEM** (NIST FIPS 203, 2024) và **ML-DSA** (FIPS 204). Đây là **lộ trình tương lai** mà nhóm em đã vẽ sẵn.*
>
> ***Kết luận:*** *Với **3 trụ cột** — mã hoá lai FIPS-197/RFC 8017, định danh dPKI trên EVM, và broker RAM không lưu vết — nhóm em đã xây dựng được một hệ sinh thái trao đổi tệp tin **hoàn chỉnh, chạy được, và kiểm chứng được bằng 39 test tự động**.*
>
> *Em xin cảm ơn thầy và các bạn. Nhóm em sẵn sàng nhận câu hỏi."*

### 📌 Nếu bị cắt thời gian → Chỉ nói bảng số + 1 hạn chế
> *"Kết quả: **580 MB/s**, **< 55 ms**, **39/39 test đạt**, khắc phục STRIDE toàn diện. Hạn chế lớn nhất là **cold boot** — giới hạn cố hữu của RAM mà chúng tôi chỉ giảm thiểu được. Hướng tương lai là chuyển sang **ML-KEM/ML-DSA** khi thuật toán Shor thành hiện thực."*

---

## 6. BẢNG TỔNG HỢP — CÁC CON SỐ CẦN NHỚ

| Con số | Giá trị | Nguồn trong báo cáo |
|--------|----------|---------------------|
| Số test tự động | **39/39 PASS** | `tests/`, Chương E |
| Thông lượng AES-128 native | **> 580 MB/s** | Hình 10 |
| Độ trễ end-to-end | **< 55 ms** | Hình 12 |
| Kích thước khóa RSA | **2048 bit** | Chương 3 |
| Khóa phiên AES | **128 bit** | Chương 2 |
| Ngưỡng chống replay | **60 giây** | Chương 4/5 |
| Số bảng trong báo cáo | **201 bảng** | Toàn bài |
| Số hình trong báo cáo | **19 hình** | Toàn bài |
| Số chuẩn tham khảo | **45 chuẩn** | Chương CK-01 → CK-45 |
| Số định lý toán học | **10 định lý** | CM-01 → CM-10 |

---

## 7. NẾU BỊ HỎI "ĐIỂM YẾU" — CÂU TRẢ LỜI MẪU

| Câu hỏi | Cách trả lời (thừa nhận + phòng thủ) |
|---------|--------------------------------------|
| *"Hệ thống này có thực tế không?"* | "Hiện tại là **prototype nghiên cứu** dùng Anvil (mạng Ethereum cục bộ). Để đưa vào production cần: audit hợp đồng thông minh, thay ví giả bằng **HSM**, và triển khai broker trên **RAM mã hoá (SGX)**. Nhóm em đã ghi nhận điểm này ở **Chương 10 — Đánh giá giới hạn**." |
| *"Broker không có database thì scale được không?"* | "Đúng, đây là **giới hạn thiết kế có chủ ý**. Broker chỉ giữ dữ liệu **tạm thời trong TTL** (vài giây đến vài phút), nên **tải rất nhẹ** — và có thể mở rộng ngang bằng cách chạy nhiều instance sau load-balancer. Mỗi instance độc lập, không cần đồng bộ trạng thái." |
| *"Sao không dùng mã hoá đối xứng end-to-end thuần?"* | "Vì mã hoá đối xứng **không giải quyết được vấn đề phân phối khóa**. Người nhận phải có sẵn khóa từ trước — không khả thi với người lạ. Vì vậy nhóm em dùng **mã hoá lai**: lợi thế của cả hai." |
| *"Số liệu benchmark có đáng tin?"* | "Chúng tôi công khai **mã nguồn benchmark** và **cấu hình máy**, và **chạy lại được** bằng `python scripts/benchmark_crypto.py`. Nhóm em thừa nhận đây là benchmark trên **một máy đơn lẻ**, chưa phải đánh giá phân tán — đã ghi rõ trong Chương 9." |

---

## 8. CHECKLIST TRƯỚC GIỜ THUYẾT TRÌNH

**Kỹ thuật:**
- [ ] Broker chạy: `python -m uvicorn broker.main:app --port 8000 --no-access-log`
- [ ] UI chạy: `python -m streamlit run ui/app.py` → http://localhost:8501
- [ ] Đã đăng nhập sẵn, tạo sẵn 2 ví liên hệ
- [ ] Chạy thử `python demo_full_flow.py` để chắc chắn không lỗi
- [ ] Chạy `python -m pytest tests/ -v` → 39/39 PASS (backup)

**Nội dung:**
- [ ] Mở trước 5 hình: hình_01 (kiến trúc), hình_09 (RAM lifecycle), hình_10 (benchmark), hình_13 (scrubbing), hình_14 (STRIDE radar)
- [ ] Báo cáo DOCX sẵn sàng để mở tra nếu thầy yêu cầu
- [ ] Thẻ ghi nhớ: 3 trụ cột, 3 con số (580 MB/s, 55 ms, 39 test), 3 hạn chế

**Kỹ năng nói:**
- [ ] Tập nói phần **demo** 2-3 lần (phần dễ trục trặc nhất)
- [ ] Chia đúng 4 phần theo đúng 4 người
- [ ] Mỗi người biết **1 hạn chế** của hệ thống (để tự trả lời khi bị hỏi)
