// SPDX-License-Identifier: GPL-2.0-or-later
#include "profile.hpp"
#include "../setup/files.hpp"
#include <QCommandLineParser>
#include <QCoreApplication>
#include <QCryptographicHash>
#include <QJsonDocument>
#include <QProcess>
#include <QProcessEnvironment>
#include <QTextStream>
#include <optional>
#include <algorithm>
#include <fcntl.h>
#include <sys/file.h>
#include <sys/stat.h>
#include <unistd.h>

namespace
{
using namespace doro_files;
const QString config = ".config/doroshell/panel.conf", autostart = ".config/autostart/lxqt-panel.desktop";
const QString record = ".local/state/doroshell-native/panel.json";
const QStringList targets{config, autostart};
const QString legacyRecord = ".local/state/doroshell/native-panel.json";
QString hash(const QByteArray &x)
{
    return QString::fromLatin1(QCryptographicHash::hash(x, QCryptographicHash::Sha256).toHex());
}
QJsonObject state(const QByteArray &data, int mode = 0600)
{
    return {{"exists", true}, {"mode", mode}, {"data", QString::fromLatin1(data.toBase64())}};
}
class Lock
{
    int fd = -1;

  public:
    explicit Lock(const QString &home)
    {
        // The legacy profile writer uses this same flock.
        const auto target = path(home, ".local/state/doroshell/native-panel.lock");
        makeParents(target);
        fd = ::open(QFile::encodeName(target).constData(), O_CREAT | O_RDWR | O_NOFOLLOW | O_CLOEXEC, 0600);
        struct stat info{};
        if (fd < 0 || fstat(fd, &info) || !S_ISREG(info.st_mode) || info.st_uid != getuid() ||
            flock(fd, LOCK_EX | LOCK_NB)) {
            if (fd >= 0)
                ::close(fd);
            fail("Cannot acquire the user panel staging lock");
        }
    }
    ~Lock() { ::close(fd); }
    Lock(const Lock &) = delete;
    Lock &operator=(const Lock &) = delete;
};

QByteArray stock(const QString &home)
{
    const auto personal = read(path(home, ".config/lxqt/panel.conf"));
    auto overrides = personal == absent() ? QByteArray{} : bytes(personal);
    if (panelDefinesLayout(overrides))
        return overrides;
    auto roots = qEnvironmentVariable("XDG_CONFIG_DIRS").split(':', Qt::SkipEmptyParts);
    if (roots.isEmpty())
        roots << "/etc/xdg";
    for (const auto &root : roots) {
        if (!QDir::isAbsolutePath(root))
            fail("A relative XDG_CONFIG_DIRS entry is unsupported");
        QFile file(root + "/lxqt/panel.conf");
        if (!file.exists())
            continue;
        if (!QFileInfo(file).isFile() || file.size() > 1024 * 1024 || !file.open(QIODevice::ReadOnly))
            fail("Cannot read stock LXQt panel profile");
        auto data = file.readAll();
        if (file.error() != QFileDevice::NoError)
            fail("Cannot read stock LXQt panel profile");
        return applyPluginOverrides(data, overrides);
    }
    fail("No user or system LXQt panel.conf was found");
}
QString checkBinary(const QString &arg)
{
    QFileInfo info(arg);
    const QString candidate = info.canonicalFilePath();
    if (!QDir::isAbsolutePath(arg) || info.fileName() != "lxqt-panel" || !info.isFile() ||
        !info.isExecutable() || candidate.isEmpty() ||
        candidate == QFileInfo("/usr/bin/lxqt-panel").canonicalFilePath() ||
        !QFileInfo(QFileInfo(candidate).absolutePath() +
                   "/../share/doroshell-panel/patches/0016-network-chooser.patch")
             .isFile())
        fail("Choose the executable in the private patched panel runtime (including its plugin and patch "
             "directories)");
    return candidate;
}
QByteArray entry(const QString &home, const QJsonObject &previous)
{
    QString command = desktopQuote(QCoreApplication::applicationFilePath()) + " --launch";
    if (home != QDir::homePath())
        command += " --home " + desktopQuote(home);
    const auto exec = "Exec=" + command.toUtf8();
    if (previous == absent())
        return "[Desktop Entry]\nType=Application\nName=DoroShell Panel\n" + exec +
               "\nOnlyShowIn=LXQt;\nX-LXQt-Module=true\n";
    auto lines = bytes(previous).split('\n');
    bool main = false, foundGroup = false, foundExec = false, foundType = false;
    for (auto &line : lines) {
        auto key = line.trimmed();
        if (key.startsWith('[')) {
            main = (key == "[Desktop Entry]");
            if (main && foundGroup)
                fail("Duplicate panel autostart Desktop Entry");
            foundGroup |= main;
        } else if (main) {
            if (key.startsWith("Exec=")) {
                if (foundExec)
                    fail("Duplicate panel autostart Exec key");
                auto before = key.mid(5).trimmed();
                if (before != "lxqt-panel" && before != "/usr/bin/lxqt-panel")
                    fail("Existing custom panel autostart command requires manual migration");
                line = exec + (line.endsWith('\r') ? "\r" : "");
                foundExec = true;
            } else if (key == "Type=Application")
                foundType = true;
            else if (key == "Hidden=true" || key == "X-LXQt-Module=false")
                fail("The existing panel autostart entry is disabled");
            else if (key.startsWith("OnlyShowIn=") && !key.mid(11).split(';').contains("LXQt"))
                fail("This panel autostart is restricted to another desktop");
            else if (key.startsWith("NotShowIn=") && key.mid(10).split(';').contains("LXQt"))
                fail("This panel autostart excludes LXQt");
        }
    }
    if (!foundGroup || !foundType || !foundExec)
        fail("Unknown existing LXQt panel autostart entry");
    return lines.join('\n');
}

QJsonObject load(const QString &home)
{
    const auto file = read(path(home, record), 12 * 1024 * 1024);
    if (file == absent())
        return {};
    if (file["mode"].toInt() != 0600)
        fail("Unexpected native panel receipt permissions");
    auto json = QJsonDocument::fromJson(bytes(file));
    auto j = json.object();
    const auto files = j["files"].toObject();
    if (!json.isObject() || j["version"].toInt() != 1 || !QDir::isAbsolutePath(j["binary"].toString()) ||
        !QStringList{"applying", "installed", "undoing"}.contains(j["phase"].toString()) ||
        files.size() != targets.size())
        fail("Invalid native panel receipt");
    for (const auto &key : targets) {
        const auto r = files.value(key).toObject();
        for (auto side : {"original", "after"}) {
            if (!r.value(side).isObject())
                fail("Missing recorded panel file state");
            validate(r[side].toObject());
        }
        if (r["after"].toObject() == absent())
            fail("Invalid panel installation target");
    }
    if (j.contains("edited")) {
        const auto e = j["edited"].toObject();
        if (e == absent() || j["phase"] != "undoing")
            fail("Invalid saved panel edits");
        validate(e);
    }
    return j;
}
void save(const QString &home, const QJsonObject &j)
{
    atomic(path(home, record), QJsonDocument(j).toJson(QJsonDocument::Compact), 0600);
}
void archiveEdits(const QString &home, const QJsonObject &edited)
{
    auto copy = state(bytes(edited), 0600);
    auto dest = path(home, ".local/state/doroshell-native/panel-edited-" + hash(bytes(edited)) + ".conf");
    auto prior = read(dest);
    if (prior == absent())
        write(dest, copy);
    else if (prior != copy)
        fail("Conflicting archived panel settings: " + dest);
    QTextStream(stdout) << "Saved personal panel settings in " << dest << Qt::endl;
}
void finish(const QString &home, QJsonObject j)
{
    const bool undo = j["phase"] == "undoing";
    auto order = targets;
    if (undo)
        std::reverse(order.begin(), order.end()); // Stop selecting the private profile before removing it.
    const auto files = j["files"].toObject();
    auto states = [&](const QString &key) {
        auto r = files[key].toObject();
        auto previous = r[undo ? "after" : "original"].toObject();
        if (undo && key == config && j.contains("edited"))
            previous = j["edited"].toObject();
        return std::pair{previous, r[undo ? "original" : "after"].toObject()};
    };
    auto check = [&](const QString &key) {
        auto [from, to] = states(key);
        auto current = read(path(home, key));
        if (from != current && to != current)
            fail("Personal edit; refusing to overwrite " + key);
        return current;
    };
    for (const auto &key : order)
        check(key);
    if (j.contains("edited"))
        archiveEdits(home, j["edited"].toObject());
    for (const auto &key : order) {
        auto to = states(key).second;
        if (check(key) != to)
            write(path(home, key), to);
    }
    for (const auto &key : order)
        if (read(path(home, key)) != states(key).second)
            fail("Panel configuration changed during staging: " + key + " (" +
                 QString::number(read(path(home, key))["mode"].toInt(), 8) + ")");
    if (undo)
        write(path(home, record), absent());
    else {
        j["phase"] = "installed";
        save(home, j);
    }
}

void ensureHome(const QString &home)
{
    auto info = QFileInfo(home);
    if (info.canonicalFilePath() != home || !info.isDir() || info.ownerId() != getuid())
        fail("Choose a canonical, user-owned home directory");
    if (home != QDir::homePath())
        return;
    for (const auto &[var, suffix] : QList<QPair<const char *, QString>>{{"XDG_CONFIG_HOME", "/.config"},
                                                                         {"XDG_DATA_HOME", "/.local/share"},
                                                                         {"XDG_STATE_HOME", "/.local/state"}}) {
        auto override = qEnvironmentVariable(var);
        if (!override.isEmpty() && QDir::cleanPath(override) != home + suffix)
            fail("Custom XDG roots need explicit panel migration");
    }
}

void stage(const QString &home, const QString &op, QString binary, bool keepEdits, const QString &panel)
{
    ensureHome(home);
    if (QFileInfo::exists(path(home, legacyRecord)) ||
        QFileInfo::exists(path(home, ".local/bin/doroshell-native-panel")))
        fail("An RC2 panel installation exists. Its separate ownership and rollback records must be migrated "
             "first.");
    std::optional<Lock> lock;
    if (op != "plan")
        lock.emplace(home);
    if (QFileInfo::exists(path(home, legacyRecord)) ||
        QFileInfo::exists(path(home, ".local/bin/doroshell-native-panel")))
        fail("An RC2 panel installation now owns these settings");
    auto j = load(home);
    if (!j.isEmpty() && !panel.isEmpty() && j["panel"].toString("panel1") != panel)
        fail("A different panel is already selected in this transaction");
    if (!j.isEmpty() && j["phase"] != "installed") {
        if (op != "recover")
            fail("An interrupted panel transaction needs --recover");
        finish(home, j);
        return;
    }
    if (op == "recover" || (op == "undo" && j.isEmpty()))
        return;
    if (op == "undo") {
        auto files = j["files"].toObject();
        for (const auto &key : targets) {
            auto current = read(path(home, key)), managed = files[key].toObject()["after"].toObject();
            if (current == managed)
                continue;
            if (key == config && current != absent() && current["mode"] == managed["mode"] && keepEdits)
                j["edited"] = current;
            else
                fail("Personal panel edit: " + key +
                     (key == config ? ". Use --undo --keep-panel-edits to archive the edited profile." : ""));
        }
        j["phase"] = "undoing";
        save(home, j);
        finish(home, j);
        QTextStream(stdout) << "Restored previous panel selection for next login.\n";
        return;
    }
    if (binary.isEmpty())
        binary = j.isEmpty() ? QCoreApplication::applicationDirPath() + "/lxqt-panel" : j["binary"].toString();
    binary = checkBinary(binary);
    if (!j.isEmpty()) {
        const auto files = j["files"].toObject();
        auto selected = read(path(home, autostart)), current = read(path(home, config));
        if (selected != files[autostart].toObject()["after"].toObject() || current == absent() ||
            current["mode"] != files[config].toObject()["after"].toObject()["mode"])
            fail("Installed panel profile or autostart was removed or changed; refusing to replace it");
        if (binary != j["binary"] && op == "apply") {
            j["binary"] = binary;
            save(home, j);
        }
        QTextStream(stdout) << "Keep existing panel profile and pins. Next-login executable: " << binary
                            << Qt::endl;
        return;
    }
    auto original = read(path(home, config));
    if (original != absent())
        fail("A private panel profile already exists without native ownership; preserving it.");
    auto prior = read(path(home, autostart));
    auto source = stock(home);
    auto profile = buildPanelProfile(source, home, panel);
    auto launch = entry(home, prior);
    for (auto id : {"lxqt-comfort.desktop", "doroshell-network.desktop"}) {
        if (!QFileInfo(path(home, QString(".local/share/applications/") + id)).isFile()) {
            if (op == "apply")
                fail("Register native application launchers with doroshell-setup --apply first");
            QTextStream(stdout) << "Requires native launcher registration: " << id << Qt::endl;
        }
    }
    QTextStream(stdout) << "Prepare " << config << " and select " << binary << " for the next LXQt login.\n";
    if (op == "plan")
        return;
    if (stock(home) != source)
        fail("The source panel profile changed during preparation; retry to include those edits");
    QJsonObject files{{config, QJsonObject{{"original", original}, {"after", state(profile)}}},
                      {autostart, QJsonObject{{"original", prior}, {"after", state(launch)}}}};
    j = {{"version", 1}, {"phase", "applying"}, {"binary", binary}, {"panel", panel.isEmpty() ? QString("panel1") : panel}, {"files", files}};
    save(home, j);
    finish(home, j);
}

[[noreturn]] void launch(const QString &home)
{
    QString selected;
    try {
        ensureHome(home);
        const auto j = load(home);
        auto installed = read(path(home, config));
        if (j["phase"] != "installed" || installed == absent() || (installed["mode"].toInt() & 0022))
            fail("Incomplete private panel selection");
        selected = j["binary"].toString();
        auto binary = checkBinary(selected);
        auto env = QProcessEnvironment::systemEnvironment();
        env.insert("LC_ALL", "C");
        QProcess ldd;
        ldd.setProcessEnvironment(env);
        ldd.setProcessChannelMode(QProcess::MergedChannels);
        ldd.start("/usr/bin/ldd", {"-r", binary});
        if (!ldd.waitForFinished(7000) || ldd.exitStatus() != QProcess::NormalExit || ldd.exitCode())
            fail("Private panel library check failed");
        const auto report = ldd.readAllStandardOutput();
        if (report.contains("not found") || report.contains("undefined symbol"))
            fail("Private panel dependency unavailable");
        auto exe = QFile::encodeName(binary), file = QFile::encodeName(path(home, config));
        execl(exe.constData(), exe.constData(), "--config", file.constData(), nullptr);
        fail("Cannot execute private panel");
    } catch (const std::exception &error) {
        QTextStream(stderr) << error.what() << ". Starting the stock LXQt panel.\n";
        if (!selected.isEmpty())
            QProcess::startDetached(QCoreApplication::applicationDirPath() + "/doroshell-maintenance",
                                    {"repair", "--kind", "panel", "--current", selected, "--home", home});
    }
    execl("/usr/bin/lxqt-panel", "/usr/bin/lxqt-panel", nullptr);
    fail("Cannot execute the stock LXQt panel");
}
} // namespace

