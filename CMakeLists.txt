cmake_minimum_required(VERSION 3.12...3.29.1)

project(VMTK)

# vmtk versions number
set(VMTK_VERSION_MAJOR 1)
set(VMTK_VERSION_MINOR 5)
set(VMTK_VERSION_PATCH 0)
set(VMTK_VERSION
    "${VMTK_VERSION_MAJOR}.${VMTK_VERSION_MINOR}.${VMTK_VERSION_PATCH}")

set(VMTK_CMAKE_DIR ${CMAKE_CURRENT_SOURCE_DIR}/CMake)
add_subdirectory(CMake)
list(INSERT CMAKE_MODULE_PATH 0
  ${VMTK_CMAKE_DIR}
  ${vtkAddon_CMAKE_DIR}
  )

# Append the library version information to the library target properties.
option(VMTK_WITH_LIBRARY_VERSION "Build with library version information" OFF)
if(VMTK_WITH_LIBRARY_VERSION)
  # This setting of SOVERSION assumes that any API change
  # will increment either the minor or major version number of vmtk.
  set(VMTK_LIBRARY_PROPERTIES
      VERSION "${VMTK_VERSION}"
      SOVERSION "${VMTK_VERSION_MAJOR}.${VMTK_VERSION_MINOR}"
     )
endif()

find_package( Python3 COMPONENTS Interpreter )
if (NOT VMTK_PYTHON_VERSION)
  set(VMTK_PYTHON_VERSION "python${PYTHON_VERSION_MAJOR}.${PYTHON_VERSION_MINOR}" CACHE STRING "" FORCE)
endif ()
mark_as_advanced(VMTK_PYTHON_VERSION)

if (APPLE AND VMTK_BREW_PYTHON)
  if(VMTK_BREW_PYTHON)
    option(VMTK_BREW_PYTHON "Link against Homebrew Python" ON)
    set(PYTHON_SHEBANG ${PYTHON_EXECUTABLE})
  else()
    set(PYTHON_SHEBANG "/usr/bin/env python")
  endif()
  #if(VMTK_BREW_PYTHON)
  #  execute_process(
  #    COMMAND /usr/local/bin/python -c "from distutils import sysconfig; print sysconfig.get_python_inc()"
  #    OUTPUT_VARIABLE PYTHON_INCLUDE_DIR
  #    OUTPUT_STRIP_TRAILING_WHITESPACE)
  #  set(PYTHON_LIBRARY ${PYTHON_INCLUDE_DIR}../../lib/lib${VMTK_PYTHON_VERSION}.dylib)
  #endif()
elseif (UNIX)
  set(PYTHON_SHEBANG "/usr/bin/env python")
endif ()

option( VMTK_USE_X
  "Compile vmtk with X11." OFF )
if( VMTK_USE_X )
  set ( VTK_USE_X ON CACHE BOOL "" FORCE )
else ()
  set ( VTK_USE_X OFF CACHE BOOL "" FORCE )
endif()

#-----------------------------------------------------------------------------
# Feature gating (dependency-minimized defaults)
# Keep these disabled by default to avoid hard dependencies on ITK, OpenGL
# rendering modules, and TetGen.
set(VMTK_ENABLE_SEGMENTATION OFF CACHE BOOL
  "Build VMTK segmentation classes (requires ITK)." FORCE)
set(VMTK_USE_RENDERING OFF CACHE BOOL
  "Build VMTK rendering classes." FORCE)
set(VMTK_BUILD_TETGEN OFF CACHE BOOL
  "Build TetGen and TetGen wrapper. Check TetGen license before you activate this." FORCE)

