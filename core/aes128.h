#ifndef AES128_H
#define AES128_H

#include <stdint.h>
#include <stddef.h>

#define AES128_BLOCK_SIZE 16
#define AES128_KEY_SIZE   16

#ifdef __cplusplus
extern "C" {
#endif

int aes128_cbc_encrypt(const uint8_t *plaintext, size_t len,
                        const uint8_t key[AES128_KEY_SIZE],
                        const uint8_t iv[AES128_BLOCK_SIZE],
                        uint8_t *out);

int aes128_cbc_decrypt(const uint8_t *ciphertext, size_t len,
                        const uint8_t key[AES128_KEY_SIZE],
                        const uint8_t iv[AES128_BLOCK_SIZE],
                        uint8_t *out);

#ifdef __cplusplus
}
#endif

#endif // AES128_H