int main(int argc, char **argv)
{
    QCoreApplication a(argc, argv);
    QCommandLineParser p;
    p.setApplicationDescription("Stage a private DoroShell taskbar for the next LXQt login. Default: preview.");
    p.addHelpOption();
    p.addOption({"home", "Target home directory.", "path", QDir::homePath()});
    p.addOption({"binary", "Patched private lxqt-panel executable.", "path"});
    p.addOption({"panel", "Panel to customise on first installation.", "panelN"});
    p.addOption({"keep-panel-edits", "Archive changed private panel settings when undoing."});
    for (auto name : {"plan", "apply", "undo", "recover", "launch"})
        p.addOption({name, QString("Perform %1.").arg(name)});
    p.process(a);
    QStringList selected;
    for (auto name : {"plan", "apply", "undo", "recover", "launch"})
        if (p.isSet(name))
            selected << name;
    const auto op = selected.value(0, "plan");
    if (selected.size() > 1 || !p.positionalArguments().isEmpty() ||
        (p.isSet("panel") && ((op != "plan" && op != "apply") || !QRegularExpression("^panel[1-9][0-9]*$").match(p.value("panel")).hasMatch())) ||
        (p.isSet("keep-panel-edits") && op != "undo") || (p.isSet("binary") && op != "plan" && op != "apply"))
        p.showHelp(2);
    try {
        auto home = QDir::cleanPath(p.value("home"));
        if (op == "launch")
            launch(home);
        stage(home, op, p.value("binary"), p.isSet("keep-panel-edits"), p.value("panel"));
        return 0;
    } catch (const std::exception &e) {
        QTextStream(stderr) << e.what() << Qt::endl;
        return 1;
    }
}
