#include "GameInstallerShim.h"
#include <zlib.h>

int gi_inflate_raw(const void *input, uint32_t input_size, void *output, uint32_t output_size) {
    z_stream stream = {0};
    stream.next_in = (Bytef *)input; stream.avail_in = input_size;
    stream.next_out = output; stream.avail_out = output_size;
    if (inflateInit2(&stream, -MAX_WBITS) != Z_OK) return 0;
    int result = inflate(&stream, Z_FINISH);
    int valid = result == Z_STREAM_END && stream.total_out == output_size && stream.total_in == input_size;
    inflateEnd(&stream); return valid;
}
