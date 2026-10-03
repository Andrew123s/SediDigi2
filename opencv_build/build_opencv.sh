#!/usr/bin/env bash
# OpenCV build script for Jetson Orin Nano
# Builds OpenCV from source with CUDA support.
# Optionally creates a portable tarball for transfer to another Jetson.
#
# Usage:
#   ./build_opencv.sh [OPTIONS] [VERSION]
#
# Options:
#   --portable    Create a portable tarball after build
#
# Examples:
#   ./build_opencv.sh
#   ./build_opencv.sh --portable
#   ./build_opencv.sh --portable 4.11.0

set -euo pipefail

# ─── Configuration ───────────────────────────────────────────────────────────
readonly DEFAULT_VERSION="4.11.0"

# Detect real user's home (sudo sets HOME=/root)
if [[ -n "${SUDO_USER:-}" ]]; then
    REAL_HOME=$(getent passwd "$SUDO_USER" | cut -d: -f6)
else
    REAL_HOME="$HOME"
fi

readonly PREFIX="${REAL_HOME}/opencv-install"
readonly BUILD_DIR="${REAL_HOME}/opencv"
readonly JOBS=4
readonly CUDA_ARCH_BIN="8.7"

PORTABLE=false

# ─── CUDA PATH ──────────────────────────────────────────────────────────────
for cuda_dir in /usr/local/cuda-12.6 /usr/local/cuda-12 /usr/local/cuda; do
    if [[ -d "${cuda_dir}/bin" ]]; then
        export PATH="${cuda_dir}/bin:${PATH}"
        break
    fi
done

# ─── Colors ──────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'

info()  { echo -e "${GREEN}[INFO]${NC}  $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*"; exit 1; }

# ─── Preflight Checks ───────────────────────────────────────────────────────

check_root() {
    if [[ $EUID -eq 0 ]]; then
        error "Do not run this script as root. Run as normal user; sudo is used automatically for apt-get."
    fi
}

check_arch() {
    local arch
    arch=$(uname -m)
    if [[ "$arch" != "aarch64" ]]; then
        error "This script is designed for aarch64 (Jetson). Detected: $arch"
    fi
}

check_nvcc() {
    if ! command -v nvcc &>/dev/null; then
        warn "nvcc not found. Will attempt to install cuda-nvcc-12-6 via apt-get."
        NVCC_MISSING=1
        return
    fi
    info "nvcc found: $(nvcc --version | grep release)"
    NVCC_MISSING=0
}

check_gcc() {
    if ! command -v g++ &>/dev/null; then
        error "g++ not found. Install build-essential first."
    fi
    info "g++ found: $(g++ --version | head -1)"
}

detect_cudnn_version() {
    local pkg_version
    pkg_version=$(dpkg -l 2>/dev/null | grep -oP 'libcudnn\d+-cuda-\d+\s+\S+' | head -1 | awk '{print $2}')
    if [[ -n "$pkg_version" ]]; then
        local major
        major=$(echo "$pkg_version" | cut -d. -f1)
        info "Detected cuDNN version: $pkg_version (major: $major)"
        CUDNN_VERSION="$major"
        return
    fi

    local so_version
    so_version=$(ls /usr/lib/aarch64-linux-gnu/libcudnn.so.* 2>/dev/null | head -1 | grep -oP '\d+\.\d+' | head -1)
    if [[ -n "$so_version" ]]; then
        local major
        major=$(echo "$so_version" | cut -d. -f1)
        info "Detected cuDNN version from libs: $so_version (major: $major)"
        CUDNN_VERSION="$major"
        return
    fi

    warn "Could not detect cuDNN version. Assuming major version 9."
    CUDNN_VERSION="9"
}

