#!/bin/bash

read -p "Enter recording name: " name

mkdir -p "/home/dev/Videos/$name"

echo "Saving recordings to folder: $name"
echo "Press Ctrl+C to stop recording."

gst-launch-1.0 nvarguscamerasrc \
sensor-mode=0 \
gainrange="1 1" \
ispdigitalgainrange="1 1" \
exposuretimerange="2500000 2500000" \
wbmode=4 \
awblock=true \
aelock=true \
tnr-mode=1 \
tnr-strength=0.1 \
ee-mode=0 \
saturation=1 \
! 'video/x-raw(memory:NVMM),width=4032,height=3040' \
! tee name=t \
t. ! queue max-size-buffers=50 leaky=0 \
! nvv4l2h264enc bitrate=80000000 \
! h264parse \
! qtmux \
! filesink location="/home/dev/Videos/$name/fullres.mp4" \
t. ! queue max-size-buffers=1 leaky=downstream \
! nvvidconv \
! 'video/x-raw(memory:NVMM),width=1280,height=960' \
! nvegltransform \
! nveglglessink sync=false \
t. ! queue max-size-buffers=30 leaky=0 \
! nvvidconv \
! 'video/x-raw(memory:NVMM),width=1008,height=760' \
! nvv4l2h264enc bitrate=20000000 \
! h264parse \
! qtmux \
! filesink location="/home/dev/Videos/$name/downsampled.mp4"
