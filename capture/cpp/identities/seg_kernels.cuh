#ifndef SEG_KERNELS_CUH
#define SEG_KERNELS_CUH

#include <cuda_runtime.h>
#include <math.h>

// BGR→Lab (OpenCV-compatible: L=[0,255], a,b=[0,255] centered at 128)
// Threshold a single Lab channel: d_out = (d_in[ch] in [lo,hi]) ? 0xFF : 0x00
// 3x3 Erosion/Dilation on C1 uint8 mask
// AND/NOT masks, apply mask to Y

#define SEG_TX 16
#define SEG_TY 16

// ---- Device functions ----

__device__ __forceinline__ float seg_srgb_to_linear(unsigned char v) {
    float f = v / 255.0f;
    return (f <= 0.04045f) ? f / 12.92f : powf((f + 0.055f) / 1.055f, 2.4f);
}

__device__ __forceinline__ float seg_lab_f(float t) {
    const float delta3 = 0.0088564517f; // (6/29)^3
    return (t > delta3) ? cbrtf(t) : t / 0.12841855f + 0.13793103f;
    // 0.12841855 = 3*(6/29)^2,  0.13793103 = 4/29
}

// ---- Kernels ----

__global__ void kernel_bgr2lab(const unsigned char *d_bgr, int bgr_pitch,
                               unsigned char *d_lab,  int lab_pitch,
                               int W, int H) {
    int x = blockIdx.x * blockDim.x + threadIdx.x;
    int y = blockIdx.y * blockDim.y + threadIdx.y;
    if (x >= W || y >= H) return;

    const unsigned char *row_bgr = d_bgr + y * bgr_pitch;
    unsigned char *row_lab = d_lab + y * lab_pitch;

    float B = seg_srgb_to_linear(row_bgr[x * 3 + 0]);
    float G = seg_srgb_to_linear(row_bgr[x * 3 + 1]);
    float R = seg_srgb_to_linear(row_bgr[x * 3 + 2]);

    float X = 0.4124564f * R + 0.3575761f * G + 0.1804375f * B;
    float Y = 0.2126729f * R + 0.7151522f * G + 0.0721750f * B;
    float Z = 0.0193339f * R + 0.1191920f * G + 0.9503041f * B;

    float fX = seg_lab_f(X / 0.95047f);
    float fY = seg_lab_f(Y);
    float fZ = seg_lab_f(Z / 1.08883f);

    float L = 116.0f * fY - 16.0f;
    float a = 500.0f * (fX - fY);
    float b = 200.0f * (fY - fZ);

    int L8 = __float2int_rd(L * 2.55f);          // L*255/100
    int a8 = __float2int_rd(a + 128.0f);
    int b8 = __float2int_rd(b + 128.0f);

    row_lab[x * 3 + 0] = (unsigned char)(L8 < 0 ? 0 : L8 > 255 ? 255 : L8);
    row_lab[x * 3 + 1] = (unsigned char)(a8 < 0 ? 0 : a8 > 255 ? 255 : a8);
    row_lab[x * 3 + 2] = (unsigned char)(b8 < 0 ? 0 : b8 > 255 ? 255 : b8);
}

__global__ void kernel_threshold_channel(const unsigned char *d_in, int in_pitch,
                                         unsigned char *d_out, int out_pitch,
                                         int W, int H, int channel,
                                         unsigned char lo, unsigned char hi) {
    int x = blockIdx.x * blockDim.x + threadIdx.x;
    int y = blockIdx.y * blockDim.y + threadIdx.y;
    if (x >= W || y >= H) return;

    unsigned char v = d_in[y * in_pitch + x * 3 + channel];
    d_out[y * out_pitch + x] = (v >= lo && v <= hi) ? 0xFF : 0x00;
}

