#include <gst/gst.h>
#include <glib.h>
#include <signal.h>
#include <cstring>
#include <cstdlib>
#include <cstdio>
#include <opencv2/imgproc.hpp>

typedef struct {
    int     sensor_id;
    int     framerate_num;
    int     framerate_den;
    int     tnr_mode;
    double  tnr_strength;
    gboolean tnr_strength_set;
    int     ee_mode;
    int     exposuretime;
    int     width;
    int     height;
} Config;

static const Config config_default = {
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
};

static GstElement *pipeline = NULL;
static GMainLoop *loop = NULL;
static volatile gboolean running = FALSE;

static void print_usage(const char *prog) {
    g_print("Usage: %s\n"
            "       [--sensor-id <n>] [--framerate <num/den>]\n"
            "       [--tnr-mode <0|1|2>] [--tnr-strength <f>]\n"
            "       [--ee-mode <0|1|2>] [--exposuretime <ns>]\n"
            "       [--width <n>]\n", prog);
}

static void stop_recording(void) {
    if (running && pipeline) {
        gst_element_send_event(pipeline, gst_event_new_eos());
    }
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
    Config *cfg = (Config *)data;
    if (!buffer || !cfg) return;

    GstMapInfo map;
    if (gst_buffer_map(buffer, &map, GST_MAP_READWRITE)) {
        int w = cfg->width, h = cfg->height;
        cv::Mat y(h, w, CV_8UC1, map.data);
        cv::Sobel(y, y, CV_8U, 1, 0, 3);
        gst_buffer_unmap(buffer, &map);
    }
}

int main(int argc, char *argv[]) {
    Config cfg = config_default;

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
            cfg.sensor_id = (int)val;
        } else if (strcmp(argv[i], "--framerate") == 0) {
            if (++i >= argc) {
                g_printerr("ERROR: --framerate requires a value (e.g. 21/1)\n");
                return 1;
            }
            if (sscanf(argv[i], "%d/%d", &cfg.framerate_num, &cfg.framerate_den) != 2
                || cfg.framerate_num <= 0 || cfg.framerate_den <= 0) {
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
            cfg.tnr_mode = (int)val;
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
            cfg.tnr_strength = val;
            cfg.tnr_strength_set = TRUE;
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
            cfg.ee_mode = (int)val;
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
            cfg.exposuretime = (int)val;
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
            cfg.width = (int)val;
        } else if (strcmp(argv[i], "--help") == 0) {
            print_usage(argv[0]);
            return 0;
        } else {
            g_printerr("ERROR: unexpected argument: %s\n", argv[i]);
            print_usage(argv[0]);
            return 1;
        }
    }

    if (cfg.tnr_strength_set && cfg.tnr_mode == 0) {
        g_printerr("ERROR: --tnr-strength requires --tnr-mode > 0\n");
        return 1;
    }

    cfg.height = cfg.width * 3 / 4;

    gst_init(&argc, &argv);

    gchar *tnr_strength_part = (cfg.tnr_mode > 0)
        ? g_strdup_printf(" tnr-strength=%.1f", cfg.tnr_strength)
        : g_strdup("");

    GString *ps = g_string_new(NULL);

    g_string_append_printf(ps,
        "nvarguscamerasrc sensor-id=%d "
        "exposuretimerange=\"%d %d\" "
        "awblock=true aelock=true "
        "tnr-mode=%d%s ee-mode=%d saturation=1 "
        "! video/x-raw(memory:NVMM),width=4032,height=3040,framerate=%d/%d,format=NV12 "
        "! nvvidconv bl-output=false "
        "! video/x-raw,format=NV12,width=%d,height=%d,framerate=%d/%d "
        "! identity name=proc "
        "! nvvidconv "
        "! video/x-raw(memory:NVMM),width=%d,height=%d "
        "! nvegltransform ! nveglglessink sync=false",
        cfg.sensor_id,
        cfg.exposuretime, cfg.exposuretime,
        cfg.tnr_mode, tnr_strength_part,
        cfg.ee_mode,
        cfg.framerate_num, cfg.framerate_den,
        cfg.width, cfg.height,
        cfg.framerate_num, cfg.framerate_den,
        cfg.width, cfg.height);

    g_free(tnr_strength_part);

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

    g_signal_connect(proc, "handoff", G_CALLBACK(on_handoff), &cfg);
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

    g_print("Live preview %dx%d (4:3) with Sobel edge detection\n", cfg.width, cfg.height);
    g_print("Sensor ID: %d\n", cfg.sensor_id);
    g_print("Framerate: %d/%d\n", cfg.framerate_num, cfg.framerate_den);
    g_print("TNR mode: %d\n", cfg.tnr_mode);
    if (cfg.tnr_mode > 0)
        g_print("TNR strength: %.1f\n", cfg.tnr_strength);
    g_print("EE mode: %d\n", cfg.ee_mode);
    g_print("Exposure time: %d ns\n", cfg.exposuretime);
    g_print("Processing: Sobel edge detection (on Y plane via identity handoff)\n");
    g_print("Press ENTER or close the window to stop.\n");

    running = TRUE;
    gst_element_set_state(pipeline, GST_STATE_PLAYING);

    g_main_loop_run(loop);

    running = FALSE;
    signal(SIGINT, SIG_DFL);

    g_source_remove(bus_watch_id);
    gst_element_set_state(pipeline, GST_STATE_NULL);
    gst_object_unref(pipeline);
    g_main_loop_unref(loop);

    return 0;
}
