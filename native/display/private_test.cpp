// SPDX-License-Identifier: GPL-2.0-or-later
#include "../testing/private_x11.hpp"
#include <QElapsedTimer>
#include <QJsonDocument>
#include <QJsonObject>
#include <QJsonArray>
#include <QStandardPaths>
#include <xcb/xcb.h>
#include <memory>
#include <cstdio>
#include <fcntl.h>
#include <poll.h>
#include <unistd.h>

namespace
{
using namespace doro_test;

QByteArray execute(QString cmd, QStringList args)
{
    QProcess p;
    p.start(cmd, args);
    require(p.waitForFinished(8000) && p.exitStatus() == QProcess::NormalExit && p.exitCode() == 0,
            "Fixture command failed");
    return p.readAllStandardOutput();
}
QJsonObject line(QProcess &p)
{
    QElapsedTimer t;
    t.start();
    while (!p.canReadLine() && t.elapsed() < 7000 && p.waitForReadyRead(int(7000 - t.elapsed()))) {
    }
    auto result = QJsonDocument::fromJson(p.readLine());
    require(result.isObject(), "Missing guard message");
    return result.object();
}
int mockNvidia(const QStringList &args)
{
    QFile file(QDir::home().filePath("private-nvidia-setting"));
    if (args == QStringList{"-t", "-q", "[screen:0]/SyncToVBlank"}) {
        if (!file.open(QIODevice::ReadOnly))
            return 1;
        const auto data = file.readAll();
        std::fwrite(data.constData(), 1, data.size(), stdout);
        return 0;
    }
    if (args.size() != 2 || args.first() != "-a" || !args.last().startsWith("[screen:0]/SyncToVBlank="))
        return 1;
    const auto value = args.last().section('=', -1).toLatin1();
    if ((value != "1" && value != "0") || !file.open(QIODevice::WriteOnly | QIODevice::Truncate))
        return 1;
    return file.write(value) == value.size() ? 0 : 1;
}

void exercise(const QString &binary)
{
    require(QDir::home().dirName().startsWith("doroshell-private-native-") && !qgetenv("DISPLAY").isEmpty() &&
                qgetenv("DISPLAY") == qgetenv("DOROSHELL_TEST_DISPLAY"),
            "Private display required");
    std::unique_ptr<xcb_connection_t, decltype(&xcb_disconnect)> connection(xcb_connect(nullptr, nullptr),
                                                                            xcb_disconnect);
    require(!xcb_connection_has_error(connection.get()), "Private RandR display unavailable");
    QString xrandr = QStandardPaths::findExecutable("xrandr");
    QString bin = QDir::home().filePath("tools");
    require(QDir().mkdir(bin) && QFile::link(xrandr, bin + "/xrandr") &&
                QFile::link(QCoreApplication::applicationFilePath(), bin + "/nvidia-settings"),
            "Cannot prepare private command path");
    auto legacy = qEnvironmentVariable("DOROSHELL_DISPLAY_REFERENCE");
    const auto python = QStandardPaths::findExecutable("python3");
    qputenv("PATH", QFile::encodeName(bin)); // No host NVIDIA tools are reachable.
    require(mockNvidia({"-a", "[screen:0]/SyncToVBlank=1"}) == 0, "Cannot initialize VSync fixture");
    for (const auto &[name, clock, vtotal] : {std::tuple{"audit-60", "241.500", "1481"},
                                              {"audit-480", "2414.000", "1849"},
                                              {"audit-120", "483.000", "1481"}}) {
        execute(xrandr, {"--newmode", name, clock, "2560", "2608", "2640", "2720", "1440", "1443", "1448",
                         vtotal, "+hsync", "-vsync"});
        execute(xrandr, {"--addmode", "screen", name});
    }
    execute(xrandr, {"--output", "screen", "--mode", "audit-480"});
    auto query = [&] { return QJsonDocument::fromJson(execute(binary, {"query"})).object(); };
    const auto initial = query();
    if (!legacy.isEmpty())
        require(initial == QJsonDocument::fromJson(execute(python, {legacy, "query"})).object(),
                "Private display projection/token differs from RC2");
    auto output = [](const QJsonObject &s) { return s["outputs"].toArray().at(0).toObject(); };
    auto modes = output(initial)["modes"].toArray();
    QMap<QString, QString> ids;
    for (const auto &m : modes)
        ids[m.toObject()["name"].toString()] = m.toObject()["id"].toString();
    require(output(initial)["current"] == ids["audit-480"] && initial["vsync"] == 1,
            "Incorrect initial snapshot");
    for (QByteArray action :
         {"keep", "revert", "partial", "timeout", "ui-closed", "terminate", "external-mode"}) {
        const auto before = query();
        auto target = (output(before)["current"] == ids["audit-480"]) ? ids["audit-60"] : ids["audit-480"];
        QJsonObject request{{"token", before["token"]},
                            {"output", "screen"},
                            {"mode", target},
                            {"vsync", 1 - before["vsync"].toInt()}};
        const auto json = QString::fromUtf8(QJsonDocument(request).toJson(QJsonDocument::Compact));
        Child guard;
        int pipeFds[2]{-1, -1};
        if (action == "ui-closed") {
            require(pipe2(pipeFds, O_CLOEXEC) == 0, "Cannot create UI output pipe");
            guard.setChildProcessModifier([writer = pipeFds[1]] {
                if (dup2(writer, STDOUT_FILENO) < 0)
                    _exit(126);
            });
        }
        guard.start(binary, {"apply", json});
        QJsonObject pending;
        if (action == "ui-closed") {
            require(guard.waitForStarted(3000), "Cannot start guard with UI pipes");
            close(pipeFds[1]);
            pollfd ready{pipeFds[0], POLLIN, 0};
            require(poll(&ready, 1, 6000) == 1, "Missing pending message on UI pipe");
            char buf[1024];
            auto n = read(pipeFds[0], buf, sizeof(buf));
            require(n > 0, "UI pipe read failed");
            pending = QJsonDocument::fromJson(QByteArray(buf, n)).object();
            close(pipeFds[0]); // Forces EPIPE on the final message.
        } else
            pending = line(guard);
        require(pending["pending"].toBool(), "Guard refused valid change");
        const auto applied = query();
        require(output(applied)["current"] == target && applied["vsync"] == request["vsync"],
                "Requested rate or VSync not applied");
        if (action == "keep") {
            Child contending;
            contending.start(binary, {"apply", json});
            require(contending.waitForFinished(3000) && contending.exitCode() != 0 &&
                        contending.readAllStandardOutput().contains("Another display confirmation"),
                    "Concurrent display transaction accepted");
        }
        if (action == "external-mode")
            execute(xrandr, {"--output", "screen", "--mode", ids["audit-120"]});
        else if (action == "ui-closed")
            guard.closeWriteChannel();
        else if (action == "terminate")
            guard.terminate();
        else if (action != "timeout") {
            guard.write(action == "partial" ? QByteArray("kee") : action + '\n');
            require(guard.waitForBytesWritten(1000), "Could not answer guard");
        }
        require(guard.waitForFinished(22000), "Guard did not return");
        const auto after = query();
        if (action == "external-mode") {
            const auto terminal = line(guard);
            require(guard.exitCode() != 0 && terminal.contains("error") &&
                        !terminal["diagnostics"].toArray().isEmpty() &&
                        output(after)["current"] == ids["audit-120"] && after["vsync"] == before["vsync"],
                    "Guard overwrote external edit or failed to recover VSync");
        } else {
            require(guard.exitCode() == 0 && after == (action == "keep" ? applied : before),
                    "Terminal state differs from expected state");
            if (action != "ui-closed") {
                const auto msg = line(guard);
                require(msg.value("done").toBool() && msg["kept"].toBool() == (action == "keep"),
                        "Incorrect guard completion message");
            }
        }
    }
}
} // namespace

int main(int argc, char **argv)
{
    QCoreApplication app(argc, argv);
    try {
        if (QFileInfo(QString::fromLocal8Bit(argv[0])).fileName() == "nvidia-settings")
            return mockNvidia(app.arguments().mid(1));
        doro_test::require(argc == 3, "Specify Xvfb and guard paths");
        auto args = app.arguments();
        if (args.at(1) == "--worker")
            exercise(args.at(2));
        else
            doro_test::isolated(args.at(1), {args.at(2)}, "2560x1440x24");
        return 0;
    } catch (const std::exception &e) {
        std::fprintf(stderr, "%s\n", e.what());
        return 1;
    }
}
