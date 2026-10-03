#define VERSION "0.1.0"

// nvcc defines __noinline__ which conflicts with glib's g_macro__has_attribute
#ifdef __NVCC__
#ifdef __noinline__
#undef __noinline__
#endif
#endif

#include <gst/gst.h>
#include <gst/video/video.h>
#include <glib.h>
#include <signal.h>
#include <cstring>
#include <cstdlib>
#include <cstdio>
#include <cstdint>

#include <cuda_runtime.h>
#include "play_kernels.cuh"

#define FULL_W 4032
#define FULL_H 3040

typedef struct {
    gchar   *input_file;
    int      width;
    int      height;
    gboolean debug;
    gboolean benchmark;
    gint64   frame_start;
    double   frame_times[30];
    int      frame_times_idx;
    gint64   frame_count;

    gboolean gpu_ok;
    int      proc_w, proc_h;
    unsigned char *d_y, *d_uv;
    size_t   y_pitch, uv_pitch;
} PlayContext;

static GstElement *pipeline = NULL;
static GMainLoop *loop = NULL;
static volatile gboolean running = FALSE;

static gboolean gpu_prepare(PlayContext *ctx, int w, int h)
{
    if (ctx->gpu_ok && ctx->proc_w == w && ctx->proc_h == h)
        return TRUE;

    if (ctx->gpu_ok) {
        cudaFree(ctx->d_y);
        cudaFree(ctx->d_uv);
        ctx->gpu_ok = FALSE;
    }

    ctx->proc_w = w;
    ctx->proc_h = h;
    ctx->y_pitch  = (size_t)w;
    ctx->uv_pitch = (size_t)w;
    if (cudaMalloc((void**)&ctx->d_y,  (size_t)w * h)     != cudaSuccess) return FALSE;
    if (cudaMalloc((void**)&ctx->d_uv, (size_t)w * h / 2) != cudaSuccess) return FALSE;
    ctx->gpu_ok = TRUE;
    return TRUE;
}

static void gpu_free(PlayContext *ctx)
{
    if (!ctx->gpu_ok) return;
    cudaFree(ctx->d_y);
    cudaFree(ctx->d_uv);
    ctx->gpu_ok = FALSE;
    ctx->proc_w = 0;
    ctx->proc_h = 0;
}

static void print_usage(const char *prog)
{
    g_print("seg_play version %s\n", VERSION);
    g_print("Usage: %s --input <video-file> [--width <n>] [--benchmark] [--debug]\n\n"
            "Plays back segmented recordings (chrseg_live / bgseg_live): pixels with\n"
            "Y==0 are shown black, all other pixels keep their original colour.\n",
            prog);
}

static void stop_playback(void)
{
    if (running && pipeline)
        gst_element_send_event(pipeline, gst_event_new_eos());
}

static void handle_sigint(int sig)
{
    (void)sig;
    stop_playback();
}

static gboolean on_stdin_input(GIOChannel *channel, GIOCondition cond, gpointer data)
{
    (void)channel;
    (void)cond;
    (void)data;
    stop_playback();
    return FALSE;
}

static gboolean bus_callback(GstBus *bus, GstMessage *msg, gpointer data)
{
    (void)bus;
    (void)data;
    switch (GST_MESSAGE_TYPE(msg)) {
    case GST_MESSAGE_EOS:
        g_main_loop_quit(loop);
        break;
    case GST_MESSAGE_ERROR: {
        gchar *debug = NULL;
        GError *error = NULL;
        gst_message_parse_error(msg, &error, &debug);
        if (g_strcmp0(error->message, "Output window was closed") == 0) {
            g_main_loop_quit(loop);
        } else {
            g_printerr("ERROR from %s: %s\n",
                        GST_OBJECT_NAME(msg->src), error->message);
            if (debug)
                g_printerr("Debug info: %s\n", debug);
            g_main_loop_quit(loop);
        }
        g_error_free(error);
        g_free(debug);
        break;
    }
    case GST_MESSAGE_WARNING: {
        gchar *debug = NULL;
        GError *warning = NULL;
        gst_message_parse_warning(msg, &warning, &debug);
        g_printerr("WARNING from %s: %s\n",
                    GST_OBJECT_NAME(msg->src), warning->message);
        g_error_free(warning);
        g_free(debug);
        break;
    }
    default:
        break;
    }
    return TRUE;
}

