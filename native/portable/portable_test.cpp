#include "portable.hpp"
#include <cstdio>
#include <sys/stat.h>
using namespace portable;
namespace {
void check(bool result, const char* msg) {
    if (!result)
        fail(msg);
}
template <class F> void refused(F f, const char* msg) {
    bool error = false;
    try {
        f();
    } catch (const std::exception&) {
        error = true;
    }
    check(error, msg);
}
void put(const QString& path, const QByteArray& bytes) {
    QDir().mkpath(QFileInfo(path).absolutePath());
    QFile f(path);
    check(f.open(QIODevice::WriteOnly) && f.write(bytes) == bytes.size(), "file write");
}
} // namespace
int main(int argc, char** argv) {
    QCoreApplication app(argc, argv);
    try {
        QTemporaryDir home;
        check(home.isValid(), "temporary home");
        auto config = home.filePath(".config"), base = config + "/lxqt-comfort/";
        Store store(config);
        auto baseline = store.exportSettings();
        validatePortable(baseline);
        auto path = [&](const QString& name) { return base + name; };
        auto personal = QByteArray(
            R"({"version":2,"folders":[{"label":"Private medical","path":"/private/medical","visible":true},{"type":"separator"},{"label":"My docs","standard":"DocumentsLocation","visible":true}],"portrait":"/private/image.png","portraitCrop":{"x":0.5,"y":0.5,"zoom":2},"hiddenSystemLinks":["computer"]})");
        auto history = QByteArray(
            R"({"enabled":true,"items":["private.desktop"],"launched_at":{"private.desktop":89000}})");
        put(path(files[2]), personal);
        put(path(files[1]), history);
        chmod(QFile::encodeName(path(files[1])).constData(), 0640);
        auto value = store.exportSettings();
        auto bytes = encode(value);
        check(!bytes.contains("private") && !bytes.contains("medical") && !bytes.contains("portrait") &&
                  !bytes.contains("My docs"),
              "path-free export");
        value.get("preferences").set("primary", str("lockscreen"));
        auto p = store.plan(value);
        check(!QFileInfo::exists(path(files[0])), "preview writes nothing");
        store.apply(p);
        auto local = decode(Store::read(path(files[2])).bytes);
        check(local.get("portrait").str() == "/private/image.png" &&
                  decode(Store::read(path(files[1])).bytes).get("launched_at").has("private.desktop"),
              "private state preserved");
        store.restore();
        check(!QFileInfo::exists(path(files[0])) && Store::read(path(files[1])).bytes == history &&
                  Store::read(path(files[1])).mode == 0640,
              "restored bytes mode and absence");
        auto v1 = Json(json_deep_copy(baseline.ptr()));
        v1.set("version", number(1));
        store.apply(store.plan(v1));
        check(decode(Store::read(path(files[2])).bytes).get("folders").list()[1].has("type"),
              "V1 preserves local separators");
        store.restore();
        auto v2 = Json(json_deep_copy(v1.ptr()));
        v2.set("version", number(2));
        store.apply(store.plan(v2));
        for (const auto& link : decode(Store::read(path(files[2])).bytes).get("folders").list())
            check(!link.has("type"), "V2 replaces separators");
        auto current = Store::read(path(files[2])).bytes;
        put(path(files[2]), current + " ");
        refused([&] { store.restore(); }, "refuse later personal edit");
        put(path(files[2]), current);
        chmod(QFile::encodeName(path(files[2])).constData(), 0600);
        store.restore();
        auto changes = store.plan(value);
        put(path(files[0]), R"({"version":1,"action":"reboot"})");
        refused([&] { store.apply(changes); }, "stale preview");
        auto tiny = Json(json_deep_copy(v1.ptr()));
        tiny.get("preferences").get("recent").set("limit", number(1));
        put(path(files[1]), R"({"enabled":true,"items":["one","two"]})");
        refused([&] { store.plan(tiny); }, "prevent local history truncation");
        refused([] { decode(R"({"limit":1,"limit":2})"); }, "duplicate keys");
        auto invalid = Json(json_deep_copy(v1.ptr()));
        invalid.set("version", Json(json_real(1.0)));
        refused([&] { validatePortable(invalid); }, "strict version type");
        QFile::remove(path(files[2]));
        QFile::link(home.filePath("missing"), path(files[2]));
        refused([&] { store.exportSettings(); }, "symlink refusal");
        check(!QFileInfo::exists(home.filePath("missing")), "symlink target left alone");
        QTemporaryDir recoveryHome;
        Store recover(recoveryHome.path());
        auto root = recoveryHome.filePath("lxqt-comfort/");
        auto undo = root + "portable-settings-undo.json";
        auto pending = root + ".portable-settings-pending.json";
        auto savedState = [](const QByteArray& bytes) {
            auto s = object();
            s.set("data", bytes.isNull() ? null() : str(QString::fromLatin1(bytes.toBase64())));
            s.set("mode", number(0600));
            return s;
        };
        for (bool restoring : {false, true}) {
            recover.apply(recover.plan(recover.exportSettings()));
            auto receipt = Store::read(undo).bytes;
            auto changes = decode(receipt).get("changes");
            if (restoring) {
                for (auto key : changes.keys()) {
                    auto item = changes.get(key.toLatin1().constData());
                    auto original = item.get("before");
                    item.set("before", item.get("after"));
                    item.set("after", original);
                }
            }
            auto control = object();
            control.set("before", savedState(restoring ? receipt : QByteArray()));
            control.set("after", savedState(restoring ? QByteArray() : receipt));
            changes.set("portable-settings-undo.json", control);
            auto j = object();
            j.set("version", number(1));
            j.set("changes", changes);
            put(pending, encode(j));
            chmod(QFile::encodeName(pending).constData(), 0600);
            QFile::remove(root + files[1]); // Simulate an interruption after one file change.
            if (!restoring)
                QFile::remove(undo);
            recover.restore();
            check(!QFileInfo::exists(undo) && !QFileInfo::exists(pending),
                  "recover import/restore receipt");
            for (auto name : files)
                check(!QFileInfo::exists(root + name), "partial transaction restored");
        }
        // The existing RC2 rollback format contains base64 strings and no version envelope.
        QByteArray original = "{\"version\":1,\"action\":\"shutdown\"}\n",
                   installed = "{\"version\":1,\"action\":\"logout\"}\n";
        auto legacy = object(), entry = object();
        entry.set("before", str(QString::fromLatin1(original.toBase64())));
        entry.set("after", str(QString::fromLatin1(installed.toBase64())));
        legacy.set("session-button.json", entry);
        put(undo, encode(legacy));
        chmod(QFile::encodeName(undo).constData(), 0600);
        put(root + files[0], installed);
        chmod(QFile::encodeName(root + files[0]).constData(), 0600);
        recover.restore();
        check(Store::read(root + files[0]).bytes == original, "RC2 rollback compatibility");
        return 0;
    } catch (const std::exception& e) {
        std::fprintf(stderr, "%s\n", e.what());
        return 1;
    }
}
