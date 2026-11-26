# Native display guard

`doroshell-display query` returns the RC2 display snapshot token, compatible rates and
NVIDIA OpenGL VSync availability as JSON. The desktop preferences widget sends the
selected output, mode ID, optional VSync value and token to `doroshell-display apply JSON`.
The guard asks for confirmation on standard output and accepts `keep` followed by a
newline on standard input. It owns the 15-second timer and rollback independently
of the widget. Keep, rollback and external-change checks compare the complete
protected state. The helper changes the current session and writes no display profile.

The desktop build applies `desktop-helper.patch` after the published Advanced-page
patch, copies the existing widget header into its build tree, and pins the SHA-256
of the companion native executable. The patched widget checks the digest and seals
a private executable copy before launching it. Rebuild the desktop after changing
or stripping that executable. The helper requires Qt Core, xrandr, a private runtime
directory and an X11 session. NVIDIA's nvidia-settings is optional.

The default CTest checks snapshot compatibility, rate eligibility, partial-state
rejection and redacted diagnostics. Set `DOROSHELL_DISPLAY_XVFB` to an Xvfb executable
to enable a private RandR integration test on three programmable modes. It exercises
the timeout, Keep, Revert, incomplete input, UI pipe closure, SIGTERM, lock contention,
and refusal to overwrite a mode changed elsewhere. It supplies a local C++ fixture
for NVIDIA VSync. Set `DOROSHELL_PATCHED_DISPLAY_INCLUDE` to the prepared PCManFM
`pcmanfm/` directory to exercise the real widget's native launch and digest refusal
offscreen. These tests do not require a physical display.
