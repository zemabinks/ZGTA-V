// GameInstallerShim: a very small C layer between Swift and libarchive.
// Swift only sees this header (via the bridging header), never archive.h.
#ifndef GAME_INSTALLER_SHIM_H
#define GAME_INSTALLER_SHIM_H

#include <stdint.h>
#include <sys/types.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef struct gi_reader gi_reader;

/// Supplies the next block of archive bytes. Set *buffer and return its length,
/// return 0 at the end of the archive, or -1 on error (cancel, network gave up...).
/// The buffer must stay valid until the next call.
typedef long (*gi_read_fn)(void *context, const void **buffer);

/// Entry kinds returned by gi_reader_next.
enum { GI_ENTRY_FILE = 0, GI_ENTRY_DIRECTORY = 1, GI_ENTRY_SYMLINK = 2, GI_ENTRY_OTHER = 3 };

/// Result codes.
enum { GI_OK = 0, GI_EOF = 1, GI_WARN = 2, GI_FAILED = -1, GI_FATAL = -2 };

typedef struct {
    const char *path;      // UTF-8 path as stored in the archive (valid until the next gi_reader_next)
    int64_t size;          // -1 when unknown
    int kind;              // GI_ENTRY_*
    int encrypted;         // 1 if the entry's data or metadata is encrypted
    int size_known;
} gi_entry_info;

/// Opens a streaming (non-seekable) reader for zip, rar, rar5, tar (and .tar.gz).
gi_reader *gi_reader_open(gi_read_fn read, void *context);
/// Reads the next entry header. Returns GI_OK, GI_EOF, GI_WARN (entry usable) or GI_FAILED/GI_FATAL.
int gi_reader_next(gi_reader *reader, gi_entry_info *info);
/// Reads the next block of the current entry's data. Returns GI_OK with *size>0, GI_EOF when
/// the entry is done, or GI_FAILED/GI_FATAL (bad CRC, truncated...).
int gi_reader_data(gi_reader *reader, const void **buffer, size_t *size, int64_t *offset);
/// Skips the rest of the current entry.
int gi_reader_skip(gi_reader *reader);
/// The last error message from libarchive (or NULL) and its errno-style number.
const char *gi_reader_error(gi_reader *reader);
int gi_reader_errno(gi_reader *reader);
/// Name of the detected format, e.g. "ZIP 2.0 (deflation)" (valid until next call).
const char *gi_reader_format_name(gi_reader *reader);
/// Whether the archive (as far as read) contains encrypted entries: 1 yes, 0 no, <0 unknown.
int gi_reader_has_encrypted_entries(gi_reader *reader);
void gi_reader_close(gi_reader *reader);

/// Frees the byte range on disk (APFS: F_PUNCHHOLE). offset/length are rounded inwards to
/// `block` (the file system block size). Returns 0 or errno.
int gi_punch_hole(int fd, int64_t offset, int64_t length, int64_t block);

/// Extracts all files from an archive (.zip, .rar, .7z, .tar) into destination_folder.
/// Returns number of files extracted on success, or -1 on error.
int gi_extract_archive(const char *archive_path, const char *destination_folder);
int gi_inflate_raw(const void *input, uint32_t input_size, void *output, uint32_t output_size);

/// libarchive version string, for logs.
const char *gi_libarchive_version(void);

#ifdef __cplusplus
}
#endif
#endif
