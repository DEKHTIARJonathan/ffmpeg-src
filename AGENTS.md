# Engineering rules

Keep FFmpeg, Kvazaar and nv-codec-headers pristine at reviewed submodule pins.
CUDA support must compile in Linux and Windows shared
and static CI consumers without a GPU, NVIDIA driver, or CUDA toolkit. Check
actual CUDA/NVDEC codec configurations and default absence; do not equate
interface enumeration with successful hardware execution. Never enable CUDA
kernel compilers or nonfree code implicitly.
Never modify native sources or generated upstream files. Stage builds under
OUT_DIR. Package
sources before compiling and enforce a strictly less than 10,000,000 byte crate.
Run prek and formatting before packaging. Test the actual extracted archive.

All project-controlled compilation requires sccache for Rust, target and host
native compilers, and dependency CMake launchers. Published consumers may supply
their own wrappers or build without a cache. Do not confuse SDK/Cargo output
caching with compiler-cache hits.

Only enable GPL through enable-gpl. Never enable nonfree or uncontrolled external
library autodetection. Preserve notices for all distributed sources.

Keep reference repositories read-only. Never push, publish, authenticate or
create remotes without authorization. Preserve published versions and tags.
Validate RCs before stable; verify tested and published archives byte for byte.
Do not add release controllers, catalogs or generated provenance inventories.

Use full-history CI checkouts (`fetch-depth: 0`), including native submodules.
Release verification must have upstream tags available without shallow-fetch
workarounds.
