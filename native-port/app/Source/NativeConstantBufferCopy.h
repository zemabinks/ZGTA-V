#pragma once

#include <algorithm>
#include <cstdint>
#include <cstring>
#include <limits>
#include <vector>

// CPU-authoritative constant-buffer shadows only. GPU-written/unknown sources
// need a separate ordered synchronization design; never substitute contents()
// of a potentially in-flight GPU allocation for an authoritative CPU shadow.
// Returns bytes copied; invalid offsets and empty copies leave all state alone.
inline uint64_t PGCopyConstantBufferShadow(
    std::vector<uint8_t>& destination, const std::vector<uint8_t>& source,
    uint64_t destinationOffset, uint64_t sourceOffset, uint64_t requestedBytes,
    uint64_t& materializedFrame, uint32_t& version) {
    if (destinationOffset > destination.size() || sourceOffset > source.size()) return 0;
    const uint64_t bytes = std::min(requestedBytes,
        std::min(uint64_t(destination.size()) - destinationOffset,
                 uint64_t(source.size()) - sourceOffset));
    if (!bytes) return 0;
    // memmove also supports an overlapping copy within the same shadow.
    std::memmove(destination.data() + destinationOffset, source.data() + sourceOffset,
                 static_cast<size_t>(bytes));
    materializedFrame = std::numeric_limits<uint64_t>::max();
    ++version;
    return bytes;
}
