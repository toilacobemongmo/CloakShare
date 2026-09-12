#include "padding.h"
#include <string.h>

int pkcs7_pad(const uint8_t *in, size_t in_len, uint8_t *out, size_t block_size) {
    if (!in || !out || block_size == 0 || block_size > 255) {
        return PKCS7_ERR_INVALID_PARAM;
    }

    uint8_t pad_val = (uint8_t)(block_size - (in_len % block_size));
    size_t padded_len = in_len + pad_val;

    memcpy(out, in, in_len);
    memset(out + in_len, pad_val, pad_val);

    return (int)padded_len;
}

int pkcs7_unpad(const uint8_t *in, size_t in_len, uint8_t *out, size_t block_size) {
    if (!in || !out || block_size == 0 || block_size > 255) {
        return PKCS7_ERR_INVALID_PARAM;
    }

    if (in_len == 0 || (in_len % block_size) != 0) {
        return PKCS7_ERR_INVALID_PADDING;
    }

    uint8_t pad_val = in[in_len - 1];

    if (pad_val == 0 || pad_val > block_size || (size_t)pad_val > in_len) {
        return PKCS7_ERR_INVALID_PADDING;
    }

    for (size_t i = in_len - pad_val; i < in_len; i++) {
        if (in[i] != pad_val) {
            return PKCS7_ERR_INVALID_PADDING;
        }
    }

    size_t unpadded_len = in_len - pad_val;
    memcpy(out, in, unpadded_len);

    return (int)unpadded_len;
}