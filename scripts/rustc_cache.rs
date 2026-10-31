//! Transport large Rust argument lists without changing compiler semantics.
use std::{env, fs, io::Write, path::Path, process::Command, time::SystemTime};

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let executable = env::current_exe()?;
    let compiler = executable.file_stem().unwrap() == "rustc";
    let args: Vec<_> = env::args().skip(1).collect();
    let rust = args
        .first()
        .is_some_and(|a| Path::new(a).file_stem().is_some_and(|s| s == "rustc"));
    if !compiler && !rust {
        let status = Command::new(env!("CACHE_EXECUTABLE"))
            .args(&args)
            .status()?;
        std::process::exit(status.code().unwrap_or(1));
    }
    let stamp = SystemTime::now()
        .duration_since(SystemTime::UNIX_EPOCH)?
        .as_nanos();
    let response = env::temp_dir().join(format!("ffmpeg-rust-{}-{stamp}.args", std::process::id()));
    let mut file = fs::OpenOptions::new()
        .write(true)
        .create_new(true)
        .open(&response)?;
    for arg in args {
        if arg.contains(['\n', '\r']) {
            return Err("newlines cannot be transported in rustc response files".into());
        }
        writeln!(file, "{arg}")?;
    }
    drop(file);
    let status = Command::new(env!("CACHE_PYTHON"))
        .arg(env!("CACHE_SCRIPT"))
        .arg(if compiler { "compiler" } else { "cache" })
        .arg(env!("CACHE_SCRIPT_SHA256"))
        .arg(&response)
        .status();
    fs::remove_file(response)?;
    std::process::exit(status?.code().unwrap_or(1));
}
