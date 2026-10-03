#define VERSION "0.1.3"

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
#include <npp.h>

#define FULL_W 4032
#define FULL_H 3040

typedef struct {
    int      sensor_id;
    int      framerate_num;
    int      framerate_den;
    int      tnr_mode;
    double   tnr_strength;
    gboolean tnr_strength_set;
    int      ee_mode;
    int      exposuretime;
    int      width;
    int      height;
    int      delta;
    gboolean first_frame;
    int      median_B;
    int      median_G;
    int      median_R;
    gboolean debug;
    gboolean benchmark;
    gint64   frame_start;
    double   frame_times[30];
    int      frame_times_idx;
    gint64   frame_count;

    gboolean gpu_ok;
    Npp8u   *d_y, *d_uv, *d_bgr, *d_p0, *d_p1, *d_p2, *d_tmp, *d_mask;
    size_t   y_pitch, uv_pitch, bgr_pitch, c1_pitch;
} ChrSegContext;

static GstElement *pipeline = NULL;
static GMainLoop *loop = NULL;
static volatile gboolean running = FALSE;

static const char* npp_err_str(NppStatus s)
{
    switch (s) {
        case NPP_SUCCESS:                     return "SUCCESS";
        case NPP_ERROR:                       return "NPP_ERROR";
        case NPP_CUDA_KERNEL_EXECUTION_ERROR: return "CUDA_KERNEL_EXECUTION_ERROR";
        case NPP_MEMORY_ALLOCATION_ERR:       return "MEMORY_ALLOCATION_ERR";
        case NPP_NULL_POINTER_ERROR:          return "NULL_POINTER_ERROR";
        case NPP_SIZE_ERROR:                  return "SIZE_ERROR";
        case NPP_STEP_ERROR:                  return "STEP_ERROR";
        case NPP_NOT_SUFFICIENT_COMPUTE_CAPABILITY: return "INSUFFICIENT_COMPUTE";
        default: {
            static char buf[32];
            snprintf(buf, sizeof(buf), "UNKNOWN(%d)", (int)s);
            return buf;
        }
    }
}

static gboolean gpu_alloc(ChrSegContext *ctx)
{
    int w = FULL_W, h = FULL_H;
    ctx->y_pitch   = (size_t)w;
    ctx->uv_pitch  = (size_t)w;
    ctx->bgr_pitch = (size_t)w * 3;
    ctx->c1_pitch  = (size_t)w;
    if (cudaMalloc((void**)&ctx->d_y,    (size_t)w * h)     != cudaSuccess) return FALSE;
    if (cudaMalloc((void**)&ctx->d_uv,   (size_t)w * h / 2) != cudaSuccess) return FALSE;
    if (cudaMalloc((void**)&ctx->d_bgr,  (size_t)w * 3 * h) != cudaSuccess) return FALSE;
    if (cudaMalloc((void**)&ctx->d_p0,   (size_t)w * h)     != cudaSuccess) return FALSE;
    if (cudaMalloc((void**)&ctx->d_p1,   (size_t)w * h)     != cudaSuccess) return FALSE;
    if (cudaMalloc((void**)&ctx->d_p2,   (size_t)w * h)     != cudaSuccess) return FALSE;
    if (cudaMalloc((void**)&ctx->d_tmp,  (size_t)w * h)     != cudaSuccess) return FALSE;
    if (cudaMalloc((void**)&ctx->d_mask, (size_t)w * h)     != cudaSuccess) return FALSE;
    ctx->gpu_ok = TRUE;
    return TRUE;
}

static void gpu_free(ChrSegContext *ctx)
{
    if (!ctx->gpu_ok) return;
    cudaFree(ctx->d_y);
    cudaFree(ctx->d_uv);
    cudaFree(ctx->d_bgr);
    cudaFree(ctx->d_p0);
    cudaFree(ctx->d_p1);
    cudaFree(ctx->d_p2);
    cudaFree(ctx->d_tmp);
    cudaFree(ctx->d_mask);
    ctx->gpu_ok = FALSE;
}

static void print_usage(const char *prog)
{
    g_print("chrseg_live version %s\n", VERSION);
    g_print("Usage: %s\n"
            "       [--sensor-id <n>] [--framerate <num/den>]\n"
            "       [--tnr-mode <0|1|2>] [--tnr-strength <f>]\n"
            "       [--ee-mode <0|1|2>] [--exposuretime <ns>]\n"
            "       [--width <n>] [--delta <n>] [--benchmark] [--debug]\n", prog);
}

