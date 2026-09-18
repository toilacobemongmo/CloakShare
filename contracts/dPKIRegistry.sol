// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

contract dPKIRegistry {
    // Lưu ánh xạ: Địa chỉ ví (0x...) -> Public Key RSA (chuỗi PEM)
    mapping(address => string) private _publicKeys;

    event PublicKeyRegistered(address indexed user, string publicKeyPem);

    /**
     * @notice Đăng ký hoặc cập nhật Public Key RSA của ví đang gọi
     */
    function registerPublicKey(string calldata publicKeyPem) external {
        require(bytes(publicKeyPem).length > 0, "Public key cannot be empty");
        _publicKeys[msg.sender] = publicKeyPem;
        emit PublicKeyRegistered(msg.sender, publicKeyPem);
    }

    /**
     * @notice Tra cứu Public Key RSA của một địa chỉ ví bất kỳ
     */
    function getPublicKey(address user) external view returns (string memory) {
        return _publicKeys[user];
    }
}