#include "preferences.hpp"
#include <fcntl.h>
#include <sys/file.h>
#include <sys/stat.h>
#include <unistd.h>

namespace input {
void fail(const QString& reason) { throw std::runtime_error(reason.toStdString()); }
QString digest(const QByteArray& raw) {
    return QString::fromLatin1(QCryptographicHash::hash(raw, QCryptographicHash::Sha256).toHex());
}
static QByteArray encoded(const QJsonObject& obj) {
    return QJsonDocument(obj).toJson(QJsonDocument::Compact);
}
QString identity(const QStringList& fields) {
    // RC2 persisted the SHA256 of json.dumps(fields), including spaces and ASCII escaping.
    QByteArray raw = "[";
    for (qsizetype i = 0; i < fields.size(); ++i) {
        if (i)
            raw += ", ";
        raw += '"';
        for (QChar ch : fields[i]) {
            auto u = ch.unicode();
            switch (u) {
            case '"':
                raw += "\\\"";
                break;
            case '\\':
                raw += "\\\\";
                break;
            case '\b':
                raw += "\\b";
                break;
            case '\f':
                raw += "\\f";
                break;
            case '\n':
                raw += "\\n";
                break;
            case '\r':
                raw += "\\r";
                break;
            case '\t':
                raw += "\\t";
                break;
            default:
                if (u < 32 || u >= 127)
                    raw += "\\u" + QByteArray::number(u, 16).rightJustified(4, '0');
                else
                    raw += char(u);
            }
        }
        raw += '"';
    }
    return digest(raw + ']');
}
QJsonObject value(int type, int format, const QJsonArray& values) {
    return {{"type", type}, {"format", format}, {"values", values}};
}
QString Device::marker() const {
    QByteArray bytes;
    for (auto item : get(markerProp)["values"].toArray())
        bytes.append(char(item.toInt()));
    return QString::fromLatin1(bytes);
}
static bool integer(const QJsonValue& v, qint64 max = 0xffffffff) {
    const auto n = v.toInteger(-1);
    return v.isDouble() && n >= 0 && n <= max && v.toDouble() == static_cast<double>(n);
}
static bool validFlags(const QJsonObject& v) {
    const auto a = v["values"].toArray();
    return integer(v["type"]) && v["format"] == 8 && (a.size() == 2 || a.size() == 3) &&
           std::all_of(a.begin(), a.end(), [](auto item) { return integer(item, 1); });
}
static bool validValue(const QString& name, const QJsonObject& v) {
    const auto a = v["values"].toArray();
    if (name == libinputProp)
        return validFlags(v) && std::count(a.begin(), a.end(), QJsonValue(1)) == 1;
    return (name == evdevProp || name == enabledProp) && integer(v["type"]) && a.size() == 1 &&
           v["format"] == (name == evdevProp ? 32 : 8) &&
           integer(a[0], name == evdevProp ? qint64(0xffffffff) : 1);
}
QJsonArray target(const QString& name, const QJsonObject& v) {
    if (name == libinputProp)
        return v["values"].toArray().size() == 2 ? QJsonArray{0, 1} : QJsonArray{0, 1, 0};
    return {name == evdevProp ? qint64(0xffffffff) : 0};
}
std::optional<Capability> capability(const Device& d) {
    QString name, action;
    if (d.kind == "touchpad") {
        name = enabledProp;
        action = "touchpad";
    } else if (d.kind == "mouse" && d.driver == "evdev") {
        name = evdevProp;
        action = "acceleration";
    } else if (d.kind == "mouse" && d.driver == "libinput") {
        name = libinputProp;
        action = "acceleration";
        auto available = d.get(availableProp);
        auto flags = available["values"].toArray();
        auto current = d.get(name)["values"].toArray();
        if (!validValue(name, d.get(name)) || !validFlags(available) || current.size() != flags.size() ||
            flags.at(1) != 1)
            return {};
        for (qsizetype i = 0; i < flags.size(); ++i)
            if (current.at(i) == 1 && flags.at(i) != 1)
                return {};
    } else
        return {};
    if (!validValue(name, d.get(name)))
        return {};
    return Capability{action, name, target(name, d.get(name))};
}
bool otherMouse(const QList<Device>& devices) {
    return std::any_of(devices.begin(), devices.end(), [](const auto& d) {
        return d.usableMouse && d.enabled && d.get(enabledProp)["values"].toArray() == QJsonArray{1};
    });
}
static QByteArray contents(const QString& file) {
    QFile f(file);
    if (!f.open(QIODevice::ReadOnly))
        fail(f.errorString());
    auto bytes = f.readAll();
    if (f.error() != QFileDevice::NoError)
        fail(f.errorString());
    return bytes;
}
Lock::Lock(const QString& path, bool wait) {
    if (!QDir().mkpath(QFileInfo(path).absolutePath()))
        fail("Cannot create input settings directory.");
    fd = ::open(QFile::encodeName(path).constData(), O_CLOEXEC | O_CREAT | O_NOFOLLOW | O_RDWR, 0600);
    if (fd < 0)
        fail(QString::fromLocal8Bit(strerror(errno)));
    int result;
    do {
        result = flock(fd, LOCK_EX | (wait ? 0 : LOCK_NB));
    } while (result < 0 && errno == EINTR);
    if (result < 0) {
        int why = errno;
        ::close(fd);
        fd = -1;
        if (why == EWOULDBLOCK)
            throw Busy();
        fail(QString::fromLocal8Bit(strerror(why)));
    }
}
Lock::~Lock() {
    if (fd >= 0)
        ::close(fd);
}
Preferences::Preferences(QString userHome, QString binary)
    : home(QDir::cleanPath(std::move(userHome))), helper(std::move(binary)),
      path(home + "/.config/doroshell/input-preferences.json"),
      startup(home + "/.config/autostart/doroshell-input.desktop"),
      lock(home + "/.config/doroshell/input-preferences.lock") {
    if (!home.startsWith('/') || !helper.startsWith('/'))
        fail("Invalid input helper paths.");
}
void Preferences::safe(const QString& name) const {
    if (!name.startsWith(home + "/") || QDir::cleanPath(name) != name)
        fail("Preference path escapes HOME.");
    QString current = name;
    while (true) {
        if (QFileInfo(current).isSymLink())
            fail("Refusing symlinked preference path.");
        if (current == home)
            break;
        current = QFileInfo(current).absolutePath();
    }
}
QString Preferences::watchLock() const {
    auto p = home + "/.local/state/doroshell/input-watch.lock";
    safe(p);
    return p;
}
static bool hex(const QString& s, int length) {
    return s.size() == length && std::all_of(s.begin(), s.end(), [](QChar c) {
               return (c >= u'0' && c <= u'9') || (c >= u'a' && c <= u'f');
           });
}
Saved Preferences::read() const {
    safe(path);
    QJsonObject data{{"version", 1}, {"rules", QJsonObject{}}, {"receipts", QJsonObject{}}};
    if (!QFileInfo::exists(path))
        return {{}, data};
    auto raw = contents(path);
    auto doc = QJsonDocument::fromJson(raw);
    data = doc.object();
    auto startupValue = data.value("startup");
    if (!doc.isObject() || data["version"] != 1 || !data["rules"].isObject() ||
        !data["receipts"].isObject() ||
        (!startupValue.isUndefined() && !startupValue.isNull() &&
         !QStringList{"pending", "installed", "removing"}.contains(startupValue.toString())) ||
        (data.contains("all_mice") && !data["all_mice"].isBool()))
        fail("Unsupported input preferences; existing file preserved.");
    const auto rules = data["rules"].toObject(), receipts = data["receipts"].toObject();
    for (auto i = rules.begin(); i != rules.end(); ++i) {
        auto r = i.value().toObject();
        if (!hex(i.key(), 64) || !r["name"].isString() ||
            (r["action"] != "acceleration" && r["action"] != "touchpad") || !r["enabled"].isBool() ||
            (r.contains("auto") && (r["auto"] != true || r["action"] != "acceleration")))
            fail("Invalid saved input preference.");
    }
    for (auto i = receipts.begin(); i != receipts.end(); ++i) {
        auto r = i.value().toObject();
        auto name = r["property"].toString();
        bool accel = rules[i.key()].toObject()["action"] == "acceleration";
        if (!rules.contains(i.key()) ||
            (accel ? (name != evdevProp && name != libinputProp) : name != enabledProp) ||
            !r["token"].isString() || !integer(r["id"], 65535) || !r["node"].isString() ||
            (r.contains("marker") && !hex(r["marker"].toString(), 32)))
            fail("Invalid input restoration identity.");
        auto before = r["before"].toObject(), after = r["after"].toObject();
        if (!validValue(name, before) || !validValue(name, after) ||
            after["values"].toArray() != target(name, after) || before["type"] != after["type"] ||
            before["values"].toArray().size() != after["values"].toArray().size())
            fail("Invalid saved input property.");
    }
    return {raw, data};
}
void Preferences::write(const QString& name, const QByteArray& bytes) const {
    safe(name);
    if (!QDir().mkpath(QFileInfo(name).absolutePath()))
        fail("Cannot create input preferences directory.");
    QSaveFile file(name);
    file.setDirectWriteFallback(false);
    if (!file.open(QIODevice::WriteOnly) ||
        !file.setPermissions(QFileDevice::ReadOwner | QFileDevice::WriteOwner) ||
        file.write(bytes) != bytes.size() || !file.flush() || ::fsync(file.handle()) || !file.commit())
        fail("Could not atomically save input preferences.");
}
void Preferences::store(const QJsonObject& data) const { write(path, encoded(data)); }
static QString quote(QString s) {
    s.replace("\\", "\\\\").replace('"', "\\\"").replace('`', "\\`").replace('$', "\\$").replace('%', "%%");
    return '"' + s + '"';
}
QByteArray Preferences::payload(bool legacy) const {
    auto command = legacy ? QString("\"/usr/bin/python\" ") +
                                quote(home + "/.local/share/doroshell/toolkit/input_preferences.py")
                          : quote(helper);
    return ("[Desktop Entry]\nType=Application\nName=DoroShell input preferences\nExec=" + command +
            " --login\nOnlyShowIn=LXQt;\n")
        .toUtf8();
}
QByteArray Preferences::checkStartup(const QJsonObject& data) const {
    safe(startup);
    if (QFileInfo::exists(startup)) {
        auto bytes = contents(startup);
        struct stat st{};
        if (data.value("startup").toString().isEmpty() || (bytes != payload() && bytes != payload(true)) ||
            ::stat(QFile::encodeName(startup).constData(), &st) || (st.st_mode & 0777) != 0600)
            fail("Input autostart entry is unowned or changed.");
        return bytes;
    }
    if (data["startup"] == "installed")
        fail("Input autostart entry was removed elsewhere.");
    return {};
}
void Preferences::autostart(QJsonObject& data, bool required) const {
    auto existing = checkStartup(data);
    if (required) {
        if (!QFileInfo(helper).isExecutable() || !QFileInfo(helper).isFile())
            fail("Install the native input helper before saving.");
        if (data["startup"] == "installed" && existing == payload())
            return;
        data["startup"] = "pending";
        store(data);
        write(startup, payload());
        data["startup"] = "installed";
        store(data);
    } else if (!data.value("startup").toString().isEmpty()) {
        data["startup"] = "removing";
        store(data);
        checkStartup(data);
        if (QFileInfo::exists(startup) && !QFile::remove(startup))
            fail("Cannot remove input autostart entry.");
        data["startup"] = QJsonValue::Null;
        store(data);
    }
}
bool Preferences::needed(const QJsonObject& data) {
    const auto rules = data["rules"].toObject();
    return data["all_mice"].toBool() || !data["receipts"].toObject().isEmpty() ||
           std::any_of(rules.begin(), rules.end(),
                       [](const auto v) { return v.toObject()["enabled"].toBool(); });
}
bool Preferences::firstLogin() {
    safe(lock);
    Lock guard(lock, true);
    auto [raw, data] = read();
    if (!raw.isNull() && data["startup"] != "pending") {
        if (data["startup"] != "installed" || checkStartup(data) != payload(true))
            return false;
        // An RC2 install can already own the watcher desktop entry. Preserve the
        // user's rules and receipts while migrating that exact entry to native.
        autostart(data, needed(data));
        return needed(data);
    }
    if (raw.isNull()) {
        data["all_mice"] = true;
        data["first_login_default"] = true;
    }
    autostart(data, needed(data));
    return needed(data);
}
void Preferences::removeFirstLogin(const std::function<Backend&()>& getBackend) {
    // Restoration first uses the usual per-device compare-and-set. Do not
    // connect to X when there are no device receipts, e.g. a headless removal.
    auto saved = read();
    if (saved.raw.isNull())
        return;
    if (saved.data["first_login_default"] != true) {
        if (needed(saved.data) || !saved.data["startup"].toString().isEmpty())
            fail("Personal input rules are active. Stop managing devices in DoroShell Input before removal.");
        return;
    }
    const QSet<QString> defaultFields{"version", "rules", "receipts", "all_mice", "startup", "first_login_default"};
    for (auto it = saved.data.constBegin(); it != saved.data.constEnd(); ++it)
        if (!defaultFields.contains(it.key()))
            fail("Unknown saved input settings; preserving the preferences.");
    auto rules = saved.data["rules"].toObject();
    for (const auto& r : rules) {
        if (r.toObject()["auto"] != true || r.toObject().size() != 4)
            fail("Personal input rules are present. Preserving the preferences.");
    }
    if (!saved.data["receipts"].toObject().isEmpty()) {
        Edit edit;
        edit.stop = true;
        edit.undoFirstLogin = true;
        edit.revision = digest(saved.raw);
        auto& backend = getBackend();
        const auto token = backend.token();
        for (const auto& v : saved.data["receipts"].toObject())
            if (v.toObject()["token"] != token)
                fail("Restore the input defaults from their original X11 session.");
        bool incomplete = false;
        run(backend, edit, &incomplete);
        if (incomplete)
            fail("Some input devices could not be restored. Restoration receipts were kept.");
        saved = read();
    }
    safe(lock);
    Lock guard(lock, true);
    auto [raw, data] = read();
    if (raw != saved.raw || data["first_login_default"] != true || !data["receipts"].toObject().isEmpty())
        fail("Input preferences changed while restoring. Retry removal.");
    checkStartup(data);
    // Persist a disabled state before deleting the autostart. An interrupted
    // removal must never wake a watcher to manage freshly attached devices.
    data["all_mice"] = false;
    auto finalRules = data["rules"].toObject();
    for (auto it = finalRules.begin(); it != finalRules.end(); ++it) {
        auto r = it.value().toObject();
        if (r["auto"] != true)
            fail("Preserving a personal input rule.");
        r["enabled"] = false;
        it.value() = r;
    }
    data["rules"] = finalRules;
    store(data);
    autostart(data, false);
    if (!QFile::remove(path))
        fail("Could not remove the restored first-login defaults.");
}
void Preferences::archive(const QString& key, const QJsonObject& rule, const QJsonObject& receipt,
                          const QString& reason) const {
    auto bytes = encoded({{"reason", reason}, {"key", key}, {"rule", rule}, {"receipt", receipt}});
    auto name = home + "/.local/state/doroshell/input-restoration/" + digest(bytes) + ".json";
    safe(name);
    if (QFileInfo::exists(name)) {
        struct stat st{};
        if (contents(name) != bytes || ::stat(QFile::encodeName(name).constData(), &st) ||
            (st.st_mode & 0777) != 0600)
            fail("Archived input restoration evidence changed.");
    } else
        write(name, bytes);
}
QStringList Preferences::run(Backend& backend, const Edit& edit, bool* incomplete) {
    safe(lock);
    Lock guard(lock, false);
    auto [raw, data] = read();
    checkStartup(data);
    auto rules = data["rules"].toObject();
    auto receipts = data["receipts"].toObject();
    if (edit.requested()) {
        if (digest(raw) != edit.revision)
            fail("Preferences changed elsewhere; refresh before saving.");
        if (edit.undoFirstLogin && data["first_login_default"]!=true)
            fail("Input ownership changed before restoring first-login defaults.");
        if (!edit.undoFirstLogin)
            data.remove("first_login_default");
        if (edit.stop) {
            data["all_mice"] = false;
            for (auto i = rules.begin(); i != rules.end(); ++i) {
                auto r = i.value().toObject();
                r["enabled"] = false;
                i.value() = r;
            }
        } else if (edit.global)
            data["all_mice"] = *edit.global;
        else {
            const auto r = edit.rule;
            if (!hex(edit.key, 64) || !r["name"].isString() ||
                (r["action"] != "acceleration" && r["action"] != "touchpad") || !r["enabled"].isBool())
                fail("Invalid input request.");
            if (receipts.contains(edit.key) && rules[edit.key].toObject()["action"] != r["action"])
                fail("Restore the saved action before changing it.");
            rules[edit.key] =
                QJsonObject{{"name", r["name"]}, {"action", r["action"]}, {"enabled", r["enabled"]}};
        }
    }
    for (auto i = rules.begin(); i != rules.end(); ++i) {
        auto rule = i.value().toObject();
        if (rule["auto"].toBool()) {
            rule["enabled"] = data["all_mice"].toBool();
            i.value() = rule;
        }
    }
    auto checkpoint = [&] {
        data["rules"] = rules;
        data["receipts"] = receipts;
        store(data);
    };
    data["rules"] = rules;
    bool required = needed(data);
    autostart(data, required);
    if (edit.requested())
        checkpoint();
    if (!required)
        return {"No managed input changes remain. Saved choices and archived evidence are retained."};
    const auto devices = backend.devices();
    const auto session = backend.token();
    auto matches = [](const QList<Device>& list, const QString& key) {
        QList<Device> result;
        for (const auto& d : list)
            if (d.key == key)
                result << d;
        return result;
    };
    if (data["all_mice"].toBool())
        for (const auto& d : devices) {
            auto cap = capability(d);
            if (cap && cap->action == "acceleration" && !rules.contains(d.key) &&
                matches(devices, d.key).size() == 1)
                rules[d.key] = QJsonObject{
                    {"name", d.name}, {"action", "acceleration"}, {"enabled", true}, {"auto", true}};
        }
    QStringList messages;
    for (auto i = rules.cbegin(); i != rules.cend(); ++i) {
        const auto key = i.key();
        const auto rule = i.value().toObject();
        auto receipt = receipts.value(key).toObject();
        auto name = rule["name"].toString();
        auto report = [&](const QString& msg) { messages << name + ": " + msg; };
        auto skip = [&](const QString& msg) {
            report(msg);
            if (incomplete)
                *incomplete = true;
        };
        const bool enabling = rule["enabled"].toBool();
        if (!receipt.isEmpty() && receipt["token"] != session) {
            archive(key, rule, receipt, "previous-x-server-session");
            receipts.remove(key);
            receipt = {};
            checkpoint();
            report("previous-session restoration evidence archived.");
        }
        if (!enabling && receipt.isEmpty()) {
            report("unmanaged; no current-session change to restore.");
            continue;
        }
        auto matching = matches(devices, key);
        if (matching.size() != 1) {
            skip("configured; absent or ambiguous, not applied.");
            continue;
        }
        auto dev = matching.front();
        name = dev.name;
        const auto cap = capability(dev);
        if (!cap || cap->action != rule["action"]) {
            skip("configured; unsupported current driver/property, not applied.");
            continue;
        }
        auto prop = cap->property;
        if (cap->action == "touchpad" && enabling && !otherMouse(devices)) {
            skip("another enabled identified mouse is required.");
            continue;
        }
        if (!receipt.isEmpty()) {
            if (receipt["id"] != dev.id || receipt["node"] != dev.node ||
                (receipt.contains("marker") && receipt["marker"] != dev.marker())) {
                archive(key, rule, receipt, "device-reconnected");
                receipts.remove(key);
                receipt = {};
                checkpoint();
                report("reconnected; previous-instance restoration evidence archived.");
                if (!enabling)
                    continue;
            } else if (receipt["property"] != prop) {
                skip("driver property changed; restoration refused.");
                continue;
            }
        }
        auto current = dev.get(prop);
        if (!receipt.isEmpty() && current != receipt["before"] && current != receipt["after"]) {
            skip("property changed elsewhere; restore/apply refused.");
            continue;
        }
        if (enabling && receipt.isEmpty()) {
            auto marker = QUuid::createUuid().toString(QUuid::Id128);
            try {
                backend.mark(dev, marker);
            } catch (const std::exception& e) {
                skip("configured, apply failed: " + QString::fromUtf8(e.what()));
                continue;
            }
            const auto marked = matches(backend.devices(), key);
            if (marked.size() != 1 || marked[0].id != dev.id || marked[0].node != dev.node ||
                marked[0].marker() != marker || capability(marked[0]) != cap) {
                skip("device changed during apply; not applied.");
                continue;
            }
            dev = marked.front();
            current = dev.get(prop);
            auto desired = current;
            desired["values"] = cap->values;
            receipt = {{"token", session}, {"id", dev.id},      {"node", dev.node}, {"marker", marker},
                       {"property", prop}, {"before", current}, {"after", desired}};
            receipts[key] = receipt;
            checkpoint();
        }
        const auto desired = receipt[enabling ? "after" : "before"].toObject();
        if (prop == libinputProp && current != desired) {
            auto wanted = desired["values"].toArray(), offered = dev.get(availableProp)["values"].toArray();
            bool available = wanted.size() == offered.size();
            for (qsizetype n = 0; available && n < wanted.size(); ++n)
                if (wanted[n] == 1 && offered[n] != 1)
                    available = false;
            if (!available) {
                skip("saved profile is no longer offered by the driver; not written.");
                continue;
            }
        }
        try {
            if (current != desired)
                backend.write(dev, prop, desired);
            if (!enabling)
                receipts.remove(key);
            report(enabling ? "applied and read back." : "prior property restored.");
        } catch (const std::exception& e) {
            skip("configured, apply failed: " + QString::fromUtf8(e.what()));
        }
        checkpoint();
    }
    checkpoint();
    if (!needed(data))
        autostart(data, false);
    return messages;
}
void Preferences::startWatcher() const {
    QProcess child;
    child.setProgram(helper);
    child.setArguments({"--login"});
    auto env = QProcessEnvironment::systemEnvironment();
    env.insert("HOME", home);
    child.setProcessEnvironment(env);
    child.setStandardInputFile(QProcess::nullDevice());
    child.setStandardOutputFile(QProcess::nullDevice());
    child.setStandardErrorFile(QProcess::nullDevice());
    if (!child.startDetached())
        fail("The preferences were saved, but the input watcher could not start.");
}
} // namespace input