static void on_handoff(GstElement *identity, GstBuffer *buffer, gpointer data)
{
    (void)identity;
    PlayContext *ctx = (PlayContext *)data;
    if (!buffer || !ctx) return;

    if (ctx->benchmark)
        ctx->frame_start = g_get_monotonic_time();

    int w = FULL_W, h = FULL_H;
    int y_stride  = w;
    int uv_stride = w;
    size_t uv_offset = (size_t)w * h;

    GstVideoMeta *vmeta = gst_buffer_get_video_meta(buffer);
    if (vmeta) {
        w = vmeta->width;
        h = vmeta->height;
        if (vmeta->n_planes >= 2) {
            y_stride  = vmeta->stride[0];
            uv_stride = vmeta->stride[1];
            uv_offset = vmeta->offset[1];
        }
    }

    GstMapInfo map;
    if (!gst_buffer_map(buffer, &map, GST_MAP_READWRITE))
        return;

    if (!ctx->gpu_ok || ctx->proc_w != w || ctx->proc_h != h) {
        int cuda_devices = 0;
        if (cudaGetDeviceCount(&cuda_devices) != cudaSuccess || cuda_devices == 0) {
            g_printerr("WARNING: no CUDA device available\n");
            gst_buffer_unmap(buffer, &map);
            return;
        }
        if (cudaSetDevice(0) != cudaSuccess) {
            g_printerr("WARNING: cudaSetDevice failed\n");
            gst_buffer_unmap(buffer, &map);
            return;
        }
        if (!gpu_prepare(ctx, w, h)) {
            g_printerr("WARNING: GPU buffer allocation failed\n");
            gst_buffer_unmap(buffer, &map);
            return;
        }
    }

    cudaGetLastError();

    gboolean ok = TRUE;

    // 1. Upload NV12 (Y + UV) to GPU
    if (cudaMemcpy2D(ctx->d_y, ctx->y_pitch,
                     map.data, (size_t)y_stride,
                     (size_t)w, (size_t)h, cudaMemcpyHostToDevice) != cudaSuccess)
        ok = FALSE;
    if (ok && cudaMemcpy2D(ctx->d_uv, ctx->uv_pitch,
                           map.data + uv_offset, (size_t)uv_stride,
                           (size_t)w, (size_t)(h / 2), cudaMemcpyHostToDevice) != cudaSuccess)
        ok = FALSE;

    // 2. Neutralize chroma of fully-background 2x2 blocks
    if (ok) {
        launch_black_bg(ctx->d_y, (int)ctx->y_pitch,
                        ctx->d_uv, (int)ctx->uv_pitch, w, h);
        cudaError_t e = cudaGetLastError();
        if (e != cudaSuccess) {
            g_printerr("ERROR: black_bg kernel failed: %s\n", cudaGetErrorString(e));
            ok = FALSE;
        }
    }

    // 3. Download modified UV back (Y is untouched by the kernel -> no copy needed)
    if (ok) {
        cudaMemcpy2D(map.data + uv_offset, (size_t)uv_stride,
                     ctx->d_uv, ctx->uv_pitch,
                     (size_t)w, (size_t)(h / 2), cudaMemcpyDeviceToHost);
    }

    gst_buffer_unmap(buffer, &map);

    if (ctx->benchmark) {
        cudaDeviceSynchronize();
        double ms = (g_get_monotonic_time() - ctx->frame_start) / 1000.0;
        int idx = ctx->frame_times_idx % 30;
        ctx->frame_times[idx] = ms;
        ctx->frame_times_idx++;
        ctx->frame_count++;

        if (ctx->frame_times_idx >= 30 && (ctx->frame_times_idx % 30 == 0)) {
            double sum = 0, min = ctx->frame_times[0], max = ctx->frame_times[0];
            for (int i = 0; i < 30; i++) {
                sum += ctx->frame_times[i];
                if (ctx->frame_times[i] < min) min = ctx->frame_times[i];
                if (ctx->frame_times[i] > max) max = ctx->frame_times[i];
            }
            double avg = sum / 30.0;
            g_print("[seg_play] avg %.1f ms  (min %.1f, max %.1f) – %.1f fps\n",
                    avg, min, max, 1000.0 / avg);
        }
    }
}

