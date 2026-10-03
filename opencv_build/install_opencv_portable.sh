#!/usr/bin/env bash
# Install portable OpenCV on target Jetson Orin Nano
# Extracts the tarball locally and sets up environment without sudo.
#
# Usage: ./install_opencv_portable.sh [TARBALL_PATH]
# Example: ./install_opencv_portable.sh /media/usb/opencv-portable.tar.gz

set -euo pipefail

# ─── Configuration ───────────────────────────────────────────────────────────
readonly DEFAULT_INSTALL_DIR="${HOME}/opencv-install"

# ─── Colors ──────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'

info()  { echo -e "${GREEN}[INFO]${NC}  $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*"; exit 1; }

# ─── Functions ───────────────────────────────────────────────────────────────

usage() {
    echo "Usage: $0 [TARBALL_PATH]"
    echo ""
    echo "  TARBALL_PATH  Path to opencv-portable.tar.gz (default: auto-detect)"
    echo ""
    echo "Examples:"
    echo "  $0 /media/usb/opencv-portable.tar.gz"
    echo "  $0 ~/opencv-portable.tar.gz"
    echo ""
}

find_tarball() {
    local tarball=""

    # Check common USB mount points
    for path in /media/*/opencv-portable.tar.gz /mnt/*/opencv-portable.tar.gz; do
        if [[ -f "$path" ]]; then
            tarball="$path"
            break
        fi
    done

    # Check home directory
    if [[ -z "$tarball" ]] && [[ -f "${HOME}/opencv-portable.tar.gz" ]]; then
        tarball="${HOME}/opencv-portable.tar.gz"
    fi

    if [[ -z "$tarball" ]]; then
        error "No opencv-portable.tar.gz found. Please specify the path:\n  $0 /path/to/opencv-portable.tar.gz"
    fi

    echo "$tarball"
}

extract_tarball() {
    local tarball="$1"
    local install_dir="$2"

    if [[ -d "$install_dir" ]]; then
        warn "Installation directory already exists: $install_dir"
        read -rp "Overwrite? [y/N] " yn
        case "$yn" in
            [Yy]*) rm -rf "$install_dir" ;;
            *) error "Aborted." ;;
        esac
    fi

    info "Extracting $tarball to ${HOME}/..."
    tar -xzf "$tarball" -C "$HOME"

    info "Extraction complete."
}

generate_env_script() {
    local install_dir="$1"
    local env_script="${install_dir}/opencv-env.sh"
    local python3_version
    python3_version=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null || echo "3.10")

    cat > "$env_script" << ENVEOF
#!/bin/bash
# OpenCV environment setup - source this file to use OpenCV
# Usage: source ${install_dir}/opencv-env.sh

export OPENCV_DIR="${install_dir}"
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

verify_installation() {
    local install_dir="$1"

    info "Verifying installation..."

    # Check lib directory
    if [[ -d "${install_dir}/lib" ]]; then
        local lib_count
        lib_count=$(find "${install_dir}/lib" -name "libopencv*" 2>/dev/null | wc -l)
        info "Found $lib_count OpenCV libraries."
    else
        warn "Lib directory not found at ${install_dir}/lib"
    fi

    # Check pkg-config
    if [[ -f "${install_dir}/lib/pkgconfig/opencv4.pc" ]]; then
        info "pkg-config file found."
    else
        warn "pkg-config file not found."
    fi

    # Check Python bindings
    local python3_version
    python3_version=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null || echo "3.10")
    local cv2_dir="${install_dir}/lib/python${python3_version}/site-packages/cv2"
    if [[ -d "$cv2_dir" ]]; then
        info "Python3 cv2 bindings found at $cv2_dir"
    else
        warn "Python3 cv2 bindings not found at $cv2_dir"
    fi

    # Check bin
    if [[ -d "${install_dir}/bin" ]]; then
        info "Binary directory found."
    else
        warn "Binary directory not found."
    fi

    # Check cmake config
    if [[ -d "${install_dir}/lib/cmake/opencv4" ]]; then
        info "CMake config found."
    else
        warn "CMake config not found."
    fi
}

add_to_bashrc_prompt() {
    local install_dir="$1"
    local env_script="${install_dir}/opencv-env.sh"

    echo ""
    info "To permanently add OpenCV to your environment, add this to ~/.bashrc:"
    echo ""
    echo "  # OpenCV portable"
    echo "  if [[ -f \"${env_script}\" ]]; then"
    echo "      source \"${env_script}\""
    echo "  fi"
    echo ""
    info "Or run manually each session:"
    echo ""
    echo "  source ${env_script}"
    echo ""
}

# ─── Main ────────────────────────────────────────────────────────────────────

main() {
    local tarball=""
    local install_dir="${DEFAULT_INSTALL_DIR}"

    # Parse arguments
    if [[ $# -gt 0 ]]; then
        case "$1" in
            -h|--help)
                usage
                exit 0
                ;;
            *)
                tarball="$1"
                if [[ ! -f "$tarball" ]]; then
                    error "File not found: $tarball"
                fi
                ;;
        esac
    fi

    echo ""
    echo "============================================================"
    echo "  OpenCV Portable Installer for Jetson Orin Nano"
    echo "============================================================"
    echo ""

    # Find tarball if not specified
    if [[ -z "$tarball" ]]; then
        tarball=$(find_tarball)
    fi

    info "Using tarball: $tarball"
    info "Installing to: $install_dir"

    # Extract and install
    extract_tarball "$tarball" "$install_dir"
    generate_env_script "$install_dir"
    verify_installation "$install_dir"

    echo ""
    echo "============================================================"
    echo "  INSTALLATION COMPLETE"
    echo "============================================================"
    echo ""
    echo "  OpenCV installed to: $install_dir"
    echo ""

    add_to_bashrc_prompt "$install_dir"
}

main "$@"
