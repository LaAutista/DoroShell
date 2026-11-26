#include "theme.hpp"
#include <sys/file.h>
#include <sys/stat.h>
#include <fcntl.h>
#include <unistd.h>
namespace theme {
namespace {
const QString dir = ".local/state/doroshell/", receipt = dir + "theme.json",
              pending = dir + "theme-native-pending.json";
struct State {
    QByteArray bytes;
    int mode = 0644;
    bool operator==(const State& b) const {
        return bytes.isNull() == b.bytes.isNull() && bytes == b.bytes && (bytes.isNull() || mode == b.mode);
    }
    QJsonObject json() const {
        return {{"data", bytes.isNull() ? QJsonValue(QJsonValue::Null)
                                        : QJsonValue(QString::fromLatin1(bytes.toBase64()))},
                {"mode", mode}};
    }
    static State parse(const QJsonValue& v) {
        auto obj = v.toObject();
        auto m = obj.value("mode");
        auto data = obj.value("data");
        if (m.toInt(-1) < 0 || m.toInt() > 0777 || (!data.isString() && !data.isNull()))
            fail("Invalid theme backup.");
        if (data.isNull())
            return {{}, m.toInt()};
        auto decoded = QByteArray::fromBase64Encoding(data.toString().toLatin1(),
                                                      QByteArray::AbortOnBase64DecodingErrors);
        if (!decoded)
            fail("Invalid theme backup encoding.");
        return {decoded.decoded.isNull() ? QByteArray("") : decoded.decoded, m.toInt()};
    }
};
QString path(const QString& home, const QString& rel) {
    auto next = home;
    if (!home.startsWith('/') || QFileInfo(home).isSymLink())
        fail("Unsafe home directory.");
    for (const auto& part : rel.split('/')) {
        if (part.isEmpty() || part == "." || part == "..")
            fail("Invalid theme path.");
        next += "/" + part;
        if (QFileInfo(next).isSymLink())
            fail("Refusing a symbolic link: " + next);
    }
    return next;
}
State read(const QString& home, const QString& rel) {
    auto name = path(home, rel);
    int fd = ::open(QFile::encodeName(name).constData(), O_RDONLY | O_NOFOLLOW | O_NONBLOCK | O_CLOEXEC);
    if (fd < 0) {
        if (errno == ENOENT)
            return {};
        fail("Cannot read " + name);
    }
    QFile f;
    if (!f.open(fd, QIODevice::ReadOnly, QFileDevice::AutoCloseHandle)) {
        close(fd);
        fail("Cannot read " + name);
    }
    struct stat st{};
    auto limit = rel == pending ? 64 * 1024 * 1024 : 16 * 1024 * 1024;
    if (fstat(fd, &st) || !S_ISREG(st.st_mode) || st.st_uid != getuid() || (st.st_mode & 07000) ||
        st.st_size > limit)
        fail("Unsupported theme file: " + name);
    auto bytes = f.read(limit + 1);
    struct stat after{};
    if (f.error() != QFileDevice::NoError || bytes.size() != st.st_size || fstat(fd, &after) ||
        st.st_mtim.tv_sec != after.st_mtim.tv_sec || st.st_mtim.tv_nsec != after.st_mtim.tv_nsec)
        fail("Concurrent change: " + name);
    return {bytes.isNull() ? QByteArray("") : bytes, int(st.st_mode & 0777)};
}
void write(const QString& home, const QString& rel, const State& from, const State& to) {
    auto name = path(home, rel);
    if (read(home, rel) != from)
        fail("Concurrent theme edit: " + name);
    if (from == to)
        return;
    if (to.bytes.isNull()) {
        if (!QFile::remove(name))
            fail("Cannot remove " + name);
        return;
    }
    if (!QDir().mkpath(QFileInfo(name).absolutePath()))
        fail("Cannot create theme directory.");
    QSaveFile f(name);
    f.setDirectWriteFallback(false);
    const auto permissions = QFileDevice::Permissions::fromInt(((to.mode & 0700) << 6) |
                                                               ((to.mode & 0070) << 1) | (to.mode & 7));
    if (!f.open(QIODevice::WriteOnly) || !f.setPermissions(permissions) ||
        f.write(to.bytes) != to.bytes.size() || !f.flush() || fsync(f.handle()) ||
        read(home, rel) != from || !f.commit())
        fail("Could not commit theme file: " + name);
}
struct Lock {
    int fd;
    explicit Lock(const QString& home) {
        auto name = path(home, dir + "theme.lock");
        if (!QDir().mkpath(QFileInfo(name).absolutePath()))
            fail("Cannot create the theme state directory.");
        fd = ::open(QFile::encodeName(name).constData(), O_NOFOLLOW | O_RDWR | O_CREAT | O_CLOEXEC, 0600);
        if (fd < 0)
            fail("Could not open theme lock.");
        struct stat st{};
        if (fstat(fd, &st) || !S_ISREG(st.st_mode) || st.st_uid != getuid() ||
            flock(fd, LOCK_EX | LOCK_NB)) {
            close(fd);
            fail("Theme settings are busy or the lock file is invalid.");
        }
    }
    ~Lock() { close(fd); }
};
using States = QMap<QString, State>;
QJsonObject serialize(const States& states) {
    QJsonObject o;
    for (auto i = states.cbegin(); i != states.cend(); ++i)
        o[i.key()] = i->json();
    return o;
}
States parseStates(const QJsonObject& o, const QStringList& names) {
    if (o.keys() != names)
        fail("Unexpected inventory in theme record.");
    States out;
    for (const auto& name : names)
        out[name] = State::parse(o.value(name));
    return out;
}
QJsonObject object(const QByteArray& bytes) {
    auto doc = QJsonDocument::fromJson(bytes);
    if (!doc.isObject())
        fail("Invalid theme receipt.");
    return doc.object();
}
QJsonObject record(const Edit& e, const QJsonValue& before) {
    QJsonObject r{{"file", e.path}, {"kind", e.kind}, {"after", e.desired}, {"before", before}};
    if (e.kind == "ini") {
        r["section"] = e.section;
        r["key"] = e.key;
    }
    return r;
}
QString presetFrom(const QJsonObject& r) {
    for (const auto& item : r["edits"].toArray()) {
        auto e = item.toObject();
        if (e["file"] == ".config/doroshell/theme.conf" && e["key"] == "name" && e["section"] == "Theme")
            return e["after"].toString();
    }
    fail("Missing theme selection in receipt.");
}
QStringList paths(const QList<Edit>& list) {
    QSet<QString> s;
    for (const auto& edit : list)
        s.insert(edit.path);
    auto names = s.values();
    names.sort();
    return names;
}
QJsonArray entries(const QList<Edit>& list, const States& backup) {
    QJsonArray a;
    for (const auto& e : list)
        a << record(e, readValue(e, backup[e.path].bytes));
    return a;
}
States image(const QList<Edit>& list, States backup, bool legacy) {
    for (const auto& e : list) {
        auto& state = backup[e.path];
        state.bytes = legacy ? rc2Value(e, state.bytes, e.desired) : setValue(e, state.bytes, e.desired);
    }
    return backup;
}
struct Plan {
    States result;
    State manifest;
};
Plan plan(const QString& preset, bool restore, const States& from, const State& previous) {
    auto editsWanted = edits(preset);
    auto names = paths(editsWanted);
    auto backup = from;
    QList<Edit> old;
    if (!previous.bytes.isNull()) {
        if (previous.mode != 0600)
            fail("Unexpected permissions on the theme receipt.");
        auto prior = object(previous.bytes);
        if (prior.contains("version") && prior["version"] != 1)
            fail("Unsupported theme receipt version.");
        auto saved = presetFrom(prior);
        old = edits(saved);
        backup = parseStates(prior["backup"].toObject(), names);
        if (entries(old, backup) != prior["edits"].toArray())
            fail("Theme receipt differs from the supported RC2 or native inventory.");
        for (const auto& e : old) {
            const auto state = from[e.path];
            if (state.bytes.isNull() || state.mode != backup[e.path].mode ||
                readValue(e, state.bytes) != e.desired)
                fail("Personal edit to a managed file or setting: " + e.path +
                     (e.key.isEmpty() ? "" : " / " + e.key));
        }
    } else if (restore)
        return {from, {}};
    QJsonObject manifest{
        {"version", 1}, {"edits", entries(editsWanted, backup)}, {"backup", serialize(backup)}};
    auto result = from;
    if (!restore) {
        for (const auto& e : editsWanted) {
            auto& current = result[e.path];
            current.bytes = setValue(e, current.bytes, e.desired);
        }
        return {result, {QJsonDocument(manifest).toJson(QJsonDocument::Compact), 0600}};
    }
    // An unchanged configuration can be restored byte-for-byte, including
    // ownership of absence, delimiters, blank sections, comments and file mode.
    auto native = image(old, backup, false), legacy = image(old, backup, true);
    for (const auto& name : names) {
        if (from[name] == native[name] || from[name] == legacy[name])
            result[name] = backup[name];
        else {
            for (const auto& edit : old)
                if (edit.path == name) {
                    auto v = readValue(edit, backup[name].bytes);
                    result[name].bytes = setValue(edit, result[name].bytes, v);
                }
        }
    }
    return {result, {}};
}
void layout(const QString& home) {
    auto config = qEnvironmentVariable("XDG_CONFIG_HOME");
    if (!config.isEmpty() && QDir::cleanPath(config) != home + "/.config")
        fail("Theme settings require the standard home configuration directory.");
}
} // namespace
QJsonObject status(const QString& home) {
    layout(home);
    auto e = Edit{".config/doroshell/theme.conf", "ini", "Theme", "name", {}};
    auto selected = readValue(e, read(home, e.path).bytes);
    return {{"preset", selected.toString("windows")},
            {"managed", !read(home, receipt).bytes.isNull()},
            {"pending", !read(home, pending).bytes.isNull()}};
}
QStringList change(const QString& home, const QString& preset, bool preview, bool restore) {
    layout(home);
    auto list = edits(preset);
    auto names = paths(list);
    std::unique_ptr<Lock> lock;
    if (!preview)
        lock = std::make_unique<Lock>(home);
    auto journal = read(home, pending), manifest = read(home, receipt);
    auto originalManifest = manifest;
    States current, from;
    for (const auto& name : names)
        current[name] = read(home, name);
    QJsonObject history;
    if (!journal.bytes.isNull()) {
        history = object(journal.bytes);
        if (journal.mode != 0600 || history["version"] != 1 || !history["restore"].isBool() ||
            !presets().contains(history["preset"].toString()))
            fail("Invalid pending theme transaction.");
        if (history["restore"] != restore || history["preset"] != preset)
            fail("Resume the pending change with doroshell-theme " +
                 (history["restore"].toBool() ? QString("--restore")
                                              : "--apply " + history["preset"].toString()));
        from = parseStates(history["files"].toObject(), names);
        originalManifest = State::parse(history["receipt"]);
    } else {
        from = current;
        history = {{"version", 1},
                   {"restore", restore},
                   {"preset", preset},
                   {"files", serialize(from)},
                   {"receipt", manifest.json()}};
    }
    auto target = plan(preset, restore, from, originalManifest);
    constexpr qsizetype fileLimit = 16 * 1024 * 1024;
    if (target.manifest.bytes.size() > fileLimit ||
        std::any_of(target.result.cbegin(), target.result.cend(),
                    [](const State& s){ return s.bytes.size() > fileLimit; }))
        fail("Theme output exceeds the supported size limit.");
    if (manifest != originalManifest && manifest != target.manifest)
        fail("Theme receipt changed during the transaction.");
    QStringList summary;
    for (const auto& name : names) {
        if (current[name] != from[name] && current[name] != target.result[name])
            fail("Concurrent theme edit: " + name);
        if (current[name] != target.result[name])
            summary << name;
    }
    if (summary.isEmpty() && manifest == target.manifest && journal.bytes.isNull())
        return {"Theme settings already match."};
    if (preview) {
        if (summary.isEmpty())
            summary << "Theme receipt";
        return summary;
    }
    if (journal.bytes.isNull()) {
        auto data = QJsonDocument(history).toJson(QJsonDocument::Compact);
        if (data.size() > 64 * 1024 * 1024)
            fail("Theme transaction exceeds the backup size limit.");
        journal = {data, 0600};
        write(home, pending, {}, journal);
    }
    for (const auto& name : names)
        write(home, name, current[name], target.result[name]);
    for (const auto& name : names)
        if (read(home, name) != target.result[name])
            fail("Theme file changed before completion: " + name);
    write(home, receipt, manifest, target.manifest);
    write(home, pending, journal, {});
    if (summary.isEmpty())
        summary << "Theme receipt";
    return summary;
}
} // namespace theme
