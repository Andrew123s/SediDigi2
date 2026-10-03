#ifndef PLAY_KERNELS_CUH
#define PLAY_KERNELS_CUH

#include <cuda_runtime.h>

// NV12 block-chroma masking for chrseg recordings.
//
// In recorded chrseg AVI files the background pixels carry Y == 0 (masked out)
// while the shared 2x2-block chroma (UV) is preserved. When such a frame is
// displayed, the YUV->RGB matrix turns the leftover chroma into a visible
// "chroma ghost" (deep blue for the bluish background).
//
// This kernel sets the shared UV sample to neutral gray (128,128) wherever the
// whole 2x2 luma block is background (all four luma bytes <= T), so the sink
// renders pure black there. Mixed blocks (containing at least one object pixel)
// keep their original chroma -> object colours are preserved; only the 2x2
// border crossing an object edge can show a faint colour fringe.
//
// T = 8 tolerates small JPEG round-trip noise in the otherwise-zero luma.

#define PLAY_TX 16
#define PLAY_TY 16
#define PLAY_BG_T 8

__global__ void kernel_black_bg(const unsigned char *d_y, int y_pitch,
                                unsigned char *d_uv, int uv_pitch,
                                int W, int H) {
    int cx = blockIdx.x * blockDim.x + threadIdx.x;   // chroma column [0, W/2)
    int cy = blockIdx.y * blockDim.y + threadIdx.y;   // chroma row    [0, H/2)
    int cw = W / 2, ch = H / 2;
    if (cx >= cw || cy >= ch) return;

    int x0 = cx * 2, y0 = cy * 2;
    const unsigned char *l = d_y + y0 * y_pitch + x0;
    unsigned char a = l[0];
    unsigned char b = l[1];
    unsigned char c = l[y_pitch];
    unsigned char d = l[y_pitch + 1];

    if (a <= PLAY_BG_T && b <= PLAY_BG_T && c <= PLAY_BG_T && d <= PLAY_BG_T) {
        unsigned char *uv = d_uv + cy * uv_pitch + cx * 2;
        uv[0] = 128;
        uv[1] = 128;
    }
}

static void launch_black_bg(const unsigned char *d_y, int y_pitch,
                            unsigned char *d_uv, int uv_pitch,
                            int W, int H, cudaStream_t stream = 0) {
    dim3 block(PLAY_TX, PLAY_TY);
    dim3 grid((W / 2 + PLAY_TX - 1) / PLAY_TX, (H / 2 + PLAY_TY - 1) / PLAY_TY);
    kernel_black_bg<<<grid, block, 0, stream>>>(d_y, y_pitch, d_uv, uv_pitch, W, H);
}

#endif