#-----------------------------------------------------------------------------
# Wheel builds (PEP517 via scikit-build-core)
# Keep install locations inside the Python package so users do not need to pass
# install-dir cache variables manually.
if(DEFINED SKBUILD)
  # Python wrapping modules are only generated for shared builds.
  set(BUILD_SHARED_LIBS ON CACHE BOOL "" FORCE)
  # Keep contrib python scripts to maximize compute utilities (numpy converters, etc.).
  set(VMTK_CONTRIB_SCRIPTS ON CACHE BOOL "" FORCE)
  # Install CLI launchers to wheel "scripts" so pip puts them on PATH.
  if(SKBUILD_SCRIPTS_DIR)
    set(VMTK_INSTALL_BIN_DIR "${SKBUILD_SCRIPTS_DIR}" CACHE STRING "" FORCE)
    set(PYPES_INSTALL_BIN_DIR "${SKBUILD_SCRIPTS_DIR}" CACHE STRING "" FORCE)
    set(VMTK_SCRIPTS_INSTALL_BIN_DIR "${SKBUILD_SCRIPTS_DIR}" CACHE STRING "" FORCE)
    set(VTK_VMTK_INSTALL_BIN_DIR "${SKBUILD_SCRIPTS_DIR}" CACHE STRING "" FORCE)
  endif()
  set(VMTK_INSTALL_LIB_DIR "vmtk" CACHE STRING "" FORCE)
  set(VMTK_MODULE_INSTALL_LIB_DIR "vmtk" CACHE STRING "" FORCE)
  set(PYPES_MODULE_INSTALL_LIB_DIR "vmtk" CACHE STRING "" FORCE)
  set(VMTK_SCRIPTS_INSTALL_LIB_DIR "vmtk" CACHE STRING "" FORCE)
  set(VMTK_CONTRIB_SCRIPTS_INSTALL_LIB_DIR "vmtk" CACHE STRING "" FORCE)
  set(VTK_VMTK_INSTALL_LIB_DIR "vmtk" CACHE STRING "" FORCE)
  set(VTK_VMTK_MODULE_INSTALL_LIB_DIR "vmtk" CACHE STRING "" FORCE)
  if(APPLE)
    set(CMAKE_INSTALL_RPATH "@loader_path" CACHE STRING "" FORCE)
  elseif(UNIX)
    set(CMAKE_INSTALL_RPATH "$ORIGIN" CACHE STRING "" FORCE)
  endif()
endif()

# Linux VTK wheels are built with the old libstdc++ ABI. Match it in SKBUILD
# source/wheel builds so vtkvmtk extensions load against vtk==9.5.* reliably.
if(DEFINED SKBUILD AND UNIX AND NOT APPLE)
  set(
    VMTK_GLIBCXX_USE_CXX11_ABI
    "0"
    CACHE STRING
    "Value for _GLIBCXX_USE_CXX11_ABI when building Linux wheels/source installs."
  )
  add_compile_definitions(_GLIBCXX_USE_CXX11_ABI=${VMTK_GLIBCXX_USE_CXX11_ABI})
endif()

#-----------------------------------------------------------------------------
# ITK setup
option( USE_SYSTEM_ITK
  "Exclude ITK from SuperBuild and use an existing build instead." OFF )
if( VMTK_ENABLE_SEGMENTATION AND USE_SYSTEM_ITK )
  find_package( ITK REQUIRED )
  include( ${ITK_USE_FILE} )
endif()

set(VMTK_RENDERING_BACKEND "OpenGL2" CACHE STRING "Graphic backend for VTK")

#-----------------------------------------------------------------------------
# VTK setup
option( USE_SYSTEM_VTK
  "Exclude VTK from SuperBuild and use an existing build instead." OFF )

# For Linux PEP517 source builds, the PyPI vtk runtime wheel does not provide
# vtk-config.cmake. Auto-stage the official wheel SDK when VTK_DIR is not set.
if(DEFINED SKBUILD AND UNIX AND NOT APPLE AND USE_SYSTEM_VTK)
  set(_vmtk_env_vtk_dir "$ENV{VTK_DIR}")
  if(NOT VTK_DIR AND NOT _vmtk_env_vtk_dir)
    set(_vmtk_linux_arch "${CMAKE_SYSTEM_PROCESSOR}")
    if(_vmtk_linux_arch STREQUAL "amd64")
      set(_vmtk_linux_arch "x86_64")
    endif()

    set(_vmtk_linux_sdk_root "$ENV{VMTK_VTK_SDK_ROOT}")
    if(NOT _vmtk_linux_sdk_root)
      set(_vmtk_linux_sdk_root "/tmp/vmtk-vtk-sdk/linux-cp${PYTHON_VERSION_MAJOR}${PYTHON_VERSION_MINOR}-${_vmtk_linux_arch}")
    endif()

    execute_process(
      COMMAND "${Python3_EXECUTABLE}" "${CMAKE_CURRENT_SOURCE_DIR}/tools/prepare_linux_vtk_sdk.py"
              --target-root "${_vmtk_linux_sdk_root}"
      RESULT_VARIABLE _vmtk_prepare_sdk_rc
      OUTPUT_VARIABLE _vmtk_prepare_sdk_out
      ERROR_VARIABLE _vmtk_prepare_sdk_err
    )
    if(NOT _vmtk_prepare_sdk_rc EQUAL 0)
      message(FATAL_ERROR
        "Failed to prepare Linux VTK SDK for source build.\n"
        "stdout:\n${_vmtk_prepare_sdk_out}\n"
        "stderr:\n${_vmtk_prepare_sdk_err}\n"
        "Set VTK_DIR manually to continue."
      )
    endif()

    set(_vmtk_auto_vtk_dir "${_vmtk_linux_sdk_root}/vtk-9.5.0.data/headers/cmake")
    if(NOT EXISTS "${_vmtk_auto_vtk_dir}/vtk-config.cmake")
      message(FATAL_ERROR
        "Linux VTK SDK prepared, but vtk-config.cmake was not found at:\n"
        "  ${_vmtk_auto_vtk_dir}\n"
        "Set VTK_DIR manually."
      )
    endif()

    set(VTK_DIR "${_vmtk_auto_vtk_dir}" CACHE PATH "Auto-detected VTK_DIR for Linux wheel/source build." FORCE)
    list(PREPEND CMAKE_PREFIX_PATH "${_vmtk_linux_sdk_root}")
    message(STATUS "Using auto-prepared Linux VTK SDK root: ${_vmtk_linux_sdk_root}")
  endif()
