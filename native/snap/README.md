# Native window snapping

The C++20 executable uses Qt Core and Network for the event loop and the existing
per-user command socket. XCB and RandR provide window, monitor and panel-strut
geometry. It accepts the RC2 commands `serve`, `left`, `right`, `restore` and
`stop`. Starting it without an argument runs the service. Openbox still owns the
keyboard bindings and actual window moves.

Build and run the optional integration test from this directory:

```sh
cmake -S . -B build -DDOROSHELL_SNAP_XVFB=/usr/bin/Xvfb
cmake --build build
ctest --test-dir build --output-on-failure
```

The test also needs xcb-xtest, xauth, dbus-run-session and Openbox. It starts its
own authenticated X server, bus, temporary home, runtime directory and window
manager. It exercises Super+Left/Right/Down, repeat and restore, drag-to-edge,
window ID reuse including destruction during a drag, unmap/remap, and a partial
panel strut on an odd-width screen.
