// SPDX-License-Identifier: GPL-2.0-or-later
#include "snap.hpp"

#include <QCoreApplication>
#include <QLocalServer>
#include <QLocalSocket>
#include <QLockFile>
#include <QStandardPaths>
#include <QTimer>
#include <cstdio>
#include <unistd.h>

namespace
{
std::optional<Action> side(const QByteArray &command)
{
    if (command == "left")
        return Action::Left;
    if (command == "right")
        return Action::Right;
    if (command == "restore")
        return Action::Restore;
    return std::nullopt;
}

bool sendToOwner(const QString &name, const QByteArray &command)
{
    QLocalSocket client;
    client.connectToServer(name);
    if (!client.waitForConnected(200))
        return false;
    if (client.write(command) != command.size() || !client.waitForBytesWritten(500))
        throw std::runtime_error("Cannot send command to snapping service");
    client.disconnectFromServer();
    return true;
}

int run(QCoreApplication &app, const QByteArray &command)
{
    if (qEnvironmentVariable("XDG_SESSION_TYPE", "x11") != "x11")
        throw std::runtime_error("Openbox/X11 required");
    if (command != "serve" && command != "stop" && !side(command))
        throw std::runtime_error("Choose serve, left, right, restore or stop");
    const QString name = QStringLiteral("doroshell-snap-") + QString::number(getuid());
    if (sendToOwner(name, command) || command == "stop")
        return 0;
    if (auto action = side(command)) {
        Snap snap;
        snap.apply(*action);
        return 0;
    }

    const auto runtime = QStandardPaths::writableLocation(QStandardPaths::RuntimeLocation);
    if (runtime.isEmpty())
        throw std::runtime_error("Cannot find runtime directory");
    QLockFile lock(runtime + "/" + name + ".lock");
    if (!lock.tryLock(0)) {
        if (lock.error() == QLockFile::LockFailedError)
            return 0;
        throw std::runtime_error("Cannot lock snapping service");
    }
    if (sendToOwner(name, command))
        return 0;
    Snap snap;
    QLocalServer server;
    server.setSocketOptions(QLocalServer::UserAccessOption);
    QLocalServer::removeServer(name);
    if (!server.listen(name))
        throw std::runtime_error(server.errorString().toStdString());
    QObject::connect(&server, &QLocalServer::newConnection, &app, [&] {
        while (auto *client = server.nextPendingConnection()) {
            client->setReadBufferSize(32);
            // Legacy clients send one command and close without a delimiter.
            auto consume = [client, &snap, &app] {
                auto request = client->readAll();
                if (auto action = side(request))
                    snap.apply(*action);
                if (request == "stop")
                    app.quit();
                client->deleteLater();
            };
            QObject::connect(client, &QLocalSocket::disconnected, client, consume);
            if (client->state() == QLocalSocket::UnconnectedState)
                consume();
        }
    });
    QTimer timer;
    QObject::connect(&timer, &QTimer::timeout, &app, [&snap] { snap.poll(); });
    timer.start(30);
    return app.exec();
}
} // namespace

int main(int argc, char **argv)
{
    QCoreApplication app(argc, argv);
    try {
        if (argc > 2)
            throw std::runtime_error("Choose serve, left, right, restore or stop");
        return run(app, argc == 2 ? argv[1] : "serve");
    } catch (const std::exception &e) {
        std::fprintf(stderr, "%s\n", e.what());
        return 1;
    }
}