endif()

if( USE_SYSTEM_VTK )
  find_package( VTK REQUIRED )
  if( ${VTK_VERSION_MAJOR} LESS 6 )
    include( ${VTK_USE_FILE} )
  endif()
endif()

# Superbuild setup
option( VMTK_USE_SUPERBUILD
  "Build VMTK and the projects it depends on via SuperBuild.cmake." ON )

set(VMTK_TEST_DATA_SOURCE "git-submodule" CACHE STRING "git-submodule initializes the vmtk-test-data repository. in-place assumes test data is already available.")
set_property(CACHE VMTK_TEST_DATA_SOURCE PROPERTY STRINGS in-place git-submodule)

# Git setup
if (VMTK_USE_SUPERBUILD OR VMTK_TEST_DATA_SOURCE MATCHES "git-submodule")
  if( NOT GIT_EXECUTABLE )
    find_package( Git REQUIRED )
  endif()

  option( GIT_PROTOCOL_HTTPS
    "Use HTTPS for git access (useful if behind a firewall)" OFF )
  if( GIT_PROTOCOL_HTTPS )
    set( GIT_PROTOCOL "https" CACHE STRING "Https protocol for file transfer" FORCE )
  else()
    set( GIT_PROTOCOL "git" CACHE STRING "Git protocol for file transfer" FORCE )
  endif()
  mark_as_advanced( GIT_PROTOCOL )
endif()

option( VMTK_USE_ITK5
  "Compile vmtk against ITK 5. OFF is ITK 4.13" ON )

option( VMTK_USE_VTK9
  "Compile vmtk against VTK 9. OFF is VTK 8" ON )

if( NOT VMTK_USE_VTK9 )
  message(FATAL_ERROR "This version of VMTK only supports VTK9")
endif()

option( VMTK_BUILD_TESTING
  "Build the VMTK testing libraries" OFF)

if(VMTK_BUILD_TESTING)
  add_subdirectory(tests)
endif()

option( VMTK_BUNJEE_BUILD
  "Build VMTK and the projects it depends on ready for being linked from Bunjee." OFF )

option( BUILD_VMTK_DOCUMENTATION "Build the methods to build doxygen documentation for VMTK locally" OFF )
mark_as_advanced(BUILD_VMTK_DOCUMENTATION)
if(BUILD_VMTK_DOCUMENTATION)
  set(BUILD_DOCUMENTATION ON)
endif()

