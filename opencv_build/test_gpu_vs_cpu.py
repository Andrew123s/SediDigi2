#!/usr/bin/env python3
"""
OpenCV GPU vs CPU Benchmark for Jetson Orin Nano
Tests basic image operations comparing CPU and CUDA-accelerated execution.

Usage:
    source ~/opencv-install/opencv-env.sh
    python3 test_gpu_vs_cpu.py
"""

import time
import sys
import numpy as np

try:
    import cv2
except ImportError:
    print("ERROR: cv2 not found. Run: source ~/opencv-install/opencv-env.sh")
    sys.exit(1)

WARMUP_RUNS = 2
BENCH_RUNS = 20
IMG_WIDTH = 3840
IMG_HEIGHT = 2160


def check_cuda():
    count = cv2.cuda.getCudaEnabledDeviceCount()
    if count == 0:
        print("ERROR: No CUDA-enabled GPU detected by OpenCV.")
        print("       Ensure OpenCV was built with CUDA support.")
        sys.exit(1)
    print(f"CUDA devices available: {count}")
    print(f"Image size: {IMG_WIDTH}x{IMG_HEIGHT}")
    print()


def make_test_image():
    img = np.random.randint(0, 256, (IMG_HEIGHT, IMG_WIDTH, 3), dtype=np.uint8)
    return img


def bench(name, cpu_func, gpu_func, img):
    # warmup
    gpu_mat = cv2.cuda_GpuMat()
    for _ in range(WARMUP_RUNS):
        cpu_func(img)
        gpu_mat.upload(img)
        gpu_func(gpu_mat)
        gpu_mat.download()

    # CPU timing
    t0 = time.perf_counter()
    for _ in range(BENCH_RUNS):
        cpu_func(img)
    cpu_time = (time.perf_counter() - t0) / BENCH_RUNS * 1000

    # GPU timing (upload + process + download)
    t0 = time.perf_counter()
    for _ in range(BENCH_RUNS):
        gpu_mat.upload(img)
        gpu_func(gpu_mat)
        gpu_mat.download()
    gpu_time = (time.perf_counter() - t0) / BENCH_RUNS * 1000

    speedup = cpu_time / gpu_time if gpu_time > 0 else float("inf")
    return name, cpu_time, gpu_time, speedup


def op_gaussian_blur_cpu(img):
    return cv2.GaussianBlur(img, (15, 15), 0)

def op_gaussian_blur_gpu(gpu_img):
    flt = cv2.cuda.createGaussianFilter(cv2.CV_8UC3, cv2.CV_8UC3, (15, 15), 0)
    return flt.apply(gpu_img)

def op_resize_cpu(img):
    return cv2.resize(img, (IMG_WIDTH // 2, IMG_HEIGHT // 2))

def op_resize_gpu(gpu_img):
    return cv2.cuda.resize(gpu_img, (IMG_WIDTH // 2, IMG_HEIGHT // 2))

def op_cvtcolor_cpu(img):
    return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

def op_cvtcolor_gpu(gpu_img):
    return cv2.cuda.cvtColor(gpu_img, cv2.COLOR_BGR2GRAY)

def op_threshold_cpu(img):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    return cv2.threshold(gray, 128, 255, cv2.THRESH_BINARY)[1]

def op_threshold_gpu(gpu_img):
    gray = cv2.cuda.cvtColor(gpu_img, cv2.COLOR_BGR2GRAY)
    return cv2.cuda.threshold(gray, 128, 255, cv2.THRESH_BINARY)[1]

def op_canny_cpu(img):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    return cv2.Canny(gray, 100, 200)

def op_canny_gpu(gpu_img):
    gray = cv2.cuda.cvtColor(gpu_img, cv2.COLOR_BGR2GRAY)
    detector = cv2.cuda.createCannyEdgeDetector(100, 200)
    return detector.detect(gray)

def op_warp_cpu(img):
    h, w = img.shape[:2]
    src_pts = np.float32([[0, 0], [w, 0], [0, h]])
    dst_pts = np.float32([[w * 0.05, h * 0.05], [w * 0.95, h * 0.1], [w * 0.1, h * 0.95]])
    M = cv2.getAffineTransform(src_pts, dst_pts)
    return cv2.warpAffine(img, M, (w, h))

def op_warp_gpu(gpu_img):
    h, w = gpu_img.size()
    src_pts = np.float32([[0, 0], [w, 0], [0, h]])
    dst_pts = np.float32([[w * 0.05, h * 0.05], [w * 0.95, h * 0.1], [w * 0.1, h * 0.95]])
    M = cv2.getAffineTransform(src_pts, dst_pts)
    return cv2.cuda.warpAffine(gpu_img, M, (w, h))


def main():
    print("=" * 64)
    print("  OpenCV GPU vs CPU Benchmark")
    print(f"  OpenCV {cv2.__version__}  |  CUDA build: {cv2.getBuildInformation().count('CUDA') > 0}")
    print("=" * 64)
    print()

    check_cuda()
    img = make_test_image()

    tests = [
        ("Gaussian Blur 15x15", op_gaussian_blur_cpu, op_gaussian_blur_gpu),
        ("Resize 50%",        op_resize_cpu,        op_resize_gpu),
        ("BGR -> Gray",       op_cvtcolor_cpu,      op_cvtcolor_gpu),
        ("Threshold",         op_threshold_cpu,      op_threshold_gpu),
        ("Canny Edge",        op_canny_cpu,          op_canny_gpu),
        ("Affine Warp",       op_warp_cpu,           op_warp_gpu),
    ]

    results = []
    for name, cpu_fn, gpu_fn in tests:
        result = bench(name, cpu_fn, gpu_fn, img)
        results.append(result)

    # Print results
    print(f"{'Operation':<20} {'CPU (ms)':>10} {'GPU (ms)':>10} {'Speedup':>10}")
    print("-" * 52)
    for name, cpu_t, gpu_t, speedup in results:
        print(f"{name:<20} {cpu_t:>10.2f} {gpu_t:>10.2f} {speedup:>9.2f}x")
    print("-" * 52)

    avg_speedup = sum(r[3] for r in results) / len(results)
    print(f"{'Average':<20} {'':>10} {'':>10} {avg_speedup:>9.2f}x")
    print()


if __name__ == "__main__":
    main()