// Combined threshold: checks both a (ch1) and b (ch2) channels of Lab image
__global__ void kernel_threshold_ab(const unsigned char *d_in, int in_pitch,
                                    unsigned char *d_out, int out_pitch,
                                    int W, int H,
                                    unsigned char a_lo, unsigned char a_hi,
                                    unsigned char b_lo, unsigned char b_hi) {
    int x = blockIdx.x * blockDim.x + threadIdx.x;
    int y = blockIdx.y * blockDim.y + threadIdx.y;
    if (x >= W || y >= H) return;

    const unsigned char *row = d_in + y * in_pitch + x * 3;
    unsigned char a = row[1];
    unsigned char b = row[2];
    d_out[y * out_pitch + x] = (a >= a_lo && a <= a_hi && b >= b_lo && b <= b_hi) ? 0xFF : 0x00;
}

// Combined threshold on all three Lab channels: L (ch0), a (ch1), b (ch2)
__global__ void kernel_threshold_lab(const unsigned char *d_in, int in_pitch,
                                     unsigned char *d_out, int out_pitch,
                                     int W, int H,
                                     unsigned char l_lo, unsigned char l_hi,
                                     unsigned char a_lo, unsigned char a_hi,
                                     unsigned char b_lo, unsigned char b_hi) {
    int x = blockIdx.x * blockDim.x + threadIdx.x;
    int y = blockIdx.y * blockDim.y + threadIdx.y;
    if (x >= W || y >= H) return;

    const unsigned char *row = d_in + y * in_pitch + x * 3;
    unsigned char L = row[0];
    unsigned char a = row[1];
    unsigned char b = row[2];
    d_out[y * out_pitch + x] = (L >= l_lo && L <= l_hi &&
                                a >= a_lo && a <= a_hi &&
                                b >= b_lo && b <= b_hi) ? 0xFF : 0x00;
}

// Background-subtraction mask (Lab): object where any channel deviates from
// the frozen background by more than t (byte domain).
__global__ void kernel_bgdiff_lab(const unsigned char *d_in, int in_pitch,
                                  const unsigned char *d_bg, int bg_pitch,
                                  unsigned char *d_out, int out_pitch,
                                  int W, int H, unsigned char t) {
    int x = blockIdx.x * blockDim.x + threadIdx.x;
    int y = blockIdx.y * blockDim.y + threadIdx.y;
    if (x >= W || y >= H) return;

    const unsigned char *row = d_in + y * in_pitch + x * 3;
    const unsigned char *bg  = d_bg + y * bg_pitch + x * 3;

    int dL = row[0] - bg[0]; if (dL < 0) dL = -dL;
    int da = row[1] - bg[1]; if (da < 0) da = -da;
    int db = row[2] - bg[2]; if (db < 0) db = -db;

    d_out[y * out_pitch + x] = (dL > t || da > t || db > t) ? 0xFF : 0x00;
}

__global__ void kernel_erode3x3(const unsigned char *d_in, int in_pitch,
                                unsigned char *d_out, int out_pitch,
                                int W, int H) {
    int x = blockIdx.x * blockDim.x + threadIdx.x;
    int y = blockIdx.y * blockDim.y + threadIdx.y;
    if (x >= W || y >= H) return;

    unsigned char mn = 255;
    for (int dy = -1; dy <= 1; dy++) {
        for (int dx = -1; dx <= 1; dx++) {
            int nx = x + dx, ny = y + dy;
            if (nx >= 0 && nx < W && ny >= 0 && ny < H) {
                unsigned char v = d_in[ny * in_pitch + nx];
                if (v < mn) mn = v;
            }
        }
    }
    d_out[y * out_pitch + x] = mn;
}

