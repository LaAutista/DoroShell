add_executable(doroshell-desktop main.cpp)
target_link_libraries(doroshell-desktop PRIVATE Qt6::Core)
install(TARGETS doroshell-desktop)
