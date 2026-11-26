#include "chooser.hpp"
#include <QApplication>
#include <QDBusConnection>
#include <QDBusInterface>
#include <QMessageBox>
int main(int argc, char** argv) {
    QApplication application(argc, argv);
    application.setApplicationName("DoroShell Wi-Fi & Network");
    const QString service = "org.doroshell.NetworkChooser";
    auto bus = QDBusConnection::sessionBus();
    if (bus.isConnected() && !bus.registerService(service)) {
        QDBusInterface previous(service, "/NetworkChooser", service, bus);
        auto result = previous.call("Present");
        if (result.type() == QDBusMessage::ReplyMessage)
            return 0;
        qWarning() << "Unable to open the running network chooser:" << result.errorMessage();
        return 1;
    }
    styleChooser();
    GError* error = nullptr;
    auto client = net::own(nm_client_new(nullptr, &error));
    if (!client) {
        QMessageBox failure(QMessageBox::Critical, "NetworkManager is unavailable",
                            error ? QString::fromUtf8(error->message)
                                  : QString("Could not open NetworkManager."),
                            QMessageBox::Close);
        failure.setTextFormat(Qt::PlainText);
        g_clear_error(&error);
        failure.exec();
        return 1;
    }
    auto chooser = createChooser(client);
    if (bus.isConnected())
        bus.registerObject("/NetworkChooser", chooser.get(), QDBusConnection::ExportScriptableSlots);
    chooser->show();
    return application.exec();
}
