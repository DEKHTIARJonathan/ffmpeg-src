# Engineering rules

Keep FFmpeg and Kvazaar pristine at their reviewed submodule pins. Never modify
native sources or generated upstream files. Stage builds under OUT_DIR. Package
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
