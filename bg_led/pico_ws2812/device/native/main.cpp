// Native Pico 2 W (RP2350) panel server for WS2812 5x5/8x8 matrices.
//
// Replaces the MicroPython panel_server.py with a deterministic PIO + DMA
// implementation. The USB serial protocol is identical, so the host clients
// (pico_link.py, blue1_perma.py, blue_dyn.py) work unchanged.

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>
#include <ctype.h>

#include "pico/stdlib.h"
#include "hardware/clocks.h"
#include "hardware/dma.h"
#include "hardware/pio.h"

#include "ws2812.pio.h"

#define WS2812_PIN 0          // GPIO 0, as in the MicroPython variant
#define NUM_LEDS 25           // 25 for 5x5 panel, 64 for 8x8 panel
#define DEFAULT_BRIGHTNESS 50
#define PROTOCOL_VERSION 1
#define WS2812_FREQ 8000000U
#define RESET_GAP_US 300      // WS2812 reset pulse (>280 us)

static PIO pio = pio0;
static uint sm = 0;
static int dma_ch;
static uint32_t color_word;

static uint8_t hex_byte(const char *p) {
    uint8_t v = 0;
    for (int i = 0; i < 2; i++) {
        char c = p[i];
        v <<= 4;
        if (c >= '0' && c <= '9') v |= (uint8_t)(c - '0');
        else if (c >= 'a' && c <= 'f') v |= (uint8_t)(c - 'a' + 10);
        else v |= (uint8_t)(c - 'A' + 10);
    }
    return v;
}

static bool hex_valid(const char *hex) {
    for (int i = 0; i < 6; i++) {
        char c = hex[i];
        if (!((c >= '0' && c <= '9') || (c >= 'a' && c <= 'f') || (c >= 'A' && c <= 'F')))
            return false;
    }
    return true;
}

static void show_frame(void) {
    dma_channel_wait_for_finish_blocking(dma_ch);
    while (pio_sm_get_tx_fifo_level(pio, sm) > 0) {
        tight_loop_contents();
    }
    sleep_us(RESET_GAP_US);   // low line long enough for the WS2812 reset

    dma_channel_config cfg = dma_channel_get_default_config(dma_ch);
    channel_config_set_transfer_data_size(&cfg, DMA_SIZE_32);
    channel_config_set_read_increment(&cfg, false);   // repeat the same color word
    channel_config_set_write_increment(&cfg, false);  // write to the PIO TX FIFO
    channel_config_set_dreq(&cfg, pio_get_dreq(pio, sm, true));
    dma_channel_configure(dma_ch, &cfg, &pio->txf[sm], &color_word, NUM_LEDS, true);
}

static void set_panel(uint8_t r, uint8_t g, uint8_t b, int brightness) {
    double scale = brightness / 100.0;
    uint32_t w = ((uint32_t)(uint8_t)(g * scale) << 24)
               | ((uint32_t)(uint8_t)(r * scale) << 16)
               | ((uint32_t)(uint8_t)(b * scale) << 8);
    color_word = w;
    show_frame();
}

static void respond(const char *msg) {
    printf("%s\n", msg);
    fflush(stdout);
}

static void parse_line(const char *line) {
    // Tokenize like Python's line.split(): split on any whitespace.
    char tokens[4][32];
    int n = 0;
    const char *s = line;
    while (*s && n < 4) {
        while (*s && isspace((unsigned char)*s)) s++;
        if (!*s) break;
        int len = 0;
        while (*s && !isspace((unsigned char)*s) && len < 31) {
            tokens[n][len++] = *s++;
        }
        tokens[n][len] = '\0';
        n++;
    }
    if (n == 0) return;                          // empty line: no response (as MicroPython)

    if (strcasecmp(tokens[0], "SET") == 0) {
        if (n < 2) { respond("ERR unknown command"); return; }
        const char *hex = tokens[1];
        if (strlen(hex) != 6 || !hex_valid(hex)) {
            respond("ERR invalid color");
            return;
        }
        int brightness = DEFAULT_BRIGHTNESS;
        if (n >= 3) {
            char *end = NULL;
            long v = strtol(tokens[2], &end, 10);
            if (!end || *end != '\0') {
                respond("ERR invalid brightness");
                return;
            }
            brightness = (int)v;
            if (brightness < 0 || brightness > 100) {
                respond("ERR brightness must be 0-100");
                return;
            }
        }
        uint8_t r = hex_byte(hex), g = hex_byte(hex + 2), b = hex_byte(hex + 4);
        set_panel(r, g, b, brightness);
        respond("OK");
        return;
    }

    if (strcasecmp(tokens[0], "OFF") == 0) {
        set_panel(0, 0, 0, 100);
        respond("OK");
        return;
    }

    if (strcasecmp(tokens[0], "PING") == 0) {
        respond("PONG");
        return;
    }

    if (strcasecmp(tokens[0], "VERSION") == 0) {
        char buf[16];
        snprintf(buf, sizeof(buf), "VERSION %d", PROTOCOL_VERSION);
        respond(buf);
        return;
    }

    respond("ERR unknown command");
}

int main(void) {
    stdio_init_all();

    uint offset = pio_add_program(pio, &ws2812_program);
    pio_gpio_init(pio, WS2812_PIN);
    pio_sm_config cfg = ws2812_program_get_default_config(offset);
    sm_config_set_sideset_pins(&cfg, WS2812_PIN);
    sm_config_set_out_shift(&cfg, false, true, 24);   // shift left, autopull 24-bit
    float div = (float)clock_get_hz(clk_sys) / (float)WS2812_FREQ;
    sm_config_set_clkdiv(&cfg, div);
    pio_sm_set_consecutive_pindirs(pio, sm, WS2812_PIN, 1, true);
    pio_sm_init(pio, sm, offset, &cfg);
    pio_sm_set_enabled(pio, sm, true);

    dma_ch = dma_claim_unused_channel(true);
    dma_channel_config dc = dma_channel_get_default_config(dma_ch);
    channel_config_set_transfer_data_size(&dc, DMA_SIZE_32);
    channel_config_set_read_increment(&dc, false);
    channel_config_set_write_increment(&dc, false);
    channel_config_set_dreq(&dc, pio_get_dreq(pio, sm, true));
    dma_channel_configure(dma_ch, &dc, &pio->txf[sm], &color_word, NUM_LEDS, false);

    char line[80];
    int len = 0;
    while (true) {
        int c = getchar_timeout_us(0);
        if (c < 0) {
            tight_loop_contents();
            continue;
        }
        if (c == '\n') {
            line[len] = '\0';
            parse_line(line);
            len = 0;
        } else if (c == '\r') {
            // ignore CR; lines end on '\n' (trailing \r is tolerated)
        } else if (len < (int)sizeof(line) - 1) {
            line[len++] = (char)c;
        }
    }
}