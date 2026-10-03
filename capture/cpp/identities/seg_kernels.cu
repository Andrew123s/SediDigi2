#include "seg_kernels.cuh"

#define TX 16
#define TY 16

// ---- BGR→Lab kernels ----

__device__ __forceinline__ float srgb_to_linear(unsigned char v) {
    float f = v / 255.0f;
    return (f <= 0.04045f) ? f / 12.92f : powf((f + 0.055f) / 1.055f, 2.4f);
}

__device__ __forceinline__ float lab_f(float t) {
    const float delta = 6.0f / 29.0f;
    const float delta3 = delta * delta * delta; // 0.008856...
    return (t > delta3) ? cbrtf(t) : t / (3.0f * delta * delta) + 4.0f / 29.0f;
}

__global__ void kernel_bgr2lab(const unsigned char *d_bgr, int bgr_pitch,
                               unsigned char *d_lab,  int lab_pitch,
                               int W, int H) {
    int x = blockIdx.x * blockDim.x + threadIdx.x;
    int y = blockIdx.y * blockDim.y + threadIdx.y;
    if (x >= W || y >= H) return;

    const unsigned char *row_bgr = d_bgr + y * bgr_pitch;
    unsigned char *row_lab = d_lab + y * lab_pitch;

    float B = srgb_to_linear(row_bgr[x * 3 + 0]);
    float G = srgb_to_linear(row_bgr[x * 3 + 1]);
    float R = srgb_to_linear(row_bgr[x * 3 + 2]);

    // sRGB → XYZ (D65)
    float X = 0.4124564f * R + 0.3575761f * G + 0.1804375f * B;
    float Y = 0.2126729f * R + 0.7151522f * G + 0.0721750f * B;
    float Z = 0.0193339f * R + 0.1191920f * G + 0.9503041f * B;

    // XYZ → Lab (D65 white point)
    float fX = lab_f(X / 0.95047f);
    float fY = lab_f(Y);
    float fZ = lab_f(Z / 1.08883f);

    float L = 116.0f * fY - 16.0f;       // [0, 100]
    float a = 500.0f * (fX - fY);         // ~[-128, 128]
    float b_val = 200.0f * (fY - fZ);     // ~[-128, 128]

    // OpenCV uint8 Lab encoding
    unsigned char L8 = (unsigned char)(L * 255.0f / 100.0f + 0.5f);
    unsigned char a8 = (unsigned char)(a + 128.0f + 0.5f);
    unsigned char b8 = (unsigned char)(b_val + 128.0f + 0.5f);

    // Clamp
    L8 = L8 > 255 ? 255 : L8;
    a8 = a8 > 255 ? 255 : (a8 < 0 ? 0 : a8);
    b8 = b8 > 255 ? 255 : (b8 < 0 ? 0 : b8);

    row_lab[x * 3 + 0] = L8;
    row_lab[x * 3 + 1] = a8;
    row_lab[x * 3 + 2] = b8;
}

// ---- Threshold on a single channel ----

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

// ---- 3x3 Erosion (min) ----

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

// ---- 3x3 Dilation (max) ----

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

// ---- AND two masks ----

__global__ void kernel_and_masks(const unsigned char *d_a, int a_pitch,
                                 const unsigned char *d_b, int b_pitch,
                                 unsigned char *d_out, int out_pitch,
                                 int W, int H) {
    int x = blockIdx.x * blockDim.x + threadIdx.x;
    int y = blockIdx.y * blockDim.y + threadIdx.y;
    if (x >= W || y >= H) return;
    d_out[y * out_pitch + x] = d_a[y * a_pitch + x] & d_b[y * b_pitch + x];
}

// ---- NOT mask ----

__global__ void kernel_not_mask(const unsigned char *d_in, int in_pitch,
                                unsigned char *d_out, int out_pitch,
                                int W, int H) {
    int x = blockIdx.x * blockDim.x + threadIdx.x;
    int y = blockIdx.y * blockDim.y + threadIdx.y;
    if (x >= W || y >= H) return;
    d_out[y * out_pitch + x] = ~d_in[y * in_pitch + x];
}

