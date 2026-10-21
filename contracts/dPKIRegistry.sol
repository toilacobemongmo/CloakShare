// SPDX-License-Identifier: MIT
pragma solidity 0.8.20;

/**
 * @title Decentralized PKI Registry with Proof-of-Possession (PoP)
 * @notice Smart contract hỗ trợ đăng ký RSA Public Key với Proof-of-Possession validation
 * @dev Tích hợp PEM parser, ASN.1 DER decoder, và RSA signature verification on-chain
 */
contract dPKIRegistry {
    // --- ERRORS ---
    error InvalidPEM();
    error InvalidBase64();
    error InvalidASN1();
    error InvalidSignatureLength();
    error ModExpFailed();
    error InvalidPoPSignature();

    // --- EVENTS ---
    event PublicKeyRegistered(address indexed user, string publicKeyPem);
    event PublicKeyRegisteredWithPoP(address indexed user, string publicKeyPem, bytes signature);

    // --- STORAGE ---
    struct KeyRecord {
        string publicKeyPem;
        bool hasPoP;
        uint256 registeredAt;
    }

    mapping(address => KeyRecord) public registry;

    // ASN.1 DigestInfo prefix cho SHA-256 (RFC 8017 PKCS#1 v2.2)
    bytes private constant SHA256_PREFIX = hex"3031300d060960864801650304020105000420";

    // =========================================================================
    // EXTERNAL FUNCTIONS
    // =========================================================================

    /**
     * @notice Hàm legacy: Giữ tương thích ngược (không yêu cầu PoP).
     */
    function registerPublicKey(string calldata publicKeyPem) external {
        registry[msg.sender] = KeyRecord({
            publicKeyPem: publicKeyPem,
            hasPoP: false,
            registeredAt: block.timestamp
        });
        emit PublicKeyRegistered(msg.sender, publicKeyPem);
    }

    /**
     * @notice Đăng ký Public Key kèm PoP validation.
     * @param publicKeyPem Chuỗi PEM chứa RSA Public Key (PKCS#1 hoặc X.509 / PKCS#8).
     * @param signature Chữ ký RSA-SHA256 PKCS#1 v1.5 của msg.sender (raw address 20 bytes).
     */
    function registerPublicKeyWithPoP(string calldata publicKeyPem, bytes calldata signature) external {
        // 1. Parse PEM và decode ASN.1 DER để lấy Modulus (N) và Exponent (e)
        (bytes memory modulus, bytes memory exponent) = parseRsaPem(publicKeyPem);

        // 2. Chữ ký phải có cùng độ dài với Modulus (VD: RSA-2048 = 256 bytes)
        if (signature.length != modulus.length) revert InvalidSignatureLength();

        // 3. Tính SHA-256 digest của msg.sender
        bytes32 messageHash = sha256(abi.encodePacked(msg.sender));

        // 4. Verify chữ ký RSA-PKCS1-v1_5 on-chain
        bool isValid = verifyRsaPkcs1v15(modulus, exponent, signature, messageHash);
        if (!isValid) revert InvalidPoPSignature();

        // 5. Lưu trữ và emit event
        registry[msg.sender] = KeyRecord({
            publicKeyPem: publicKeyPem,
            hasPoP: true,
            registeredAt: block.timestamp
        });

        emit PublicKeyRegisteredWithPoP(msg.sender, publicKeyPem, signature);
    }

    /**
     * @notice Tra cứu Public Key RSA của một địa chỉ ví bất kỳ
     */
    function getPublicKey(address user) external view returns (string memory) {
        return registry[user].publicKeyPem;
    }

    // =========================================================================
    // RSA VERIFICATION VIA PRECOMPILE 0x05 (BigModExp)
    // =========================================================================

    function verifyRsaPkcs1v15(
        bytes memory n,
        bytes memory e,
        bytes memory sig,
        bytes32 digest
    ) internal view returns (bool) {
        uint256 k = n.length;
        if (k < 11 + SHA256_PREFIX.length + 32) return false;

        // Tính s^e mod n qua Precompile 0x05
        bytes memory em = modExp(sig, e, n);
        if (em.length != k) {
            // Padding trường hợp em trả về ngắn hơn do 0-bytes đầu bị triệt tiêu
            bytes memory paddedEm = new bytes(k);
            uint256 offset = k - em.length;
            for (uint256 i = 0; i < em.length; i++) {
                paddedEm[offset + i] = em[i];
            }
            em = paddedEm;
        }

        // Kiểm tra định dạng EMSA-PKCS1-v1_5: 0x00 || 0x01 || PS (all 0xFF) || 0x00 || T
        if (em[0] != 0x00 || em[1] != 0x01) return false;

        uint256 tLen = SHA256_PREFIX.length + 32;
        uint256 psEnd = k - tLen - 1;

        for (uint256 i = 2; i < psEnd; i++) {
            if (em[i] != 0xFF) return false;
        }
        if (em[psEnd] != 0x00) return false;

        // So khớp ASN.1 prefix
        uint256 tStart = psEnd + 1;
        for (uint256 i = 0; i < SHA256_PREFIX.length; i++) {
            if (em[tStart + i] != SHA256_PREFIX[i]) return false;
        }

        // So khớp Digest
        // NOTE: Client code (pop_helper.py) hashes wallet_address một lần với sha256(),
        // rồi rsa_key.sign() với hashes.SHA256() tạo DigestInfo prefix + hash lần 2.
        // Contract nhận digest = sha256(msg.sender), cần hash lại để khớp với DigestInfo trong EM.
        bytes32 expectedHash = sha256(abi.encodePacked(digest));
        uint256 hashStart = tStart + SHA256_PREFIX.length;
        for (uint256 i = 0; i < 32; i++) {
            if (em[hashStart + i] != expectedHash[i]) return false;
        }

        return true;
    }

    function modExp(bytes memory base, bytes memory exp, bytes memory modulus) internal view returns (bytes memory output) {
        bytes memory inputData = abi.encodePacked(
            uint256(base.length),
            uint256(exp.length),
            uint256(modulus.length),
            base,
            exp,
            modulus
        );
        output = new bytes(modulus.length);
        bool success;
        assembly {
            success := staticcall(gas(), 0x05, add(inputData, 0x20), mload(inputData), add(output, 0x20), mload(modulus))
        }
        if (!success) revert ModExpFailed();
    }

    // =========================================================================
    // PEM & ASN.1 PARSING
    // =========================================================================

    function parseRsaPem(string calldata pem) internal pure returns (bytes memory modulus, bytes memory exponent) {
        bytes calldata b = bytes(pem);
        uint256 len = b.length;

        // Tìm điểm bắt đầu và kết thúc của Base64 content giữa "-----"
        uint256 start = 0;
        uint256 end = 0;
        uint256 dashes = 0;

        for (uint256 i = 0; i < len - 4; i++) {
            if (b[i] == '-' && b[i+1] == '-' && b[i+2] == '-' && b[i+3] == '-' && b[i+4] == '-') {
                dashes++;
                if (dashes == 2) start = i + 5; // Đi qua "-----BEGIN ...-----"
                if (dashes == 3) {
                    end = i;
                    break;
                }
            }
        }
        if (start == 0 || end == 0 || start >= end) revert InvalidPEM();

        // Decode Base64 thành DER bytes
        bytes memory der = base64Decode(b[start:end]);

        // Phân giải ASN.1 để lấy (n, e)
        return extractRsaKey(der);
    }

    function extractRsaKey(bytes memory der) internal pure returns (bytes memory modulus, bytes memory exponent) {
        uint256 cursor = 0;
        (cursor, ) = readTagLength(der, cursor); // Đọc outer SEQUENCE

        // Kiểm tra xem là X.509 SubjectPublicKeyInfo hay PKCS#1 RSAPublicKey
        if (der[cursor] == 0x30) {
            // X.509 format: SEQUENCE chứa AlgorithmIdentifier và BIT STRING
            uint256 nextSeqLen;
            (cursor, nextSeqLen) = readTagLength(der, cursor);
            cursor += nextSeqLen; // Bỏ qua AlgorithmIdentifier SEQUENCE

            if (uint8(der[cursor]) != 0x03) revert InvalidASN1(); // Phải là BIT STRING
            (cursor, ) = readTagLength(der, cursor);
            cursor++; // Bỏ qua unused bits count (1 byte)

            // Bây giờ trỏ vào inner PKCS#1 SEQUENCE
            (cursor, ) = readTagLength(der, cursor);
        }

        // Đọc Modulus (INTEGER)
        if (der[cursor] != 0x02) revert InvalidASN1();
        uint256 modLen;
        (cursor, modLen) = readTagLength(der, cursor);

        // Bỏ qua leading zero của unsigned INTEGER nếu có
        uint256 modStart = cursor;
        if (der[modStart] == 0x00 && modLen > 0) {
            modStart++;
            modLen--;
        }
        modulus = new bytes(modLen);
        for (uint256 i = 0; i < modLen; i++) modulus[i] = der[modStart + i];
        cursor += modLen + (modStart - cursor);

        // Đọc Exponent (INTEGER)
        if (der[cursor] != 0x02) revert InvalidASN1();
        uint256 expLen;
        (cursor, expLen) = readTagLength(der, cursor);

        uint256 expStart = cursor;
        if (der[expStart] == 0x00 && expLen > 0) {
            expStart++;
            expLen--;
        }
        exponent = new bytes(expLen);
        for (uint256 i = 0; i < expLen; i++) exponent[i] = der[expStart + i];

        return (modulus, exponent);
    }

    function readTagLength(bytes memory data, uint256 offset) internal pure returns (uint256 newOffset, uint256 length) {
        if (offset + 1 >= data.length) revert InvalidASN1();
        offset++; // Bỏ qua tag byte

        uint8 firstLen = uint8(data[offset]);
        offset++;

        if (firstLen < 0x80) {
            return (offset, firstLen);
        } else if (firstLen == 0x81) {
            if (offset >= data.length) revert InvalidASN1();
            length = uint8(data[offset]);
            return (offset + 1, length);
        } else if (firstLen == 0x82) {
            if (offset + 1 >= data.length) revert InvalidASN1();
            length = (uint256(uint8(data[offset])) << 8) | uint256(uint8(data[offset + 1]));
            return (offset + 2, length);
        }
        revert InvalidASN1();
    }

    // =========================================================================
    // BASE64 DECODER
    // =========================================================================

    function base64Decode(bytes calldata input) internal pure returns (bytes memory) {
        // Đếm số ký tự base64 hợp lệ (bỏ newline \r, \n, spaces)
        uint256 validLen = 0;
        for (uint256 i = 0; i < input.length; i++) {
            bytes1 c = input[i];
            if ((c >= "A" && c <= "Z") || (c >= "a" && c <= "z") || (c >= "0" && c <= "9") || c == "+" || c == "/" || c == "=") {
                validLen++;
            }
        }

        bytes memory clean = new bytes(validLen);
        uint256 idx = 0;
        for (uint256 i = 0; i < input.length; i++) {
            bytes1 c = input[i];
            if ((c >= "A" && c <= "Z") || (c >= "a" && c <= "z") || (c >= "0" && c <= "9") || c == "+" || c == "/" || c == "=") {
                clean[idx++] = c;
            }
        }

        if (validLen % 4 != 0) revert InvalidBase64();

        uint256 padding = 0;
        if (validLen > 0 && clean[validLen - 1] == "=") padding++;
        if (validLen > 1 && clean[validLen - 2] == "=") padding++;

        uint256 outLen = (validLen / 4) * 3 - padding;
        bytes memory out = new bytes(outLen);

        uint256 outIdx = 0;
        for (uint256 i = 0; i < validLen; i += 4) {
            uint32 b64 = (b64Val(clean[i]) << 18) |
                         (b64Val(clean[i+1]) << 12) |
                         (b64Val(clean[i+2]) << 6) |
                         b64Val(clean[i+3]);

            if (outIdx < outLen) out[outIdx++] = bytes1(uint8(b64 >> 16));
            if (outIdx < outLen) out[outIdx++] = bytes1(uint8(b64 >> 8));
            if (outIdx < outLen) out[outIdx++] = bytes1(uint8(b64));
        }

        return out;
    }

    function b64Val(bytes1 c) private pure returns (uint32) {
        if (c >= "A" && c <= "Z") return uint32(uint8(c)) - 65;
        if (c >= "a" && c <= "z") return uint32(uint8(c)) - 71;
        if (c >= "0" && c <= "9") return uint32(uint8(c)) + 4;
        if (c == "+") return 62;
        if (c == "/") return 63;
        if (c == "=") return 0;
        revert InvalidBase64();
    }
}
