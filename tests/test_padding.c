#include <stdio.h>
#include <string.h>
#include <assert.h>
#include "../core/padding.h"

static void test_pad_10_bytes(void) {
    uint8_t in[10] = {0, 1, 2, 3, 4, 5, 6, 7, 8, 9};
    uint8_t out[32];
    int len = pkcs7_pad(in, sizeof(in), out, 16);

    assert(len == 16);
    for (int i = 0; i < 10; i++) {
        assert(out[i] == (uint8_t)i);
    }
    for (int i = 10; i < 16; i++) {
        assert(out[i] == 0x06);
    }
    printf("[PASS] test_pad_10_bytes\n");
}

static void test_pad_16_bytes(void) {
    uint8_t in[16];
    memset(in, 0xAA, sizeof(in));
    uint8_t out[32];
    int len = pkcs7_pad(in, sizeof(in), out, 16);

    assert(len == 32);
    for (int i = 0; i < 16; i++) {
        assert(out[i] == 0xAA);
    }
    for (int i = 16; i < 32; i++) {
        assert(out[i] == 0x10);
    }
    printf("[PASS] test_pad_16_bytes\n");
}

static void test_unpad_valid(void) {
    uint8_t padded[16] = {
        0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08,
        0x09, 0x0A, 0x06, 0x06, 0x06, 0x06, 0x06, 0x06
    };
    uint8_t out[16];
    int len = pkcs7_unpad(padded, sizeof(padded), out, 16);

    assert(len == 10);
    for (int i = 0; i < 10; i++) {
        assert(out[i] == (uint8_t)(i + 1));
    }
    printf("[PASS] test_unpad_valid\n");
}

static void test_unpad_invalid(void) {
    uint8_t out[32];

    uint8_t bad_pad1[16] = {
        0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 0x06, 0x06, 0x06, 0x06, 0x05, 0x06
    };
    assert(pkcs7_unpad(bad_pad1, sizeof(bad_pad1), out, 16) == PKCS7_ERR_INVALID_PADDING);

    uint8_t bad_pad2[16] = {0};
    assert(pkcs7_unpad(bad_pad2, sizeof(bad_pad2), out, 16) == PKCS7_ERR_INVALID_PADDING);

    // Byte padding lớn hơn block_size (> 16)
    uint8_t bad_pad3[16] = {0};
    bad_pad3[15] = 0x11;
    assert(pkcs7_unpad(bad_pad3, sizeof(bad_pad3), out, 16) == PKCS7_ERR_INVALID_PADDING);

    // Chiều dài không chia hết cho block_size
    uint8_t bad_pad4[15] = {0};
    assert(pkcs7_unpad(bad_pad4, sizeof(bad_pad4), out, 16) == PKCS7_ERR_INVALID_PADDING);

    printf("[PASS] test_unpad_invalid\n");
}

int main(void) {
    test_pad_10_bytes();
    test_pad_16_bytes();
    test_unpad_valid();
    test_unpad_invalid();
    printf("\nAll PKCS#7 tests passed successfully!\n");
    return 0;
}