#ifndef AES128_H
#define AES128_H

#include <stdint.h>
#include <stddef.h>

#define AES128_BLOCK_SIZE 16
#define AES128_KEY_SIZE   16

#ifdef __cplusplus
extern "C" {
#endif

/*
 * pkcs7_pad
 * ---------
 * Đệm `in` (dài `in_len`) theo chuẩn PKCS#7 tới bội số 16 byte.
 * Cấp phát buffer mới bằng malloc(), caller phải free() sau khi dùng.
 * `out_len` nhận độ dài buffer sau khi đệm.
 * Trả về con trỏ buffer đã đệm, hoặc NULL nếu lỗi cấp phát.
 */
uint8_t *pkcs7_pad(const uint8_t *in, size_t in_len, size_t *out_len);

/*
 * pkcs7_unpad
 * -----------
 * Gỡ đệm PKCS#7 khỏi `in` (dài `in_len`, phải chia hết cho 16).
 * `out_len` nhận độ dài dữ liệu thật sau khi gỡ đệm.
 * Trả về 0 nếu padding hợp lệ, -1 nếu sai định dạng (dữ liệu có thể bị hỏng/giả mạo).
 */
int pkcs7_unpad(const uint8_t *in, size_t in_len, size_t *out_len);

/*
 * aes128_cbc_encrypt
 * ------------------
 * Mã hoá `plaintext` (đã pad từ trước bằng pkcs7_pad, dài `len` là bội số
 * 16 byte) bằng AES-128-CBC. `key` và `iv` đều 16 byte. `iv` nên sinh
 * ngẫu nhiên mỗi lần mã hoá, không tái sử dụng cùng iv với cùng key.
 * `out` phải được caller cấp phát sẵn với kích thước >= len.
 * Trả về 0 nếu thành công, -1 nếu tham số không hợp lệ.
 */
int aes128_cbc_encrypt(const uint8_t *plaintext, size_t len,
                        const uint8_t key[AES128_KEY_SIZE],
                        const uint8_t iv[AES128_BLOCK_SIZE],
                        uint8_t *out);

/*
 * aes128_cbc_decrypt
 * ------------------
 * Giải mã `ciphertext` (dài `len`, bội số 16 byte) bằng AES-128-CBC.
 * Kết quả trong `out` (chưa gỡ padding — gọi pkcs7_unpad() sau đó).
 * Trả về 0 nếu thành công, -1 nếu tham số không hợp lệ.
 */
int aes128_cbc_decrypt(const uint8_t *ciphertext, size_t len,
                        const uint8_t key[AES128_KEY_SIZE],
                        const uint8_t iv[AES128_BLOCK_SIZE],
                        uint8_t *out);

#ifdef __cplusplus
}
#endif

#endif // AES128_H
