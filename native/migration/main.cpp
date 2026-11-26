// SPDX-License-Identifier: GPL-2.0-or-later
#include "../setup/files.hpp"
#include <QCommandLineParser>
#include <QCoreApplication>
#include <QCryptographicHash>
#include <QJsonArray>
#include <QJsonDocument>
#include <QTextStream>
#include <sys/file.h>
using namespace doro_files;
namespace {
const QString legacy = ".local/state/doroshell/",
              journal = ".local/state/doroshell-native/migration.json";
const QString menu = ".local/state/lxqt-comfort/menu-install.json";
const QString watcher = ".config/autostart/doroshell-input.desktop";
struct Surface {
  QString receipt, name, command;
};
const QList<Surface> surfaces = {
    {menu, ".local/bin/lxqt-comfort-menu", "doroshell-start"},
    {menu, ".local/bin/doroshell-settings", "doroshell-settings"},
    {menu, ".local/share/applications/doroshell-network.desktop",
     "doroshell-network"},
    {legacy + "snapping.json", ".local/bin/doroshell-snap", "doroshell-snap"},
    {legacy + "screenshots.json", ".local/bin/doroshell-screenshot",
     "doroshell-screenshot"},
    {legacy + "clipboard.json", ".local/bin/doroshell-clipboard",
     "doroshell-clipboard"},
    {legacy + "input-settings.json", ".local/bin/doroshell-config-input",
     "lxqt-config-input"},
    {legacy + "input-settings.json",
     ".local/share/applications/lxqt-config-input.desktop",
     "lxqt-config-input"},
    {legacy + "input-settings.json",
     ".config/autostart/doroshell-input-defaults.desktop",
     "doroshell-input-preferences"},
    {legacy + "native-panel.json", ".local/bin/doroshell-native-panel",
     "lxqt-panel"},
    {legacy + "wallpaper.json", ".local/bin/doroshell-wallpaper-desktop",
     "doroshell-desktop"},
    {legacy + "wallpaper.json", ".config/autostart/lxqt-desktop.desktop",
     "doroshell-desktop"},
    {legacy + "wallpaper.json", ".local/bin/doroshell-wallpaper",
     "doroshell-wallpaper"},
    {legacy + "maintenance.json", ".local/bin/doroshell-update",
     "doroshell-maintenance"},
    {legacy + "maintenance.json", ".local/bin/doroshell-remove",
     "doroshell-maintenance"}};
QJsonObject json(const QJsonObject &state) {
  auto doc = QJsonDocument::fromJson(bytes(state));
  if (!doc.isObject())
    fail("Expected a JSON object");
  return doc.object();
}
QByteArray sha(const QByteArray &data) {
  return QCryptographicHash::hash(data, QCryptographicHash::Sha256).toHex();
}
QJsonObject state(const QByteArray &data, int mode) {
  return {{"exists", true},
          {"mode", mode},
          {"data", QString::fromLatin1(data.toBase64())}};
}
QString exe(const QString &name) {
  auto result = QCoreApplication::applicationDirPath() + '/' + name;
  if (!QFileInfo(result).isExecutable() || !QFileInfo(result).isFile())
    fail("Missing native component: " + result);
  return result;
}
void verifyLegacy(const Surface &s, const QJsonObject &record,
                  const QJsonObject &original) {
  bool match = false;
  if (s.receipt == menu || s.command == "lxqt-panel") {
    auto entry = record[s.name].toObject();
    bool panel = s.command == "lxqt-panel";
    match = !entry.contains("pending_from") &&
            !entry.contains("pending_after") &&
            entry[panel ? "after" : "installed"].toString() ==
                sha(bytes(original)) &&
            original["mode"].toInt() ==
                (panel ? 0755 : entry["installed_mode"].toInt(-1));
  } else {
    auto backup = record["backup"].toObject()[s.name].toObject();
    int matches = 0;
    for (auto e : record["edits"].toArray()) {
      auto edit = e.toObject();
      if (edit["file"] != s.name)
        continue;
      ++matches;
      match = edit["kind"] == "file" && edit["after"] == original["data"] &&
              backup["mode"] == original["mode"];
    }
    match = match && matches == 1 && !record.contains("phase");
  }
  if (!match)
    fail("Changed or incomplete RC2 ownership evidence: " + s.name);
}
QByteArray route(const QStringList &argv) {
  QFile stub(exe("doroshell-route"));
  if (!stub.open(QIODevice::ReadOnly))
    fail(stub.errorString());
  auto data = stub.readAll();
  auto args = QJsonDocument(QJsonArray::fromStringList(argv))
                  .toJson(QJsonDocument::Compact);
  if (!data.startsWith("\x7f"
                       "ELF") ||
      data.size() > 512 * 1024 || args.size() > 65536)
    fail("Invalid native route payload");
  return data + args +
         QByteArray::number(args.size(), 16).rightJustified(8, '0');
}
QByteArray withCommand(QByteArray original, const QStringList &argv) {
  QStringList escaped;
  for (auto &arg : argv)
    escaped << desktopQuote(arg);
  auto lines = original.split('\n');
  int count = 0;
  bool entry = false;
  for (auto &line : lines) {
    if (line.startsWith('['))
      entry = line == "[Desktop Entry]";
    if (entry && line.startsWith("Exec=")) {
      ++count;
      line = "Exec=" + escaped.join(' ').toUtf8();
    }
  }
  if (count != 1)
    fail("Ambiguous RC2 desktop command");
  return lines.join('\n');
}
QJsonObject replacement(const QString &home, const Surface &s,
                        const QJsonObject &original) {
  if (s.name.endsWith("/lxqt-config-input.desktop")) {
    // RC2 explicitly runs its wrapper through Python. The replacement wrapper
    // is a native ELF and retains the dependency-check/stock fallback.
    return state(withCommand(bytes(original),
                             {path(home, ".local/bin/doroshell-config-input")}),
                 original["mode"].toInt());
  }
  if (s.name.endsWith("/lxqt-desktop.desktop")) {
    auto lines = bytes(original).split('\n');
    int found = -1;
    bool main = false;
    for (qsizetype i = 0; i < lines.size(); ++i) {
      const auto trimmed = lines[i].trimmed();
      if (trimmed.startsWith('['))
        main = trimmed == "[Desktop Entry]";
      if (main && trimmed.startsWith("TryExec=")) {
        if (found != -1 || trimmed != "TryExec=/usr/bin/python")
          fail("Conflicting RC2 desktop launch precondition");
        found = i;
      }
    }
    if (found < 0)
      fail("Unrecognized RC2 desktop launch precondition");
    lines.removeAt(found);
    return state(lines.join('\n'), original["mode"].toInt());
  }
  QStringList args{exe(s.command)};
  if (s.command == "lxqt-panel")
    args << "--config" << path(home, ".config/doroshell/panel.conf");
  if (s.command == "doroshell-desktop") {
    if (bytes(original).contains("subprocess.run(['systemctl', '--user', "
                                 "'start', 'plasma-dolphin.service'])"))
      args << "--dolphin-service";
    for (auto name :
         {"pcmanfm-qt", "doroshell-video-worker", "doroshell-display"}) {
      QFile f(exe(name));
      QCryptographicHash h(QCryptographicHash::Sha256);
      if (!f.open(QIODevice::ReadOnly) || !h.addData(&f))
        fail("Cannot digest " + f.fileName());
      args << QString::fromLatin1(h.result().toHex());
    }
  }
  if (s.name.endsWith("input-defaults.desktop"))
    args << "--first-login";
  if (s.name.endsWith("doroshell-update"))
    args << "update" << "--channel"
         << (bytes(original).contains("'--channel', 'stable'") ? "stable"
                                                               : "development");
  if (s.name.endsWith("doroshell-remove"))
    args << "remove";
  return state(s.name.endsWith(".desktop") ? withCommand(bytes(original), args)
                                           : route(args),
               original["mode"].toInt());
}
QStringList allowed() {
  QStringList names{watcher};
  for (auto &s : surfaces)
    names << s.name;
  return names;
}
QJsonObject loadJournal(const QString &home) {
  auto raw = read(path(home, journal), 32 * 1024 * 1024);
  if (raw == absent())
    return {};
  auto j = json(raw);
  if (raw["mode"] != 0600 || j["version"] != 1 ||
      !QStringList{"applying", "installed", "undoing"}.contains(
          j["phase"].toString()) ||
      !j["files"].isObject() || j["files"].toObject().isEmpty())
    fail("Invalid migration journal");
  auto files = j["files"].toObject();
  for (auto it = files.begin(); it != files.end(); ++it) {
    if (!allowed().contains(it.key()))
      fail("Unexpected migration target");
    auto entry = it.value().toObject();
    for (auto key : {"before", "from", "to"}) {
      auto recorded = entry[key].toObject();
      validate(recorded);
      if (recorded == absent())
        fail("Unexpected absent migration target");
    }
  }
  return j;
}
void save(const QString &home, const QJsonObject &j) {
  atomic(path(home, journal), QJsonDocument(j).toJson(QJsonDocument::Compact),
         0600);
}
void runPending(const QString &home, QJsonObject j) {
  auto files = j["files"].toObject();
  // Check the entire set first; a personal edit late in the inventory must not
  // cause an otherwise predictable partial migration.
  for (auto it = files.begin(); it != files.end(); ++it) {
    auto actual = read(path(home, it.key()));
    auto entry = it.value().toObject();
    if (actual != entry["from"] && actual != entry["to"])
      fail("Edited launcher: " + it.key());
  }
  for (auto it = files.begin(); it != files.end(); ++it) {
    const auto filename = path(home, it.key());
    auto actual = read(filename), entry = it.value().toObject();
    if (actual == entry["to"])
      continue;
    if (actual != entry["from"])
      fail("Launcher changed before write: " + it.key());
    write(filename, entry["to"].toObject());
  }
  if (j["phase"] == "undoing")
    write(path(home, journal), absent());
  else {
    j["phase"] = "installed";
    save(home, j);
  }
}
QByteArray inputWatcher(QString command) {
  return ("[Desktop Entry]\nType=Application\nName=DoroShell input "
          "preferences\nExec=" +
          command + " --login\nOnlyShowIn=LXQt;\n")
      .toUtf8();
}
// Keep exact compatibility with the two released input helper implementations.
QString inputQuote(QString text) {
  text.replace("\\", "\\\\")
      .replace('"', "\\\"")
      .replace('`', "\\`")
      .replace('$', "\\$")
      .replace('%', "%%");
  return '"' + text + '"';
}
bool plan(const QString &home, const QString &action,
          const QJsonObject &prior) {
  const bool undo = action == "undo";
  if (undo && prior.isEmpty())
    return true;
  auto previous = prior["files"].toObject();
  QJsonObject files;
  QMap<QString, QJsonObject> receipts;
  auto pointer = read(path(home, legacy + "deployment.json"));
  QJsonArray installed;
  if (pointer != absent()) {
    auto record = json(pointer);
    if (record["status"] != "complete")
      fail("Recover the RC2 deployment first");
    if ((record["format"] != 1 && record["format"] != 2) ||
        !record["modules"].isArray() ||
        !QRegularExpression("^[0-9]{8}T[0-9]{6}-[0-9a-f]{12}$")
             .match(record["transaction"].toString())
             .hasMatch() ||
        !QRegularExpression("^[0-9a-f]{64}$")
             .match(record["source"].toString())
             .hasMatch())
      fail("Unsupported RC2 deployment record");
    installed = record["modules"].toArray();
  }
  QString inputHelper;
  for (auto &s : surfaces) {
    if (!receipts.contains(s.receipt)) {
      auto raw = read(path(home, s.receipt), 32 * 1024 * 1024);
      if (raw != absent()) {
        if (raw["mode"] != 0600)
          fail("Unexpected receipt permissions: " + s.receipt);
        receipts.insert(s.receipt, json(raw));
      }
    }
    auto old = previous.value(s.name).toObject();
    if (!receipts.contains(s.receipt)) {
      QString module =
          s.receipt == menu ? "menu" : QFileInfo(s.receipt).baseName();
      if (!old.isEmpty() || installed.contains(module))
        fail("RC2 receipt was removed: " + s.receipt);
      continue;
    }
    auto actual = read(path(home, s.name)),
         original = old.isEmpty() ? actual : old["before"].toObject();
    if (actual == absent() || (!old.isEmpty() && actual != old["to"]))
      fail("Edited or missing launcher: " + s.name);
    verifyLegacy(s, receipts.value(s.receipt), original);
    if (!undo && s.command == "lxqt-panel") {
      auto configPath = QStringLiteral(".config/doroshell/panel.conf");
      auto info = receipts.value(s.receipt)[configPath].toObject();
      auto config = read(path(home, configPath));
      if (info.contains("startup_tray") || info.contains("pending_after"))
        fail("Complete the staged RC2 panel change at login before migrating");
      if (config == absent() || config["mode"].toInt() & 0022)
        fail("Missing or writable-by-others RC2 panel configuration");
    }
    auto desired = undo ? original : replacement(home, s, original);
    files[s.name] =
        QJsonObject{{"before", original}, {"from", actual}, {"to", desired}};
    if (s.command == "doroshell-input-preferences" && !undo)
      inputHelper = exe(s.command);
    if (actual != desired)
      QTextStream(stdout) << s.name << '\n';
  }
  if (files.isEmpty())
    fail("No installed RC2 launcher receipts found");
  if (receipts.contains(legacy + "input-settings.json")) {
    const auto prefs =
        read(path(home, ".config/doroshell/input-preferences.json"));
    const auto startup =
        prefs == absent() ? QJsonValue() : json(prefs)["startup"];
    const auto actual = read(path(home, watcher));
    if (startup.isString() && startup != "installed")
      fail("Recover the pending input preference change first");
    if ((startup == "installed") != (actual != absent()))
      fail("Inconsistent input watcher ownership");
    if (actual != absent()) {
      auto rc2 = state(
          inputWatcher(
              "\"/usr/bin/python\" " +
              inputQuote(
                  home +
                  "/.local/share/doroshell/toolkit/input_preferences.py")),
          0600);
      auto old = prior["inputHelper"].toString();
      if (actual != rc2 &&
          (old.isEmpty() ||
           actual != state(inputWatcher(inputQuote(old)), 0600)))
        fail("Edited input watcher entry");
      files[watcher] = QJsonObject{
          {"before", rc2},
          {"from", actual},
          {"to",
           undo ? rc2 : state(inputWatcher(inputQuote(inputHelper)), 0600)}};
    }
  }
  if (action == "plan")
    return true;
  if (!undo && !prior.isEmpty() && previous.keys() == files.keys() &&
      prior["inputHelper"].toString() == inputHelper) {
    bool same = true;
    for (auto it = files.begin(); it != files.end(); ++it)
      if (it.value().toObject()["to"] != previous[it.key()].toObject()["to"])
        same = false;
    if (same)
      return true;
  }
  QJsonObject j{{"version", 1},
                {"phase", undo ? "undoing" : "applying"},
                {"files", files},
                {"inputHelper", inputHelper}};
  save(home, j);
  runPending(home, j);
  return true;
}
class Locks {
  QList<int> handles;

public:
  void acquire(const QString &name) {
    makeParents(name);
    int fd = ::open(QFile::encodeName(name).constData(),
                    O_RDWR | O_CREAT | O_CLOEXEC | O_NOFOLLOW, 0600);
    struct stat st{};
    if (fd < 0 || fstat(fd, &st) || !S_ISREG(st.st_mode) ||
        st.st_uid != getuid() || flock(fd, LOCK_EX | LOCK_NB)) {
      if (fd >= 0)
        close(fd);
      fail("Cannot lock " + name);
    }
    handles << fd;
  }
  ~Locks() {
    for (int fd : handles)
      close(fd);
  }
};
} // namespace
int main(int argc, char **argv) {
  QCoreApplication app(argc, argv);
  QCommandLineParser p;
  p.addHelpOption();
  p.addOption({"home", "RC2 installation home", "path", QDir::homePath()});
  p.addOptions(
      {{"plan", "Review owned RC2 entry points."},
       {"apply", "Route owned entries to this native bundle."},
       {"undo", "Restore the previous RC2 installation."},
       {"recover", "Complete an interrupted change."},
       {"refresh",
        "Select this release only if the migration remains installed."}});
  p.process(app);
  try {
    auto home = p.value("home");
    if (home == "/" || QFileInfo(home).canonicalFilePath() != home ||
        !QFileInfo(home).isDir() || QFileInfo(home).ownerId() != getuid())
      fail("Expected a canonical home directory");
    QStringList actions;
    for (auto a : {"apply", "recover", "plan", "undo", "refresh"})
      if (p.isSet(a))
        actions << a;
    if (actions.size() > 1 || !p.positionalArguments().isEmpty())
      fail("Choose one action");
    auto action = actions.value(0, "plan");
    Locks locks;
    if (action != "plan") {
      if (!QFileInfo::exists(path(home, menu)) &&
          !QFileInfo::exists(path(home, legacy + "native-panel.json")) &&
          !QFileInfo::exists(path(home, journal)) &&
          !QFileInfo::exists(path(home, legacy + "deployment.json")))
        fail("No RC2 deployment to migrate");
      for (auto name : {"deployment", "wallpaper", "clipboard",
                        "input-settings", "native-panel"})
        locks.acquire(path(home, legacy + name + ".lock"));
      if (QFileInfo::exists(path(home, legacy + "input-settings.json")))
        locks.acquire(path(home, ".config/doroshell/input-preferences.lock"));
    }
    auto prior = loadJournal(home);
    if (action == "refresh" && prior["phase"] != "installed")
      fail("RC2 migration is no longer selected");
    if (!prior.isEmpty() && prior["phase"] != "installed") {
      if (action != "recover")
        fail("Interrupted migration: use --recover");
      runPending(home, prior);
    } else if (action != "recover")
      plan(home, action, prior);
  } catch (const std::exception &e) {
    QTextStream(stderr) << e.what() << '\n';
    return 1;
  }
  return 0;
}
