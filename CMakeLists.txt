# SPDX-License-Identifier: GPL-3.0-or-later

cmake_minimum_required(VERSION 3.24)

project(hagoromo_cosserat VERSION 0.1.0 LANGUAGES CXX CUDA)

include(CTest)
add_subdirectory(native)
