# A disposable build copy makes patch preparation repeatable, even after an
# upstream file was touched by several patches. Never reset a working checkout.
file(REMOVE_RECURSE "${WORK}/.preparing")
file(MAKE_DIRECTORY "${WORK}/.preparing")
file(COPY "${UPSTREAM}/" DESTINATION "${WORK}/.preparing" PATTERN ".git" EXCLUDE)
set(dest "${WORK}/.preparing")
if(KIND STREQUAL "desktop")
    set(patches wallpaper/desktop-video.patch display/pcmanfm-advanced.patch native/upstream/wallpaper-preferences.patch)
    foreach(name dorowallpaper.cpp dorowallpaper.h dorovideoworker.cpp dorovideotransport.h dorovideoscale.h dorowallpapercontrols.h)
        file(COPY "${ROOT}/wallpaper/${name}" DESTINATION "${dest}/pcmanfm")
    endforeach()
    file(COPY "${ROOT}/display/dorodisplaycontrols.h" DESTINATION "${dest}/pcmanfm")
    list(APPEND patches native/display/desktop-helper.patch)
elseif(KIND STREQUAL "input")
    set(patches input/unified-pointer.patch native/upstream/input-helper.patch)
else()
    message(FATAL_ERROR "Unknown component")
endif()
foreach(patch IN LISTS patches)
    # This copy has no .git. An enclosing checkout must not change how Git
    # interprets the patch paths (including when building inside a checkout).
    execute_process(COMMAND "${CMAKE_COMMAND}" -E env "GIT_CEILING_DIRECTORIES=${WORK}"
        "${GIT}" apply "${ROOT}/${patch}" WORKING_DIRECTORY "${dest}" COMMAND_ERROR_IS_FATAL ANY)
endforeach()
if(KIND STREQUAL "desktop")
    file(SHA256 "${HELPER}" hash)
    file(APPEND "${dest}/pcmanfm/CMakeLists.txt"
        "\ntarget_compile_definitions(pcmanfm-qt PRIVATE DOROSHELL_DISPLAY_SHA256=\"${hash}\")\n")
endif()
# Only copy modified files on incremental builds, preserving source timestamps.
file(COPY "${dest}/" DESTINATION "${WORK}/prepared")
