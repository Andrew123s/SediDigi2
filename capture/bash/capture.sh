#!/bin/bash

# Ask user for folder name
read -p "Enter recording name: " name

# Create directory
mkdir -p "/home/dev/Videos/$name"

echo "Saving frames to folder: $name"
echo "Press Ctrl+C to stop recording."

# Run GStreamer pipeline
gst-launch-1.0 nvarguscamerasrc \
sensor-mode=0 \
gainrange="1 1" \
ispdigitalgainrange="1 1" \
exposuretimerange="2500000 2500000" \
wbmode=4 \
awblock=true \
aelock=true \
tnr-mode=0 \
ee-mode=0 \
saturation=1 \
! 'video/x-raw(memory:NVMM), width=4032, height=3040, framerate=21/1' \
! tee name=t \
! queue ! nvvidconv ! jpegenc ! avimux ! filesink location="/home/dev/Videos/$name.avi" \
t. ! queue max-size-buffers=1 leaky=downstream \
! nvvidconv ! 'video/x-raw(memory:NVMM),width=1280,height=960' \
! nvegltransform ! nveglglessink sync=false

