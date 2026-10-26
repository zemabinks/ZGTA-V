// Offline shader translation for the native Metal renderer.
//
// Reads a list of translated game shaders (WGSL, one entry point `main` each) and writes, per shader, Metal Shading
// Language with the D3D11 register slots mapped straight onto Metal argument-table indices, plus one reflection line
// (JSON) that the renderer reads at startup. The mapping (keep in sync with Source/MetalRenderer/MRShaders.h):
//   buffers : constant buffer bN (binding N, 0..13) -> buffer N; the shader's constant table (binding 15) -> buffer 14;
//             immediate block (array lengths) -> buffer 15; storage buffers -> 16.. in binding order;
//             vertex buffer slot s -> buffer 30 - s (set by the renderer's vertex descriptor).
//   textures: sampled and storage textures are numbered 0.. in declaration order (some GPUs, e.g. the simulator's,
//             have only 31 texture slots; the reflection records each binding's index).
//   samplers: sN (binding 16 + N) -> sampler N.
//
// Usage: pgmsl <list file> <out dir> <reflection file>
//   list file: one "<hash> <stage> <wgsl path>" per line.

#include <cstdio>
#include <fstream>
#include <iostream>
#include <sstream>
#include <string>
#include <vector>

#include "src/tint/api/tint.h"
#include "src/tint/lang/msl/writer/writer.h"
#include "src/tint/lang/wgsl/inspector/inspector.h"
#include "src/tint/lang/wgsl/reader/reader.h"
#include "src/tint/lang/wgsl/reader/options.h"
#include "src/tint/utils/diagnostic/source.h"

using RB = tint::inspector::ResourceBinding;

static const char* KindName(RB::ResourceType t) {
    switch (t) {
        case RB::ResourceType::kUniformBuffer: return "ubo";
        case RB::ResourceType::kStorageBuffer: return "rw";
        case RB::ResourceType::kReadOnlyStorageBuffer: return "ro";
        case RB::ResourceType::kSampler: return "smp";
        case RB::ResourceType::kSampledTexture: return "tex";
        case RB::ResourceType::kMultisampledTexture: return "texms";
        case RB::ResourceType::kWriteOnlyStorageTexture: return "stw";
        case RB::ResourceType::kReadOnlyStorageTexture: return "str";
        case RB::ResourceType::kReadWriteStorageTexture: return "strw";
        case RB::ResourceType::kDepthTexture: return "depth";
        case RB::ResourceType::kDepthMultisampledTexture: return "depthms";
        default: return "other";
    }
}
static const char* DimName(RB::TextureDimension d) {
    switch (d) {
        case RB::TextureDimension::k1d: return "1d";
        case RB::TextureDimension::k2d: return "2d";
        case RB::TextureDimension::k2dArray: return "2d-array";
        case RB::TextureDimension::k3d: return "3d";
        case RB::TextureDimension::kCube: return "cube";
        case RB::TextureDimension::kCubeArray: return "cube-array";
        default: return "";
    }
}
static const char* SampleName(RB::SampledKind k) {
    switch (k) {
        case RB::SampledKind::kUInt: return "uint";
        case RB::SampledKind::kSInt: return "sint";
        default: return "float";
    }
}