__global__ void kernel_dilate3x3(const unsigned char *d_in, int in_pitch,
                                 unsigned char *d_out, int out_pitch,
                                 int W, int H) {
    int x = blockIdx.x * blockDim.x + threadIdx.x;
    int y = blockIdx.y * blockDim.y + threadIdx.y;
    if (x >= W || y >= H) return;

    unsigned char mx = 0;
    for (int dy = -1; dy <= 1; dy++) {
        for (int dx = -1; dx <= 1; dx++) {
            int nx = x + dx, ny = y + dy;
            if (nx >= 0 && nx < W && ny >= 0 && ny < H) {
                unsigned char v = d_in[ny * in_pitch + nx];
                if (v > mx) mx = v;
            }
        }
    }
    d_out[y * out_pitch + x] = mx;
}

__global__ void kernel_and_masks(const unsigned char *d_a, int a_pitch,
                                 const unsigned char *d_b, int b_pitch,
                                 unsigned char *d_out, int out_pitch,
                                 int W, int H) {
    int x = blockIdx.x * blockDim.x + threadIdx.x;
    int y = blockIdx.y * blockDim.y + threadIdx.y;
    if (x >= W || y >= H) return;
    d_out[y * out_pitch + x] = d_a[y * a_pitch + x] & d_b[y * b_pitch + x];
}

__global__ void kernel_not_mask(const unsigned char *d_in, int in_pitch,
                                unsigned char *d_out, int out_pitch,
                                int W, int H) {
    int x = blockIdx.x * blockDim.x + threadIdx.x;
    int y = blockIdx.y * blockDim.y + threadIdx.y;
    if (x >= W || y >= H) return;
    d_out[y * out_pitch + x] = ~d_in[y * in_pitch + x];
}

__global__ void kernel_apply_mask(unsigned char *d_y, int y_pitch,
                                  const unsigned char *d_mask, int mask_pitch,
                                  int W, int H) {
    int x = blockIdx.x * blockDim.x + threadIdx.x;
    int y = blockIdx.y * blockDim.y + threadIdx.y;
    if (x >= W || y >= H) return;
    d_y[y * y_pitch + x] &= d_mask[y * mask_pitch + x];
}

// ---- Launch helpers ----

static void launch_bgr2lab(const unsigned char *d_bgr, int bgr_pitch,
                           unsigned char *d_lab, int lab_pitch,
                           int W, int H, cudaStream_t stream = 0) {
    dim3 block(SEG_TX, SEG_TY);
    dim3 grid((W + SEG_TX - 1) / SEG_TX, (H + SEG_TY - 1) / SEG_TY);
    kernel_bgr2lab<<<grid, block, 0, stream>>>(d_bgr, bgr_pitch, d_lab, lab_pitch, W, H);
}

static void launch_threshold_channel(const unsigned char *d_in, int in_pitch,
                                     unsigned char *d_out, int out_pitch,
                                     int W, int H, int channel,
                                     unsigned char lo, unsigned char hi,
                                     cudaStream_t stream = 0) {
    dim3 block(SEG_TX, SEG_TY);
    dim3 grid((W + SEG_TX - 1) / SEG_TX, (H + SEG_TY - 1) / SEG_TY);
    kernel_threshold_channel<<<grid, block, 0, stream>>>(d_in, in_pitch, d_out, out_pitch, W, H, channel, lo, hi);
}

static void launch_threshold_ab(const unsigned char *d_in, int in_pitch,
                                unsigned char *d_out, int out_pitch,
                                int W, int H,
                                unsigned char a_lo, unsigned char a_hi,
                                unsigned char b_lo, unsigned char b_hi,
                                cudaStream_t stream = 0) {
    dim3 block(SEG_TX, SEG_TY);
    dim3 grid((W + SEG_TX - 1) / SEG_TX, (H + SEG_TY - 1) / SEG_TY);
    kernel_threshold_ab<<<grid, block, 0, stream>>>(d_in, in_pitch, d_out, out_pitch, W, H, a_lo, a_hi, b_lo, b_hi);
}

