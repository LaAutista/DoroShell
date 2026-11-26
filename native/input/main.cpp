#include "xinput.hpp"
using namespace input;
int main(int argc, char** argv) {
    QCoreApplication app(argc, argv);
    auto args = app.arguments().mid(1);
    try {
        Preferences store(QDir::homePath(), QCoreApplication::applicationFilePath());
        if (args == QStringList{"--remove-first-login"} ||
            args == QStringList{"--remove-first-login", "--offline"}) {
            std::unique_ptr<XInput> backend;
            store.removeFirstLogin([&]() -> Backend& {
                if (args.contains("--offline") || qgetenv("XDG_SESSION_TYPE") != "x11" ||
                    qEnvironmentVariableIsEmpty("DISPLAY"))
                    fail("Device receipts need the original X11 session for restoration.");
                backend = std::make_unique<XInput>();
                return *backend;
            });
            return 0;
        }
        if (args == QStringList{"--global-status"}) {
            auto saved = store.read();
            QJsonObject result{{"enabled", saved.data["all_mice"].toBool()},
                               {"revision", digest(saved.raw)}};
            QTextStream(stdout) << QJsonDocument(result).toJson(QJsonDocument::Compact) << Qt::endl;
            return 0;
        }
        if (args == QStringList{"--first-login"}) {
            if (qgetenv("XDG_SESSION_TYPE") != "x11" || qEnvironmentVariableIsEmpty("DISPLAY"))
                return 0;
            if (!store.firstLogin())
                return 0;
        } else if (args != QStringList{"--login"}) {
            if (args == QStringList{"--list"}) {
                XInput xi;
                QJsonArray rows;
                for (const auto& d : xi.devices()) {
                    auto cap = capability(d);
                    QJsonObject row{{"name", d.name}, {"id", d.id},         {"key", d.key},
                                    {"kind", d.kind}, {"driver", d.driver}, {"node", d.node}};
                    if (cap) {
                        row["action"] = cap->action;
                        row["observed"] = d.get(cap->property);
                        row["target"] = cap->values;
                    }
                    rows << row;
                }
                QTextStream(stdout) << QJsonDocument(rows).toJson(QJsonDocument::Compact) << Qt::endl;
                return 0;
            }
            auto saved = store.read();
            Edit edit;
            bool perDevice = false;
            if (args.size() == 3 && args[0] == "--global-set" && (args[1] == "on" || args[1] == "off"))
                edit.global = args[1] == "on";
            else if (args.size() == 2 && args[0] == "--stop")
                edit.stop = true;
            else if (args.size() == 4 && args[0] == "--device-set" && (args[2] == "on" || args[2] == "off"))
                perDevice = true;
            else
                fail("Use --global-status, --global-set on|off REVISION, --list, --device-set KEY on|off "
                     "REVISION, --stop REVISION, --first-login or --login.");
            edit.revision = args.back();
            if (digest(saved.raw) != edit.revision)
                fail("Preferences changed elsewhere; refresh before saving.");
            XInput xi;
            if (perDevice) {
                auto devices = xi.devices();
                QList<Device> matches;
                for (const auto& device : devices)
                    if (device.key == args[1])
                        matches << device;
                if (matches.size() != 1 || !capability(matches.front()))
                    fail("The selected device is absent, ambiguous or unsupported.");
                auto cap = capability(matches.front());
                edit.key = matches.front().key;
                edit.rule = {
                    {"name", matches.front().name}, {"action", cap->action}, {"enabled", args[2] == "on"}};
            }
            bool incomplete = false;
            auto messages = store.run(xi, edit, &incomplete);
            if (Preferences::needed(store.read().data))
                store.startWatcher();
            if (incomplete)
                QTextStream(stdout) << "Preference saved." << Qt::endl;
            QTextStream(stdout) << messages.join('\n') << Qt::endl;
            return 0;
        }
        XInput xi;
        xi.watch(store);
        return 0;
    } catch (const std::exception& e) {
        QTextStream(stderr) << e.what() << Qt::endl;
        return 1;
    }
}
