use ffmpeg_next as ffmpeg;
use std::ffi::{CStr, CString};
extern "C" {
    fn native_smoke(gpl: i32, kvazaar: i32, path: *const std::os::raw::c_char);
}
fn main() {
    let path = CString::new(
        std::env::temp_dir()
            .join(format!("ffmpeg-src-{}.mp4", std::process::id()))
            .to_str()
            .unwrap(),
    )
    .unwrap();
    unsafe {
        native_smoke(
            i32::from(std::env::var("EXPECT_GPL").as_deref() == Ok("1")),
            i32::from(std::env::var("EXPECT_KVAZAAR").as_deref() == Ok("1")),
            path.as_ptr(),
        );
    }
    ffmpeg::init().unwrap();
    unsafe {
        let version = CStr::from_ptr(ffmpeg::ffi::av_version_info())
            .to_str()
            .unwrap();
        assert_eq!(version, "8.0");
        assert_eq!(ffmpeg::ffi::avcodec_version(), (62 << 16) | (11 << 8) | 100);
        let license = CStr::from_ptr(ffmpeg::ffi::avcodec_license())
            .to_str()
            .unwrap();
        let config = CStr::from_ptr(ffmpeg::ffi::avcodec_configuration())
            .to_str()
            .unwrap();
        println!("{version}\n{license}\n{config}");
        assert!(!config.contains("--enable-nonfree"));
        for (actual, expected) in [
            (ffmpeg::ffi::avutil_version(), (60 << 16) | (8 << 8) | 100),
            (ffmpeg::ffi::avformat_version(), (62 << 16) | (3 << 8) | 100),
            #[cfg(feature = "filter")]
            (ffmpeg::ffi::avfilter_version(), (11 << 16) | (4 << 8) | 100),
            (ffmpeg::ffi::swscale_version(), (9 << 16) | (1 << 8) | 100),
        ] {
            assert_eq!(actual, expected);
        }
        for report in [
            ffmpeg::ffi::avutil_license(),
            ffmpeg::ffi::avformat_license(),
            #[cfg(feature = "filter")]
            ffmpeg::ffi::avfilter_license(),
            ffmpeg::ffi::swscale_license(),
        ] {
            assert_eq!(CStr::from_ptr(report).to_str().unwrap(), license);
        }
        let gpl = std::env::var("EXPECT_GPL").as_deref() == Ok("1");
        assert_eq!(config.contains("--enable-gpl"), gpl);
        #[cfg(feature = "filter")]
        assert_eq!(
            !ffmpeg::ffi::avfilter_get_by_name(CString::new("boxblur").unwrap().as_ptr()).is_null(),
            gpl
        );
        let version3 = std::env::var("EXPECT_VERSION3").as_deref() == Ok("1");
        assert_eq!(config.contains("--enable-version3"), version3);
        assert_eq!(license.contains("version 3"), version3);
        if !gpl {
            assert!(license.contains("LGPL"));
        }
    }
    assert!(ffmpeg::encoder::find(ffmpeg::codec::Id::PNG).is_some());
    let mut input = ffmpeg::util::frame::video::Video::new(ffmpeg::format::Pixel::RGB24, 8, 8);
    input.data_mut(0).fill(0);
    let mut scale = ffmpeg::software::scaling::Context::get(
        ffmpeg::format::Pixel::RGB24,
        8,
        8,
        ffmpeg::format::Pixel::RGBA,
        4,
        4,
        ffmpeg::software::scaling::Flags::POINT,
    )
    .unwrap();
    let mut output = ffmpeg::util::frame::video::Video::empty();
    scale.run(&input, &mut output).unwrap();
    for y in 0..4 {
        for x in 0..4 {
            assert_eq!(
                &output.data(0)[y * output.stride(0) + x * 4..][..4],
                &[0, 0, 0, 255]
            );
        }
    }
}