// ---- Apply mask to Y ----

__global__ void kernel_apply_mask(unsigned char *d_y, int y_pitch,
                                  const unsigned char *d_mask, int mask_pitch,
                                  int W, int H) {
    int x = blockIdx.x * blockDim.x + threadIdx.x;
    int y = blockIdx.y * blockDim.y + threadIdx.y;
    if (x >= W || y >= H) return;
    d_y[y * y_pitch + x] &= d_mask[y * mask_pitch + x];
}

// ---- Launch helpers ----

void launch_bgr2lab(const unsigned char *d_bgr, int bgr_pitch,
                    unsigned char *d_lab, int lab_pitch,
                    int W, int H, cudaStream_t stream) {
    dim3 block(TX, TY);
    dim3 grid((W + TX - 1) / TX, (H + TY - 1) / TY);
    kernel_bgr2lab<<<grid, block, 0, stream>>>(d_bgr, bgr_pitch, d_lab, lab_pitch, W, H);
}

void launch_threshold_channel(const unsigned char *d_in, int in_pitch,
                              unsigned char *d_out, int out_pitch,
                              int W, int H, int channel,
                              unsigned char lo, unsigned char hi,
                              cudaStream_t stream) {
    dim3 block(TX, TY);
    dim3 grid((W + TX - 1) / TX, (H + TY - 1) / TY);
    kernel_threshold_channel<<<grid, block, 0, stream>>>(d_in, in_pitch, d_out, out_pitch, W, H, channel, lo, hi);
}

void launch_erode3x3(const unsigned char *d_in, int in_pitch,
                     unsigned char *d_out, int out_pitch,
                     int W, int H, cudaStream_t stream) {
    dim3 block(TX, TY);
    dim3 grid((W + TX - 1) / TX, (H + TY - 1) / TY);
    kernel_erode3x3<<<grid, block, 0, stream>>>(d_in, in_pitch, d_out, out_pitch, W, H);
}

void launch_dilate3x3(const unsigned char *d_in, int in_pitch,
                      unsigned char *d_out, int out_pitch,
                      int W, int H, cudaStream_t stream) {
    dim3 block(TX, TY);
    dim3 grid((W + TX - 1) / TX, (H + TY - 1) / TY);
    kernel_dilate3x3<<<grid, block, 0, stream>>>(d_in, in_pitch, d_out, out_pitch, W, H);
}

void launch_and_masks(const unsigned char *d_a, int a_pitch,
                      const unsigned char *d_b, int b_pitch,
                      unsigned char *d_out, int out_pitch,
                      int W, int H, cudaStream_t stream) {
    dim3 block(TX, TY);
    dim3 grid((W + TX - 1) / TX, (H + TY - 1) / TY);
    kernel_and_masks<<<grid, block, 0, stream>>>(d_a, a_pitch, d_b, b_pitch, d_out, out_pitch, W, H);
}

void launch_not_mask(const unsigned char *d_in, int in_pitch,
                     unsigned char *d_out, int out_pitch,
                     int W, int H, cudaStream_t stream) {
    dim3 block(TX, TY);
    dim3 grid((W + TX - 1) / TX, (H + TY - 1) / TY);
    kernel_not_mask<<<grid, block, 0, stream>>>(d_in, in_pitch, d_out, out_pitch, W, H);
}

void launch_apply_mask(unsigned char *d_y, int y_pitch,
                       const unsigned char *d_mask, int mask_pitch,
                       int W, int H, cudaStream_t stream) {
    dim3 block(TX, TY);
    dim3 grid((W + TX - 1) / TX, (H + TY - 1) / TY);
    kernel_apply_mask<<<grid, block, 0, stream>>>(d_y, y_pitch, d_mask, mask_pitch, W, H);
}
