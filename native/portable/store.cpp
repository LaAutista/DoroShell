#include "portable.hpp"
#include <fcntl.h>
#include <sys/file.h>
#include <sys/stat.h>
#include <unistd.h>
namespace portable {
namespace {
const QString undo = "portable-settings-undo.json", pending = ".portable-settings-pending.json";
constexpr auto undoLimit = limit * 10;
constexpr auto journalLimit = limit * 44;
void safe(const QString& path) {
    if (!path.startsWith('/') || QDir::cleanPath(path) != path)
        fail("Settings path must be absolute and normalized.");
    QString dir = path;
    while (dir != "/") {
        if (QFileInfo(dir).isSymLink())
            fail("Symbolic links are not supported for settings files.");
        dir = QFileInfo(dir).absolutePath();
    }
}
void put(const QString& file, const State& from, const State& to, qsizetype cap) {
    if (Store::read(file, cap) != from)
        fail("Settings changed after preview.");
    if (from == to)
        return;
    if (to.bytes.isNull()) {
        safe(file);
        if (!QFile::remove(file))
            fail("Cannot remove " + file);
        return;
    }
    if (to.bytes.size() > cap)
        fail("Settings exceed the size limit.");
    if (!QDir().mkpath(QFileInfo(file).absolutePath()))
        fail("Cannot create the settings directory.");
    QSaveFile f(file);
    f.setDirectWriteFallback(false);
    auto permissions = QFileDevice::Permissions::fromInt(((to.mode & 0700) << 6) | ((to.mode & 0070) << 1) |
                                                         (to.mode & 7));
    if (!f.open(QIODevice::WriteOnly) || !f.setPermissions(permissions) ||
        f.write(to.bytes) != to.bytes.size() || !f.flush() || fsync(f.handle()) ||
        Store::read(file, cap) != from || !f.commit())
        fail("Could not commit " + file);
}
struct Lock {
    int fd;
    explicit Lock(const QString& base) {
        safe(base);
        if (!QDir().mkpath(base))
            fail("Cannot create the settings directory.");
        auto file = base + "/.portable-settings.lock";
        safe(file);
        fd = ::open(QFile::encodeName(file).constData(), O_RDWR | O_CREAT | O_CLOEXEC | O_NOFOLLOW, 0600);
        if (fd < 0)
            fail("Cannot open the portable settings lock.");
        struct stat st{};
        if (fstat(fd, &st) || !S_ISREG(st.st_mode) || st.st_uid != getuid() ||
            flock(fd, LOCK_EX | LOCK_NB)) {
            close(fd);
            fail("Portable settings are busy or the lock file is invalid.");
        }
    }
    ~Lock() { close(fd); }
};
Json packed(const State& s) {
    auto v = object();
    v.set("mode", number(s.mode));
    v.set("data", s.bytes.isNull() ? null() : str(QString::fromLatin1(s.bytes.toBase64())));
    return v;
}
State unpack(const Json& v, qsizetype cap, bool legacy = false) {
    State s;
    auto data = v;
    if (!legacy) {
        auto mode = v.get("mode");
        if (v.keys() != QStringList{"data", "mode"} || !json_is_integer(mode.ptr()) || mode.integer() < 0 ||
            mode.integer() > 0777)
            fail("Invalid rollback record.");
        s.mode = mode.integer();
        data = v.get("data");
    }
    if (json_is_null(data.ptr()))
        return s;
    if (!data.string())
        fail("Invalid backup.");
    auto bytes =
        QByteArray::fromBase64Encoding(data.str().toLatin1(), QByteArray::AbortOnBase64DecodingErrors);
    if (!bytes || bytes.decoded.size() > cap)
        fail("Invalid or oversized rollback data.");
    s.bytes = bytes.decoded.isNull() ? QByteArray("") : bytes.decoded;
    return s;
}
Json packedChanges(const Changes& changes) {
    auto items = object();
    for (auto it = changes.cbegin(); it != changes.cend(); ++it) {
        auto item = object();
        item.set("before", packed(it->before));
        item.set("after", packed(it->after));
        items.set(it.key().toLatin1().constData(), item);
    }
    return items;
}
Changes parseChanges(const Json& items, bool includeUndo, bool legacy = false) {
    if (!items.object() || items.keys().isEmpty())
        fail("Invalid rollback record.");
    Changes out;
    for (const auto& name : items.keys()) {
        if (!files.contains(name) && !(includeUndo && name == undo))
            fail("Unexpected rollback file.");
        auto item = items.get(name.toLatin1().constData());
        if (item.keys() != QStringList{"after", "before"})
            fail("Invalid rollback entry.");
        auto cap = name == undo ? undoLimit : limit;
        Change c{unpack(item.get("before"), cap, legacy), unpack(item.get("after"), cap, legacy)};
        if (!includeUndo) {
            if (c.after.bytes.isNull())
                fail("Missing previous import output.");
            if (!c.before.bytes.isNull())
                validateLocal(name, decode(c.before.bytes));
            validateLocal(name, decode(c.after.bytes));
        }
        out[name] = c;
    }
    return out;
}
void replay(const QString& base, const Changes& changes, bool forward, bool exact) {
    QStringList order = changes.keys();
    if (order.removeOne(undo))
        order << undo;
    QMap<QString, State> current, desired;
    for (const auto& name : order) {
        auto cap = name == undo ? undoLimit : limit;
        auto actual = Store::read(base + "/" + name, cap);
        auto c = changes[name];
        auto from = forward ? c.before : c.after, to = forward ? c.after : c.before;
        if (actual != from && (exact || actual != to))
            fail("Settings changed since preview or import. Restore refused: " + name);
        desired[name] = to;
        current[name] = actual;
    }
    for (const auto& name : order)
        put(base + "/" + name, current[name], desired[name], name == undo ? undoLimit : limit);
}
Changes restored(const State& record) {
    auto doc = decode(record.bytes, undoLimit);
    bool legacy = !doc.has("version");
    if (!legacy && (doc.keys() != QStringList{"changes", "version"} ||
                    !json_is_integer(doc.get("version").ptr()) || doc.get("version").integer() != 2))
        fail("Invalid portable rollback record.");
    auto changes = parseChanges(legacy ? doc : doc.get("changes"), false, legacy);
    for (auto& change : changes)
        std::swap(change.before, change.after);
    return changes;
}
} // namespace
Store::Store(const QString& config) : base(QDir(config).absoluteFilePath("lxqt-comfort")) { safe(base); }
State Store::read(const QString& file, qsizetype cap) {
    safe(file);
    auto fd = ::open(QFile::encodeName(file).constData(), O_RDONLY | O_NOFOLLOW | O_NONBLOCK | O_CLOEXEC);
    if (fd < 0) {
        if (errno == ENOENT)
            return {};
        fail("Cannot open " + file);
    }
    QFile f;
    if (!f.open(fd, QIODevice::ReadOnly, QFileDevice::AutoCloseHandle)) {
        close(fd);
        fail("Cannot read " + file);
    }
    struct stat st{}, after{};
    if (fstat(fd, &st) || !S_ISREG(st.st_mode) || (st.st_mode & 07000) || st.st_size > cap)
        fail("Unsupported or oversized settings file.");
    auto data = f.read(cap + 1);
    if (f.error() != QFileDevice::NoError || data.size() != st.st_size || fstat(fd, &after) ||
        st.st_mtim.tv_sec != after.st_mtim.tv_sec || st.st_mtim.tv_nsec != after.st_mtim.tv_nsec)
        fail("Concurrent settings edit.");
    return {data.isNull() ? QByteArray("") : data, int(st.st_mode & 0777)};
}
QMap<QString, State> Store::snapshot(Values& local) const {
    QMap<QString, State> states;
    for (auto& name : files) {
        auto s = read(base + "/" + name);
        states[name] = s;
        if (!s.bytes.isNull()) {
            auto v = decode(s.bytes);
            validateLocal(name, v);
            local[name] = v;
        }
    }
    return states;
}
Json Store::exportSettings() const {
    Values local;
    snapshot(local);
    return exportValues(local);
}
void Store::exportFile(const QString& name, bool overwrite) const {
    auto out = QFileInfo(name).absoluteFilePath();
    if (out.startsWith(base + "/") || out == base)
        fail("Choose an export destination outside the local Start settings directory.");
    auto previous = read(out);
    if (!previous.bytes.isNull() && !overwrite)
        fail("Choose a new export file or confirm replacement in the dialog.");
    put(out, previous, {encode(exportSettings()), 0600}, limit);
}
Changes Store::plan(const Json& v) const {
    Values local;
    auto snapshotFiles = snapshot(local);
    auto after = importValues(local, v);
    Changes changes;
    for (const auto& name : files) {
        if (local.contains(name) && local[name] == after[name])
            continue;
        auto bytes = encode(after[name]);
        if (bytes.size() > limit)
            fail("Updated preferences exceed the safe size limit.");
        changes[name] = {snapshotFiles[name], {bytes, 0600}};
    }
    return changes;
}
void Store::transaction(const Changes& changes) const {
    auto jpath = base + "/" + pending;
    auto previous = read(jpath, journalLimit);
    if (!previous.bytes.isNull())
        fail("An interrupted change needs recovery. Use Restore last import.");
    auto j = object();
    j.set("version", number(1));
    j.set("changes", packedChanges(changes));
    auto journal = State{encode(j), 0600};
    for (auto it = changes.cbegin(); it != changes.cend(); ++it)
        if (read(base + "/" + it.key(), it.key() == undo ? undoLimit : limit) != it->before)
            fail("Settings changed after preview; preview again.");
    put(jpath, {}, journal, journalLimit);
    try {
        replay(base, changes, true, true);
        put(jpath, journal, {}, journalLimit);
    } catch (...) {
        // Restore only bytes still matching this operation, including the
        // former undo file. The journal stays private until rollback succeeds.
        replay(base, changes, false, false);
        put(jpath, journal, {}, journalLimit);
        throw;
    }
}
void Store::apply(const Changes& changes) const {
    if (changes.isEmpty())
        return;
    Lock guard(base);
    for (auto i = changes.cbegin(); i != changes.cend(); ++i) {
        if (!files.contains(i.key()) || i->after.bytes.isNull() || i->after.bytes.size() > limit)
            fail("Invalid import plan.");
        validateLocal(i.key(), decode(i->after.bytes));
    }
    auto old = read(base + "/" + undo, undoLimit);
    auto record = object();
    record.set("version", number(2));
    record.set("changes", packedChanges(changes));
    auto all = changes;
    all[undo] = {old, {encode(record), 0600}};
    transaction(all);
}
void Store::restore() const {
    Lock guard(base);
    auto jpath = base + "/" + pending;
    auto unfinished = read(jpath, journalLimit);
    if (!unfinished.bytes.isNull()) {
        auto j = decode(unfinished.bytes, journalLimit);
        if (unfinished.mode != 0600 || j.keys() != QStringList{"changes", "version"} ||
            !json_is_integer(j.get("version").ptr()) || j.get("version").integer() != 1)
            fail("Invalid interrupted transaction.");
        auto changes = parseChanges(j.get("changes"), true);
        if (!changes.contains(undo))
            fail("Interrupted import has no undo record.");
        // The embedded undo record must independently explain every destination
        // and its exact bytes. A journal cannot enlarge the set of allowed files.
        auto proof = changes.take(undo);
        bool importing = !proof.after.bytes.isNull();
        auto inverse = restored(importing ? proof.after : proof.before);
        if (inverse.keys() != changes.keys())
            fail("Inconsistent interrupted transaction.");
        for (auto i = changes.cbegin(); i != changes.cend(); ++i) {
            const auto& verify = inverse[i.key()];
            if ((importing ? i->before : i->after) != verify.after ||
                (importing ? i->after : i->before) != verify.before)
                fail("Inconsistent interrupted import evidence.");
        }
        changes[undo] = proof;
        // A failed import is reverted. A restore interrupted by process death
        // finishes restoring the original settings.
        replay(base, changes, !importing, false);
        put(jpath, unfinished, {}, journalLimit);
        return;
    }
    auto old = read(base + "/" + undo, undoLimit);
    if (old.bytes.isNull())
        fail("No portable import to restore.");
    auto changes = restored(old);
    changes[undo] = {old, {}};
    transaction(changes);
}
} // namespace portable