static void stop_recording(void)
{
    if (running && pipeline)
        gst_element_send_event(pipeline, gst_event_new_eos());
}

static void handle_sigint(int sig)
{
    (void)sig;
    stop_recording();
}

static gboolean on_stdin_input(GIOChannel *channel, GIOCondition cond, gpointer data)
{
    (void)channel;
    (void)cond;
    (void)data;
    stop_recording();
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
        if (debug)
            g_printerr("Debug info: %s\n", debug);
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
    ChrSegContext *ctx = (ChrSegContext *)data;
    if (!buffer || !ctx) return;

    if (ctx->benchmark)
        ctx->frame_start = g_get_monotonic_time();

    int w = FULL_W, h = FULL_H;

    GstMapInfo map;
    if (!gst_buffer_map(buffer, &map, GST_MAP_READWRITE))
        return;

    int y_stride  = w;
    int uv_stride = w;
    size_t uv_offset = (size_t)w * h;

    GstVideoMeta *vmeta = gst_buffer_get_video_meta(buffer);
    if (vmeta && vmeta->n_planes >= 2) {
        y_stride  = vmeta->stride[0];
        uv_stride = vmeta->stride[1];
        uv_offset = vmeta->offset[1];
    }

    if (!ctx->gpu_ok) {
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
        if (!gpu_alloc(ctx)) {
            g_printerr("WARNING: GPU buffer allocation failed\n");
            gst_buffer_unmap(buffer, &map);
            return;
        }
    }

    NppiSize roi = { w, h };

    cudaGetLastError();

    gboolean ok = TRUE;

    // 1. Upload NV12 to GPU
    cudaMemcpy2D(ctx->d_y, ctx->y_pitch,
                 map.data, (size_t)y_stride,
                 (size_t)w, (size_t)h, cudaMemcpyHostToDevice);
    cudaMemcpy2D(ctx->d_uv, ctx->uv_pitch,
                 map.data + uv_offset, (size_t)uv_stride,
                 (size_t)w, (size_t)(h / 2), cudaMemcpyHostToDevice);

    // 2. NV12 → BGR
    if (ok) {
        const Npp8u* src_nv12[2] = { ctx->d_y, ctx->d_uv };
        NppStatus s = nppiNV12ToBGR_8u_P2C3R(src_nv12, (int)ctx->y_pitch,
                                              ctx->d_bgr, (int)ctx->bgr_pitch, roi);
        if (s != NPP_SUCCESS) {
            g_printerr("ERROR: NPP NV12->BGR failed (status=%d %s)\n", (int)s, npp_err_str(s));
            ok = FALSE;
        }
    }

    // 3. Split BGR → 3 C1 planes
    if (ok) {
        Npp8u* planes[3] = { ctx->d_p0, ctx->d_p1, ctx->d_p2 };
        NppStatus s = nppiCopy_8u_C3P3R(ctx->d_bgr, (int)ctx->bgr_pitch,
                                         planes, (int)ctx->c1_pitch, roi);
        if (s != NPP_SUCCESS) {
            g_printerr("ERROR: NPP C3->P3 failed (status=%d %s)\n", (int)s, npp_err_str(s));
            ok = FALSE;
        }
    }

    // 4. First frame only: compute median per channel at full resolution
    if (ok && ctx->first_frame) {
        uint8_t *plane_cpu = new uint8_t[(size_t)w * h];
        auto median_plane = [&](Npp8u *d_plane, int &out) {
            cudaMemcpy2D(plane_cpu, (size_t)w,
                         d_plane, ctx->c1_pitch,
                         (size_t)w, (size_t)h, cudaMemcpyDeviceToHost);
            int hist[256] = {0};
            for (int i = 0; i < w * h; i++) hist[plane_cpu[i]]++;
            int half = w * h / 2, cum = 0;
            for (int i = 0; i < 256; i++) { cum += hist[i]; if (cum > half) { out = i; break; } }
        };
        median_plane(ctx->d_p0, ctx->median_B);
        median_plane(ctx->d_p1, ctx->median_G);
        median_plane(ctx->d_p2, ctx->median_R);
        delete[] plane_cpu;
        g_print("Median BGR (full-res): B=%d  G=%d  R=%d  (delta=%d%%)\n",
                ctx->median_B, ctx->median_G, ctx->median_R, ctx->delta);
        ctx->first_frame = FALSE;
    }

    // 5. Per-channel inRange + combine across channels
    if (ok) {
        int range = 255 * ctx->delta / 100;
        auto clamp = [&](int v) -> uint8_t {
            return (uint8_t)(v < 0 ? 0 : v > 255 ? 255 : v);
        };
        Npp8u lo[3] = { clamp(ctx->median_B - range),
                        clamp(ctx->median_G - range),
                        clamp(ctx->median_R - range) };
        Npp8u hi[3] = { clamp(ctx->median_B + range),
                        clamp(ctx->median_G + range),
                        clamp(ctx->median_R + range) };
        Npp8u *planes[3] = { ctx->d_p0, ctx->d_p1, ctx->d_p2 };

        for (int ch = 0; ch < 3 && ok; ch++) {
            NppStatus s = nppiCompareC_8u_C1R(planes[ch], (int)ctx->c1_pitch, lo[ch],
                                               ctx->d_tmp, (int)ctx->c1_pitch,
                                               roi, NPP_CMP_GREATER_EQ);
            if (s != NPP_SUCCESS) {
                g_printerr("ERROR: NPP compareC ch%d GE failed (status=%d %s)\n", ch, (int)s, npp_err_str(s));
                ok = FALSE; break;
            }
            s = nppiCompareC_8u_C1R(planes[ch], (int)ctx->c1_pitch, hi[ch],
                                     planes[ch], (int)ctx->c1_pitch,
                                     roi, NPP_CMP_LESS_EQ);
            if (s != NPP_SUCCESS) {
                g_printerr("ERROR: NPP compareC ch%d LE failed (status=%d %s)\n", ch, (int)s, npp_err_str(s));
                ok = FALSE; break;
            }
            s = nppiAnd_8u_C1R(ctx->d_tmp, (int)ctx->c1_pitch,
                               planes[ch], (int)ctx->c1_pitch,
                               planes[ch], (int)ctx->c1_pitch, roi);
            if (s != NPP_SUCCESS) {
                g_printerr("ERROR: NPP AND ch%d failed (status=%d %s)\n", ch, (int)s, npp_err_str(s));
                ok = FALSE; break;
            }
        }
        if (ok) {
            NppStatus s = nppiAnd_8u_C1R(ctx->d_p0, (int)ctx->c1_pitch,
                                          ctx->d_p1, (int)ctx->c1_pitch,
                                          ctx->d_mask, (int)ctx->c1_pitch, roi);
            if (s != NPP_SUCCESS) {
                g_printerr("ERROR: NPP AND C1 (B&G) failed (status=%d %s)\n", (int)s, npp_err_str(s));
                ok = FALSE;
            }
        }
        if (ok) {
            NppStatus s = nppiAnd_8u_C1R(ctx->d_mask, (int)ctx->c1_pitch,
                                          ctx->d_p2, (int)ctx->c1_pitch,
                                          ctx->d_mask, (int)ctx->c1_pitch, roi);
            if (s != NPP_SUCCESS) {
                g_printerr("ERROR: NPP AND C1 (BG&R) failed (status=%d %s)\n", (int)s, npp_err_str(s));
                ok = FALSE;
            }
        }
        if (ok) {
            NppStatus s = nppiNot_8u_C1R(ctx->d_mask, (int)ctx->c1_pitch,
                                          ctx->d_mask, (int)ctx->c1_pitch, roi);
            if (s != NPP_SUCCESS) {
                g_printerr("ERROR: NPP NOT failed (status=%d %s)\n", (int)s, npp_err_str(s));
                ok = FALSE;
            }
        }
    }

    // 6. Apply mask to Y on GPU → download modified Y → UV=128
    if (ok) {
        NppStatus s = nppiAnd_8u_C1R(ctx->d_y, (int)ctx->y_pitch,
                                      ctx->d_mask, (int)ctx->c1_pitch,
                                      ctx->d_y, (int)ctx->y_pitch,
                                      roi);
        if (s != NPP_SUCCESS) {
            g_printerr("ERROR: NPP mask apply failed (status=%d %s)\n", (int)s, npp_err_str(s));
            ok = FALSE;
        }
    }
    if (ok) {
        cudaMemcpy2D(map.data, (size_t)y_stride,
                     ctx->d_y, ctx->y_pitch,
                     (size_t)w, (size_t)h, cudaMemcpyDeviceToHost);
        memset(map.data + uv_offset, 128, (size_t)(uv_stride * h / 2));
    } else if (ctx->first_frame == FALSE) {
        g_printerr("WARNING: GPU processing skipped (ok=FALSE) at frame %ld\n",
                    (long)ctx->frame_count + 1);
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
            g_print("[chrseg] avg %.1f ms  (min %.1f, max %.1f) \u2013 %.1f fps\n",
                    avg, min, max, 1000.0 / avg);
        }
    }
}

