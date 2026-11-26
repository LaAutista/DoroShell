// SPDX-License-Identifier: GPL-2.0-or-later
#include "../setup/files.hpp"
#include "options.hpp"
#include <sys/file.h>
namespace {
using namespace doro_files;
using modules::paths;
struct Locks {
  QList<int> fds;
  void take(const QString &file) {
    makeParents(file);
    int fd =
        ::open(QFile::encodeName(file).constData(),
               O_RDWR | O_CREAT | O_CLOEXEC | O_NOFOLLOW | O_NONBLOCK, 0600);
    struct stat s{};
    if (fd < 0 || fstat(fd, &s) || !S_ISREG(s.st_mode) ||
        s.st_uid != getuid() || flock(fd, LOCK_EX | LOCK_NB)) {
      if (fd >= 0)
        close(fd);
      fail("Module settings are busy or the lock is unsafe");
    }
    fds << fd;
  }
  ~Locks() {
    for (auto fd : fds)
      close(fd);
  }
};
using Files = QMap<QString, QByteArray>;
QByteArray content(const QJsonObject &s) {
  return s == absent() ? QByteArray() : bytes(s);
}
QJsonObject state(const QByteArray &b, const QJsonObject &base) {
  if (b.isNull())
    return absent();
  return {{"exists", true},
          {"mode", base["mode"].toInt(0600)},
          {"data", QString::fromLatin1(b.toBase64())}};
}
const QString nstate = ".local/state/doroshell-native/";
QJsonObject load(const QString &filename, const QString &module) {
  auto raw = read(filename, 24 * 1024 * 1024);
  if (raw == absent())
    return {};
  auto j = QJsonDocument::fromJson(bytes(raw)).object();
  auto expected = paths(module);
  expected.sort();
  if (raw["mode"] != 0600 || j["version"] != 1 || j["module"] != module ||
      !QStringList{"applying", "installed", "undoing", "suspending",
                   "suspended", "resuming"}
           .contains(j["phase"].toString()) ||
      !j["options"].isObject() || !j["files"].isObject() ||
      j["files"].toObject().keys() != expected || !j["claim"].isString())
    fail("Invalid optional-module receipt");
  for (auto f : j["files"].toObject()) {
    auto e = f.toObject();
    for (auto k : {"original", "effective", "from", "to", "installed"})
      validate(e[k].toObject());
  }
  return j;
}
void save(const QString &file, const QJsonObject &j) {
  atomic(file, QJsonDocument(j).toJson(QJsonDocument::Compact), 0600);
}
void finish(const QString &home, const QString &file, QJsonObject j) {
  auto files = j["files"].toObject();
  for (auto i = files.begin(); i != files.end(); ++i) {
    auto current = read(path(home, i.key()));
    auto e = i.value().toObject();
    if (current != e["from"] && current != e["to"])
      fail("File changed since the module transaction: " + i.key());
  }
  for (auto i = files.begin(); i != files.end(); ++i) {
    auto name = path(home, i.key());
    auto current = read(name), e = i.value().toObject();
    if (current == e["to"])
      continue;
    if (current != e["from"])
      fail("Concurrent edit: " + i.key());
    write(name, e["to"].toObject());
  }
  if (j["phase"] == "undoing")
    write(file, absent());
  else {
    j["phase"] = j["phase"] == "suspending" ? "suspended" : "installed";
    save(file, j);
  }
}
QString binary(const QString &name) {
  return QCoreApplication::applicationDirPath() + "/" + name;
}
QJsonObject effective(const QString &name, const QJsonObject &original) {
  if (original != absent() ||
      (name != modules::shortcuts && name != modules::stockPanel &&
       name != modules::openbox))
    return original;
  auto roots = qEnvironmentVariable("XDG_CONFIG_DIRS", "/etc/xdg")
                   .split(':', Qt::SkipEmptyParts);
  roots << "/usr/share";
  QString relative = name.sliced(QString(".config/").size());
  for (const auto &root : roots) {
    if (!QDir::isAbsolutePath(root))
      fail("Unexpected relative system configuration directory");
    QFile f(root + '/' + relative);
    if (!f.exists())
      continue;
    if (!QFileInfo(f).isFile() || !f.open(QIODevice::ReadOnly) ||
        f.size() > 1024 * 1024)
      fail("Cannot read distribution defaults: " + f.fileName());
    auto data = f.readAll();
    if (f.error() != QFileDevice::NoError || data.isEmpty())
      fail("Invalid distribution defaults");
    return state(data, original);
  }
  fail("Missing distribution defaults for " + relative);
}
void requirePanel(const QString &home) {
  for (auto name : {"panel.json", "migration.json"}) {
    auto record = read(path(home, nstate + name), 32 * 1024 * 1024);
    if (record == absent())
      continue;
    auto json = QJsonDocument::fromJson(bytes(record)).object();
    if (json["phase"] != "installed")
      fail("Complete the pending panel deployment first");
    if (QString(name) == "panel.json" ||
        json["files"].toObject().contains(".local/bin/doroshell-native-panel"))
      return;
  }
  fail("Stage the native DoroShell panel first");
}
int run(const QString &home, const QString &module, const QString &action,
        const QJsonObject &input, QString claim) {
  auto receipt = path(home, modules::dir + module + ".json");
  auto legacy = path(home, ".local/state/doroshell/" + module + ".json");
  const bool suspend = action == "suspend", resume = action == "resume",
             layer = suspend || resume;
  if (layer && (claim.isEmpty() || !input.isEmpty()))
    fail("A layer change requires only its deployment --claim");
  if (layer && !QFileInfo::exists(receipt))
    return 0;
  bool changing = action != "status" && action != "plan";
  Locks locks;
  if (changing) {
    locks.take(path(home, modules::dir + "options.lock"));
    if (paths(module).contains(modules::privatePanel))
      locks.take(path(home, ".local/state/doroshell/native-panel.lock"));
    if (module == "single-desktop" || module.endsWith("-dark"))
      locks.take(path(home, ".local/state/doroshell/theme.lock"));
  }
  auto j = load(receipt, module);
  if (layer && (j.isEmpty() || j.value("claim") != claim))
    return 0;
  bool rc2 = QFileInfo::exists(legacy);
  const auto phase = j.value("phase").toString();
  const bool suspended = phase == "suspended";
  bool pending = !j.isEmpty() && phase != "installed" && !suspended;
  if (action != "status" && !claim.isEmpty() && !j.isEmpty() &&
      j.value("claim") != claim)
    return 0;
  if ((action == "recover" && pending) || (suspend && phase == "suspending") ||
      (resume && phase == "resuming")) {
    if (rc2)
      fail("RC2 and native ownership overlap; refusing recovery");
    finish(home, receipt, j);
    return 0;
  }
  if ((suspend && suspended) || (resume && phase == "installed"))
    return 0;
  if (action == "undo" && suspended) {
    if (rc2)
      fail("RC2 and native ownership overlap");
    write(receipt, absent());
    return 0;
  }
  bool session = false;
  if (module == "start-shortcut") {
    for (auto name : {"start-key.json", "session.json"}) {
      auto owner = read(path(home, nstate + name), 24 * 1024 * 1024);
      if (owner == absent())
        continue;
      auto record = QJsonDocument::fromJson(bytes(owner)).object();
      if (record["phase"] != "installed")
        fail("Complete the pending shortcut transaction first");
      session = true;
    }
  }
  if (action == "status") {
    QString owner = rc2            ? "rc2"
                    : !j.isEmpty() ? "native"
                    : session      ? "session"
                                   : "none";
    if (module == "taskbar-drag" && owner == "none") {
      try {
        requirePanel(home);
        modules::taskPanel(content(read(path(home, modules::privatePanel))));
        owner = "panel";
      } catch (const std::exception &) {
      }
    }
    QTextStream(stdout)
        << QJsonDocument(QJsonObject{{"owner", owner},
                                     {"enabled", owner != "none"},
                                     {"pending", pending},
                                     {"suspended", suspended},
                                     {"claim", j.value("claim").toString()}})
               .toJson(QJsonDocument::Compact)
        << '\n';
    return 0;
  }
  if (rc2) {
    if (!j.isEmpty() || claim.isEmpty())
      fail("The RC2 receipt owns this module; use its original rollback before "
           "taking over");
    return 0;
  }
  if (action == "recover")
    return 0;
  if (pending)
    fail("Interrupted optional module: use --recover");
  if (suspended && !resume)
    fail("The deployment suspended this module; resume its update first");
  bool undo = action == "undo" || suspend;
  if (undo && j.isEmpty())
    return 0;
  if (!undo) {
    if (paths(module).contains(modules::privatePanel))
      requirePanel(home);
    if (module == "taskbar-drag") {
      modules::taskPanel(content(read(path(home, modules::privatePanel))));
      QTextStream(stdout)
          << "Dragging is built into the selected native taskbar.\n";
      return 0;
    }
    if (module.endsWith("-dark")) {
      if (QFileInfo::exists(path(home, ".local/state/doroshell/theme.json")))
        fail("The active DoroShell theme owns the application colour scheme");
      if (!QFileInfo::exists("/usr/share/color-schemes/BreezeDark.colors"))
        fail("Install breeze with the Breeze Dark colour scheme first");
    }
    if (module == "start-shortcut" &&
        QFileInfo::exists(
            path(home, ".local/state/lxqt-comfort/menu-integration.json")))
      fail("Restore legacy shortcut integration before changing Alt+F1");
  }
  auto previous = resume ? QJsonObject{} : j.value("files").toObject();
  QJsonObject files, originals, actuals, effectiveStates;
  Files base;
  for (const auto &name : paths(module)) {
    auto current = read(path(home, name));
    auto initial = previous.contains(name)
                       ? previous[name].toObject()["original"].toObject()
                       : current;
    auto inherited = previous.contains(name)
                         ? previous[name].toObject()["effective"].toObject()
                         : effective(name, initial);
    actuals[name] = current;
    originals[name] = initial;
    effectiveStates[name] = inherited;
    base[name] = content(inherited);
  }
  auto opts = j.isEmpty() ? QJsonObject{{"size", "medium"},
                                        {"style", "icons"},
                                        {"replace", false}}
                          : j["options"].toObject();
  for (auto i = input.begin(); i != input.end(); ++i)
    opts[i.key()] = i.value();
  opts["start"] = binary("doroshell-start");
  opts["clipboard"] = binary("doroshell-clipboard");
  if (module == "clipboard" && !undo &&
      (!QFileInfo(opts["clipboard"].toString()).isExecutable() ||
       !QFileInfo::exists(path(
           home, ".local/share/applications/doroshell-clipboard.desktop"))))
    fail("Install the native clipboard launcher first");
  if (module == "start-shortcut" && !undo &&
      !QFileInfo(opts["start"].toString()).isExecutable())
    fail("Install the native Start menu first");
  auto oldOpts = j.isEmpty() ? opts : j["options"].toObject();
  auto oldEdits = modules::edits(home, module, oldOpts, base),
       newEdits = modules::edits(home, module, undo ? oldOpts : opts, base);
  if (session) {
    if (!j.isEmpty() && !resume)
      fail("Both the session and optional module claim Alt+F1");
    for (auto &e : newEdits)
      if (modules::value(e, base[e.path]) != e.desired)
        fail("The session owns Alt+F1 and its binding differs");
    // The base layer now supplies Alt+F1. Keep the previous selection
    // suspended: if that base is later removed, maintenance can resume the
    // optional binding.
    QTextStream(stdout) << "Alt+F1 belongs to the native session shortcuts.\n";
    return 0;
  }
  for (auto name : paths(module)) {
    auto original = originals[name].toObject(),
         current = actuals[name].toObject();
    auto pristine = base[name];
    auto data = (previous.isEmpty() && current == absent()) ? pristine
                                                            : content(current);
    QByteArray beforeInstalled = pristine;
    for (auto &e : oldEdits)
      if (e.path == name)
        beforeInstalled = modules::set(e, beforeInstalled, e.desired);
    if (!previous.isEmpty()) {
      if (current == absent() ||
          current["mode"] !=
              previous[name].toObject()["installed"].toObject()["mode"])
        fail("Managed file removed or permissions changed: " + name);
      for (auto &e : oldEdits)
        if (e.path == name && modules::value(e, data) != e.desired)
          fail("Personal edit to a managed setting: " + name);
    }
    auto desired = current;
    if (undo && data == beforeInstalled)
      desired = original;
    else {
      for (const auto &e : newEdits)
        if (e.path == name)
          data = modules::set(e, data,
                              undo ? modules::value(e, pristine) : e.desired);
      desired = state(data, current);
    }
    auto installed = desired;
    files[name] = QJsonObject{{"original", original},
                              {"effective", effectiveStates[name]},
                              {"from", current},
                              {"to", desired},
                              {"installed", installed}};
    if (current != desired)
      QTextStream(stdout) << name << '\n';
  }
  if (action == "plan")
    return 0;
  if (!undo && !previous.isEmpty() && opts == oldOpts) {
    bool same = true;
    for (auto f : files) {
      auto e = f.toObject();
      if (e["from"] != e["to"])
        same = false;
    }
    if (same)
      return 0;
  }
  QJsonObject result{{"version", 1},
                     {"module", module},
                     {"phase", suspend  ? "suspending"
                               : resume ? "resuming"
                               : undo   ? "undoing"
                                        : "applying"},
                     {"claim", j.isEmpty() ? claim : j["claim"].toString()},
                     {"options", undo ? oldOpts : opts},
                     {"files", files}};
  save(receipt, result);
  finish(home, receipt, result);
  return 0;
}
} // namespace
int main(int argc, char **argv) {
  QCoreApplication app(argc, argv);
  QCommandLineParser p;
  p.addHelpOption();
  p.addPositionalArgument("module", modules::names().join(", "));
  for (auto a : {"plan", "apply", "undo", "status", "recover", "suspend",
                 "resume", "replace-start-shortcut"})
    p.addOption({a, QString(a)});
  p.addOptions({{"home", "Target home", "path", QDir::homePath()},
                {"claim", "Deployment ownership identifier", "id"},
                {"taskbar-size", "small, medium, large", "size"},
                {"taskbar-style", "icons, standard", "style"}});
  p.process(app);
  try {
    auto args = p.positionalArguments();
    if (args.size() != 1 || !modules::names().contains(args.first()))
      fail("Expected one optional module");
    auto module = args.first(), home = p.value("home"),
         claim = p.value("claim");
    if (home == "/" || QFileInfo(home).canonicalFilePath() != home ||
        !QFileInfo(home).isDir() || QFileInfo(home).ownerId() != getuid())
      fail("Expected an owned canonical home");
    if (!claim.isEmpty() &&
        !QRegularExpression("^[A-Za-z0-9_.-]{1,128}$").match(claim).hasMatch())
      fail("Invalid claim identifier");
    QStringList selected;
    for (auto a :
         {"plan", "apply", "undo", "recover", "status", "suspend", "resume"})
      if (p.isSet(a))
        selected << a;
    if (selected.size() > 1)
      fail("Choose one operation");
    QJsonObject options;
    if (p.isSet("taskbar-size")) {
      if (module != "taskbar-size")
        fail("Select taskbar-size");
      options["size"] = p.value("taskbar-size");
    }
    if (p.isSet("taskbar-style")) {
      if (module != "taskbar")
        fail("Select taskbar");
      options["style"] = p.value("taskbar-style");
    }
    if (p.isSet("replace-start-shortcut")) {
      if (module != "start-shortcut")
        fail("Select start-shortcut");
      options["replace"] = true;
    }
    return run(home, module, selected.value(0, "plan"), options, claim);
  } catch (const std::exception &e) {
    QTextStream(stderr) << e.what() << '\n';
    return 1;
  }
}
