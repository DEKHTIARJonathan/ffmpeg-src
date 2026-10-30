fn main() {
    println!("cargo:rerun-if-changed=smoke.c");
    let includes = if let Some(prefix) = std::env::var_os("FFMPEG_DIR") {
        vec![std::path::PathBuf::from(prefix).join("include")]
    } else {
        pkg_config::Config::new()
            .cargo_metadata(false)
            .probe("libavcodec")
            .unwrap()
            .include_paths
    };
    let mut build = cc::Build::new();
    if std::env::var_os("CARGO_FEATURE_FILTER").is_some() {
        build.define("HAVE_AVFILTER", None);
    }
    build
        .file("smoke.c")
        .includes(includes)
        .compile("native_smoke");
}
