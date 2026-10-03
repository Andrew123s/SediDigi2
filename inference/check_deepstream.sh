# Check if DeepStream binary is in PATH, if DeepStream packages are installed, if /opt/nvidia/deepstream/ exists, if CUDA compiler is available, and read the Jetson Tegra release file
which deepstream-app 2>/dev/null; dpkg -l | grep deepstream 2>/dev/null; ls /opt/nvidia/deepstream/ 2>/dev/null; nvcc --version 2>/dev/null || echo "No CUDA/nvcc"; cat /etc/nv_tegra_release 2>/dev/null || echo "No Jetson Tegra release file"

# Search for DeepStream in dpkg, list /opt/nvidia/ contents, find nvinfer binary, list TensorRT libraries, check pip for deepstream and tensorrt, check dpkg for tensorrt
dpkg -l | grep -i deepstream 2>/dev/null; ls /opt/nvidia/ 2>/dev/null; which nvinfer 2>/dev/null; ls /usr/lib/aarch64-linux-gnu/libnvinfer* 2>/dev/null; pip list 2>/dev/null | grep -i deepstream; pip list 2>/dev/null | grep -i tensorrt; dpkg -l | grep -i tensorrt 2>/dev/null

# Check installed GStreamer packages, locate gst-launch-1.0, and check for NVIDIA GStreamer plugins (nvinfer, nvv4l2decoder, etc.)
dpkg -l | grep -i gstreamer 2>/dev/null | head -20; which gst-launch-1.0 2>/dev/null; ls /usr/lib/aarch64-linux-gnu/gstreamer-1.0/libnv* 2>/dev/null

# Read NVIDIA apt sources list and check for DeepStream debs in /opt/nvidia/debs/
cat /etc/apt/sources.list.d/nvidia* 2>/dev/null; ls /opt/nvidia/debs/ 2>/dev/null | grep -i deepstream

# Search apt cache for deepstream packages
apt-cache search deepstream 2>/dev/null

# Read Jetson Tegra release info, check apt policy for nvidia-l4t-core, and search for nvidia-l4t packages
cat /etc/nv_tegra_release; echo "---"; apt-cache policy nvidia-l4t-core 2>/dev/null; echo "---"; apt-cache search nvidia-l4t 2>/dev/null | head -20

# Check current user, groups, whether sudo works without password, and search for deepstream in dpkg again
whoami; id; sudo -n true 2>&1; dpkg -l | grep -i deepstream 2>/dev/null

# Update apt package lists (last 5 lines of output)
apt-get update 2>&1 | tail -5
