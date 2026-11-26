// SPDX-License-Identifier: GPL-2.0-or-later
#include "private_x11.hpp"
#include "../setup/files.hpp"
#include <QElapsedTimer>
#include <QThread>
#include <csignal>
#include <unistd.h>

namespace {
using doro_test::require;
void exercise(const QString &bin) {
    const auto home = QDir::homePath();
    require(QDir(home).dirName().startsWith("doroshell-private-native-") &&
            !qgetenv("DISPLAY").isEmpty() && qgetenv("DISPLAY") == qgetenv("DOROSHELL_TEST_DISPLAY"),
            "A private session is required");
    for (const auto &[var, suffix] : QList<QPair<QByteArray, QString>>{
            {"XDG_CONFIG_HOME", "/.config"}, {"XDG_DATA_HOME", "/.local/share"}, {"XDG_STATE_HOME", "/.local/state"}})
        qputenv(var.constData(), QFile::encodeName(home + suffix));
    qputenv("XDG_CURRENT_DESKTOP", "LXQt");
    qputenv("QT_QPA_PLATFORM", "xcb");
    qputenv("DBUS_SYSTEM_BUS_ADDRESS", QFile::encodeName("unix:path=" + home + "/no-system-bus"));
    qputenv("PULSE_SERVER", QFile::encodeName("unix:" + home + "/no-audio"));
    qunsetenv("SESSION_MANAGER");
    qunsetenv("ICEAUTHORITY");
    qputenv("XDG_CONFIG_DIRS", "/etc/xdg");
    require(!QProcess::execute(bin + "/doroshell-core", {"--apply"}), "Core staging failed");
    // Only launch the desktop entries staged in this home. Exclude the
    // distribution's unrelated power, device and network autostarts.
    auto defaults = home + "/empty-defaults";
    QDir().mkdir(defaults);
    qputenv("XDG_CONFIG_DIRS", QFile::encodeName(defaults));
    doro_files::atomic(home + "/.config/lxqt/session.conf", "[General]\nwindow_manager=openbox\n", 0600);
    doro_test::Child session;
    session.setChildProcessModifier([] { ::setsid(); });
    session.setProcessChannelMode(QProcess::ForwardedChannels);
    session.start("/usr/bin/lxqt-session", QStringList{});
    require(session.waitForStarted(), "Private LXQt session failed to start");
    const pid_t group = session.processId();
    struct Cleanup {
        pid_t group;
        ~Cleanup() { if (group > 1) ::kill(-group, SIGTERM); }
    } cleanup{group};
    QStringList required{"lxqt-panel", "pcmanfm-qt", "doroshell-start", "doroshell-snap"};
    QElapsedTimer time;
    time.start();
    qint64 healthySince = -1;
    while (time.elapsed() < 20000) {
        auto pending = required;
        for (const auto &pid : QDir("/proc").entryList(QDir::Dirs | QDir::NoDotAndDotDot)) {
            bool ok;
            const int n = pid.toInt(&ok);
            if (!ok || n < 2) continue;
            const auto exe = QFileInfo("/proc/" + pid + "/exe").symLinkTarget();
            if (!exe.startsWith(bin + '/')) continue;
            QFile env("/proc/" + pid + "/environ");
            if (!env.open(QIODevice::ReadOnly) || !env.readAll().split('\0').contains("DISPLAY=" + qgetenv("DISPLAY"))) continue;
            pending.removeAll(QFileInfo(exe).fileName());
        }
        if (pending.isEmpty()) {
            if (healthySince < 0) healthySince = time.elapsed();
            if (time.elapsed() - healthySince >= 3000) return;
        } else {
            healthySince = -1;
        }
        if (time.elapsed() > 19500) qWarning() << "Missing from the private session:" << pending;
        if (session.waitForFinished(250)) break;
    }
    throw std::runtime_error("The LXQt session did not start the registered native components");
}
}
int main(int argc, char **argv) {
    QCoreApplication app(argc, argv);
    try {
        const auto args = app.arguments();
        if (args.size() != 3) return 2;
        if (args[1] == "--worker") exercise(args[2]);
        else doro_test::isolated(args[1], {args[2]}, "1024x768x24");
        return 0;
    } catch (const std::exception &e) {
        qCritical("%s", e.what());
        return 1;
    }
}
