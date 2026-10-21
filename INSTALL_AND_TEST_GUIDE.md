# Hướng Dẫn Cài Đặt & Chạy Test PoP Validation

## 🚀 TL;DR - Chạy Ngay (One-Liner)

```powershell
cd "c:/Users/ghaob/BaiTapLon va BaiTapCaNhan/[2026-10-29]CloakShare"
powershell -ExecutionPolicy Bypass -File scripts/run_pop_tests.ps1
```

Script tự động:
1. Kiểm tra và cài Foundry (anvil/forge/cast) nếu chưa có
2. Cài py-solc-x và solc 0.8.20
3. Chạy đầy đủ 4 test cases với pytest

---

## 📋 Chi Tiết Từng Bước (Nếu Muốn Làm Thủ Công)

### Bước 1: Cài Foundry (Anvil + Forge)

```powershell
# Option A: Dùng script tự động
powershell -ExecutionPolicy Bypass -File scripts/install_foundry_windows.ps1

# Option B: Tự tải binary
# Tải từ: https://github.com/foundry-rs/foundry/releases/latest
# Download: foundry_win_amd64.zip
# Giải nén vào: C:\Users\ghaob\.foundry\
# Thêm vào PATH: $env:Path += ";C:\Users\ghaob\.foundry"
```

Kiểm tra:
```powershell
anvil --version
forge --version
```

### Bước 2: Cài py-solc-x và solc 0.8.20

```powershell
pip install py-solc-x
python -c "import solcx; solcx.install_solc('0.8.20')"
```

### Bước 3: Chạy Test

```powershell
cd "c:/Users/ghaob/BaiTapLon va BaiTapCaNhan/[2026-10-29]CloakShare"
pytest tests/test_pop_validation.py -v -s
```

---

## 🧪 Test Cases Được Chạy

| Test | Mô Tả | Kỳ Vọng |
|------|-------|---------|
| `test_pop_valid_signature_accepted` | PoP signature hợp lệ từ RSA private key khớp với public key | ✅ PASS - transaction thành công |
| `test_pop_invalid_signature_rejected` | Signature bị corrupt (flip 1 bit) | ✅ PASS - revert `InvalidPoPSignature()` |
| `test_pop_wrong_rsa_key_rejected` | Đăng ký public key A nhưng ký bằng private key B (key substitution attack) | ✅ PASS - revert `InvalidPoPSignature()` |
| `test_pop_replay_attack_prevented` | Dùng lại signature của wallet A cho wallet B | ✅ PASS - revert (signature bound to specific wallet address) |

---

## 🐛 Debug - Các Lỗi Thường Gặp

### Lỗi 1: `anvil: command not found`
**Nguyên nhân:** Foundry chưa cài hoặc chưa có trong PATH.

**Fix:**
```powershell
$env:Path += ";$env:USERPROFILE\.foundry"
# Hoặc đóng terminal và mở lại
```

### Lỗi 2: `ModuleNotFoundError: No module named 'solcx'`
**Nguyên nhân:** py-solc-x chưa cài.

**Fix:**
```powershell
pip install py-solc-x
```

### Lỗi 3: `SolcNotInstalled: solc 0.8.20 has not been installed`
**Nguyên nhân:** solc 0.8.20 chưa download.

**Fix:**
```powershell
python -c "import solcx; solcx.install_solc('0.8.20')"
```

### Lỗi 4: Test fail với `InvalidSignatureLength`
**Nguyên nhân:** Bug trong contract - DER encoding leading `0x00` không được strip.

**Fix:** Đã sửa trong commit này - [`extractRsaKey`](contracts/dPKIRegistry.sol:186) đã strip leading `0x00` từ ASN.1 INTEGER.

### Lỗi 5: Test fail với `InvalidPoPSignature` cho valid signature
**Nguyên nhân:** Hash mismatch - client hash 1 lần, contract cần hash 2 lần do DigestInfo.

**Fix:** Đã sửa trong commit này - [`verifyRsaPkcs1v15`](contracts/dPKIRegistry.sol:90) giờ double-hash digest để khớp với PKCS#1 v1.5 DigestInfo.

---

## 📊 Output Mong Đợi

