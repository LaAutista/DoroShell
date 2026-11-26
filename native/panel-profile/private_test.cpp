// SPDX-License-Identifier: GPL-2.0-or-later
#include "../testing/private_x11.hpp"
#include "../setup/files.hpp"
#include <QElapsedTimer>
#include <QThread>
#include <xcb/xcb.h>
#include <cstring>
#include <memory>

namespace
{
using doro_test::require;
template <class T> auto owned(T *p) { return std::unique_ptr<T, decltype(&std::free)>(p, std::free); }

void exercise(const QString &helper, const QString &binary)
{
    auto home = QDir::homePath();
    require(QDir::home().dirName().startsWith("doroshell-private-native-") && !qgetenv("DISPLAY").isEmpty() &&
                qgetenv("DISPLAY") == qgetenv("DOROSHELL_TEST_DISPLAY"),
            "Private X server required");
    qputenv("XDG_CONFIG_HOME", QFile::encodeName(home + "/.config"));
    qputenv("XDG_STATE_HOME", QFile::encodeName(home + "/.local/state"));
    qputenv("XDG_DATA_HOME", QFile::encodeName(home + "/.local/share"));
    qputenv("XDG_CONFIG_DIRS", "/etc/xdg");
    qputenv("DBUS_SYSTEM_BUS_ADDRESS", QFile::encodeName("unix:path=" + home + "/no-system-bus"));
    qputenv("QT_QPA_PLATFORM", "xcb");
    for (auto id : {"lxqt-comfort.desktop", "doroshell-network.desktop"})
        doro_files::atomic(home + "/.local/share/applications/" + id,
                           "[Desktop Entry]\nType=Application\nName=Fixture\nExec=/usr/bin/true\n", 0644);
    auto run = [&](QStringList args) {
        require(QProcess::execute(helper, args) == 0, "Staging command failed");
    };
    run({"--apply", "--binary", binary});
    std::unique_ptr<xcb_connection_t, decltype(&xcb_disconnect)> conn(xcb_connect(nullptr, nullptr),
                                                                      xcb_disconnect);
    auto *c = conn.get();
    require(!xcb_connection_has_error(c), "Private X connection failed");
    auto root = xcb_setup_roots_iterator(xcb_get_setup(c)).data->root;
    auto atom = [&](const char *name) {
        auto r = owned(xcb_intern_atom_reply(c, xcb_intern_atom(c, false, std::strlen(name), name), nullptr));
        require(bool(r), "Missing atom");
        return r->atom;
    };
    auto values = [&](xcb_window_t w, xcb_atom_t key) {
        QList<uint32_t> result;
        auto r = owned(
            xcb_get_property_reply(c, xcb_get_property(c, false, w, key, XCB_ATOM_ANY, 0, 1024), nullptr));
        if (r && r->format == 32) {
            const auto *v = static_cast<uint32_t *>(xcb_get_property_value(r.get()));
            for (uint32_t i = 0; i < r->value_len; ++i)
                result << v[i];
        }
        return result;
    };
    doro_test::Child wm;
    wm.start("openbox", {"--sm-disable", "--config-file", "/etc/xdg/openbox/rc.xml"});
    auto wait = [&](auto check, const char *error) {
        QElapsedTimer t;
        t.start();
        while (!check()) {
            require(t.elapsed() < 10000, error);
            QThread::msleep(35);
        }
    };
    const auto wmCheck = atom("_NET_SUPPORTING_WM_CHECK");
    wait([&] { return !values(root, wmCheck).isEmpty(); }, "Private Openbox did not start");
    auto checkLaunch = [&](const QString &expected, bool custom) {
        doro_test::Child panel;
        panel.start(helper, {"--launch"});
        require(panel.waitForStarted(3000), "Cannot launch staged panel");
        const auto pid = panel.processId();
        const auto clients = atom("_NET_CLIENT_LIST"), type = atom("_NET_WM_WINDOW_TYPE"),
                   dock = atom("_NET_WM_WINDOW_TYPE_DOCK"), wmPid = atom("_NET_WM_PID");
        wait(
            [&] {
                for (auto w : values(root, clients))
                    if (values(w, type).contains(dock) && values(w, wmPid).contains(uint32_t(pid)))
                        return true;
                require(panel.state() != QProcess::NotRunning, "Private panel exited prematurely");
                return false;
            },
            "Private panel dock window not mapped");
        require(QFileInfo("/proc/" + QString::number(pid) + "/exe").canonicalFilePath() ==
                    QFileInfo(expected).canonicalFilePath(),
                "Wrong panel executable selected");
        QFile cmd("/proc/" + QString::number(pid) + "/cmdline");
        require(cmd.open(QIODevice::ReadOnly), "Cannot inspect panel arguments");
        auto args = cmd.readAll().split('\0');
        if (custom)
            require(args.value(1) == "--config" &&
                        args.value(2) == QFile::encodeName(home + "/.config/doroshell/panel.conf"),
                    "Missing private panel config option");
        else
            require(args.size() == 2 && args.last().isEmpty(), "Fallback received an unexpected config option");
        panel.terminate();
        require(panel.waitForFinished(4000), "Private panel shutdown timed out");
    };
    checkLaunch(binary, true);
    run({"--undo", "--keep-panel-edits"});
    require(!QFile::exists(home + "/.config/autostart/lxqt-panel.desktop") &&
                !QFile::exists(home + "/.config/lxqt/panel.conf"),
            "Rollback left a selected panel");
    auto copy = home + "/candidate/bin/lxqt-panel";
    doro_files::makeParents(copy);
    require(QFile::copy(binary, copy), "Cannot prepare disposable native binary");
    doro_files::atomic(home + "/candidate/share/doroshell-panel/patches/0016-network-chooser.patch", "fixture",
                       0644);
    run({"--apply", "--binary", copy});
    require(QFile::remove(copy), "Cannot remove disposable native binary");
    checkLaunch("/usr/bin/lxqt-panel", false);
    run({"--undo", "--keep-panel-edits"});
}
} // namespace
int main(int argc, char **argv)
{
    QCoreApplication app(argc, argv);
    try {
        require(argc == 4, "Specify Xvfb, panel-profile and patched panel executable");
        auto args = app.arguments();
        if (args[1] == "--worker")
            exercise(args[2], args[3]);
        else
            doro_test::isolated(args[1], args.mid(2), "1024x768x24");
        return 0;
    } catch (const std::exception &e) {
        std::fprintf(stderr, "%s\n", e.what());
        return 1;
    }
}
