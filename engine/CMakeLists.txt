cmake_minimum_required(VERSION 3.16)
project(HelixGuardAlignmentEngine LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

if(MSVC)
    add_compile_options(/EHsc /utf-8 /W3)
    add_compile_definitions(WIN32_LEAN_AND_MEAN NOMINMAX _CRT_SECURE_NO_WARNINGS)
else()
    add_compile_options(-Wall -Wextra -O2)
endif()

# Core alignment library
add_library(alignment_lib STATIC
    alignment.cpp
    alignment.hpp
)

target_include_directories(alignment_lib PUBLIC
    ${CMAKE_CURRENT_SOURCE_DIR}
)

# HTTP server executable (also supports --test CLI mode and /test endpoint)
add_executable(server
    main.cpp
    tests/test_alignment.cpp
)

target_include_directories(server PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}
    ${CMAKE_CURRENT_SOURCE_DIR}/include
)

target_link_libraries(server PRIVATE
    alignment_lib
)

if(WIN32)
    target_link_libraries(server PRIVATE ws2_32 crypt32)
else()
    find_package(Threads REQUIRED)
    target_link_libraries(server PRIVATE Threads::Threads)
endif()

# Standalone unit tests executable
add_executable(test_alignment
    tests/test_alignment.cpp
)

target_include_directories(test_alignment PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}
)

target_link_libraries(test_alignment PRIVATE
    alignment_lib
)

target_compile_definitions(test_alignment PRIVATE
    STANDALONE_TEST_RUNNER
)

if(WIN32)
    target_link_libraries(test_alignment PRIVATE ws2_32 crypt32)
else()
    find_package(Threads REQUIRED)
    target_link_libraries(test_alignment PRIVATE Threads::Threads)
endif()

# Sign binaries on Windows with development certificate
if(WIN32)
    find_program(SIGNTOOL_EXECUTABLE signtool
        HINTS
            "C:/Program Files (x86)/Windows Kits/10/bin/10.0.26100.0/x64"
            "C:/Program Files (x86)/Windows Kits/10/bin/x64"
    )
    if(SIGNTOOL_EXECUTABLE)
        add_custom_command(TARGET server POST_BUILD
            COMMAND "${SIGNTOOL_EXECUTABLE}" sign /fd SHA256 /sha1 E2470CC034C0EF476291AFFF256A2C5FE6D51001 "$<TARGET_FILE:server>"
            COMMENT "Signing server executable for Windows Smart App Control"
        )
        add_custom_command(TARGET test_alignment POST_BUILD
            COMMAND "${SIGNTOOL_EXECUTABLE}" sign /fd SHA256 /sha1 E2470CC034C0EF476291AFFF256A2C5FE6D51001 "$<TARGET_FILE:test_alignment>"
            COMMENT "Signing test_alignment executable for Windows Smart App Control"
        )
    endif()
endif()

enable_testing()
add_test(NAME alignment_unit_tests COMMAND server --test)
