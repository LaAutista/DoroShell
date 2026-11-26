# Build the reviewed LXQt sources under the build tree. Upstream installation
# contains absolute /etc entries; only copy the staged private prefix back.
include(ExternalProject)
find_package(PkgConfig REQUIRED)
pkg_check_modules(SYSTEM_LXQT REQUIRED lxqt)
if(SYSTEM_LXQT_VERSION MATCHES "^2\\.5\\.")
    set(tools_rev ca90f9b0c5eedc3ab89d4031811dff833392bf3b)
elseif(SYSTEM_LXQT_VERSION MATCHES "^2\\.4\\.")
    set(tools_rev 0f56cd400d2afcb6f16d4ca88538ed716439c2c2)
else()
    message(FATAL_ERROR "The panel patch set supports liblxqt 2.4 and 2.5")
endif()
find_package(Git REQUIRED)
set(private "${CMAKE_CURRENT_BINARY_DIR}/runtime")
set(tools "${CMAKE_CURRENT_BINARY_DIR}/tools")
ExternalProject_Add(doroshell-lxqt-tools
    GIT_REPOSITORY https://github.com/lxqt/lxqt-build-tools.git
    GIT_TAG ${tools_rev} UPDATE_DISCONNECTED TRUE EXCLUDE_FROM_ALL TRUE
    CMAKE_ARGS "-DCMAKE_INSTALL_PREFIX=${tools}"
    BUILD_COMMAND "${CMAKE_COMMAND}" --build <BINARY_DIR> --parallel 3)
set(patchdir "${PROJECT_SOURCE_DIR}/panel/patches")
file(GLOB patches CONFIGURE_DEPENDS "${patchdir}/*.patch")
list(SORT patches)
list(LENGTH patches count)
if(NOT count EQUAL 16)
    message(FATAL_ERROR "Review the panel patch inventory before building")
endif()
set(patch_key "")
foreach(patch IN LISTS patches)
    file(SHA256 "${patch}" digest)
    string(APPEND patch_key "${digest}")
    set_property(DIRECTORY APPEND PROPERTY CMAKE_CONFIGURE_DEPENDS "${patch}")
endforeach()
string(SHA256 patch_key "${patch_key}")
ExternalProject_Add(doroshell-panel
    PREFIX "${CMAKE_CURRENT_BINARY_DIR}/panel-${patch_key}"
    GIT_REPOSITORY https://github.com/lxqt/lxqt-panel.git
    GIT_TAG cffb0cd29c6ce0360356006ce727a9b01347e062
    UPDATE_DISCONNECTED TRUE EXCLUDE_FROM_ALL TRUE
    DEPENDS doroshell-lxqt-tools
    PATCH_COMMAND "${CMAKE_COMMAND}" "-DGIT=${GIT_EXECUTABLE}" "-DPATCH_DIR=${patchdir}"
        -P "${CMAKE_CURRENT_SOURCE_DIR}/apply-panel.cmake"
    CMAKE_ARGS "-DCMAKE_PREFIX_PATH=${tools}" "-DCMAKE_INSTALL_PREFIX=${private}"
    BUILD_COMMAND "${CMAKE_COMMAND}" --build <BINARY_DIR> --parallel 4
    INSTALL_COMMAND "${CMAKE_COMMAND}" -E env "DESTDIR=${CMAKE_CURRENT_BINARY_DIR}/stage"
        "${CMAKE_COMMAND}" --install <BINARY_DIR>
    COMMAND "${CMAKE_COMMAND}" -E copy_directory "${CMAKE_CURRENT_BINARY_DIR}/stage${private}" "${private}"
    COMMAND "${CMAKE_COMMAND}" -E copy_directory "${PROJECT_SOURCE_DIR}/panel/licenses" "${private}/share/doroshell-panel/licenses"
    COMMAND "${CMAKE_COMMAND}" -E copy_directory "${patchdir}" "${private}/share/doroshell-panel/patches")
ExternalProject_Add_Step(doroshell-panel patch_inputs DEPENDEES update DEPENDERS patch
    DEPENDS ${patches} "${CMAKE_CURRENT_SOURCE_DIR}/apply-panel.cmake" INDEPENDENT TRUE)

