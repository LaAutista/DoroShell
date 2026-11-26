#include "theme.hpp"
#include <cstdio>
#include <sys/stat.h>
using namespace theme;
namespace {
void require(bool ok, const QString& why) {
    if (!ok)
        fail(why);
}
void put(const QString& name, const QByteArray& bytes) {
    require(QDir().mkpath(QFileInfo(name).absolutePath()), "directory");
    QFile f(name);
    require(f.open(QIODevice::WriteOnly) && f.write(bytes) == bytes.size(), "write");
}
QByteArray get(const QString& name) {
    QFile f(name);
    require(f.open(QIODevice::ReadOnly), "read " + name);
    return f.readAll();
}
} // namespace
int main(int argc, char** argv) {
    QCoreApplication app(argc, argv);
    try {
        QTemporaryDir tmp;
        require(tmp.isValid(), "temporary home");
        auto home = tmp.path();
        qputenv("XDG_CONFIG_HOME", (home + "/.config").toUtf8());
        const QStringList hashes = {"f43841d4d7cdbf4b102e1097d303b828b2d4b27f05d773bcfeff4fa5e96060b0",
                                    "800ea98dfe58d0fd2b49346d48c2901802e61a0b1b7afea8ca982d41810ca835",
                                    "6bb953fc140082963c46b13452083ebca9eb80515c6808a2ec4617602e83d21d",
                                    "1a06309aacd2e2a79dfc52d1ccfac5defb356cf5a67315abd0da92cdeaa6470d"};
        for (int i = 0; i < hashes.size(); ++i) {
            QMap<QString, QByteArray> files;
            for (const auto& e : edits(presets()[i]))
                if (e.kind == "file")
                    files[e.path] = QByteArray::fromBase64(e.desired.toString().toLatin1());
            QCryptographicHash hash(QCryptographicHash::Sha256);
            for (const auto& bytes : files)
                hash.addData(bytes);
            require(files.size() == 7 && hash.result().toHex() == hashes[i],
                    "output mismatch with RC2: " + presets()[i]);
        }
        Edit ob{".config/openbox/rc.xml", "obtheme", {}, {}, "DoroShell"};
        for (const auto& source : QList<QByteArray>{
                 "<ob:openbox_config xmlns:ob='urn:openbox'/>",
                 "<ob:openbox_config xmlns:ob='urn:openbox'><ob:theme font='kept'/></ob:openbox_config>"}) {
            auto updated = setValue(ob, source, ob.desired);
            require(readValue(ob, updated) == ob.desired && updated.contains("<ob:name>"),
                    "namespace preserved");
        }
        auto rc = home + "/.config/openbox/rc.xml", ini = home + "/.config/lxqt/lxqt.conf",
             manifest = home + "/.local/state/doroshell/theme.json";
        QByteArray xml =
            "<?xml version=\"1.0\"?><openbox_config><!-- saved --><theme><name>Personal &amp; "
            "blue</name><font place=\"Menu\"><name>Serif</name></font></theme></openbox_config>\n";
        QByteArray settings = "[General]\r\nicon_theme =custom\r\n[Extra]\r\nkeep=true\r\n";
        put(rc, xml);
        put(ini, settings);
        chmod(QFile::encodeName(rc).constData(), 0640);
        require(!status(home)["managed"].toBool(), "fresh home");
        change(home, "windows", true, false);
        require(!QFileInfo::exists(manifest) && get(rc) == xml, "preview is read-only");
        for (auto preset : presets()) {
            change(home, preset, false, false);
            auto raw = get(manifest);
            require(status(home)["preset"] == preset, "selected preset");
            change(home, preset, false, false);
            require(get(manifest) == raw, "repeat stable");
            require(get(rc).contains("<name>DoroShell</name>") && get(rc).contains("<name>Serif</name>"),
                    "scoped XML edit");
        }
        auto expected = get(ini);
        put(ini, expected + "# unrelated\r\n");
        change(home, "windows", false, true);
        require(get(ini).contains("# unrelated\r\n") && get(ini).contains("icon_theme =custom\r\n"),
                "personal INI change preserved");
        require(get(rc) == xml && !QFileInfo::exists(manifest) &&
                    !QFileInfo::exists(home + "/.config/katerc"),
                "exact absence and XML restored");
        change(home, "windows", false, false);
        auto sheet = home + "/.config/doroshell/panel-theme.qss";
        auto original = get(sheet);
        put(sheet, original + "/* mine */");
        auto before = get(manifest);
        bool refused = false;
        try {
            change(home, "spring", false, false);
        } catch (const std::exception&) {
            refused = true;
        }
        require(refused && get(manifest) == before && status(home)["preset"] == "windows",
                "conflict preflight");
        put(sheet, original);
        change(home, "windows", false, true);
        // Model a process kill immediately after the first config write and
        // before the receipt commit, using the saved pre-operation inventory.
        QJsonObject files;
        for (const auto& e : edits("polar")) {
            auto name = home + "/" + e.path;
            QJsonValue data = QJsonValue::Null;
            int mode = 0644;
            if (QFileInfo::exists(name)) {
                data = QString::fromLatin1(get(name).toBase64());
                struct stat st{};
                require(!stat(QFile::encodeName(name).constData(), &st), "stat");
                mode = st.st_mode & 0777;
            }
            files[e.path] = QJsonObject{{"data", data}, {"mode", mode}};
        }
        QJsonObject journal{{"version", 1},
                            {"preset", "polar"},
                            {"restore", false},
                            {"files", files},
                            {"receipt", QJsonObject{{"data", QJsonValue::Null}, {"mode", 0644}}}};
        auto pending = home + "/.local/state/doroshell/theme-native-pending.json";
        put(pending, QJsonDocument(journal).toJson(QJsonDocument::Compact));
        chmod(QFile::encodeName(pending).constData(), 0600);
        put(rc, setValue(ob, xml, ob.desired));
        put(ini, get(ini) + "# changed mid-transaction\n");
        bool blocked = false;
        try {
            change(home, "polar", false, false);
        } catch (const std::exception&) {
            blocked = true;
        }
        require(blocked && !QFileInfo::exists(manifest) && QFileInfo::exists(pending),
                "pending conflict preserved");
        put(ini, QByteArray::fromBase64(
                     files[".config/lxqt/lxqt.conf"].toObject()["data"].toString().toLatin1()));
        change(home, "polar", false, false);
        require(!QFileInfo::exists(pending) && status(home)["managed"].toBool(),
                "interrupted apply recovered");
        change(home, "windows", false, true);
        require(get(rc) == xml, "interrupted transaction undoes exactly");
        return 0;
    } catch (const std::exception& e) {
        std::fprintf(stderr, "%s\n", e.what());
        return 1;
    }
}
