# SPDX-License-Identifier: MIT

add_library(hagoromo_cosserat SHARED
    src/c_api.cpp
    src/cuda_solver.cu
)

target_include_directories(hagoromo_cosserat
    PUBLIC
        ${CMAKE_CURRENT_SOURCE_DIR}/include
    PRIVATE
        ${CMAKE_CURRENT_SOURCE_DIR}/src
)

target_compile_features(hagoromo_cosserat PUBLIC cxx_std_20)
target_compile_definitions(hagoromo_cosserat PRIVATE HSC_BUILD_DLL)
set_target_properties(hagoromo_cosserat PROPERTIES
    CUDA_STANDARD 20
    CUDA_STANDARD_REQUIRED ON
    CUDA_RUNTIME_LIBRARY Static
    CUDA_ARCHITECTURES "75;80;86;89;90;100;120"
    MSVC_RUNTIME_LIBRARY "MultiThreaded$<$<CONFIG:Debug>:Debug>"
)

if(MSVC)
    target_compile_options(hagoromo_cosserat PRIVATE
        $<$<COMPILE_LANGUAGE:CXX>:/W4;/permissive-;/EHsc;/utf-8>
    )
else()
    target_compile_options(hagoromo_cosserat PRIVATE -Wall -Wextra -Wpedantic)
endif()

set_target_properties(hagoromo_cosserat PROPERTIES
    OUTPUT_NAME "hagoromo_cosserat"
    RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin"
    LIBRARY_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin"
    ARCHIVE_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/lib"
)

install(TARGETS hagoromo_cosserat
    RUNTIME DESTINATION bin
    LIBRARY DESTINATION bin
)

if(BUILD_TESTING)
    add_executable(hagoromo_cosserat_tests tests/test_solver.cpp)
    target_link_libraries(hagoromo_cosserat_tests PRIVATE hagoromo_cosserat)
    target_compile_features(hagoromo_cosserat_tests PRIVATE cxx_std_20)
    if(MSVC)
        target_compile_options(hagoromo_cosserat_tests PRIVATE /W4 /permissive- /EHsc /utf-8)
    else()
        target_compile_options(hagoromo_cosserat_tests PRIVATE -Wall -Wextra -Wpedantic)
    endif()
    set_target_properties(hagoromo_cosserat_tests PROPERTIES
        RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin"
        MSVC_RUNTIME_LIBRARY "MultiThreaded$<$<CONFIG:Debug>:Debug>"
    )
    add_test(NAME hagoromo_cosserat_tests COMMAND hagoromo_cosserat_tests)
endif()
