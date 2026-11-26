// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once
#include <QCoreApplication>
#include <QDir>
#include <QFile>
#include <QProcess>
#include <QTemporaryDir>
#include <QUuid>
#include <stdexcept>

namespace doro_test
{
inline void require(bool pass, const char *message)
{
    if (!pass)
        throw std::runtime_error(message);
}
struct Child : QProcess {
    ~Child() override
    {
        if (state() != NotRunning) {
            terminate();
            if (!waitForFinished(1000)) {
                kill();
                waitForFinished(1000);
            }
        }
    }
};
inline void isolated(const QString &xvfb, const QStringList &workerArguments, const QString &geometry)
{
    QTemporaryDir temp(QDir::tempPath() + "/doroshell-private-native-XXXXXX");
    require(temp.isValid(), "Cannot create temporary home");
    auto env = QProcessEnvironment::systemEnvironment();
    for (auto key : {"DISPLAY", "DBUS_SESSION_BUS_ADDRESS", "WAYLAND_DISPLAY"})
        env.remove(key);
    env.insert("HOME", temp.path());
    for (auto key : {"XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_CACHE_HOME", "XDG_STATE_HOME", "XDG_RUNTIME_DIR",
                     "TMPDIR"}) {
        auto path = temp.filePath(key);
        require(QDir().mkdir(path) &&
                    QFile::setPermissions(path, QFile::ReadOwner | QFile::WriteOwner | QFile::ExeOwner),
                "Cannot create private directory");
        env.insert(key, path);
    }
    env.insert("XDG_SESSION_TYPE", "x11");
    auto auth = temp.filePath("authority");
    QFile file(auth);
    require(file.open(QIODevice::WriteOnly), "Cannot create Xauthority");
    file.close();
    env.insert("XAUTHORITY", auth);
    const auto cookie = QUuid::createUuid().toString(QUuid::Id128);
    auto addCookie = [&](const QString &display) {
        QProcess tool;
        tool.setProcessEnvironment(env);
        tool.start("xauth", {"-f", auth, "add", display, "MIT-MAGIC-COOKIE-1", cookie});
        require(tool.waitForFinished(5000) && tool.exitCode() == 0, "Cannot authorize test X server");
    };
    addCookie(":0"); // Xvfb reads the cookie before announcing its allocated display number.
    Child server;
    server.setProcessEnvironment(env);
    server.start(xvfb, {"-displayfd", "1", "-screen", "0", geometry, "-nolisten", "tcp", "-auth", auth});
    require(server.waitForReadyRead(5000), "Private Xvfb did not start");
    bool ok = false;
    const auto number = server.readLine().trimmed().toUInt(&ok);
    require(ok, "Invalid Xvfb display number");
    const auto display = ":" + QString::number(number);
    addCookie(display);
    env.insert("DISPLAY", display);
    env.insert("DOROSHELL_TEST_DISPLAY", display);
    Child worker;
    worker.setProcessEnvironment(env);
    worker.setProcessChannelMode(QProcess::ForwardedChannels);
    worker.start("dbus-run-session",
                 QStringList{"--", QCoreApplication::applicationFilePath(), "--worker"} + workerArguments);
    require(worker.waitForFinished(55000) && worker.exitCode() == 0, "Private X11 test failed");
}
} // namespace doro_test