static bool Translate(const std::string& hash, const std::string& stage, const std::string& path,
                      const std::string& outDir, std::ostream& refl) {
    std::ifstream in(path);
    if (!in) { std::cerr << hash << ": cannot read " << path << "\n"; return false; }
    std::stringstream ss; ss << in.rdbuf();
    std::string text = ss.str();
    tint::Source::File file(path, text);
    tint::wgsl::reader::Options parseOptions;
    parseOptions.allowed_features = tint::wgsl::AllowedFeatures::Everything();
    tint::Program program = tint::wgsl::reader::Parse(&file, parseOptions);
    if (!program.IsValid()) { std::cerr << hash << ": parse failed: " << program.Diagnostics().Str() << "\n"; return false; }
    tint::inspector::Inspector inspector(program);
    auto ep = inspector.GetEntryPoint("main");
    auto resources = inspector.GetResourceBindings("main");

    tint::msl::writer::Options opt;
    opt.entry_point_name = "main";
    opt.remapped_entry_point_name = "s_" + hash;
    opt.strip_all_names = true;
    opt.immediate_binding_point = tint::BindingPoint{0, 15};
    std::ostringstream res;
    uint32_t nextStorage = 16, sizeIndex = 0, nextTexture = 0;
    bool first = true;
    std::ostringstream alen;
    for (auto& r : resources) {
        tint::BindingPoint src{r.bind_group, r.binding};
        uint32_t index = 0;
        switch (r.resource_type) {
            case RB::ResourceType::kUniformBuffer:
                index = r.binding == 15 ? 14 : r.binding;
                opt.bindings.uniform.emplace(src, tint::BindingPoint{0, index});
                break;
            case RB::ResourceType::kStorageBuffer:
            case RB::ResourceType::kReadOnlyStorageBuffer:
                index = nextStorage++;
                opt.bindings.storage.emplace(src, tint::BindingPoint{0, index});
                opt.array_length_from_constants.bindpoint_to_size_index.emplace(src, sizeIndex);
                alen << (sizeIndex ? "," : "") << "[" << index << "," << sizeIndex << "]";
                sizeIndex++;
                break;
            case RB::ResourceType::kSampler:
                index = r.binding - 16;
                opt.bindings.sampler.emplace(src, tint::BindingPoint{0, index});
                break;
            case RB::ResourceType::kWriteOnlyStorageTexture:
            case RB::ResourceType::kReadOnlyStorageTexture:
            case RB::ResourceType::kReadWriteStorageTexture:
                index = nextTexture++;
                opt.bindings.storage_texture.emplace(src, tint::BindingPoint{0, index});
                break;
            case RB::ResourceType::kSampledTexture:
            case RB::ResourceType::kMultisampledTexture:
            case RB::ResourceType::kDepthTexture:
            case RB::ResourceType::kDepthMultisampledTexture:
                index = nextTexture++;
                opt.bindings.texture.emplace(src, tint::BindingPoint{0, index});
                break;
            default:
                std::cerr << hash << ": unsupported resource kind at binding " << r.binding << "\n";
                return false;
        }
        res << (first ? "" : ",") << "[\"" << KindName(r.resource_type) << "\"," << r.binding << "," << index << ",\""
            << DimName(r.dim) << "\",\"" << SampleName(r.sampled_kind) << "\","
            << (r.sampler_type == RB::SamplerType::kComparison ? 1 : 0) << "," << r.size << "]";
        first = false;
    }
    // The immediate block: a zero word that Tint uses to defeat constant folding at 0, then the storage buffer sizes.
    opt.non_constant_zero_offset = 0;
    if (sizeIndex) opt.array_length_from_constants.buffer_sizes_offset = 16;

    tint::wgsl::reader::IROptions irOptions{};
    auto ir = tint::wgsl::reader::ProgramToLoweredIR(program, irOptions);
    if (ir != tint::Success) { std::cerr << hash << ": IR failed: " << ir.Failure().reason << "\n"; return false; }
    auto result = tint::msl::writer::Generate(ir.Get(), opt);
    if (result != tint::Success) { std::cerr << hash << ": MSL failed: " << result.Failure().reason << "\n"; return false; }

    // Helper functions and types go into a namespace of their own: every shader's Tint output uses the same names, and the
    // metallib links all of them together. Only the entry point (the last function) stays global.
    std::string msl = result->msl;
    size_t head = msl.find("using namespace metal;\n");
    size_t entry = std::string::npos;
    for (const char* kw : {"\nvertex ", "\nfragment ", "\nkernel "}) {
        size_t at = msl.rfind(kw);
        if (at != std::string::npos && (entry == std::string::npos || at > entry)) entry = at;
    }
    // attribute lines such as [[max_total_threads_per_threadgroup(N)]] belong to the entry point
    while (entry != std::string::npos && entry > 0) {
        size_t prev = msl.rfind('\n', entry - 1);
        if (prev == std::string::npos || msl.compare(prev + 1, 2, "[[") != 0) break;
        entry = prev;
    }
    if (head != std::string::npos && entry != std::string::npos && entry > head) {
        msl.insert(entry + 1, "}  // namespace\nusing namespace n_" + hash + ";\n");
        msl.insert(head + 23, "namespace n_" + hash + " {\n");
    }
    // unchanged sources keep their timestamp, so the AIR compile step only rebuilds what changed
    std::string target = outDir + "/" + hash + ".metal";
    std::ifstream existing(target);
    std::stringstream previous;
    if (existing) previous << existing.rdbuf();
    if (!existing || previous.str() != msl) {
        std::ofstream out(target);
        out << msl;
    }

    std::ostringstream ins, outs;
    bool f1 = true;
    for (auto& v : ep.input_variables) if (v.attributes.location) { ins << (f1 ? "" : ",") << *v.attributes.location; f1 = false; }
    f1 = true;
    for (auto& v : ep.output_variables) if (v.attributes.location) { outs << (f1 ? "" : ",") << *v.attributes.location; f1 = false; }
    std::ostringstream pairs;
    bool firstPair = true;
    for (auto& use : inspector.GetSamplerTextureUses("main")) {
        pairs << (firstPair ? "" : ",") << "[" << use.sampler_binding_point.binding << "," << use.texture_binding_point.binding << "]";
        firstPair = false;
    }
    std::ostringstream wg;
    if (ep.workgroup_size) wg << ep.workgroup_size->x << "," << ep.workgroup_size->y << "," << ep.workgroup_size->z;
    std::ostringstream wgm;
    for (size_t i = 0; i < result->workgroup_allocations.size(); i++) wgm << (i ? "," : "") << result->workgroup_allocations[i];
    bool usesImmediate = result->msl.find("buffer(15)") != std::string::npos;
    refl << "{\"h\":\"" << hash << "\",\"st\":\"" << stage << "\",\"res\":[" << res.str() << "],\"in\":[" << ins.str()
         << "],\"out\":[" << outs.str() << "],\"wg\":[" << wg.str() << "],\"wgm\":[" << wgm.str() << "],\"vid\":"
         << (ep.vertex_index_used ? 1 : 0) << ",\"iid\":" << (ep.instance_index_used ? 1 : 0) << ",\"fd\":"
         << (ep.frag_depth_used ? 1 : 0) << ",\"imm\":" << (usesImmediate ? 1 : 0) << ",\"alen\":[" << alen.str()
         << "],\"pairs\":[" << pairs.str() << "]}\n";
    return true;
}

int main(int argc, char** argv) {
    if (argc != 4) { std::cerr << "usage: pgmsl <list> <out dir> <reflection>\n"; return 2; }
    tint::Initialize();
    std::ifstream list(argv[1]);
    std::ofstream refl(argv[3]);
    std::string hash, stage, path;
    int ok = 0, failed = 0;
    while (list >> hash >> stage >> path) {
        if (Translate(hash, stage, path, argv[2], refl)) ok++; else failed++;
    }
    std::cerr << "translated " << ok << ", failed " << failed << "\n";
    return 0;
}
