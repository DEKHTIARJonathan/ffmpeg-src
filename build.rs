use std::{env, path::PathBuf, process::Command};

fn main() {
    let root = PathBuf::from(env::var_os("CARGO_MANIFEST_DIR").unwrap());
    let out = PathBuf::from(env::var_os("OUT_DIR").unwrap());
    for path in [
        "scripts/native.py",
        "native",
        "ffmpeg",
        "kvazaar",
        "nv-codec-headers",
    ] {
        println!("cargo:rerun-if-changed={path}");
    }
    for key in [
        "CC",
        "CXX",
        "HOST_CC",
        "CFLAGS",
        "CXXFLAGS",
        "LDFLAGS",
        "RUSTC_WRAPPER",
        "SDKROOT",
        "MACOSX_DEPLOYMENT_TARGET",
        "CMAKE_GENERATOR",
        "PKG_CONFIG_PATH",
        "PKG_CONFIG_LIBDIR",
        "PYTHON",
        "FFMPEG_SRC_MSYS_BIN",
        "FFMPEG_SRC_REQUIRE_SCCACHE",
    ] {
        println!("cargo:rerun-if-env-changed={key}");
    }
    let status = Command::new(env::var_os("PYTHON").unwrap_or_else(|| "python3".into()))
        .arg(root.join("scripts/native.py"))
        .arg(&root)
        .arg(&out)
        .status()
        .expect("FFmpeg SDK builds require Python 3.11 or newer");
    assert!(
        status.success(),
        "FFmpeg SDK build failed; inspect native tool output"
    );
    let prefix = out.join("sdk");
    println!("cargo:root={}", prefix.display());
    println!("cargo:include={}", prefix.join("include").display());
    println!("cargo:libdir={}", prefix.join("lib").display());
    println!("cargo:rustc-env=FFMPEG_SRC_PREFIX={}", prefix.display());
}