if( VMTK_USE_SUPERBUILD )
  if( VMTK_BUNJEE_BUILD )
    set ( VTK_VMTK_WRAP_PYTHON OFF CACHE BOOL "" FORCE )
    set ( VMTK_CONTRIB_SCRIPTS OFF CACHE BOOL "" FORCE )
    # set ( VMTK_ENABLE_DISTRIBUTION OFF CACHE BOOL "" FORCE )
    #set ( VMTK_BUILD_TETGEN OFF CACHE BOOL "" FORCE )
    set ( VMTK_SCRIPTS_ENABLED OFF CACHE BOOL "" FORCE )
    set ( BUILD_EXAMPLES OFF CACHE BOOL "" FORCE )
    set ( BUILD_SHARED_LIBS OFF CACHE BOOL "" FORCE )
    # set ( BUILD_TESTING OFF CACHE BOOL "" FORCE )
    set ( VTK_USE_COCOA ON )
    set ( VTK_VMTK_USE_COCOA ON )
    set ( VMTK_USE_RENDERING OFF CACHE BOOL "" FORCE )
    set (  OFF )
    set ( VTK_WRAP_PYTHON OFF )
    set ( VTK_WRAP_TCL OFF )
    set ( CMAKE_OSX_ARCHITECTURES "x86_64" CACHE STRING "" FORCE )
    set ( CMAKE_BUILD_TYPE "Release" CACHE STRING "" FORCE )
    set ( ITK_NO_LIBRARY_VERSION ON )
    set ( VTK_NO_LIBRARY_VERSION ON )
    set ( VMTK_WITH_LIBRARY_VERSION OFF )
    set ( VTK_REQUIRED_OBJCXX_FLAGS "-fobjc-gc" CACHE STRING "" FORCE)
  else ()
    option ( VTK_VMTK_WRAP_PYTHON "Generate Python wrappings for C++ classes." ON )
    if (UNIX)
      set ( VTK_USE_X ON )
    endif ()
    if (APPLE)
      set ( VTK_USE_X OFF )
    endif()
    option ( VMTK_CONTRIB_SCRIPTS "Install modules from the vmtkScripts/contrib directory." OFF )
    option ( VTK_VMTK_CONTRIB "Build and install classes in the vtkVmtk/Contrib directory." OFF )
    # option ( VMTK_ENABLE_DISTRIBUTION "Enable distribution targets." OFF )
    option ( VMTK_BUILD_TETGEN "Build TetGen and TetGen wrapper. Check TetGen license before you activate this." OFF )
    option ( VMTK_BUILD_STREAMTRACER "Build static temporal stream tracer." ON )
    if (APPLE)
      option ( VTK_VMTK_USE_COCOA "Build with Cocoa support." ON )
      set ( CMAKE_OSX_ARCHITECTURES "x86_64" CACHE STRING "" FORCE )
    endif ()
    set ( CMAKE_BUILD_TYPE "Release" CACHE STRING "" FORCE )
    option ( BUILD_SHARED_LIBS "Build shared libraries." ON )
    option ( VMTK_USE_RENDERING "Build VMTK rendering classes." OFF )
    #option ( VTK_USE_HYBRID "Build VTK Hybrid classes." ON )
    option(VMTK_SCRIPTS_ENABLED "Build and install vmtkScripts and Pypes" ON)
    option(VMTK_MINIMAL_INSTALL "Do not install individual scripts, only vmtk.py" OFF)
  endif ()

  include( "${CMAKE_CURRENT_SOURCE_DIR}/SuperBuild.cmake" )
  return()

else()

  if ( VMTK_ENABLE_SEGMENTATION AND NOT ITK_FOUND )
    find_package( ITK REQUIRED )
    include( ${ITK_USE_FILE} )
  endif()

  if ( NOT VTK_FOUND )
    find_package( VTK REQUIRED )
    if( ${VTK_VERSION_MAJOR} LESS 6 )
      include( ${VTK_USE_FILE} )
    endif()
  endif()

endif()

option(VMTK_SCRIPTS_ENABLED "Build and install vmtkScripts and Pypes" ON)
mark_as_advanced(VMTK_SCRIPTS_ENABLED)

if(VMTK_SCRIPTS_ENABLED)
  set(vmtk_directories
    PypeS
    vtkVmtk
    vmtkScripts
    )
else()
  set(vmtk_directories
    vtkVmtk
    )
endif()

foreach(vmtk_directory ${vmtk_directories})
  add_subdirectory(${vmtk_directory})
endforeach()

option(VMTK_MINIMAL_INSTALL "Do not install individual scripts, only vmtk.py" OFF)

set(LIBRARY_OUTPUT_PATH ${VMTK_BINARY_DIR}/bin CACHE PATH
    "Single output directory for building all libraries.")
set(EXECUTABLE_OUTPUT_PATH ${VMTK_BINARY_DIR}/bin CACHE PATH
    "Single output directory for building all executables.")
mark_as_advanced(LIBRARY_OUTPUT_PATH EXECUTABLE_OUTPUT_PATH)

set(VMTK_SRCS
   vmtk.py
   )

set(VMTK_MODULE_SRCS
   __init__.py.in
   )

if(NOT VMTK_INSTALL_BIN_DIR)
  if(DEFINED SKBUILD AND SKBUILD_SCRIPTS_DIR)
    set(VMTK_INSTALL_BIN_DIR "${SKBUILD_SCRIPTS_DIR}")
  else()
    set(VMTK_INSTALL_BIN_DIR bin)
  endif()
endif()

if(NOT VMTK_INSTALL_LIB_DIR)
  set(VMTK_INSTALL_LIB_DIR lib)
endif()

