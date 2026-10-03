cmake_minimum_required(VERSION 3.10)
project(identities LANGUAGES CXX CUDA)
set(CMAKE_CUDA_ARCHITECTURES "87")

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

find_package(PkgConfig REQUIRED)

pkg_check_modules(GSTREAMER REQUIRED
    gstreamer-1.0
    gstreamer-app-1.0
    gstreamer-video-1.0
)

find_package(OpenCV REQUIRED)

add_executable(sobel sobel.cpp)
target_link_libraries(sobel PRIVATE
    ${GSTREAMER_LIBRARIES}
    ${OpenCV_LIBS}
)
target_include_directories(sobel PRIVATE
    ${GSTREAMER_INCLUDE_DIRS}
    ${OpenCV_INCLUDE_DIRS}
)
target_compile_options(sobel PRIVATE ${GSTREAMER_CFLAGS_OTHER})

add_executable(sobel_live sobel_live.cpp)
target_link_libraries(sobel_live PRIVATE
    ${GSTREAMER_LIBRARIES}
    ${OpenCV_LIBS}
)
target_include_directories(sobel_live PRIVATE
    ${GSTREAMER_INCLUDE_DIRS}
    ${OpenCV_INCLUDE_DIRS}
)
target_compile_options(sobel_live PRIVATE ${GSTREAMER_CFLAGS_OTHER})

add_executable(chrseg_live_v0_1_0 chrseg_live_v0_1_0.cpp)
target_link_libraries(chrseg_live_v0_1_0 PRIVATE
    ${GSTREAMER_LIBRARIES}
    ${OpenCV_LIBS}
)
target_include_directories(chrseg_live_v0_1_0 PRIVATE
    ${GSTREAMER_INCLUDE_DIRS}
    ${OpenCV_INCLUDE_DIRS}
)
target_compile_options(chrseg_live_v0_1_0 PRIVATE ${GSTREAMER_CFLAGS_OTHER})

add_executable(chrseg_live_v0_1_1 chrseg_live_v0_1_1.cpp)
target_link_libraries(chrseg_live_v0_1_1 PRIVATE
    ${GSTREAMER_LIBRARIES}
    ${OpenCV_LIBS}
)
target_include_directories(chrseg_live_v0_1_1 PRIVATE
    ${GSTREAMER_INCLUDE_DIRS}
    ${OpenCV_INCLUDE_DIRS}
)
target_compile_options(chrseg_live_v0_1_1 PRIVATE ${GSTREAMER_CFLAGS_OTHER})

add_executable(chrseg_live_v0_1_2 chrseg_live_v0_1_2.cu)
target_link_libraries(chrseg_live_v0_1_2 PRIVATE
    ${GSTREAMER_LIBRARIES}
    -lnppicc -lnppim -lnppial -lnppidei -lnppitc -lcudart
)
target_include_directories(chrseg_live_v0_1_2 PRIVATE
    ${GSTREAMER_INCLUDE_DIRS}
    /usr/local/cuda/include
)
target_link_directories(chrseg_live_v0_1_2 PRIVATE
    /usr/local/cuda/lib64
)
target_compile_options(chrseg_live_v0_1_2 PRIVATE ${GSTREAMER_CFLAGS_OTHER}
    $<$<COMPILE_LANGUAGE:CUDA>:-diag-suppress=1217>)

add_executable(chrseg_live_v0_1_3 chrseg_live_v0_1_3.cu)
target_link_libraries(chrseg_live_v0_1_3 PRIVATE
    ${GSTREAMER_LIBRARIES}
    -lnppicc -lnppim -lnppial -lnppidei -lnppitc -lcudart
)
target_include_directories(chrseg_live_v0_1_3 PRIVATE
    ${GSTREAMER_INCLUDE_DIRS}
    /usr/local/cuda/include
)
target_link_directories(chrseg_live_v0_1_3 PRIVATE
    /usr/local/cuda/lib64
)
target_compile_options(chrseg_live_v0_1_3 PRIVATE ${GSTREAMER_CFLAGS_OTHER}
    $<$<COMPILE_LANGUAGE:CUDA>:-diag-suppress=1217>)

add_executable(chrseg_live_v0_1_4 chrseg_live_v0_1_4.cu)
target_link_libraries(chrseg_live_v0_1_4 PRIVATE
    ${GSTREAMER_LIBRARIES}
    -lnppicc -lnppim -lnppial -lnppidei -lnppitc -lcudart
)
target_include_directories(chrseg_live_v0_1_4 PRIVATE
    ${GSTREAMER_INCLUDE_DIRS}
    /usr/local/cuda/include
)
target_link_directories(chrseg_live_v0_1_4 PRIVATE
    /usr/local/cuda/lib64
)
target_compile_options(chrseg_live_v0_1_4 PRIVATE ${GSTREAMER_CFLAGS_OTHER}
    $<$<COMPILE_LANGUAGE:CUDA>:-diag-suppress=1217>)

add_executable(chrseg_live_v0_1_5 chrseg_live_v0_1_5.cu)
target_link_libraries(chrseg_live_v0_1_5 PRIVATE
    ${GSTREAMER_LIBRARIES}
    -lnppicc -lnppim -lnppial -lnppidei -lnppitc -lcudart
)
target_include_directories(chrseg_live_v0_1_5 PRIVATE
    ${GSTREAMER_INCLUDE_DIRS}
    /usr/local/cuda/include
)
target_link_directories(chrseg_live_v0_1_5 PRIVATE
    /usr/local/cuda/lib64
)
target_compile_options(chrseg_live_v0_1_5 PRIVATE ${GSTREAMER_CFLAGS_OTHER}
    $<$<COMPILE_LANGUAGE:CUDA>:-diag-suppress=1217>)