check_missing_packages() {
    local REQUIRED_PKGS=(
        build-essential cmake git gfortran
        libatlas-base-dev libavcodec-dev libavformat-dev libswscale-dev libpostproc-dev
        libdc1394-dev libeigen3-dev libglew-dev libgtk-3-dev
        libgstreamer-plugins-base1.0-dev libgstreamer-plugins-good1.0-dev libgstreamer1.0-dev
        libjpeg-dev libjpeg-turbo8-dev libpng-dev libtiff-dev
        libv4l-dev libxine2-dev libxvidcore-dev libx264-dev
        liblapack-dev liblapacke-dev libopenblas-dev libtbb-dev libtesseract-dev
        libcanberra-gtk3-module pkg-config python3-dev python3-numpy python3-matplotlib
        v4l-utils zlib1g-dev libcudnn9-dev-cuda-12 cuda-nvcc-12-6 libcublas-dev-12-6 libcufft-dev-12-6 libnpp-dev-12-6
    )
    local MISSING=()

    for pkg in "${REQUIRED_PKGS[@]}"; do
        if ! dpkg -l "$pkg" 2>/dev/null | grep -q "^ii"; then
            MISSING+=("$pkg")
        fi
    done

    if [[ ${#MISSING[@]} -gt 0 ]]; then
        warn "Missing ${#MISSING[@]} packages:"
        printf '  %s\n' "${MISSING[@]}"
        echo ""
        return 1
    fi
    return 0
}

# ─── Dependency Installation ────────────────────────────────────────────────

install_dependencies() {
    if ! check_missing_packages; then
        info "Some packages are missing. Installing via apt-get..."
    fi

    info "Installing build dependencies..."

    if ! sudo apt-get update -qq 2>&1; then
        warn "apt-get update encountered errors."
        warn "Some packages may not be available. Check /etc/apt/sources.list."
        warn "arm64 systems need ports.ubuntu.com, not archive.ubuntu.com."
        echo ""
    fi

    sudo apt-get install -y --no-install-recommends \
        build-essential \
        cmake \
        git \
        gfortran \
        libatlas-base-dev \
        libavcodec-dev \
        libavformat-dev \
        libswscale-dev \
        libpostproc-dev \
        libcanberra-gtk3-module \
        libdc1394-dev \
        libeigen3-dev \
        libglew-dev \
        libgstreamer-plugins-base1.0-dev \
        libgstreamer-plugins-good1.0-dev \
        libgstreamer1.0-dev \
        libgtk-3-dev \
        libjpeg-dev \
        libjpeg-turbo8-dev \
        libpng-dev \
        libtiff-dev \
        libv4l-dev \
        libxine2-dev \
        libxvidcore-dev \
        libx264-dev \
        liblapack-dev \
        liblapacke-dev \
        libopenblas-dev \
        libtbb-dev \
        libtesseract-dev \
        pkg-config \
        python3-dev \
        python3-numpy \
        python3-matplotlib \
        v4l-utils \
        zlib1g-dev \
        libcublas-dev-12-6 \
        libcufft-dev-12-6 \
        libnpp-dev-12-6

    if ! dpkg -l libcudnn9-dev-cuda-12 &>/dev/null 2>&1; then
        info "Installing cuDNN development headers..."
        sudo apt-get install -y --no-install-recommends libcudnn9-dev-cuda-12
    fi

    if [[ "${NVCC_MISSING:-0}" -eq 1 ]]; then
        info "Installing CUDA nvcc compiler..."
        sudo apt-get install -y --no-install-recommends cuda-nvcc-12-6
    fi

    info "Dependencies installed."
}

# ─── Source Download ─────────────────────────────────────────────────────────

git_source() {
    local version="$1"

    # Skip if source already exists
    if [[ -d "$BUILD_DIR/src" ]] && [[ -n "$(ls -A "$BUILD_DIR/src" 2>/dev/null)" ]]; then
        info "OpenCV source already exists at $BUILD_DIR/src — skipping download."
        return
    fi

    if [[ -d "$BUILD_DIR" ]]; then
        warn "Existing build directory found at $BUILD_DIR — removing."
        rm -rf "$BUILD_DIR"
    fi

    mkdir -p "$BUILD_DIR"
    cd "$BUILD_DIR"

    info "Cloning OpenCV $version (shallow)..."
    git clone --depth 1 --branch "$version" https://github.com/opencv/opencv.git src
    git clone --depth 1 --branch "$version" https://github.com/opencv/opencv_contrib.git contrib

    info "Source downloaded."
}

# ─── CMake Configuration ────────────────────────────────────────────────────

configure() {
    cd "$BUILD_DIR/src"
    mkdir -p build
    cd build

    local PYTHON3_VERSION
    PYTHON3_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")

    local CMAKEFLAGS=(
        -D BUILD_EXAMPLES=OFF
        -D BUILD_opencv_python2=OFF
        -D BUILD_opencv_python3=ON
        -D CMAKE_BUILD_TYPE=RELEASE
        -D CMAKE_INSTALL_PREFIX="${PREFIX}"
        -D CUDA_ARCH_BIN="${CUDA_ARCH_BIN}"
        -D CUDA_ARCH_PTX=
        -D CUDA_FAST_MATH=ON
        -D CUDNN_VERSION="${CUDNN_VERSION}"
        -D EIGEN_INCLUDE_PATH=/usr/include/eigen3
        -D ENABLE_NEON=ON
        -D OPENCV_DNN_CUDA=ON
        -D OPENCV_ENABLE_NONFREE=ON
        -D OPENCV_EXTRA_MODULES_PATH="${BUILD_DIR}/contrib/modules"
        -D OPENCV_GENERATE_PKGCONFIG=ON
        -D WITH_CUBLAS=ON
        -D WITH_CUDA=ON
        -D WITH_CUDNN=ON
        -D WITH_GSTREAMER=ON
        -D WITH_LIBV4L=ON
        -D WITH_OPENGL=ON
        -D WITH_NVCUVID=OFF
        -D WITH_NVCUVENC=OFF
        -D BUILD_PERF_TESTS=OFF
        -D BUILD_TESTS=OFF
        -D PYTHON3_NUMPY_INCLUDE_DIRS="/usr/lib/python3/dist-packages/numpy/core/include"
        -D PYTHON3_PACKAGES_PATH="${PREFIX}/lib/python${PYTHON3_VERSION}/site-packages"
    )

    info "Running cmake..."
    echo "cmake flags: ${CMAKEFLAGS[*]}"
    cmake "${CMAKEFLAGS[@]}" .. 2>&1 | tee "${BUILD_DIR}/configure.log"
    info "CMake configuration complete."
}

# ─── Build & Install ────────────────────────────────────────────────────────

build_and_install() {
    cd "$BUILD_DIR/src/build"

    info "Building with ${JOBS} jobs (this may take 1-2 hours)..."
    make -j"${JOBS}" 2>&1 | tee "${BUILD_DIR}/build.log"

    info "Installing to ${PREFIX}..."
    mkdir -p "$PREFIX"
    make install 2>&1 | tee "${BUILD_DIR}/install.log"

    info "Build and install complete."
}

# ─── Packaging ───────────────────────────────────────────────────────────────

create_package() {
    local tarball="${REAL_HOME}/opencv-portable.tar.gz"

    info "Creating tarball..."
    tar -czf "$tarball" -C "$REAL_HOME" "$(basename "$PREFIX")"

    local size
    size=$(du -h "$tarball" | cut -f1)
    info "Tarball created: $tarball ($size)"

    echo ""
    echo "============================================================"
    echo "  PORTABLE PACKAGE READY"
    echo "============================================================"
    echo ""
    echo "  Tarball:  $tarball"
    echo "  Size:     $size"
    echo ""
    echo "  Next steps:"
    echo "  1. Move tarball to target device."
    echo ""
    echo "  2. On target device, run:"
    echo "     ./install_opencv_portable.sh /path/to/opencv-portable.tar.gz"
    echo ""
    echo "============================================================"
}

# ─── Generate Environment Script ────────────────────────────────────────────

generate_env_script() {
    local env_script="${PREFIX}/opencv-env.sh"
    local python3_version
    python3_version=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")

    cat > "$env_script" << ENVEOF
#!/bin/bash
# OpenCV environment setup - source this file to use OpenCV
# Usage: source ~/opencv-install/opencv-env.sh

export OPENCV_DIR="${PREFIX}"
export LD_LIBRARY_PATH="\${OPENCV_DIR}/lib:\${LD_LIBRARY_PATH:-}"
export PKG_CONFIG_PATH="\${OPENCV_DIR}/lib/pkgconfig:\${PKG_CONFIG_PATH:-}"
export PYTHONPATH="\${OPENCV_DIR}/lib/python${python3_version}/site-packages:\${PYTHONPATH:-}"
export PATH="\${OPENCV_DIR}/bin:\${PATH}"
export CMAKE_PREFIX_PATH="\${OPENCV_DIR}:\${CMAKE_PREFIX_PATH:-}"

echo "OpenCV environment loaded from \${OPENCV_DIR}"
ENVEOF

    chmod +x "$env_script"
    info "Environment script generated: $env_script"
}

# ─── Main ────────────────────────────────────────────────────────────────────

main() {
    local VERSION="${DEFAULT_VERSION}"

    while [[ $# -gt 0 ]]; do
        case "$1" in
            --portable)
                PORTABLE=true
                shift
                ;;
            -h|--help)
                echo "Usage: $0 [OPTIONS] [VERSION]"
                echo ""
                echo "Options:"
                echo "  --portable    Create a portable tarball after build"
                echo "  -h, --help    Show this help"
                echo ""
                echo "Examples:"
                echo "  $0"
                echo "  $0 --portable"
                echo "  $0 --portable 4.11.0"
                exit 0
                ;;
            -*)
                error "Unknown option: $1 (use -h for help)"
                ;;
            *)
                VERSION="$1"
                shift
                ;;
        esac
    done

    echo ""
    echo "============================================================"
    echo "  OpenCV Build for Jetson Orin Nano"
    echo "  Version:       ${VERSION}"
    echo "  Install prefix: ${PREFIX}"
    echo "  CUDA arch:     ${CUDA_ARCH_BIN}"
    echo "  Make jobs:     ${JOBS}"
    echo "  Portable:      ${PORTABLE}"
    echo "============================================================"
    echo ""

    check_root
    check_arch
    check_nvcc
    check_gcc
    detect_cudnn_version

    install_dependencies

    if ! command -v nvcc &>/dev/null; then
        error "nvcc still not found after installing dependencies. Please install cuda-nvcc-12-6 manually."
    fi

    git_source "$VERSION"
    configure
    build_and_install
    generate_env_script

    echo ""
    echo "============================================================"
    echo "  BUILD COMPLETE"
    echo "============================================================"
    echo ""
    echo "  OpenCV installed to: ${PREFIX}"
    echo ""
    echo "  To use, run:"
    echo "    source ${PREFIX}/opencv-env.sh"
    echo ""

    if [[ "$PORTABLE" == true ]]; then
        create_package
    fi
}

main "$@"
