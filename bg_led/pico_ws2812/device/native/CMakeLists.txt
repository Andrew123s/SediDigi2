cmake_minimum_required(VERSION 3.13)

include(pico_sdk_import.cmake)

project(pico_ws2812_native C CXX ASM)

pico_sdk_init()

add_executable(pico_ws2812_native
    main.cpp
)

pico_generate_pio_header(pico_ws2812_native
    ${CMAKE_CURRENT_LIST_DIR}/ws2812.pio
)

target_link_libraries(pico_ws2812_native
    pico_stdlib
    hardware_dma
    hardware_pio
)

pico_enable_stdio_uart(pico_ws2812_native 0)
pico_enable_stdio_usb(pico_ws2812_native 1)

pico_add_extra_outputs(pico_ws2812_native)