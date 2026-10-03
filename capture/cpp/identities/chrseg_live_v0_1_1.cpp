#define VERSION "0.1.1"

#include <gst/gst.h>
#include <glib.h>
#include <signal.h>
#include <cstring>
#include <cstdlib>
#include <cstdio>
#include <opencv2/imgproc.hpp>
#include <opencv2/highgui.hpp>

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
    int      median_L;
    int      median_A;
    int      median_B;
    cv::Mat  kernel;
    gboolean benchmark;
    gint64   frame_start;
    gint64   frame_times[30];
    int      frame_times_idx;
    gint64   frame_count;
} ChrSegContext;

static const ChrSegContext config_default = {
    .sensor_id        = 0,
    .framerate_num    = 21,
    .framerate_den    = 1,
    .tnr_mode         = 1,
    .tnr_strength     = 0.1,
    .tnr_strength_set = FALSE,
    .ee_mode          = 0,
    .exposuretime     = 2500000,
    .width            = 1280,
    .height           = 960,
    .delta            = 10,
    .first_frame      = TRUE,
    .median_L         = 0,
    .median_A         = 0,
    .median_B         = 0,
    .kernel           = cv::Mat(),
    .benchmark        = FALSE,
    .frame_start      = 0,
    .frame_times      = {},
    .frame_times_idx  = 0,
    .frame_count      = 0,
};

static GstElement *pipeline = NULL;
static GMainLoop *loop = NULL;
static volatile gboolean running = FALSE;

static int median_8u(const cv::Mat &channel) {
    int hist[256] = {0};
    for (int r = 0; r < channel.rows; r++) {
        const uchar *row = channel.ptr<uchar>(r);
        for (int c = 0; c < channel.cols; c++)
            hist[row[c]]++;
    }
    int total = channel.rows * channel.cols;
    int half = total / 2;
    int cum = 0;
    for (int i = 0; i < 256; i++) {
        cum += hist[i];
        if (cum >= half) return i;
    }
    return 255;
}

static void print_usage(const char *prog) {
    g_print("chrseg_live version %s\n", VERSION);
    g_print("Usage: %s\n"
            "       [--sensor-id <n>] [--framerate <num/den>]\n"
            "       [--tnr-mode <0|1|2>] [--tnr-strength <f>]\n"
            "       [--ee-mode <0|1|2>] [--exposuretime <ns>]\n"
            "       [--width <n>] [--delta <n>] [--benchmark]\n", prog);
}

static void stop_recording(void) {
    if (running && pipeline)
        gst_element_send_event(pipeline, gst_event_new_eos());
}

static void handle_sigint(int sig) {
    (void)sig;
    stop_recording();
}

static gboolean on_stdin_input(GIOChannel *channel, GIOCondition cond, gpointer data) {
    (void)channel;
    (void)cond;
    (void)data;
    stop_recording();
    return FALSE;
}