# Optional native PCManFM desktop and LXQt input preferences. Both forks need
# private build-tools. Plugins and system data continue to use distro paths.
function(doro_upstream_app kind repo revision target bindir helper)
    set(work "${CMAKE_CURRENT_BINARY_DIR}/${kind}")
    set(extra_args)
    if(kind STREQUAL "input")
        foreach(component APPEARANCE BRIGHTNESS FILE_ASSOCIATIONS LOCALE MONITOR)
            list(APPEND extra_args "-DWITH_${component}=OFF")
        endforeach()
        set(inputs "${PROJECT_SOURCE_DIR}/input/unified-pointer.patch" "${CMAKE_CURRENT_SOURCE_DIR}/input-helper.patch")
    else()
        file(GLOB inputs CONFIGURE_DEPENDS "${PROJECT_SOURCE_DIR}/wallpaper/*.h" "${PROJECT_SOURCE_DIR}/wallpaper/*.cpp")
        list(APPEND inputs "${PROJECT_SOURCE_DIR}/wallpaper/desktop-video.patch" "${PROJECT_SOURCE_DIR}/display/dorodisplaycontrols.h"
            "${PROJECT_SOURCE_DIR}/display/pcmanfm-advanced.patch" "${PROJECT_SOURCE_DIR}/native/display/desktop-helper.patch"
            "${CMAKE_CURRENT_SOURCE_DIR}/wallpaper-preferences.patch")
    endif()
    ExternalProject_Add(doroshell-${kind}-build
        GIT_REPOSITORY "https://github.com/lxqt/${repo}.git" GIT_TAG ${revision}
        UPDATE_DISCONNECTED TRUE EXCLUDE_FROM_ALL TRUE
        DEPENDS doroshell-lxqt-tools ${helper}
        PATCH_COMMAND ""
        CONFIGURE_COMMAND "${CMAKE_COMMAND}" -S "${work}/prepared" -B <BINARY_DIR> -G "${CMAKE_GENERATOR}"
            "-DCMAKE_PREFIX_PATH=${tools}" "-DCMAKE_INSTALL_PREFIX=/usr" ${extra_args}
        BUILD_COMMAND "${CMAKE_COMMAND}" --build <BINARY_DIR> --target ${target} --parallel 4
        INSTALL_COMMAND "${CMAKE_COMMAND}" -E copy_if_different "<BINARY_DIR>/${bindir}/${target}" "${private}/bin/${target}"
        COMMAND "${CMAKE_COMMAND}" -E copy_if_different "$<TARGET_FILE:${helper}>" "${private}/bin/${helper}")
    ExternalProject_Add_Step(doroshell-${kind}-build prepare_sources DEPENDEES patch DEPENDERS configure
        COMMAND "${CMAKE_COMMAND}" "-DWORK=${work}" "-DUPSTREAM=<SOURCE_DIR>" "-DROOT=${PROJECT_SOURCE_DIR}"
            "-DHELPER=$<TARGET_FILE:${helper}>" "-DKIND=${kind}" "-DGIT=${GIT_EXECUTABLE}" -P "${CMAKE_CURRENT_SOURCE_DIR}/prepare.cmake"
        DEPENDS ${inputs} "${CMAKE_CURRENT_SOURCE_DIR}/prepare.cmake" "$<TARGET_FILE:${helper}>")
    if(kind STREQUAL "desktop")
        ExternalProject_Add_Step(doroshell-desktop-build worker DEPENDEES install
            COMMAND "${CMAKE_COMMAND}" -E copy_if_different "<BINARY_DIR>/pcmanfm/doroshell-video-worker" "${private}/bin/doroshell-video-worker")
    endif()
endfunction()
file(MAKE_DIRECTORY "${private}/bin")
if(SYSTEM_LXQT_VERSION MATCHES "^2\\.5\\.")
    set(pcmanfm_rev f4be744f07d929228fcdcf0232fd3bf4d2879910)
    set(input_rev 41ad5aa1f052204979993117ca3b6b36fe72d919)
else()
    set(pcmanfm_rev 8c4715a327170c20e7d7f3088e9cdc29ca485ba0)
    set(input_rev f8a164838afbc09db6e1962392b96f82eb779887)
endif()
doro_upstream_app(desktop pcmanfm-qt ${pcmanfm_rev} pcmanfm-qt pcmanfm doroshell-display)
if(TARGET doroshell-input-preferences)
    doro_upstream_app(input lxqt-config ${input_rev} lxqt-config-input lxqt-config-input doroshell-input-preferences)
endif()

set(import_patch "${PROJECT_SOURCE_DIR}/screengrab/import-png.patch")
set_property(DIRECTORY APPEND PROPERTY CMAKE_CONFIGURE_DEPENDS "${import_patch}")
file(SHA256 "${import_patch}" import_digest)
ExternalProject_Add(doroshell-screengrab-build
    PREFIX "${CMAKE_CURRENT_BINARY_DIR}/screengrab-${import_digest}"
    GIT_REPOSITORY https://github.com/lxqt/screengrab.git
    GIT_TAG 1fc2d35a4449706de9a2c279d6c5f79c5fbcd883
    UPDATE_DISCONNECTED TRUE EXCLUDE_FROM_ALL TRUE
    DEPENDS doroshell-lxqt-tools
    PATCH_COMMAND "${GIT_EXECUTABLE}" apply "${import_patch}"
    CMAKE_ARGS "-DCMAKE_PREFIX_PATH=${tools}" "-DCMAKE_INSTALL_PREFIX=/usr"
    BUILD_COMMAND "${CMAKE_COMMAND}" --build <BINARY_DIR> --target screengrab --parallel 4
    INSTALL_COMMAND "${CMAKE_COMMAND}" -E copy_if_different "<BINARY_DIR>/screengrab" "${private}/bin/doroshell-screengrab-import")
