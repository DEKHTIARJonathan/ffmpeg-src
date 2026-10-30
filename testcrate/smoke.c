/* Original synthetic fixtures: MIT, see the repository LICENSE.md. */
#include <assert.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <libavcodec/avcodec.h>
#include <libavformat/avformat.h>
#ifdef HAVE_AVFILTER
#include <libavfilter/avfilter.h>
#include <libavfilter/buffersrc.h>
#include <libavfilter/buffersink.h>
#endif
#include <libavutil/opt.h>
#include <libavutil/hwcontext.h>

static void check(int result) {
    if (result < 0) {
        char error[AV_ERROR_MAX_STRING_SIZE];
        av_strerror(result, error, sizeof(error));
        fprintf(stderr, "FFmpeg smoke failed: %s\n", error);
        abort();
    }
}

static void roundtrip(const char *name, enum AVPixelFormat format, const char *path) {
    const AVCodec *codec = avcodec_find_encoder_by_name(name);
    assert(codec);
    AVCodecContext *encoder = avcodec_alloc_context3(codec);
    encoder->width = encoder->height = 64;
    encoder->pix_fmt = format;
    encoder->time_base = (AVRational){1, 25};
    encoder->thread_count = 1;
    if (!strcmp(name, "mpeg4")) encoder->flags |= AV_CODEC_FLAG_GLOBAL_HEADER;
    if (!strcmp(name, "libkvazaar"))
        check(av_opt_set(encoder->priv_data, "kvazaar-params", "preset=ultrafast,threads=1", 0));
    check(avcodec_open2(encoder, codec, NULL));
    AVFrame *frame = av_frame_alloc();
    frame->width = encoder->width;
    frame->height = encoder->height;
    frame->format = format;
    check(av_frame_get_buffer(frame, 32));
    for (int y = 0; y < 64; y++)
        memset(frame->data[0] + y * frame->linesize[0], 64, format == AV_PIX_FMT_RGB24 ? 192 : 64);
    if (format == AV_PIX_FMT_YUV420P) {
        for (int y = 0; y < 32; y++) {
            memset(frame->data[1] + y * frame->linesize[1], 128, 32);
            memset(frame->data[2] + y * frame->linesize[2], 128, 32);
        }
    }
    frame->pts = 0;
    check(avcodec_send_frame(encoder, frame));
    check(avcodec_send_frame(encoder, NULL));
    AVPacket *packet = av_packet_alloc();
    check(avcodec_receive_packet(encoder, packet));
    const AVCodec *decoder_codec = avcodec_find_decoder(codec->id);
    AVCodecContext *decoder = avcodec_alloc_context3(decoder_codec);
    decoder->thread_count = 1;
    AVCodecParameters *parameters = avcodec_parameters_alloc();
    check(avcodec_parameters_from_context(parameters, encoder));
    check(avcodec_parameters_to_context(decoder, parameters));
    avcodec_parameters_free(&parameters);
    check(avcodec_open2(decoder, decoder_codec, NULL));
    check(avcodec_send_packet(decoder, packet));
    check(avcodec_send_packet(decoder, NULL));
    AVFrame *decoded = av_frame_alloc();
    check(avcodec_receive_frame(decoder, decoded));
    assert(decoded->width == 64 && decoded->height == 64);
    assert(decoded->data[0][0] >= 60 && decoded->data[0][0] <= 68);
    if (!strcmp(name, "mpeg4")) {
        AVFormatContext *mux = NULL;
        check(avformat_alloc_output_context2(&mux, NULL, "mp4", path));
        AVStream *stream = avformat_new_stream(mux, NULL);
        assert(stream);
        check(avcodec_parameters_from_context(stream->codecpar, encoder));
        stream->time_base = encoder->time_base;
        check(avio_open(&mux->pb, path, AVIO_FLAG_WRITE));
        check(avformat_write_header(mux, NULL));
        AVPacket *copy = av_packet_clone(packet);
        copy->duration = 1;
        av_packet_rescale_ts(copy, encoder->time_base, stream->time_base);
        copy->stream_index = stream->index;
        check(av_interleaved_write_frame(mux, copy));
        av_packet_free(&copy);
        check(av_write_trailer(mux));
        check(avio_closep(&mux->pb));
        avformat_free_context(mux);
        AVFormatContext *demux = NULL;
        check(avformat_open_input(&demux, path, NULL, NULL));
        check(avformat_find_stream_info(demux, NULL));
        assert(demux->nb_streams == 1);
        check(av_seek_frame(demux, 0, 0, AVSEEK_FLAG_BACKWARD));
        AVPacket *read = av_packet_alloc();
        check(av_read_frame(demux, read));
        assert(read->size == packet->size);
        assert(!memcmp(read->data, packet->data, packet->size));
        av_packet_free(&read);
        avformat_close_input(&demux);
        assert(remove(path) == 0);
    }
    av_frame_free(&decoded);
    avcodec_free_context(&decoder);
    av_packet_free(&packet);
    av_frame_free(&frame);
    avcodec_free_context(&encoder);
}

#ifdef HAVE_AVFILTER
static void blur(void) {
    AVFilterGraph *graph = avfilter_graph_alloc();
    AVFilterContext *source, *filter, *sink;
    char args[128];
    snprintf(args, sizeof(args), "video_size=8x8:pix_fmt=%d:time_base=1/25:pixel_aspect=1/1", AV_PIX_FMT_GRAY8);
    check(avfilter_graph_create_filter(&source, avfilter_get_by_name("buffer"), "src", args, NULL, graph));
    check(avfilter_graph_create_filter(&filter, avfilter_get_by_name("boxblur"), "blur", "luma_radius=1:luma_power=1:chroma_radius=0", NULL, graph));
    check(avfilter_graph_create_filter(&sink, avfilter_get_by_name("buffersink"), "sink", NULL, NULL, graph));
    check(avfilter_link(source, 0, filter, 0));
    check(avfilter_link(filter, 0, sink, 0));
    check(avfilter_graph_config(graph, NULL));
    AVFrame *frame = av_frame_alloc();
    frame->format = AV_PIX_FMT_GRAY8;
    frame->width = frame->height = 8;
    check(av_frame_get_buffer(frame, 32));
    for (int y = 0; y < 8; y++) memset(frame->data[0] + frame->linesize[0] * y, 0, 8);
    frame->data[0][3 * frame->linesize[0] + 3] = 255;
    check(av_buffersrc_add_frame(source, frame));
    check(av_buffersink_get_frame(sink, frame));
    assert(frame->data[0][0] == 0);
    int center = frame->data[0][3 * frame->linesize[0] + 3];
    assert(center >= 27 && center <= 29);
    av_frame_free(&frame);
    avfilter_graph_free(&graph);
}

#endif

void native_smoke(int gpl, int kvazaar, const char *path) {
    check(avformat_network_init());
    enum AVHWDeviceType type = AV_HWDEVICE_TYPE_NONE;
    while ((type = av_hwdevice_iterate_types(type)) != AV_HWDEVICE_TYPE_NONE)
        fprintf(stderr, "Compiled hardware interface: %s (execution not tested)\n", av_hwdevice_get_type_name(type));
    roundtrip("png", AV_PIX_FMT_RGB24, path);
    roundtrip("mpeg4", AV_PIX_FMT_YUV420P, path);
    if (!kvazaar) assert(!avcodec_find_encoder_by_name("libkvazaar"));
    if (kvazaar) roundtrip("libkvazaar", AV_PIX_FMT_YUV420P, path);
#ifdef HAVE_AVFILTER
    if (gpl) blur();
#else
    assert(!gpl);
#endif
    check(avformat_network_deinit());
}
