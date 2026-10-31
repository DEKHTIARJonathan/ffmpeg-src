# ffmpeg-src

FFmpeg n8.0, built from pristine source with configure/Make. Cargo 8.0.0-rcN
identifies wrapper candidates; native FFmpeg remains 8.0. This implementation is
under qualification; platform and feature support must be validated before release.

Prerequisites: Rust, Python 3.11+, a C/C++ compiler, GNU Make, POSIX shell,
pkg-config, CMake 3.25+, Ninja, and NASM on x86. Windows requires MSVC and MSYS2
Unix tools. Apple builds require the Xcode SDK. No native sources are downloaded
by published builds. Packaging downloads checksum-locked zlib 1.3.2; Kvazaar is
pinned to FrameForge's reviewed BSD-licensed revision.

Default features build all seven libraries, shared, with bundled zlib, assembly
and network support. Each library has its own feature named after the library.
Use default-features=false and select a linking mode plus libraries to customize.
Dependencies imply their required libraries. Optional kvazaar enables software
HEVC without GPL. Optional hardware features: videotoolbox (macOS), vaapi (Linux,
requires libva/libdrm development packages), d3d11va and dxva2 (Windows).
static-crt selects the Windows static native CRT. Static consumers must match it.

Only enable-gpl permits GPL compilation, including the boxblur filter; it implies
avfilter. enable-version3 changes LGPL 2.1+ to LGPL 3+, or GPL 2+ to GPL 3+ when
GPL is enabled. Nonfree and automatic external-library discovery are disabled.
Cargo features unify: another dependency enabling enable-gpl affects the build.
Source archives contain GPL files even when the resulting libraries are LGPL.
See LICENSE.md and the installed share/licenses directory. These controls are
not legal certification or patent clearance.

## Consumer ordering

Build a separate preparer depending on ffmpeg-src, and obtain
`ffmpeg_src::artifacts().prefix()` before launching the consumer's Cargo process.
Set FFMPEG_DIR to that prefix for shared ffmpeg-sys-next discovery. Headers are
in include, libraries in lib, Windows DLLs in bin, and pkg-config files in
lib/pkgconfig. A downstream build.rs cannot prepare its own dependencies' SDK.
Use pkg-config discovery for static consumers, which need the complete native
link dependency closure. Do not enable ffmpeg-sys-next's own build feature.
Static builds query pkg-config with `--static`. For Kvazaar, the builder supplies
the upstream CMake template's `LIBS` input for math and pthread dependencies;
the pinned CMake project otherwise leaves its private link metadata empty.

SDK paths live in OUT_DIR and are not permanent installations. Consumers own
runtime staging, loader paths, signing, notices, and redistribution compliance.
Preserve versioned dylib/SONAME filenames and symlinks. No FFmpeg CLI is built.

## Development

Install sccache and prek before make setup. Project Make targets require
RUSTC_WRAPPER=sccache and disable incremental Rust compilation. FFmpeg target and
host compiler commands use the supplied cache wrapper; CMake uses C/C++ launchers.
A repeated no-op build is not cache evidence. Cache-hit qualification must remove
native outputs while preserving the compiler cache and record actual statistics.

Windows CI uses `scripts/rustc_cache.py setup` after initializing MSVC. Its small
compiler adapter works around sccache 0.19.0 expanding long Rust response files
past Windows' process command-line limit. It preserves all cfg/check-cfg flags,
includes their SHA-256 digest and compiler identity in the cache key, and restores
them through a response file when invoking rustc. Native calls use sccache directly.
`scripts/rustc_cache.py test` compiles an oversized argument list, removes outputs,
checks an actual Rust cache hit, and verifies different cfg values yield different
outputs. This helper is CI tooling, not part of the published native builder.

Run make package, make build, and make test. Packaging runs prek and formatting,
then measures the actual archive. make test extracts it into an isolated project.
Native source compression keeps one source crate below the registry limit.

## FrameForge migration

Keep ffmpeg-next 9.0.0 and ffmpeg-sys-next 9.0.1 initially. Add this source crate to
the independent xtask/preparer phase, with shared,avformat,swscale,zlib,kvazaar,
asm,network and the platform hardware features. Export SDK discovery before
application Cargo starts. Replace native downloads and SDK marker machinery;
retain Tauri staging, signing, executable loader paths, deployment targets and
the Windows bindgen stack workaround. Stage all native notices.

This changes FrameForge's native baseline from 9.0 to the requested 8.0 and needs
extraction/encoding/remux regression tests. Its separate Python-wheel x265 recipes
are outside this migration. Reference checkouts must remain read-only.

## Releases

Publish candidates as 8.0.0-rcN from n8.0-rcN tags. After qualification, rebuild
8.0.0 and release n8.0. Transfer the exact tested crate between CI jobs; reconstruct
publication inputs, restore Cargo.toml.orig, and require identical repackaging.
Trusted publishing requires separate authorization and registry configuration.
Download the exact published archive, compare its bytes and freshly test a consumer.
Preserve published tags and stop sequencing on validation failures.
