// WABT's macOS release archive references OpenSSL SHA256. Use the system digest
// implementation for the build tool, avoiding a second OpenSSL installation.
#include <CommonCrypto/CommonDigest.h>
#include <stddef.h>
#include <stdint.h>

unsigned char *SHA256(const unsigned char *bytes, size_t length,
                       unsigned char *digest) {
  CC_SHA256_CTX context;
  CC_SHA256_Init(&context);
  while (length) {
    CC_LONG chunk = length > UINT32_MAX ? UINT32_MAX : (CC_LONG)length;
    CC_SHA256_Update(&context, bytes, chunk);
    bytes += chunk;
    length -= chunk;
  }
  CC_SHA256_Final(digest, &context);
  return digest;
}
