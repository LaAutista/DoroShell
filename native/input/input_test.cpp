#include "preferences.hpp"
#include "diagnostic.hpp"
#include <cstdio>
using namespace input;
namespace {
struct Fake : Backend {
    QList<Device> list;
    QString session = QString(32, 'c');
    bool replaceOnMark = false;
    int writes = 0;
    QList<Device> devices() override { return list; }
    QString token() override { return session; }
    void mark(const Device& d, const QString& marker) override {
        for (auto& actual : list)
            if (d.key == actual.key) {
                QJsonArray bytes;
                for (auto c : marker.toLatin1())
                    bytes.append(int(c));
                actual.props[markerProp] = value(31, 8, bytes);
                if (replaceOnMark)
                    actual.props[libinputProp] = value(19, 8, {0, 1, 0});
            }
    }
    void write(const Device& d, const QString& name, const QJsonObject& desired) override {
        for (auto& actual : list)
            if (d.key == actual.key) {
                actual.props[name] = desired;
                ++writes;
            }
    }
};
void verify(bool b, const char* msg) {
    if (!b)
        throw std::runtime_error(msg);
}
Device mouse() {
    Device d{};
    d.key = QString(64, 'a');
    d.name = "Mouse";
    d.node = "/dev/input/event4";
    d.kind = "mouse";
    d.driver = "libinput";
    d.id = 12;
    d.enabled = true;
    d.usableMouse = true;
    d.props[enabledProp] = value(19, 8, {1});
    d.props[libinputProp] = value(19, 8, {0, 0, 1});
    d.props[availableProp] = value(19, 8, {1, 1, 1});
    return d;
}
} // namespace
int main(int argc, char** argv) {
    QCoreApplication app(argc, argv);
    try {
        QTemporaryDir dir;
        verify(dir.isValid(), "temp home");
        Preferences store(dir.path(), app.applicationFilePath());
        Fake backend;
        backend.list << mouse();
        auto setup = [&](bool global) {
            Edit e;
            e.global = global;
            e.revision = digest(store.read().raw);
            return store.run(backend, e);
        };
        verify(store.read().raw.isNull(), "no file before inspection");
        verify(store.firstLogin(), "first login");
        verify(!store.firstLogin(), "default seeded only once");
        // Replace the fixture's native entry with the exact pre-rewrite payload.
        QFile desktop(dir.filePath(".config/autostart/doroshell-input.desktop"));
        auto legacy =
            QString(
                "[Desktop Entry]\nType=Application\nName=DoroShell input "
                "preferences\nExec=\"/usr/bin/python\" "
                "\"%1/.local/share/doroshell/toolkit/input_preferences.py\" --login\nOnlyShowIn=LXQt;\n")
                .arg(dir.path())
                .toUtf8();
        verify(desktop.open(QIODevice::WriteOnly) && desktop.write(legacy) == legacy.size(), "RC2 fixture");
        desktop.close();
        verify(store.firstLogin(), "RC2 watcher migrated");
        verify(desktop.open(QIODevice::ReadOnly) && !desktop.readAll().contains("/usr/bin/python"),
               "native watcher selected");
        desktop.close();
        store.run(backend);
        verify(backend.writes == 1 &&
                   backend.list[0].get(libinputProp)["values"].toArray() == QJsonArray{0, 1, 0},
               "flat applied");
        auto receipts = store.read().data["receipts"].toObject();
        verify(receipts.size() == 1 &&
                   receipts.begin().value().toObject()["before"].toObject()["values"].toArray() ==
                       QJsonArray{0, 0, 1},
               "custom saved");
        verify(!backend.list[0].marker().isEmpty(), "instance marked");
        store.run(backend);
        verify(backend.writes == 1, "idempotent");
        backend.list[0].props[availableProp] = value(19, 8, {1, 1, 0});
        setup(false);
        verify(backend.writes == 1 && !store.read().data["receipts"].toObject().isEmpty(),
               "withdrawn profile retained");
        backend.list[0].props[availableProp] = value(19, 8, {1, 1, 1});
        store.run(backend);
        verify(backend.writes == 2 && !Preferences::needed(store.read().data), "baseline restored");
        verify(!QFileInfo::exists(dir.filePath(".config/autostart/doroshell-input.desktop")),
               "autostart removed");
        setup(true);
        backend.list[0].props.remove(markerProp);
        setup(false);
        verify(backend.writes == 3, "replacement not overwritten");
        verify(QDir(dir.filePath(".local/state/doroshell/input-restoration"))
                       .entryList({"*.json"}, QDir::Files)
                       .size() == 1,
               "receipt archived");
        backend.list[0] = mouse();
        backend.replaceOnMark = true;
        setup(true);
        verify(backend.writes == 3, "replacement baseline captured after mark");
        setup(false);
        verify(backend.writes == 3, "replacement baseline restored without write");
        Edit stale;
        stale.global = true;
        stale.revision = digest("old");
        bool refused = false;
        try {
            store.run(backend, stale);
        } catch (const std::exception&) {
            refused = true;
        }
        verify(refused, "stale revision refused");
        // Only the installer's first-login choices belong to removal. A
        // personally selected global setting must remain untouched.
        {
            QTemporaryDir h;
            Preferences automatic(h.path(), app.applicationFilePath());
            Fake mouseBackend;
            mouseBackend.list << mouse();
            verify(automatic.firstLogin(), "seed undo fixture");
            automatic.run(mouseBackend);
            auto savedDefault = automatic.read();
            mouseBackend.session = QString(32, 'e');
            bool wrongSession = false;
            try {
                automatic.removeFirstLogin([&]() -> Backend& { return mouseBackend; });
            } catch (const std::exception&) {
                wrongSession = true;
            }
            verify(wrongSession && automatic.read().raw == savedDefault.raw && mouseBackend.writes == 1,
                   "wrong X session changed defaults");
            mouseBackend.session = QString(32, 'c');
            mouseBackend.list[0].props[availableProp] = value(19, 8, {1, 1, 0});
            bool withdrawn = false;
            try {
                automatic.removeFirstLogin([&]() -> Backend& { return mouseBackend; });
            } catch (const std::exception&) {
                withdrawn = true;
            }
            verify(withdrawn && !automatic.read().data["receipts"].toObject().isEmpty(),
                   "withdrawn restore target lost its receipt");
            mouseBackend.list[0].props[availableProp] = value(19, 8, {1, 1, 1});
            automatic.removeFirstLogin([&]() -> Backend& { return mouseBackend; });
            verify(automatic.read().raw.isNull() && mouseBackend.writes == 2 &&
                       mouseBackend.list[0].get(libinputProp)["values"].toArray() == QJsonArray{0, 0, 1} &&
                       !QFileInfo::exists(h.filePath(".config/autostart/doroshell-input.desktop")),
                   "first-login removal did not restore exact custom baseline");
            verify(automatic.firstLogin(), "reseed in fresh fixture");
            Edit personal;
            personal.global = true;
            personal.revision = digest(automatic.read().raw);
            automatic.run(mouseBackend, personal);
            const auto before = automatic.read().raw;
            bool protectedPersonal = false;
            try {
                automatic.removeFirstLogin([&]() -> Backend& { return mouseBackend; });
            } catch (const std::exception&) {
                protectedPersonal = true;
            }
            verify(protectedPersonal && automatic.read().raw == before,
                   "personal rule overwritten during removal");
        }
        auto duplicate = mouse();
        backend.list = {duplicate, duplicate};
        setup(true);
        verify(backend.writes == 3, "duplicate refused");
        auto pad = mouse();
        pad.key = QString(64, 'b');
        pad.kind = "touchpad";
        pad.usableMouse = false;
        backend.list = {pad};
        Edit e;
        e.key = pad.key;
        e.rule = {{"name", "pad"}, {"action", "touchpad"}, {"enabled", true}};
        e.revision = digest(store.read().raw);
        store.run(backend, e);
        verify(backend.writes == 3, "touchpad alone remains enabled");
        auto malformed = mouse();
        malformed.props[libinputProp] = value(19, 8, {1, 1, 0});
        verify(!capability(malformed), "malformed libinput state refused");
        auto evdev = mouse();
        evdev.driver = "evdev";
        evdev.props[evdevProp] = value(19, 32, {0});
        verify(capability(evdev)->values == QJsonArray{qint64(0xffffffff)}, "evdev -1");
        auto expected = digest("[\"Mouse\", \"SS\\u00e9\", \"port\", \"1\", \"2\"]");
        verify(identity({"Mouse", "SSé", "port", "1", "2"}) == expected, "RC2 identity digest");
        Configuration config;
        config.parse(
            "Section \"InputClass\"\n Identifier \"My Mouse\"\n MatchProduct \"Mouse\"\n MatchDevicePath "
            "\"/dev/input/event*\"\n Option \"AccelerationScheme\" \"none\" # comment\n EndSection");
        verify(config.describe(mouse(), true).contains("requests none (intent only)"),
               "configuration intent");
        config.parse("Section \"InputClass\"\n Identifier \"Other\"\n Option \"AccelerationScheme\" "
                     "\"predictable\"\n EndSection");
        verify(config.describe(mouse(), true).contains("conflicting"), "ambiguous configuration");
        config.parse("Section \"inputclass");
        verify(config.issues.contains("malformed"), "malformed configuration refused");
        return 0;
    } catch (const std::exception& e) {
        std::fprintf(stderr, "%s\n", e.what());
        return 1;
    }
}
