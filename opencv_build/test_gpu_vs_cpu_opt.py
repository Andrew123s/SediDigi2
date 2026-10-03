#!/usr/bin/env python3
"""
OpenCV GPU vs CPU Benchmark (Optimized) for Jetson Orin Nano

Pre-creates filter/detector objects and measures GPU kernel time
separately from upload/download overhead using CUDA Events.

Usage:
    source ~/opencv-install/opencv-env.sh
    python3 test_gpu_vs_cpu_opt.py
"""

import time
import sys
import numpy as np

try:
    import cv2
except ImportError:
    print("ERROR: cv2 not found. Run: source ~/opencv-install/opencv-env.sh")
    sys.exit(1)

WARMUP_RUNS = 3
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
    return np.random.randint(0, 256, (IMG_HEIGHT, IMG_WIDTH, 3), dtype=np.uint8)


def bench(name, cpu_func, gpu_func, img, gpu_mat):
    # warmup
    for _ in range(WARMUP_RUNS):
        cpu_func(img)
        gpu_mat.upload(img)
        gpu_func(gpu_mat)
        gpu_mat.download()

    # CPU timing
    t0 = time.perf_counter()
    for _ in range(BENCH_RUNS):
        cpu_func(img)
    cpu_ms = (time.perf_counter() - t0) / BENCH_RUNS * 1000

    # GPU total timing (upload + kernel + download)
    t0 = time.perf_counter()
    for _ in range(BENCH_RUNS):
        gpu_mat.upload(img)
        gpu_func(gpu_mat)
        gpu_mat.download()
    gpu_total_ms = (time.perf_counter() - t0) / BENCH_RUNS * 1000

    # GPU kernel-only timing via CUDA Events
    ev_start = cv2.cuda.Event()
    ev_end = cv2.cuda.Event()
    for _ in range(WARMUP_RUNS):
        gpu_mat.upload(img)
        gpu_func(gpu_mat)

    ev_start.record()
    for _ in range(BENCH_RUNS):
        gpu_func(gpu_mat)
    ev_end.record()
    ev_end.waitForCompletion()
    gpu_kernel_ms = cv2.cuda.Event.elapsedTime(ev_start, ev_end) / BENCH_RUNS

    return name, cpu_ms, gpu_total_ms, gpu_kernel_ms


