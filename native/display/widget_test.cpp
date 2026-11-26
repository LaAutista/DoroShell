// SPDX-License-Identifier: GPL-2.0-or-later
#include "dorodisplaycontrols.h"
#include <QApplication>
#include <QElapsedTimer>
#include <QTemporaryDir>
#include <QThread>
#include <cstdio>

int main(int argc, char **argv)
{
    qputenv("QT_QPA_PLATFORM", "offscreen");
    qputenv("XDG_SESSION_TYPE", "wayland"); // Exercises actual execution with no display query.
    qunsetenv("DISPLAY");
    qunsetenv("DBUS_SESSION_BUS_ADDRESS");
    QTemporaryDir home;
    if (!home.isValid() || argc != 2)
        return 1;
    qputenv("HOME", QFile::encodeName(home.path()));
    qputenv("XDG_RUNTIME_DIR", QFile::encodeName(home.path()));
    QApplication app(argc, argv);
    QFile binary(QString::fromLocal8Bit(argv[1]));
    if (!binary.open(QIODevice::ReadOnly))
        return 1;
    const auto sha = QCryptographicHash::hash(binary.readAll(), QCryptographicHash::Sha256).toHex();
    for (bool intact : {true, false}) {
        DoroDisplayControls controls({binary.fileName()}, nullptr, intact ? sha : QByteArray(64, '0'));
        const QString expected = intact ? "These controls require an X11 session" : "missing or changed";
        bool found = false;
        QElapsedTimer timer;
        timer.start();
        while (!found && timer.elapsed() < 5000) {
            app.processEvents();
            for (const auto *label : controls.findChildren<QLabel *>())
                found |= label->text().contains(expected);
            QThread::msleep(10);
        }
        if (!found) {
            for (const auto *label : controls.findChildren<QLabel *>())
                std::fprintf(stderr, "%s\n", qPrintable(label->text()));
            return 1;
        }
    }
    return 0;
}
