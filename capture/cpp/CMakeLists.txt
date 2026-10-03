cmake_minimum_required(VERSION 3.10)
project(capture LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

find_package(PkgConfig REQUIRED)

pkg_check_modules(GSTREAMER REQUIRED
    gstreamer-1.0
    gstreamer-app-1.0
    gstreamer-video-1.0
)

add_executable(capture capture.cpp)

target_link_libraries(capture PRIVATE
    ${GSTREAMER_LIBRARIES}
)

target_include_directories(capture PRIVATE
    ${GSTREAMER_INCLUDE_DIRS}
)

target_compile_options(capture PRIVATE
    ${GSTREAMER_CFLAGS_OTHER}
)

add_executable(capture2 capture2.cpp)

target_link_libraries(capture2 PRIVATE
    ${GSTREAMER_LIBRARIES}
)

target_include_directories(capture2 PRIVATE
    ${GSTREAMER_INCLUDE_DIRS}
)

target_compile_options(capture2 PRIVATE
    ${GSTREAMER_CFLAGS_OTHER}
)

# ──────────────────────────────────────────────
# 3) capture2_x264  – Software encoding (x264enc) fallback for Orin Nano
# ──────────────────────────────────────────────
add_executable(capture2_x264 capture2_x264.cpp)
target_link_libraries(capture2_x264 PRIVATE ${GSTREAMER_LIBRARIES})
target_include_directories(capture2_x264 PRIVATE ${GSTREAMER_INCLUDE_DIRS})
target_compile_options(capture2_x264 PRIVATE ${GSTREAMER_CFLAGS_OTHER})

# ──────────────────────────────────────────────
# 4) liveview  – Live preview only (no tee, no recording)
# ──────────────────────────────────────────────
add_executable(liveview liveview.cpp)
target_link_libraries(liveview PRIVATE ${GSTREAMER_LIBRARIES})
target_include_directories(liveview PRIVATE ${GSTREAMER_INCLUDE_DIRS})
target_compile_options(liveview PRIVATE ${GSTREAMER_CFLAGS_OTHER})