int main(int argc, char *argv[])
{
    ChrSegContext ctx = {};

    ctx.sensor_id        = 0;
    ctx.framerate_num    = 21;
    ctx.framerate_den    = 1;
    ctx.tnr_mode         = 1;
    ctx.tnr_strength     = 0.1;
    ctx.tnr_strength_set = FALSE;
    ctx.ee_mode          = 0;
    ctx.exposuretime     = 2500000;
    ctx.width            = 1280;
    ctx.height           = 960;
    ctx.delta            = 10;
    ctx.first_frame      = TRUE;

    for (int i = 1; i < argc; i++) {
        if (strcmp(argv[i], "--sensor-id") == 0) {
            if (++i >= argc) { g_printerr("ERROR: --sensor-id requires a value\n"); return 1; }
            char *end; long val = strtol(argv[i], &end, 10);
            if (*end != '\0' || val < 0) { g_printerr("ERROR: invalid --sensor-id: %s\n", argv[i]); return 1; }
            ctx.sensor_id = (int)val;
        } else if (strcmp(argv[i], "--framerate") == 0) {
            if (++i >= argc) { g_printerr("ERROR: --framerate requires a value (e.g. 21/1)\n"); return 1; }
            if (sscanf(argv[i], "%d/%d", &ctx.framerate_num, &ctx.framerate_den) != 2
                || ctx.framerate_num <= 0 || ctx.framerate_den <= 0) {
                g_printerr("ERROR: invalid --framerate format: %s\n", argv[i]); return 1;
            }
        } else if (strcmp(argv[i], "--tnr-mode") == 0) {
            if (++i >= argc) { g_printerr("ERROR: --tnr-mode requires a value (0,1,2)\n"); return 1; }
            char *end; long val = strtol(argv[i], &end, 10);
            if (*end != '\0' || val < 0 || val > 2) { g_printerr("ERROR: --tnr-mode must be 0-2\n"); return 1; }
            ctx.tnr_mode = (int)val;
        } else if (strcmp(argv[i], "--tnr-strength") == 0) {
            if (++i >= argc) { g_printerr("ERROR: --tnr-strength requires a value\n"); return 1; }
            char *end; double val = strtod(argv[i], &end);
            if (*end != '\0' || val < 0.0 || val > 1.0) { g_printerr("ERROR: --tnr-strength 0.0-1.0\n"); return 1; }
            ctx.tnr_strength = val; ctx.tnr_strength_set = TRUE;
        } else if (strcmp(argv[i], "--ee-mode") == 0) {
            if (++i >= argc) { g_printerr("ERROR: --ee-mode requires a value (0,1,2)\n"); return 1; }
            char *end; long val = strtol(argv[i], &end, 10);
            if (*end != '\0' || val < 0 || val > 2) { g_printerr("ERROR: --ee-mode must be 0-2\n"); return 1; }
            ctx.ee_mode = (int)val;
        } else if (strcmp(argv[i], "--exposuretime") == 0) {
            if (++i >= argc) { g_printerr("ERROR: --exposuretime requires a value (ns)\n"); return 1; }
            char *end; long val = strtol(argv[i], &end, 10);
            if (*end != '\0' || val <= 0) { g_printerr("ERROR: invalid --exposuretime: %s\n", argv[i]); return 1; }
            ctx.exposuretime = (int)val;
        } else if (strcmp(argv[i], "--width") == 0) {
            if (++i >= argc) { g_printerr("ERROR: --width requires a value\n"); return 1; }
            char *end; long val = strtol(argv[i], &end, 10);
            if (*end != '\0' || val <= 0 || val % 4 != 0) { g_printerr("ERROR: --width must be >0 and divisible by 4\n"); return 1; }
            ctx.width = (int)val;
        } else if (strcmp(argv[i], "--delta") == 0) {
            if (++i >= argc) { g_printerr("ERROR: --delta requires a value (0-100)\n"); return 1; }
            char *end; long val = strtol(argv[i], &end, 10);
            if (*end != '\0' || val < 0 || val > 100) { g_printerr("ERROR: --delta must be 0-100\n"); return 1; }
            ctx.delta = (int)val;
        } else if (strcmp(argv[i], "--benchmark") == 0) {
            ctx.benchmark = TRUE;
        } else if (strcmp(argv[i], "--debug") == 0) {
            ctx.debug = TRUE;
        } else if (strcmp(argv[i], "--help") == 0) {
            print_usage(argv[0]);
            return 0;
        } else {
            g_printerr("ERROR: unexpected argument: %s\n", argv[i]);
            print_usage(argv[0]);
            return 1;
        }
    }

    if (ctx.tnr_strength_set && ctx.tnr_mode == 0) {
        g_printerr("ERROR: --tnr-strength requires --tnr-mode > 0\n");
        return 1;
    }

    ctx.height = ctx.width * 3 / 4;

    gst_init(&argc, &argv);

    gchar *tnr_part = (ctx.tnr_mode > 0)
        ? g_strdup_printf(" tnr-strength=%.1f", ctx.tnr_strength)
        : g_strdup("");

    GString *ps = g_string_new(NULL);
    g_string_append_printf(ps,
        "nvarguscamerasrc sensor-id=%d "
        "exposuretimerange=\"%d %d\" "
        "awblock=true aelock=true "
        "tnr-mode=%d%s ee-mode=%d saturation=1 "
        "! video/x-raw(memory:NVMM),width=%d,height=%d,framerate=%d/%d,format=NV12 "
        "! nvvidconv bl-output=false "
        "! video/x-raw,format=NV12,width=%d,height=%d,framerate=%d/%d "
        "! identity name=proc "
        "! nvvidconv "
        "! video/x-raw(memory:NVMM),width=%d,height=%d "
        "! nvegltransform ! nveglglessink sync=false",
        ctx.sensor_id,
        ctx.exposuretime, ctx.exposuretime,
        ctx.tnr_mode, tnr_part,
        ctx.ee_mode,
        FULL_W, FULL_H, ctx.framerate_num, ctx.framerate_den,
        FULL_W, FULL_H, ctx.framerate_num, ctx.framerate_den,
        ctx.width, ctx.height);

    g_free(tnr_part);

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

    g_print("Chromatic segmentation live preview (version %s)\n", VERSION);
    g_print("GPU processing: %dx%d (full camera resolution)\n", FULL_W, FULL_H);
    g_print("Display: %dx%d (4:3)\n", ctx.width, ctx.height);
    g_print("Sensor ID: %d\n", ctx.sensor_id);
    g_print("Framerate: %d/%d\n", ctx.framerate_num, ctx.framerate_den);
    g_print("TNR mode: %d\n", ctx.tnr_mode);
    if (ctx.tnr_mode > 0) g_print("TNR strength: %.1f\n", ctx.tnr_strength);
    g_print("EE mode: %d\n", ctx.ee_mode);
    g_print("Exposure time: %d ns\n", ctx.exposuretime);
    g_print("Delta: %d%%\n", ctx.delta);
    if (ctx.benchmark) g_print("Benchmarking enabled\n");
    if (ctx.debug) g_print("Debug mode enabled\n");
    g_print("Press ENTER or close the window to stop.\n");

    running = TRUE;
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
        g_print("\n[chrseg] FINAL  avg %.1f ms  (min %.1f, max %.1f) \u2013 "
                "%.1f fps  (%ld frames)\n",
                avg, min, max, 1000.0 / avg, (long)ctx.frame_count);
    }

    gpu_free(&ctx);

    g_source_remove(bus_watch_id);
    gst_element_set_state(pipeline, GST_STATE_NULL);
    gst_object_unref(pipeline);
    g_main_loop_unref(loop);

    return 0;
}
