# RumbleRecomp: llvm-mingw clang toolchain settings for building ModernGekko/Dolphin on Windows.
# Usage: cmake -DCMAKE_TOOLCHAIN_FILE=tools/toolchain-llvm-mingw.cmake ...
set(CMAKE_C_COMPILER   clang)
set(CMAKE_CXX_COMPILER clang++)
# llvm-mingw defaults to a pre-Win8 target, which hides Get/SetProcessInformation and CM_* notification APIs.
set(_rr_win10 "-DWINVER=0x0A00 -D_WIN32_WINNT=0x0A00 -DNTDDI_VERSION=0x0A000000")
set(CMAKE_C_FLAGS_INIT   "${_rr_win10}")
set(CMAKE_CXX_FLAGS_INIT "${_rr_win10}")
