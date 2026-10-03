cmake_minimum_required(VERSION 3.10)
project(meas LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

find_package(OpenCV REQUIRED COMPONENTS core imgproc imgcodecs)

add_executable(focus_measure focus_measure.cpp)

target_link_libraries(focus_measure PRIVATE ${OpenCV_LIBS})

target_include_directories(focus_measure PRIVATE ${OpenCV_INCLUDE_DIRS})

target_compile_options(focus_measure PRIVATE ${OpenCV_CFLAGS_OTHER})