static void launch_threshold_lab(const unsigned char *d_in, int in_pitch,
                                 unsigned char *d_out, int out_pitch,
                                 int W, int H,
                                 unsigned char l_lo, unsigned char l_hi,
                                 unsigned char a_lo, unsigned char a_hi,
                                 unsigned char b_lo, unsigned char b_hi,
                                 cudaStream_t stream = 0) {
    dim3 block(SEG_TX, SEG_TY);
    dim3 grid((W + SEG_TX - 1) / SEG_TX, (H + SEG_TY - 1) / SEG_TY);
    kernel_threshold_lab<<<grid, block, 0, stream>>>(d_in, in_pitch, d_out, out_pitch, W, H, l_lo, l_hi, a_lo, a_hi, b_lo, b_hi);
}

static void launch_bgdiff_lab(const unsigned char *d_in, int in_pitch,
                              const unsigned char *d_bg, int bg_pitch,
                              unsigned char *d_out, int out_pitch,
                              int W, int H, unsigned char t,
                              cudaStream_t stream = 0) {
    dim3 block(SEG_TX, SEG_TY);
    dim3 grid((W + SEG_TX - 1) / SEG_TX, (H + SEG_TY - 1) / SEG_TY);
    kernel_bgdiff_lab<<<grid, block, 0, stream>>>(d_in, in_pitch, d_bg, bg_pitch, d_out, out_pitch, W, H, t);
}

static void launch_erode3x3(const unsigned char *d_in, int in_pitch,
                            unsigned char *d_out, int out_pitch,
                            int W, int H, cudaStream_t stream = 0) {
    dim3 block(SEG_TX, SEG_TY);
    dim3 grid((W + SEG_TX - 1) / SEG_TX, (H + SEG_TY - 1) / SEG_TY);
    kernel_erode3x3<<<grid, block, 0, stream>>>(d_in, in_pitch, d_out, out_pitch, W, H);
}

static void launch_dilate3x3(const unsigned char *d_in, int in_pitch,
                             unsigned char *d_out, int out_pitch,
                             int W, int H, cudaStream_t stream = 0) {
    dim3 block(SEG_TX, SEG_TY);
    dim3 grid((W + SEG_TX - 1) / SEG_TX, (H + SEG_TY - 1) / SEG_TY);
    kernel_dilate3x3<<<grid, block, 0, stream>>>(d_in, in_pitch, d_out, out_pitch, W, H);
}

static void launch_and_masks(const unsigned char *d_a, int a_pitch,
                             const unsigned char *d_b, int b_pitch,
                             unsigned char *d_out, int out_pitch,
                             int W, int H, cudaStream_t stream = 0) {
    dim3 block(SEG_TX, SEG_TY);
    dim3 grid((W + SEG_TX - 1) / SEG_TX, (H + SEG_TY - 1) / SEG_TY);
    kernel_and_masks<<<grid, block, 0, stream>>>(d_a, a_pitch, d_b, b_pitch, d_out, out_pitch, W, H);
}

static void launch_not_mask(const unsigned char *d_in, int in_pitch,
                            unsigned char *d_out, int out_pitch,
                            int W, int H, cudaStream_t stream = 0) {
    dim3 block(SEG_TX, SEG_TY);
    dim3 grid((W + SEG_TX - 1) / SEG_TX, (H + SEG_TY - 1) / SEG_TY);
    kernel_not_mask<<<grid, block, 0, stream>>>(d_in, in_pitch, d_out, out_pitch, W, H);
}

static void launch_apply_mask(unsigned char *d_y, int y_pitch,
                              const unsigned char *d_mask, int mask_pitch,
                              int W, int H, cudaStream_t stream = 0) {
    dim3 block(SEG_TX, SEG_TY);
    dim3 grid((W + SEG_TX - 1) / SEG_TX, (H + SEG_TY - 1) / SEG_TY);
    kernel_apply_mask<<<grid, block, 0, stream>>>(d_y, y_pitch, d_mask, mask_pitch, W, H);
}

#endif
