#include "xinput.hpp"
#include <cstdlib>
#include <memory>
#include <cstdio>
using namespace input;
namespace {
class Child : public QProcess {
  public:
    ~Child() {
        if (state() != NotRunning) {
            terminate();
            if (!waitForFinished(2000)) {
                kill();
                waitForFinished();
            }
        }
    }
};
void require(bool condition, const QString& why) {
    if (!condition)
        fail(why);
}
} // namespace
int main(int argc, char** argv) {
    QCoreApplication app(argc, argv);
    QString xvfb = qEnvironmentVariable("DOROSHELL_TEST_XVFB");
    if (xvfb.isEmpty())
        xvfb = QStandardPaths::findExecutable("Xvfb");
    if (xvfb.isEmpty())
        return 77;
    try {
        QTemporaryDir home;
        require(home.isValid(), "Cannot allocate an isolated test home.");
        Child server;
        server.start(xvfb,
                     {"-displayfd", "1", "-screen", "0", "800x600x24", "-nolisten", "tcp", "-noreset"});
        require(server.waitForStarted() && server.waitForReadyRead(), "Private Xvfb did not start.");
        bool ok = false;
        int display = server.readLine().trimmed().toInt(&ok);
        require(ok && display >= 0, "Private Xvfb did not provide a display number.");
        qputenv("DISPLAY", ":" + QByteArray::number(display));
        qputenv("HOME", home.path().toUtf8());
        qputenv("XDG_SESSION_TYPE", "x11");
        qunsetenv("XAUTHORITY");
        const auto binary = app.applicationDirPath() + "/doroshell-input-preferences";
        XInput backend;
        require(backend.devices().isEmpty(), "Unexpected identified udev devices on the private Xvfb.");
        require(backend.token() == backend.token(), "Session token changed.");
        // Verify the marker request and its readback on an Xvfb-only pointer.
        auto serverConn = std::unique_ptr<xcb_connection_t, decltype(&xcb_disconnect)>(
            xcb_connect(nullptr, nullptr), xcb_disconnect);
        auto x = serverConn.get();
        auto info = std::unique_ptr<xcb_input_xi_query_device_reply_t, decltype(&std::free)>(
            xcb_input_xi_query_device_reply(x, xcb_input_xi_query_device(x, XCB_INPUT_DEVICE_ALL), nullptr),
            std::free);
        require(bool(info), "Cannot inspect private Xvfb pointers.");
        Device dev{};
        for (auto it = xcb_input_xi_query_device_infos_iterator(info.get()); it.rem;
             xcb_input_xi_device_info_next(&it))
            if (it.data->type == XCB_INPUT_DEVICE_TYPE_SLAVE_POINTER) {
                dev.id = it.data->deviceid;
                break;
            }
        require(dev.id > 0, "No Xvfb pointer available for the marker check.");
        backend.mark(dev, QString(32, 'a'));
        Child watcher;
        watcher.start(binary, {"--first-login"});
        require(watcher.waitForStarted(), "Cannot start native watcher.");
        Preferences prefs(home.path(), binary);
        QDeadlineTimer deadline(5000);
        bool ready = false;
        while (!deadline.hasExpired()) {
            auto data = prefs.read().data;
            if (data["startup"] == "installed") {
                try {
                    Lock check(prefs.watchLock(), false);
                } catch (const Busy&) {
                    ready = true;
                    break;
                }
            }
            QThread::msleep(10);
        }
        require(ready, "Watcher did not claim its lock.");
        require(QProcess::execute(binary, {"--login"}) == 0, "Duplicate watcher failed.");
        auto revision = digest(prefs.read().raw);
        require(QProcess::execute(binary, {"--global-set", "off", revision}) == 0,
                "Could not opt out on the private server.");
        require(watcher.waitForFinished(7500) && watcher.exitCode() == 0,
                "Watcher did not exit after opt-out.");
        require(!Preferences::needed(prefs.read().data), "First-login state failed to restore.");
        require(!QFileInfo::exists(home.filePath(".config/autostart/doroshell-input.desktop")),
                "Unmanaged watcher left autostart installed.");
        QTemporaryDir fresh;
        require(fresh.isValid(), "Cannot allocate separate first-login removal home.");
        qputenv("HOME", fresh.path().toUtf8());
        Preferences defaults(fresh.path(), binary);
        Child freshWatcher;
        freshWatcher.start(binary, {"--first-login"});
        require(freshWatcher.waitForStarted(), "Cannot start isolated defaults watcher.");
        deadline = QDeadlineTimer(5000);
        while (!deadline.hasExpired() && defaults.read().data["startup"] != "installed")
            QThread::msleep(10);
        require(defaults.read().data["startup"] == "installed", "Defaults did not initialize.");
        require(QProcess::execute(binary, {"--remove-first-login", "--offline"}) == 0,
                "Could not undo seeded default");
        require(freshWatcher.waitForFinished(7500) && freshWatcher.exitCode() == 0 &&
                    defaults.read().raw.isNull() &&
                    !QFileInfo::exists(fresh.filePath(".config/autostart/doroshell-input.desktop")),
                "Removing defaults left a watcher or preferences");
        return 0;
    } catch (const std::exception& e) {
        std::fprintf(stderr, "%s\n", e.what());
        return 1;
    }
}
