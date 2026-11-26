file(GLOB patches "${PATCH_DIR}/*.patch")
list(SORT patches)
# git apply cannot check a whole ordered series against the original source in
# one pass. Use each patch on the state produced by its predecessor.
foreach(patch IN LISTS patches)
    execute_process(COMMAND "${GIT}" apply --reverse --check "${patch}" RESULT_VARIABLE already ERROR_QUIET)
    if(NOT already EQUAL 0)
        execute_process(COMMAND "${GIT}" apply "${patch}" COMMAND_ERROR_IS_FATAL ANY)
    endif()
endforeach()
