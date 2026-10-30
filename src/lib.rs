//! Native SDK paths. Prepare this crate before launching a binding consumer's Cargo build.
use std::path::{Path, PathBuf};

/// An SDK owned by this Cargo build's OUT_DIR. Do not persist paths beyond its lifetime.
pub struct Artifacts;

pub fn artifacts() -> Artifacts {
    Artifacts
}

impl Artifacts {
    pub fn prefix(&self) -> &'static Path {
        Path::new(env!("FFMPEG_SRC_PREFIX"))
    }
    pub fn include_dir(&self) -> PathBuf {
        self.prefix().join("include")
    }
    pub fn lib_dir(&self) -> PathBuf {
        self.prefix().join("lib")
    }
    pub fn bin_dir(&self) -> PathBuf {
        self.prefix().join("bin")
    }
    pub fn pkg_config_dir(&self) -> PathBuf {
        self.lib_dir().join("pkgconfig")
    }
    /// Runtime library names, including ABI symlinks, for consumer-owned staging.
    pub fn runtime_files(&self) -> std::io::Result<Vec<PathBuf>> {
        let mut files = Vec::new();
        for directory in [self.lib_dir(), self.bin_dir()] {
            if !directory.exists() {
                continue;
            }
            for entry in std::fs::read_dir(directory)? {
                let path = entry?.path();
                let name = path.file_name().unwrap().to_string_lossy();
                if name.ends_with(".dll")
                    || name.ends_with(".dylib")
                    || name.ends_with(".so")
                    || name.contains(".so.")
                {
                    files.push(path);
                }
            }
        }
        files.sort();
        Ok(files)
    }
    pub fn license_dir(&self) -> PathBuf {
        self.prefix().join("share/licenses")
    }
}