if(NOT VMTK_MODULE_INSTALL_LIB_DIR)
  set(VMTK_MODULE_INSTALL_LIB_DIR ${VMTK_INSTALL_LIB_DIR}/${VMTK_PYTHON_VERSION}/site-packages/vmtk)
endif()

if(VMTK_SCRIPTS_ENABLED)

  foreach (SCRIPT_FILE ${VMTK_SRCS})
    configure_file(${VMTK_SOURCE_DIR}/${SCRIPT_FILE} ${VMTK_BINARY_DIR}/${SCRIPT_FILE} COPYONLY)
  endforeach ()

  configure_file(${VMTK_SOURCE_DIR}/__init__.py.in ${VMTK_BINARY_DIR}/__init__.py COPYONLY)

  install(FILES __init__.py.in
    DESTINATION ${VMTK_MODULE_INSTALL_LIB_DIR}
    COMPONENT PythonRuntimeLibraries
    RENAME __init__.py)

  if (NOT WIN32)

    set (STRIPPED_SCRIPTS_SRCS )

    foreach (SCRIPT_FILE ${VMTK_SRCS})
      configure_file(${VMTK_SOURCE_DIR}/${SCRIPT_FILE} ${VMTK_BINARY_DIR}/${SCRIPT_FILE} COPYONLY)
      string(REGEX REPLACE ".py" "" STRIPPED_SCRIPT_FILE ${SCRIPT_FILE})
      configure_file(${VMTK_SOURCE_DIR}/${SCRIPT_FILE} ${VMTK_BINARY_DIR}/${STRIPPED_SCRIPT_FILE})
      set (STRIPPED_SCRIPTS_SRCS ${STRIPPED_SCRIPTS_SRCS} ${VMTK_BINARY_DIR}/${STRIPPED_SCRIPT_FILE})
    endforeach ()

    install(PROGRAMS ${STRIPPED_SCRIPTS_SRCS}
      DESTINATION ${VMTK_INSTALL_BIN_DIR}
      COMPONENT RuntimeExecutables)

  else ()

    foreach (SCRIPT_FILE ${VMTK_SRCS})
      configure_file(${VMTK_SOURCE_DIR}/${SCRIPT_FILE} ${VMTK_BINARY_DIR}/${SCRIPT_FILE} COPYONLY)
      string(REGEX REPLACE ".py" "-exe.py" STRIPPED_SCRIPT_FILE ${SCRIPT_FILE})
      configure_file(${VMTK_SOURCE_DIR}/${SCRIPT_FILE} ${VMTK_BINARY_DIR}/${STRIPPED_SCRIPT_FILE} COPYONLY)
      set (STRIPPED_SCRIPTS_SRCS ${STRIPPED_SCRIPTS_SRCS} ${VMTK_BINARY_DIR}/${STRIPPED_SCRIPT_FILE})
    endforeach ()

    install(PROGRAMS ${STRIPPED_SCRIPTS_SRCS}
      DESTINATION ${VMTK_INSTALL_BIN_DIR}
      COMPONENT RuntimeExecutables)

  endif ()

  # option(VMTK_ENABLE_DISTRIBUTION "Enable distribution targets." OFF)
  # if(VMTK_ENABLE_DISTRIBUTION)
  #   add_subdirectory(distribution)
  # endif()

  install(EXPORT VMTK-Targets DESTINATION ${VMTK_BINARY_DIR})

  get_property(_wrap_hierarchy_targets GLOBAL PROPERTY VMTK_WRAP_HIERARCHY_TARGETS)
  if(_wrap_hierarchy_targets)
    foreach(target ${_wrap_hierarchy_targets})
      set(VMTK_WRAP_HIERARCHY_FILES_CONFIG
  "${VMTK_WRAP_HIERARCHY_FILES_CONFIG}
  set(${target}_WRAP_HIERARCHY_FILE
    \"${${target}_WRAP_HIERARCHY_FILE}\")"
  )
    endforeach()
  endif()

  configure_file(
    ${VMTK_SOURCE_DIR}/CMake/VMTKConfig.cmake.in
    ${VMTK_BINARY_DIR}/VMTKConfig.cmake
  @ONLY IMMEDIATE
  )
  install(FILES ${VMTK_BINARY_DIR}/VMTKConfig.cmake
    TYPE LIB
  )

  configure_file(
    ${VMTK_SOURCE_DIR}/CMake/VMTKUse.cmake.in
    ${VMTK_BINARY_DIR}/VMTKUse.cmake
  @ONLY IMMEDIATE
  )
  install(FILES ${VMTK_BINARY_DIR}/VMTKUse.cmake
    TYPE LIB
  )

endif()