int main(int argc, char *argv[])
{
    PlayContext ctx = {};

    ctx.width      = 1280;
    ctx.height     = 960;

    for (int i = 1; i < argc; i++) {
        if (strcmp(argv[i], "--input") == 0) {
            if (++i >= argc) { g_printerr("ERROR: --input requires a file path\n"); return 1; }
            g_free(ctx.input_file);
            ctx.input_file = g_strdup(argv[i]);
        } else if (strcmp(argv[i], "--width") == 0) {
            if (++i >= argc) { g_printerr("ERROR: --width requires a value\n"); return 1; }
            char *end; long val = strtol(argv[i], &end, 10);
            if (*end != '\0' || val <= 0 || val % 4 != 0) { g_printerr("ERROR: --width must be >0 and divisible by 4\n"); return 1; }
            ctx.width = (int)val;
        } else if (strcmp(argv[i], "--benchmark") == 0) {
            ctx.benchmark = TRUE;
        } else if (strcmp(argv[i], "--debug") == 0) {
            ctx.debug = TRUE;
        } else if (strcmp(argv[i], "--help") == 0) {
            print_usage(argv[0]);
            return 0;
        } else if (argv[i][0] != '-') {
            // positional filename shortcut
            g_free(ctx.input_file);
            ctx.input_file = g_strdup(argv[i]);
        } else {
            g_printerr("ERROR: unexpected argument: %s\n", argv[i]);
            print_usage(argv[0]);
            return 1;
        }
    }

    if (!ctx.input_file) {
        g_printerr("ERROR: --input <video-file> is required\n");
        print_usage(argv[0]);
        return 1;
    }

    ctx.height = ctx.width * 3 / 4;

    gst_init(&argc, &argv);

    GString *ps = g_string_new(NULL);
    g_string_append_printf(ps,
        "filesrc location=\"%s\" "
        "! decodebin "
        "! nvvidconv bl-output=false "
        "! video/x-raw,format=NV12 "
        "! identity name=proc "
        "! nvvidconv "
        "! video/x-raw(memory:NVMM),width=%d,height=%d "
        "! nvegltransform ! nveglglessink sync=false",
        ctx.input_file, ctx.width, ctx.height);

    gchar *pipeline_str = ps->str;
    g_string_free(ps, FALSE);

    g_print("Pipeline string:\n%s\n\n", pipeline_str);

    GError *error = NULL;
    pipeline = gst_parse_launch(pipeline_str, &error);
    g_free(pipeline_str);

    if (!pipeline) {
        g_printerr("ERROR: Failed to create pipeline: %s\n",
                    error ? error->message : "unknown error");
        if (error) g_error_free(error);
        return 1;
    }

    GstElement *proc = gst_bin_get_by_name(GST_BIN(pipeline), "proc");
    if (!proc) {
        g_printerr("ERROR: Failed to get identity element from pipeline\n");
        gst_object_unref(pipeline);
        return 1;
    }

    g_signal_connect(proc, "handoff", G_CALLBACK(on_handoff), &ctx);
    g_object_set(G_OBJECT(proc), "signal-handoffs", TRUE, NULL);
    gst_object_unref(proc);

    GstBus *bus = gst_pipeline_get_bus(GST_PIPELINE(pipeline));
    guint bus_watch_id = gst_bus_add_watch(bus, bus_callback, NULL);
    gst_object_unref(bus);

    GIOChannel *stdin_ch = g_io_channel_unix_new(STDIN_FILENO);
    g_io_add_watch(stdin_ch, G_IO_IN, on_stdin_input, NULL);
    g_io_channel_unref(stdin_ch);

    signal(SIGINT, handle_sigint);

    loop = g_main_loop_new(NULL, FALSE);

    g_print("seg_play (version %s)\n", VERSION);
    g_print("Input: %s\n", ctx.input_file);
    g_print("Display: %dx%d (4:3)\n", ctx.width, ctx.height);
    g_print("Rendering: Y==0 -> black, Y!=0 -> original colour\n");
    if (ctx.benchmark) g_print("Benchmarking enabled\n");
    if (ctx.debug) g_print("Debug mode enabled\n");
    g_print("Press ENTER or close the window to stop.\n");

    running = TRUE;
    gst_element_set_state(pipeline, GST_STATE_PAUSED);
    {
        GstState s = GST_STATE_VOID_PENDING;
        if (gst_element_get_state(pipeline, &s, NULL, 10 * GST_SECOND) == GST_STATE_CHANGE_FAILURE)
            g_printerr("WARNING: pipeline failed to reach PAUSED\n");
    }
    gst_element_set_state(pipeline, GST_STATE_PLAYING);

    g_main_loop_run(loop);

    running = FALSE;
    signal(SIGINT, SIG_DFL);

    if (ctx.benchmark && ctx.frame_count > 0) {
        double sum = 0, min = ctx.frame_times[0], max = ctx.frame_times[0];
        int n = ctx.frame_times_idx < 30 ? ctx.frame_times_idx : 30;
        for (int i = 0; i < n; i++) {
            sum += ctx.frame_times[i];
            if (ctx.frame_times[i] < min) min = ctx.frame_times[i];
            if (ctx.frame_times[i] > max) max = ctx.frame_times[i];
        }
        double avg = sum / n;
        g_print("\n[seg_play] FINAL  avg %.1f ms  (min %.1f, max %.1f) – "
                "%.1f fps  (%ld frames)\n",
                avg, min, max, 1000.0 / avg, (long)ctx.frame_count);
    }

    gpu_free(&ctx);
    g_free(ctx.input_file);

    g_source_remove(bus_watch_id);
    gst_element_set_state(pipeline, GST_STATE_NULL);
    gst_object_unref(pipeline);
    g_main_loop_unref(loop);

    return 0;
}