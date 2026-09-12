#ifndef PADDING_H
#define PADDING_H

#include <stddef.h>
#include <stdint.h>

#define PKCS7_ERR_INVALID_PARAM -1
#define PKCS7_ERR_INVALID_PADDING -2

int pkcs7_pad(const uint8_t *in, size_t in_len, uint8_t *out, size_t block_size);
int pkcs7_unpad(const uint8_t *in, size_t in_len, uint8_t *out, size_t block_size);

#endif