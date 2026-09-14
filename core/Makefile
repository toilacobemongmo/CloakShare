# Makefile - core/ (CloakShare)
# Biên dịch module AES-128-CBC + PKCS#7 thành thư viện động.
#
# Public API xuất ra (kiểm bằng `nm -D`):
#   aes128_cbc_encrypt, aes128_cbc_decrypt, pkcs7_pad, pkcs7_unpad
#
# Mục tiêu:
#   make / make shared -> build core/libaes.so (Linux)
#   make win           -> build core/aes128.dll (cross-compile bằng mingw, tuỳ chọn)
#   make clean          -> dọn *.o *.so *.dll

CC      = gcc
CFLAGS  = -O3 -Wall -Wextra -fPIC
SRCS    = aes128.c
TARGET  = libaes.so

WIN_CC      = x86_64-w64-mingw32-gcc
WIN_TARGET  = aes128.dll

.PHONY: all shared win clean clean_obj

all: shared clean_obj

# Build thư viện động cho Linux (.so)
shared:
	$(CC) $(CFLAGS) -shared $(SRCS) -o $(TARGET)

# Build thư viện động cho Windows (.dll) - cần mingw-w64 cài sẵn
win:
	$(WIN_CC) $(CFLAGS) -shared $(SRCS) -o $(WIN_TARGET)

clean_obj:
	rm -f *.o

clean:
	rm -f *.o *.so *.dll
