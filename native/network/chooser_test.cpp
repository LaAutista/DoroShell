#include "chooser.hpp"
#include <QtWidgets>
#include <QtDBus>
#include <QtTest>

using namespace std::chrono_literals;
namespace {
constexpr auto service = "org.freedesktop.NetworkManager";
constexpr auto mockInterface = "org.freedesktop.DBus.Mock";
class Process : public QProcess {
  public:
    ~Process() {
        if (state() != NotRunning) {
            terminate();
            if (!waitForFinished(2000)) {
                kill();
                waitForFinished();
            }
        }
    }
};
} // namespace
int main(int argc, char** argv) {
    QTemporaryDir home;
    if (!home.isValid())
        return 1;
    Process bus;
    bus.start("dbus-daemon", {"--session", "--nofork", "--print-address=1"});
    if (!bus.waitForStarted() || !bus.waitForReadyRead())
        return 1;
    const auto address = bus.readLine().trimmed();
    if (!address.startsWith("unix:"))
        return 1;
    qputenv("DBUS_SYSTEM_BUS_ADDRESS", address);
    qputenv("DBUS_SESSION_BUS_ADDRESS", address);
    qputenv("QT_QPA_PLATFORM", "offscreen");
    qputenv("HOME", home.path().toUtf8());
    qputenv("XDG_CONFIG_HOME", home.filePath("config").toUtf8());
    qputenv("XDG_RUNTIME_DIR", home.path().toUtf8());
    qunsetenv("DISPLAY");
    qunsetenv("WAYLAND_DISPLAY");
    QApplication app(argc, argv);
    if (QProcess::execute("python", {"-m", "dbusmock", "--help"}) != 0)
        return 77;
    Process mock;
    mock.start("python",
               {"-m", "dbusmock", "--system", "-t", "networkmanager", "-p", "{\"WirelessEnabled\": true}"});
    if (!mock.waitForStarted())
        return 1;
    auto qtbus = QDBusConnection::systemBus();
    if (!QTest::qWaitFor([&] { return qtbus.interface()->isServiceRegistered(service).value(); }, 5s))
        return 1;
    QDBusInterface fixture(service, "/org/freedesktop", mockInterface, qtbus);
    QDBusReply<QString> dev = fixture.call("AddWiFiDevice", "wifi", "wlan0", 30);
    if (!dev.isValid()) {
        qCritical() << dev.error();
        return 1;
    }
    auto reply = fixture.call("AddAccessPoint", dev.value(), "phone", "Phone hotspot", "02:00:00:00:00:01",
                              2u, 2412u, 5400u, QVariant::fromValue(uchar(85)), 0x100u);
    if (reply.type() == QDBusMessage::ErrorMessage) {
        qCritical() << reply;
        return 1;
    }
    GError* error = nullptr;
    auto client = net::own(nm_client_new(nullptr, &error));
    if (!client || !nm_client_get_nm_running(client.get())) {
        g_clear_error(&error);
        return 1;
    }
    styleChooser();
    auto window = createChooser(client);
    window->show();
    auto list = window->findChild<QListWidget*>("wireless");
    auto button = window->findChild<QPushButton*>("primary");
    if (!list || !button || list->count() != 1 || !list->item(0)->text().startsWith("Phone hotspot"))
        return 1;
    list->setCurrentRow(0);
    bool accepted = false;
    QTimer::singleShot(0, [&] {
        auto dialog = qobject_cast<QDialog*>(QApplication::activeModalWidget());
        if (!dialog)
            return;
        auto field = dialog->findChild<QLineEdit*>();
        auto show = dialog->findChild<QCheckBox*>();
        auto ok = dialog->findChild<QPushButton*>("primary");
        if (!field || !show || !ok || field->echoMode() != QLineEdit::Password || ok->isEnabled()) {
            dialog->reject();
            return;
        }
        field->setText("fixture-password");
        show->click();
        if (field->echoMode() != QLineEdit::Normal || !ok->isEnabled()) {
            dialog->reject();
            return;
        }
        accepted = true;
        ok->click();
    });
    button->click();
    if (!accepted ||
        !QTest::qWaitFor([&] { return nm_client_get_active_connections(client.get())->len == 1; }, 5s)) {
        qCritical() << "Secured join failed";
        return 1;
    }
    auto active =
        static_cast<NMActiveConnection*>(nm_client_get_active_connections(client.get())->pdata[0]);
    auto profile = nm_active_connection_get_connection(active);
    if (!profile || QString(nm_connection_get_id(NM_CONNECTION(profile))) != "Phone hotspot")
        return 1;
    // Some mock releases do not publish ActiveAccessPoint. Both wired and Wi-Fi menu
    // actions still require a current target and a matching saved connection.
    if (!QTest::qWaitFor([&] { return button->isEnabled(); }, 3s))
        return 1;
    bool menuFound = false;
    QTimer::singleShot(0, [&] {
        auto popup = qobject_cast<QMenu*>(QApplication::activePopupWidget());
        if (!popup)
            return;
        QStringList labels;
        for (auto action : popup->actions())
            labels << action->text();
        menuFound = labels.contains("Forget saved network…") && labels.contains("Change password…");
        popup->close();
    });
    auto where = list->visualItemRect(list->item(0)).center();
    QContextMenuEvent context(QContextMenuEvent::Mouse, where, list->viewport()->mapToGlobal(where));
    QApplication::sendEvent(list->viewport(), &context);
    if (!menuFound) {
        qCritical() << "Saved profile actions missing";
        return 1;
    }
    auto originalPath = QString::fromUtf8(nm_object_get_path(NM_OBJECT(profile)));
    bool refusedReplacement = false;
    QTimer::singleShot(0, [&] {
        auto popup = qobject_cast<QMenu*>(QApplication::activePopupWidget());
        if (!popup)
            return;
        for (auto action : popup->actions()) {
            if (action->text() != "Forget saved network…")
                continue;
            QTimer::singleShot(0, [&] {
                auto dialog = qobject_cast<QMessageBox*>(QApplication::activeModalWidget());
                if (!dialog)
                    return;
                if (dialog->defaultButton() != dialog->button(QMessageBox::Cancel)) {
                    dialog->reject();
                    return;
                }
                auto remove = fixture.call("RemoveWifiConnection", dev.value(), originalPath);
                QDBusReply<QString> replacement = fixture.call("AddWiFiConnection", dev.value(),
                                                               "replacement", "Phone hotspot", "wpa-psk");
                if (remove.type() == QDBusMessage::ErrorMessage || !replacement.isValid()) {
                    dialog->reject();
                    return;
                }
                refusedReplacement = QTest::qWaitFor(
                    [&] {
                        auto profiles =
                            net::objects<NMRemoteConnection>(nm_client_get_connections(client.get()));
                        return profiles.size() == 1 &&
                               QString::fromUtf8(nm_object_get_path(NM_OBJECT(profiles.front()))) ==
                                   replacement.value();
                    },
                    2s);
                for (auto button : dialog->buttons())
                    if (dialog->buttonRole(button) == QMessageBox::DestructiveRole) {
                        button->click();
                        return;
                    }
                dialog->reject();
            });
            action->trigger();
            break;
        }
        popup->close();
    });
    QContextMenuEvent keyboard(QContextMenuEvent::Keyboard, QPoint(), QPoint());
    QApplication::sendEvent(list->viewport(), &keyboard);
    bool stale = false;
    for (auto label : window->findChildren<QLabel*>())
        stale |= label->text().contains("network changed");
    if (!refusedReplacement || !stale || nm_client_get_connections(client.get())->len != 1) {
        qCritical() << "Forget confirmation did not protect the replacement profile";
        return 1;
    }
    return 0;
}
