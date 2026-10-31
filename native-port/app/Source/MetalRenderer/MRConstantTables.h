// Immutable shader tables, interned by their actual GPU-visible words.
// Exact vector equality (including length) is deliberate: no hash collision
// can alias two different programs' constants. Offsets retain Metal alignment.
#pragma once
#include <algorithm>
#include <cstddef>
#include <cstdint>
#include <map>
#include <vector>

class PGConstantTables {
    std::map<std::vector<uint32_t>, size_t> offsets_;
    size_t bytes_ = 0;
public:
    size_t intern(const std::vector<uint32_t>& words) {
        auto found = offsets_.find(words);
        if (found != offsets_.end()) return found->second;
        const size_t at = bytes_;
        bytes_ += (words.size() * 16 + 255) & ~size_t(255);
        offsets_.emplace(words, at);
        return at;
    }
    size_t bytes() const { return bytes_; }
    size_t count() const { return offsets_.size(); }
    void write(uint8_t* destination) const {
        // Every row's unused components and all alignment bytes are zero.
        std::fill(destination, destination + bytes_, uint8_t(0));
        for (const auto& entry : offsets_) {
            auto rows = reinterpret_cast<uint32_t*>(destination + entry.second);
            for (size_t i = 0; i < entry.first.size(); ++i) rows[i * 4] = entry.first[i];
        }
    }
};