def main():
    print("=" * 72)
    print("  OpenCV GPU vs CPU Benchmark (Optimized)")
    print(f"  OpenCV {cv2.__version__}  |  CUDA build: {cv2.getBuildInformation().count('CUDA') > 0}")
    print("=" * 72)
    print()

    check_cuda()
    img = make_test_image()
    gpu_mat = cv2.cuda_GpuMat()
    gpu_mat.upload(img)

    # Pre-create reusable objects
    gaussian_filter = cv2.cuda.createGaussianFilter(cv2.CV_8UC3, cv2.CV_8UC3, (15, 15), 0)
    canny_detector = cv2.cuda.createCannyEdgeDetector(100, 200)

    h, w = IMG_HEIGHT, IMG_WIDTH
    src_pts = np.float32([[0, 0], [w, 0], [0, h]])
    dst_pts = np.float32([[w * 0.05, h * 0.05], [w * 0.95, h * 0.1], [w * 0.1, h * 0.95]])
    M_warp = cv2.getAffineTransform(src_pts, dst_pts)

    # CPU operations
    def cpu_gaussian(img):
        return cv2.GaussianBlur(img, (15, 15), 0)

    def cpu_resize(img):
        return cv2.resize(img, (w // 2, h // 2))

    def cpu_cvtcolor(img):
        return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    def cpu_cvtcolor_lab(img):
        return cv2.cvtColor(img, cv2.COLOR_BGR2Lab)

    def cpu_threshold(img):
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        return cv2.threshold(gray, 128, 255, cv2.THRESH_BINARY)[1]

    def cpu_canny(img):
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        return cv2.Canny(gray, 100, 200)

    def cpu_warp(img):
        return cv2.warpAffine(img, M_warp, (w, h))

    # GPU operations (capture pre-created objects via closure)
    def gpu_gaussian(gpu_img):
        return gaussian_filter.apply(gpu_img)

    def gpu_resize(gpu_img):
        return cv2.cuda.resize(gpu_img, (w // 2, h // 2))

    def gpu_cvtcolor(gpu_img):
        return cv2.cuda.cvtColor(gpu_img, cv2.COLOR_BGR2GRAY)

    def gpu_cvtcolor_lab(gpu_img):
        return cv2.cuda.cvtColor(gpu_img, cv2.COLOR_BGR2Lab)

    def gpu_threshold(gpu_img):
        gray = cv2.cuda.cvtColor(gpu_img, cv2.COLOR_BGR2GRAY)
        return cv2.cuda.threshold(gray, 128, 255, cv2.THRESH_BINARY)[1]

    def gpu_canny(gpu_img):
        gray = cv2.cuda.cvtColor(gpu_img, cv2.COLOR_BGR2GRAY)
        return canny_detector.detect(gray)

    def gpu_warp(gpu_img):
        return cv2.cuda.warpAffine(gpu_img, M_warp, (w, h))

    tests = [
        ("Gaussian Blur 15x15", cpu_gaussian, gpu_gaussian),
        ("Resize 50%",         cpu_resize,   gpu_resize),
        ("BGR -> Gray",        cpu_cvtcolor, gpu_cvtcolor),
        ("BGR -> Lab",         cpu_cvtcolor_lab, gpu_cvtcolor_lab),
        ("Threshold",          cpu_threshold, gpu_threshold),
        ("Canny Edge",         cpu_canny,    gpu_canny),
        ("Affine Warp",        cpu_warp,     gpu_warp),
    ]

    results = []
    for name, cpu_fn, gpu_fn in tests:
        result = bench(name, cpu_fn, gpu_fn, img, gpu_mat)
        results.append(result)

    # Pipeline: BGR -> Lab -> GaussianBlur -> resize -> BGR
    def cpu_pipeline(img):
        lab = cv2.cvtColor(img, cv2.COLOR_BGR2Lab)
        blurred = cv2.GaussianBlur(lab, (15, 15), 0)
        resized = cv2.resize(blurred, (w // 2, h // 2))
        return cv2.cvtColor(resized, cv2.COLOR_Lab2BGR)

    def gpu_pipeline(gpu_img):
        lab = cv2.cuda.cvtColor(gpu_img, cv2.COLOR_BGR2Lab)
        blurred = gaussian_filter.apply(lab)
        resized = cv2.cuda.resize(blurred, (w // 2, h // 2))
        return cv2.cuda.cvtColor(resized, cv2.COLOR_Lab2BGR)

    # Print single operation results
    print("  Single operations")
    print(f"  {'Operation':<20} {'CPU (ms)':>10} {'GPU total':>10} {'GPU kernel':>11} {'Speedup':>10}")
    print("  " + "-" * 65)
    for name, cpu_t, gpu_total, gpu_kernel in results:
        speedup = cpu_t / gpu_kernel if gpu_kernel > 0 else float("inf")
        print(f"  {name:<20} {cpu_t:>10.2f} {gpu_total:>10.2f} {gpu_kernel:>11.2f} {speedup:>9.2f}x")
    print("  " + "-" * 65)

    avg_cpu = sum(r[1] for r in results) / len(results)
    avg_kernel = sum(r[3] for r in results) / len(results)
    avg_speedup = avg_cpu / avg_kernel if avg_kernel > 0 else float("inf")
    print(f"  {'Average':<20} {avg_cpu:>10.2f} {'':>10} {avg_kernel:>11.2f} {avg_speedup:>9.2f}x")
    print()

    # Pipeline benchmark
    print("  Pipeline: BGR -> Lab -> GaussianBlur -> Resize -> BGR")
    print("  " + "-" * 65)

    pipeline_result = bench("Pipeline 4-op", cpu_pipeline, gpu_pipeline, img, gpu_mat)
    p_name, p_cpu, p_gpu_total, p_gpu_kernel = pipeline_result
    p_speedup = p_cpu / p_gpu_kernel if p_gpu_kernel > 0 else float("inf")

    print(f"  {'CPU (ms)':>10} {'GPU total':>10} {'GPU kernel':>11} {'Speedup':>10}")
    print("  " + "-" * 52)
    print(f"  {p_cpu:>10.2f} {p_gpu_total:>10.2f} {p_gpu_kernel:>11.2f} {p_speedup:>9.2f}x")
    print("  " + "-" * 52)
    print()

    print("GPU total = upload + kernel + download")
    print("GPU kernel = pure GPU computation (via CUDA Events)")
    print("Pipeline keeps data on GPU across multiple operations — avoids repeated transfers.")


if __name__ == "__main__":
    main()
