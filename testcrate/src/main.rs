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
        assert_eq!(version, std::env::var("EXPECT_FFMPEG_VERSION").unwrap());
        assert_eq!(
            ffmpeg::ffi::avcodec_version(),
            ((ffmpeg::ffi::LIBAVCODEC_VERSION_MAJOR << 16)
                | (ffmpeg::ffi::LIBAVCODEC_VERSION_MINOR << 8)
                | ffmpeg::ffi::LIBAVCODEC_VERSION_MICRO) as u32
        );
        let license = CStr::from_ptr(ffmpeg::ffi::avcodec_license())
            .to_str()
            .unwrap();
        let config = CStr::from_ptr(ffmpeg::ffi::avcodec_configuration())
            .to_str()
            .unwrap();
        println!("{version}\n{license}\n{config}");
        assert!(!config.contains("--enable-nonfree"));
        let cuda = std::env::var("EXPECT_CUDA").as_deref() == Ok("1");
        assert_eq!(config.contains("--enable-ffnvcodec"), cuda);
        assert_eq!(config.contains("--enable-nvdec"), cuda);
        assert!(config.contains("--disable-cuda-nvcc"));
        assert!(config.contains("--disable-cuda-llvm"));
        let mut device = ffmpeg::ffi::AVHWDeviceType::AV_HWDEVICE_TYPE_NONE;
        let mut has_cuda_device = false;
        loop {
            device = ffmpeg::ffi::av_hwdevice_iterate_types(device);
            if device == ffmpeg::ffi::AVHWDeviceType::AV_HWDEVICE_TYPE_NONE {
                break;
            }
            has_cuda_device |= device == ffmpeg::ffi::AVHWDeviceType::AV_HWDEVICE_TYPE_CUDA;
        }
        assert_eq!(has_cuda_device, cuda);
        for id in [
            ffmpeg::ffi::AVCodecID::AV_CODEC_ID_H264,
            ffmpeg::ffi::AVCodecID::AV_CODEC_ID_HEVC,
        ] {
            let decoder = ffmpeg::ffi::avcodec_find_decoder(id);
            assert!(!decoder.is_null());
            let mut has_nvdec = false;
            let mut index = 0;
            loop {
                let hardware = ffmpeg::ffi::avcodec_get_hw_config(decoder, index);
                if hardware.is_null() {
                    break;
                }
                let hardware = &*hardware;
                has_nvdec |= hardware.device_type
                    == ffmpeg::ffi::AVHWDeviceType::AV_HWDEVICE_TYPE_CUDA
                    && hardware.pix_fmt == ffmpeg::ffi::AVPixelFormat::AV_PIX_FMT_CUDA
                    && hardware.methods
                        & ffmpeg::ffi::AV_CODEC_HW_CONFIG_METHOD_HW_DEVICE_CTX as i32
                        != 0;
                index += 1;
            }
            assert_eq!(has_nvdec, cuda, "NVDEC interface for {id:?}");
        }
        assert!(ffmpeg::ffi::avcodec_find_encoder_by_name(
            CString::new("h264_nvenc").unwrap().as_ptr()
        )
        .is_null());
        println!("CUDA/NVDEC compiled: {cuda}; GPU execution is not required or tested");
        for (actual, expected) in [
            (
                ffmpeg::ffi::avutil_version(),
                ((ffmpeg::ffi::LIBAVUTIL_VERSION_MAJOR << 16)
                    | (ffmpeg::ffi::LIBAVUTIL_VERSION_MINOR << 8)
                    | ffmpeg::ffi::LIBAVUTIL_VERSION_MICRO) as u32,
            ),
            (
                ffmpeg::ffi::avformat_version(),
                ((ffmpeg::ffi::LIBAVFORMAT_VERSION_MAJOR << 16)
                    | (ffmpeg::ffi::LIBAVFORMAT_VERSION_MINOR << 8)
                    | ffmpeg::ffi::LIBAVFORMAT_VERSION_MICRO) as u32,
            ),
            #[cfg(feature = "filter")]
            (
                ffmpeg::ffi::avfilter_version(),
                ((ffmpeg::ffi::LIBAVFILTER_VERSION_MAJOR << 16)
                    | (ffmpeg::ffi::LIBAVFILTER_VERSION_MINOR << 8)
                    | ffmpeg::ffi::LIBAVFILTER_VERSION_MICRO) as u32,
            ),
            (
                ffmpeg::ffi::swscale_version(),
                ((ffmpeg::ffi::LIBSWSCALE_VERSION_MAJOR << 16)
                    | (ffmpeg::ffi::LIBSWSCALE_VERSION_MINOR << 8)
                    | ffmpeg::ffi::LIBSWSCALE_VERSION_MICRO) as u32,
            ),
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