add_executable(chrseg_live_v0_1_6 chrseg_live_v0_1_6.cu)
target_link_libraries(chrseg_live_v0_1_6 PRIVATE
    ${GSTREAMER_LIBRARIES}
    -lnppicc -lnppim -lnppial -lnppidei -lnppitc -lcudart
)
target_include_directories(chrseg_live_v0_1_6 PRIVATE
    ${GSTREAMER_INCLUDE_DIRS}
    /usr/local/cuda/include
)
target_link_directories(chrseg_live_v0_1_6 PRIVATE
    /usr/local/cuda/lib64
)
target_compile_options(chrseg_live_v0_1_6 PRIVATE ${GSTREAMER_CFLAGS_OTHER}
    $<$<COMPILE_LANGUAGE:CUDA>:-diag-suppress=1217>)

add_executable(chrseg_live_v0_1_7 chrseg_live_v0_1_7.cu)
target_link_libraries(chrseg_live_v0_1_7 PRIVATE
    ${GSTREAMER_LIBRARIES}
    -lnppicc -lnppim -lnppial -lnppidei -lnppitc -lcudart
)
target_include_directories(chrseg_live_v0_1_7 PRIVATE
    ${GSTREAMER_INCLUDE_DIRS}
    /usr/local/cuda/include
)
target_link_directories(chrseg_live_v0_1_7 PRIVATE
    /usr/local/cuda/lib64
)
target_compile_options(chrseg_live_v0_1_7 PRIVATE ${GSTREAMER_CFLAGS_OTHER}
    $<$<COMPILE_LANGUAGE:CUDA>:-diag-suppress=1217>)

add_executable(chrseg_live_v0_1_8 chrseg_live_v0_1_8.cu)
target_link_libraries(chrseg_live_v0_1_8 PRIVATE
    ${GSTREAMER_LIBRARIES}
    -lnppicc -lnppim -lnppial -lnppidei -lnppitc -lcudart
)
target_include_directories(chrseg_live_v0_1_8 PRIVATE
    ${GSTREAMER_INCLUDE_DIRS}
    /usr/local/cuda/include
)
target_link_directories(chrseg_live_v0_1_8 PRIVATE
    /usr/local/cuda/lib64
)
target_compile_options(chrseg_live_v0_1_8 PRIVATE ${GSTREAMER_CFLAGS_OTHER}
    $<$<COMPILE_LANGUAGE:CUDA>:-diag-suppress=1217>)

add_executable(chrseg_live_v0_2_0 chrseg_live_v0_2_0.cu)
target_link_libraries(chrseg_live_v0_2_0 PRIVATE
    ${GSTREAMER_LIBRARIES}
    -lnppicc -lnppim -lnppial -lnppidei -lnppitc -lcudart
)
target_include_directories(chrseg_live_v0_2_0 PRIVATE
    ${GSTREAMER_INCLUDE_DIRS}
    /usr/local/cuda/include
)
target_link_directories(chrseg_live_v0_2_0 PRIVATE
    /usr/local/cuda/lib64
)
target_compile_options(chrseg_live_v0_2_0 PRIVATE ${GSTREAMER_CFLAGS_OTHER}
    $<$<COMPILE_LANGUAGE:CUDA>:-diag-suppress=1217>)

add_executable(chrseg_live_v0_2_1 chrseg_live_v0_2_1.cu)
target_link_libraries(chrseg_live_v0_2_1 PRIVATE
    ${GSTREAMER_LIBRARIES}
    -lnppicc -lnppim -lnppial -lnppidei -lnppitc -lcudart
)
target_include_directories(chrseg_live_v0_2_1 PRIVATE
    ${GSTREAMER_INCLUDE_DIRS}
    /usr/local/cuda/include
)
target_link_directories(chrseg_live_v0_2_1 PRIVATE
    /usr/local/cuda/lib64
)
target_compile_options(chrseg_live_v0_2_1 PRIVATE ${GSTREAMER_CFLAGS_OTHER}
    $<$<COMPILE_LANGUAGE:CUDA>:-diag-suppress=1217>)

add_executable(seg_play seg_play.cu)
target_link_libraries(seg_play PRIVATE
    ${GSTREAMER_LIBRARIES}
    -lcudart
)
target_include_directories(seg_play PRIVATE
    ${GSTREAMER_INCLUDE_DIRS}
    /usr/local/cuda/include
)
target_link_directories(seg_play PRIVATE
    /usr/local/cuda/lib64
)
target_compile_options(seg_play PRIVATE ${GSTREAMER_CFLAGS_OTHER}
    $<$<COMPILE_LANGUAGE:CUDA>:-diag-suppress=1217>)

add_executable(bgseg_live_v0_0_1 bgseg_live_v0_0_1.cu)
target_link_libraries(bgseg_live_v0_0_1 PRIVATE
    ${GSTREAMER_LIBRARIES}
    -lnppicc -lnppim -lnppial -lnppidei -lnppitc -lcudart
)
target_include_directories(bgseg_live_v0_0_1 PRIVATE
    ${GSTREAMER_INCLUDE_DIRS}
    /usr/local/cuda/include
)
target_link_directories(bgseg_live_v0_0_1 PRIVATE
    /usr/local/cuda/lib64
)
target_compile_options(bgseg_live_v0_0_1 PRIVATE ${GSTREAMER_CFLAGS_OTHER}
    $<$<COMPILE_LANGUAGE:CUDA>:-diag-suppress=1217>)