static gboolean bus_callback(GstBus *bus, GstMessage *msg, gpointer data) {
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

static void on_handoff(GstElement *identity, GstBuffer *buffer, gpointer data) {
    (void)identity;
    ChrSegContext *ctx = (ChrSegContext *)data;
    if (!buffer || !ctx) return;

    if (ctx->benchmark)
        ctx->frame_start = g_get_monotonic_time();

    int w = 4032, h = 3040;

    GstMapInfo map;
    if (!gst_buffer_map(buffer, &map, GST_MAP_READWRITE))
        return;

    cv::Mat nv12(h * 3 / 2, w, CV_8UC1, map.data);
    cv::Mat bgr(h, w, CV_8UC3);
    cv::cvtColor(nv12, bgr, cv::COLOR_YUV2BGR_NV12);

    cv::Mat lab;
    cv::cvtColor(bgr, lab, cv::COLOR_BGR2Lab);

    if (ctx->first_frame) {
        std::vector<cv::Mat> lab_channels(3);
        cv::split(lab, lab_channels);
        ctx->median_L = median_8u(lab_channels[0]);
        ctx->median_A = median_8u(lab_channels[1]);
        ctx->median_B = median_8u(lab_channels[2]);
        ctx->kernel = cv::getStructuringElement(cv::MORPH_ELLIPSE, cv::Size(5, 5));
        ctx->first_frame = FALSE;
    }

    int range = 255 * ctx->delta / 100;
    cv::Scalar low(
        ctx->median_L - range,
        ctx->median_A - range,
        ctx->median_B - range);
    cv::Scalar high(
        ctx->median_L + range,
        ctx->median_A + range,
        ctx->median_B + range);

    cv::Mat mask;
    cv::inRange(lab, low, high, mask);
    cv::bitwise_not(mask, mask);

    cv::morphologyEx(mask, mask, cv::MORPH_CLOSE, ctx->kernel);

    uchar *y = map.data;
    for (int i = 0; i < w * h; i++)
        y[i] = mask.data[i];

    uchar *uv = map.data + w * h;
    memset(uv, 128, w * h / 2);

    gst_buffer_unmap(buffer, &map);

    if (ctx->benchmark) {
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

int main(int argc, char *argv[]) {
    ChrSegContext ctx = config_default;

    for (int i = 1; i < argc; i++) {
        if (strcmp(argv[i], "--sensor-id") == 0) {
            if (++i >= argc) {
                g_printerr("ERROR: --sensor-id requires a value\n");
                return 1;
            }
            char *end;
            long val = strtol(argv[i], &end, 10);
            if (*end != '\0' || val < 0) {
                g_printerr("ERROR: invalid --sensor-id value: %s\n", argv[i]);
                return 1;
            }
            ctx.sensor_id = (int)val;
        } else if (strcmp(argv[i], "--framerate") == 0) {
            if (++i >= argc) {
                g_printerr("ERROR: --framerate requires a value (e.g. 21/1)\n");
                return 1;
            }
            if (sscanf(argv[i], "%d/%d", &ctx.framerate_num, &ctx.framerate_den) != 2
                || ctx.framerate_num <= 0 || ctx.framerate_den <= 0) {
                g_printerr("ERROR: invalid --framerate format: %s (expected num/den)\n", argv[i]);
                return 1;
            }
        } else if (strcmp(argv[i], "--tnr-mode") == 0) {
            if (++i >= argc) {
                g_printerr("ERROR: --tnr-mode requires a value (0, 1, or 2)\n");
                return 1;
            }
            char *end;
            long val = strtol(argv[i], &end, 10);
            if (*end != '\0' || val < 0 || val > 2) {
                g_printerr("ERROR: --tnr-mode must be 0, 1, or 2 (got %s)\n", argv[i]);
                return 1;
            }
            ctx.tnr_mode = (int)val;
        } else if (strcmp(argv[i], "--tnr-strength") == 0) {
            if (++i >= argc) {
                g_printerr("ERROR: --tnr-strength requires a value (0.0 – 1.0)\n");
                return 1;
            }
            char *end;
            double val = strtod(argv[i], &end);
            if (*end != '\0' || val < 0.0 || val > 1.0) {
                g_printerr("ERROR: --tnr-strength must be between 0.0 and 1.0 (got %s)\n", argv[i]);
                return 1;
            }
            ctx.tnr_strength = val;
            ctx.tnr_strength_set = TRUE;
        } else if (strcmp(argv[i], "--ee-mode") == 0) {
            if (++i >= argc) {
                g_printerr("ERROR: --ee-mode requires a value (0, 1, or 2)\n");
                return 1;
            }
            char *end;
            long val = strtol(argv[i], &end, 10);
            if (*end != '\0' || val < 0 || val > 2) {
                g_printerr("ERROR: --ee-mode must be 0, 1, or 2 (got %s)\n", argv[i]);
                return 1;
            }
            ctx.ee_mode = (int)val;
        } else if (strcmp(argv[i], "--exposuretime") == 0) {
            if (++i >= argc) {
                g_printerr("ERROR: --exposuretime requires a value (ns)\n");
                return 1;
            }
            char *end;
            long val = strtol(argv[i], &end, 10);
            if (*end != '\0' || val <= 0) {
                g_printerr("ERROR: invalid --exposuretime value: %s\n", argv[i]);
                return 1;
            }
            ctx.exposuretime = (int)val;
        } else if (strcmp(argv[i], "--width") == 0) {
            if (++i >= argc) {
                g_printerr("ERROR: --width requires a value\n");
                return 1;
            }
            char *end;
            long val = strtol(argv[i], &end, 10);
            if (*end != '\0' || val <= 0 || val % 4 != 0) {
                g_printerr("ERROR: --width must be > 0 and divisible by 4 (got %s)\n", argv[i]);
                return 1;
            }
            ctx.width = (int)val;
        } else if (strcmp(argv[i], "--delta") == 0) {
            if (++i >= argc) {
                g_printerr("ERROR: --delta requires a value (0 – 100)\n");
                return 1;
            }
            char *end;
            long val = strtol(argv[i], &end, 10);
            if (*end != '\0' || val < 0 || val > 100) {
                g_printerr("ERROR: --delta must be between 0 and 100 (got %s)\n", argv[i]);
                return 1;
            }
            ctx.delta = (int)val;
        } else if (strcmp(argv[i], "--benchmark") == 0) {
            ctx.benchmark = TRUE;
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
        "! video/x-raw(memory:NVMM),width=4032,height=3040,framerate=%d/%d,format=NV12 "
        "! nvvidconv bl-output=false "
        "! video/x-raw,format=NV12,width=4032,height=3040,framerate=%d/%d "
        "! identity name=proc "
        "! nvvidconv "
        "! video/x-raw(memory:NVMM),width=%d,height=%d "
        "! nvegltransform ! nveglglessink sync=false",
        ctx.sensor_id,
        ctx.exposuretime, ctx.exposuretime,
        ctx.tnr_mode, tnr_part,
        ctx.ee_mode,
        ctx.framerate_num, ctx.framerate_den,
        ctx.framerate_num, ctx.framerate_den,
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
    g_print("Display: %dx%d (4:3)\n", ctx.width, ctx.height);
    g_print("Processing: full resolution (4032x3040)\n");
    g_print("Sensor ID: %d\n", ctx.sensor_id);
    g_print("Framerate: %d/%d\n", ctx.framerate_num, ctx.framerate_den);
    g_print("TNR mode: %d\n", ctx.tnr_mode);
    if (ctx.tnr_mode > 0)
        g_print("TNR strength: %.1f\n", ctx.tnr_strength);
    g_print("EE mode: %d\n", ctx.ee_mode);
    g_print("Exposure time: %d ns\n", ctx.exposuretime);
    g_print("Delta: %d%%\n", ctx.delta);
    if (ctx.benchmark)
        g_print("Benchmarking enabled\n");
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

    g_source_remove(bus_watch_id);
    gst_element_set_state(pipeline, GST_STATE_NULL);
    gst_object_unref(pipeline);
    g_main_loop_unref(loop);

    return 0;
}