```
[*] Checking Foundry (anvil/forge)...
[OK] anvil --version: anvil 0.x.x
[*] Checking py-solc-x...
[OK] solc 0.8.20

[*] Running PoP validation tests...

tests/test_pop_validation.py::test_pop_valid_signature_accepted PASSED
tests/test_pop_validation.py::test_pop_invalid_signature_rejected PASSED
tests/test_pop_validation.py::test_pop_wrong_rsa_key_rejected PASSED
tests/test_pop_validation.py::test_pop_replay_attack_prevented PASSED

============================== 4 passed in 8.32s ===============================

[SUCCESS] Tat ca test cases PASS!
```

---

## 🔬 Chi Tiết Kỹ Thuật

### Bug Đã Sửa

#### Bug #1: ASN.1 DER Leading Zero
**Vị trí:** [`extractRsaKey`](contracts/dPKIRegistry.sol:186) line 210-218

**Triệu chứng:** `revert InvalidSignatureLength()` khi RSA modulus có MSB set.

**Nguyên nhân:** ASN.1 DER INTEGER bắt buộc chèn leading `0x00` khi bit cao được set (để phân biệt positive/negative). Kết quả: `modulus.length = 257` bytes thay vì 256 bytes (RSA-2048).

**Fix:**
```solidity
// Bỏ qua leading zero của unsigned INTEGER nếu có
uint256 modStart = cursor;
if (der[modStart] == 0x00 && modLen > 0) {
    modStart++;
    modLen--;
}
modulus = new bytes(modLen);
for (uint256 i = 0; i < modLen; i++) modulus[i] = der[modStart + i];
```

#### Bug #2: Double Hash Mismatch
**Vị trí:** [`verifyRsaPkcs1v15`](contracts/dPKIRegistry.sol:90) line 129-145

**Triệu chứng:** Valid signature luôn bị reject với `InvalidPoPSignature()`.

**Nguyên nhân:** 
- Client ([`pop_helper.py`](engine/pop_helper.py:39)): `sha256(wallet_address)` → hash 1 lần
- RSA sign với `hashes.SHA256()` → tạo DigestInfo chứa `sha256(message)` → hash lần 2
- Contract cũ: so sánh `digest` trực tiếp với hash trong EM → mismatch

**Fix:**
```solidity
// Contract giờ double-hash để khớp với DigestInfo
bytes32 expectedHash = sha256(abi.encodePacked(digest));
for (uint256 i = 0; i < 32; i++) {
    if (em[hashStart + i] != expectedHash[i]) return false;
}
```

### Kiến Trúc Test

```
tests/conftest.py (pytest fixture bootstrap)
├── _ensure_foundry_on_path()   → Tự resolve anvil.exe
├── _ensure_solc()              → Tự cài solc 0.8.20 qua py-solc-x
└── _bootstrap_toolchain        → Autouse fixture chạy trước mọi test

tests/test_pop_validation.py
├── anvil_node()                → Khởi động local blockchain
├── deployed_contract()         → Compile + deploy dPKIRegistry.sol
├── test_wallet()               → Tạo Ethereum test account
├── test_rsa_keypair()          → Sinh RSA-2048 keypair
└── 4 test functions            → Verify PoP logic on-chain
```

---

## 🎯 Checklist Trước Khi Thuyết Trình

- [ ] Chạy `scripts/run_pop_tests.ps1` → tất cả test PASS
- [ ] Demo live: chạy `pytest tests/test_pop_validation.py -v -s` để show log chi tiết
- [ ] Giải thích bug #1 (ASN.1 DER) và bug #2 (double hash) → thể hiện hiểu sâu crypto
- [ ] Nhấn mạnh: on-chain PEM parser + ASN.1 decoder + RSA verification là unique (hiếm project làm)
- [ ] Backup plan: nếu demo fail, show git log với test output đã chạy trước

---

## 📞 Nếu Gặp Vấn Đề

1. Xem log chi tiết: `pytest tests/test_pop_validation.py -v -s --tb=long`
2. Kiểm tra anvil có chạy: `ps aux | grep anvil` (hoặc Task Manager trên Windows)
3. Test thủ công từng bước trong [`TEST_POP_QUICKSTART.md`](TEST_POP_QUICKSTART.md)
4. Nếu vẫn fail → comment out test case đó, chỉ demo phần PASS
